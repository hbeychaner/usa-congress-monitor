import os
import re
import subprocess
import time
from collections.abc import Iterator
from contextlib import ExitStack
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import BaseModel, Field, TypeAdapter

from cdm.config.app_config import QueueConfig
from cdm.contracts.api import AnalysisErrorResponse, HealthResponse
from cdm.jobs.store import JobKind
from cdm.store.index_manager import load_definitions
from cdm.workers.dispatch import TaskName
from tools.release_smoke_probe import (
    HttpReply,
    MappingReply,
    ProbeMode,
    ProbeReply,
    ProbeUnavailable,
    RoutingReply,
    RuntimeReply,
    WorkerReply,
)


class ReleaseConfig(BaseModel):
    backend_image: str
    worker_image: str
    frontend_image: str
    broker_image: str = "rabbitmq:3.13-alpine"
    startup_seconds: float = 120
    command_seconds: float = 120
    api_port: int = 8097
    backend_memory: int = 1536 * 1024 * 1024
    frontend_memory: int = 128 * 1024 * 1024
    broker_memory: int = 512 * 1024 * 1024
    cpu_nanos: int = 1_000_000_000
    probe: Path = Path(__file__).resolve().parents[2] / "tools/release_smoke_probe.py"


class DockerHealth(BaseModel):
    status: str = Field(alias="Status")


class DockerState(BaseModel):
    running: bool = Field(alias="Running")
    oom_killed: bool = Field(alias="OOMKilled")
    health: DockerHealth | None = Field(default=None, alias="Health")


class DockerLimits(BaseModel):
    memory: int = Field(alias="Memory")
    cpus: int = Field(alias="NanoCpus")


class DockerContainer(BaseModel):
    state: DockerState = Field(alias="State")
    limits: DockerLimits = Field(alias="HostConfig")
    restart_count: int = Field(default=0, alias="RestartCount")


class ReleaseFixture:
    def __init__(
        self, config: ReleaseConfig, queues: QueueConfig, cleanup: ExitStack
    ) -> None:
        self.config = config
        self.queues = queues
        self.cleanup = cleanup
        self.scope = f"release-acceptance-{uuid4().hex}"
        self.network = self.scope
        self.backend = f"{self.scope}-backend"
        self.frontend = f"{self.scope}-frontend"
        self.broker = f"{self.scope}-broker"
        self.worker = f"{self.scope}-worker"
        self.analysis = f"{self.scope}-analysis"
        self.password = uuid4().hex

    def docker(self, *arguments: str, input_text: str | None = None) -> str:
        try:
            result = subprocess.run(
                ["docker", *arguments],
                input=input_text,
                text=True,
                capture_output=True,
                timeout=self.config.command_seconds,
                check=True,
            )
        except subprocess.CalledProcessError as exc:
            raise RuntimeError(
                f"Docker {arguments[0]} failed:\n{exc.stdout}\n{exc.stderr}"
            ) from exc
        if arguments[0] == "logs":
            return result.stdout + result.stderr
        return result.stdout

    def inspect(self, container: str) -> DockerContainer:
        return TypeAdapter(list[DockerContainer]).validate_json(
            self.docker("container", "inspect", container)
        )[0]

    def start(
        self,
        name: str,
        image: str,
        memory: int,
        options: list[str],
        command: list[str],
    ) -> None:
        self.docker(
            "create",
            "--name",
            name,
            "--label",
            f"copilot.release-acceptance={self.scope}",
            "--network",
            self.network,
            "--cpus=1",
            f"--memory={memory}",
            *options,
            image,
            *command,
        )
        self.cleanup.callback(self.docker, "rm", "--force", "--volumes", name)
        self.docker("start", name)

    def setup(self) -> None:
        self.docker(
            "network",
            "create",
            "--internal",
            "--label",
            f"copilot.release-acceptance={self.scope}",
            self.network,
        )
        self.cleanup.callback(self.docker, "network", "rm", self.network)
        assert (
            self.docker(
                "network", "inspect", "--format", "{{.Internal}}", self.network
            ).strip()
            == "true"
        )
        self.start(
            self.broker,
            self.config.broker_image,
            self.config.broker_memory,
            [
                "--network-alias=broker",
                "--env=RABBITMQ_DEFAULT_USER=acceptance",
                f"--env=RABBITMQ_DEFAULT_PASS={self.password}",
                (
                    "--health-cmd=rabbitmq-diagnostics -q check_running && "
                    "rabbitmq-diagnostics -q check_port_connectivity"
                ),
                "--health-interval=5s",
                "--health-timeout=10s",
                "--health-retries=20",
            ],
            [],
        )
        self.start(
            self.backend,
            self.config.backend_image,
            self.config.backend_memory,
            self.application_options() + [f"--env=PORT={self.config.api_port}"],
            [],
        )
        self.start(
            self.frontend,
            self.config.frontend_image,
            self.config.frontend_memory,
            ["--network-alias=frontend"],
            [],
        )

    def application_options(self) -> list[str]:
        return [
            f"--env=RABBITMQ_URL=amqp://acceptance:{self.password}@broker:5672//",
            "--env=ES_LOCAL_URL=http://127.0.0.1:9",
            "--env=ES_LOCAL_API_KEY=synthetic-not-a-credential",
            "--env=JOB_DB_PATH=/tmp/acceptance/jobs.sqlite3",
            "--env=PYTHONWARNINGS=error::UserWarning",
        ]

    def require_running(self, name: str) -> DockerContainer:
        inspected = self.inspect(name)
        assert inspected.state.running and not inspected.state.oom_killed, self.docker(
            "logs", name
        )
        return inspected

    def probe(
        self, mode: ProbeMode, url: str | None = None, *, target: str | None = None
    ) -> ProbeReply:
        arguments = [] if url is None else ["--url", url]
        return TypeAdapter(ProbeReply).validate_json(
            self.docker(
                "exec",
                "--interactive",
                self.backend if target is None else target,
                "python",
                "-",
                mode.value,
                *arguments,
                input_text=self.config.probe.read_text(),
            )
        )

    def wait(
        self, mode: ProbeMode, url: str | None = None, *, target: str | None = None
    ) -> ProbeReply:
        container = self.backend if target is None else target
        deadline = time.monotonic() + self.config.startup_seconds
        last_error = "Probe has not run"
        while time.monotonic() < deadline:
            self.require_running(self.backend)
            if container != self.backend:
                self.require_running(container)
            reply = self.probe(mode, url)
            if not isinstance(reply, ProbeUnavailable):
                return reply
            last_error = reply.error
            time.sleep(1)
        raise AssertionError(
            f"{mode} did not become ready: {last_error}\n"
            f"Container logs:\n{self.docker('logs', container)}"
        )

    def wait_broker(self) -> None:
        deadline = time.monotonic() + self.config.startup_seconds
        while time.monotonic() < deadline:
            inspected = self.require_running(self.broker)
            assert inspected.state.health is not None
            if inspected.state.health.status == "healthy":
                return
            assert inspected.state.health.status != "unhealthy", self.docker(
                "logs", self.broker
            )
            time.sleep(1)
        raise AssertionError(self.docker("logs", self.broker))


@pytest.fixture(scope="module")
def release() -> Iterator[ReleaseFixture]:
    backend = os.environ.get("RELEASE_TEST_BACKEND_IMAGE")
    worker = os.environ.get("RELEASE_TEST_WORKER_IMAGE")
    frontend = os.environ.get("RELEASE_TEST_FRONTEND_IMAGE")
    if not backend or not worker or not frontend:
        pytest.skip(
            "Set RELEASE_TEST_BACKEND_IMAGE, RELEASE_TEST_WORKER_IMAGE "
            "and RELEASE_TEST_FRONTEND_IMAGE "
            "to locally built production images"
        )
    config = ReleaseConfig(
        backend_image=backend, worker_image=worker, frontend_image=frontend
    )
    with ExitStack() as cleanup:
        fixture = ReleaseFixture(config, QueueConfig.model_construct(), cleanup)
        fixture.setup()
        yield fixture


class TestReleaseImages:
    def test_container_supervision_restarts_api_without_losing_the_ledger(
        self, release: ReleaseFixture
    ) -> None:
        health = f"http://127.0.0.1:{release.config.api_port}/health"
        release.wait(ProbeMode.HTTP, health)
        source = """
import json
import sys
from cdm.config import get_config
from cdm.jobs.store import JobKind, JobStore
store = JobStore(get_config().ledger.job_db_path, repair=False)
job = (
    store.create(JobKind.INDEX, "release-supervision", {"resource": "bill"})
    if sys.argv[1] == "create" else store.get("release-supervision")
)
print(json.dumps(job, sort_keys=True))
store.engine.dispose()
"""
        before = release.docker(
            "exec", release.backend, "python", "-c", source, "create"
        )
        count = release.inspect(release.backend).restart_count
        release.docker("update", "--restart=unless-stopped", release.backend)
        release.docker(
            "exec",
            release.backend,
            "python",
            "-c",
            "import os, signal; os.kill(1, signal.SIGTERM)",
        )
        deadline = time.monotonic() + release.config.startup_seconds
        while time.monotonic() < deadline:
            state = release.inspect(release.backend)
            if state.state.running and state.restart_count > count:
                break
            time.sleep(1)
        else:
            raise AssertionError("Docker did not restart the failed API container")
        reply = release.wait(ProbeMode.HTTP, health)
        assert isinstance(reply, HttpReply) and reply.status == 200
        after = release.docker("exec", release.backend, "python", "-c", source, "read")
        assert after == before

    def test_api_excludes_training_without_changing_normalization_or_contracts(
        self, release: ReleaseFixture
    ) -> None:
        api = release.probe(ProbeMode.RUNTIME)
        assert isinstance(api, RuntimeReply)
        assert api.loaded_training_modules == []
        assert api.installed_training_packages == []
        release.start(
            release.analysis,
            release.config.worker_image,
            release.config.backend_memory,
            release.application_options(),
            ["sleep", "300"],
        )
        analysis = release.probe(ProbeMode.RUNTIME, target=release.analysis)
        assert isinstance(analysis, RuntimeReply)
        assert set(analysis.installed_training_packages) == {
            "bertopic",
            "sentence_transformers",
            "scipy",
            "sklearn",
            "torch",
        }
        assert api.normalized_queries == analysis.normalized_queries
        assert api.normalized_queries == ["worker fund school", "taxes regulation", ""]
        assert api.contract_hash == analysis.contract_hash
        release.require_running(release.analysis)

    def test_api_default_command_port_mappings_and_dependency_failure(
        self, release: ReleaseFixture
    ) -> None:
        reply = release.wait(
            ProbeMode.HTTP, f"http://127.0.0.1:{release.config.api_port}/health"
        )
        assert isinstance(reply, HttpReply) and reply.status == 200
        assert HealthResponse.model_validate_json(reply.body).status == "ok"
        mappings = release.probe(ProbeMode.MAPPINGS)
        assert isinstance(mappings, MappingReply)
        assert set(mappings.names) == set(load_definitions())
        assert not mappings.installer_cache_exists
        ready = release.probe(
            ProbeMode.HTTP, f"http://127.0.0.1:{release.config.api_port}/ready"
        )
        assert isinstance(ready, HttpReply) and ready.status == 503
        assert (
            AnalysisErrorResponse.model_validate_json(ready.body).analysis_state
            == "unavailable"
        )
        inspected = release.require_running(release.backend)
        assert inspected.limits.memory == release.config.backend_memory
        assert inspected.limits.cpus == release.config.cpu_nanos

    def test_frontend_serves_spa_assets_and_missing_assets_are_not_html(
        self, release: ReleaseFixture
    ) -> None:
        root = release.wait(
            ProbeMode.HTTP, "http://frontend:8080/", target=release.frontend
        )
        assert isinstance(root, HttpReply) and root.status == 200
        assert "text/html" in root.content_type
        route = release.probe(ProbeMode.HTTP, "http://frontend:8080/members/A000001")
        assert isinstance(route, HttpReply) and route.status == 200
        assert route.body == root.body
        match = re.search(r'src="(/assets/[^"]+\.js)"', root.body)
        assert match is not None
        asset = release.probe(ProbeMode.HTTP, f"http://frontend:8080{match.group(1)}")
        assert isinstance(asset, HttpReply) and asset.status == 200
        assert asset.cache_control is not None
        assert "immutable" in asset.cache_control
        assert "http://localhost:8000" not in asset.body
        missing = release.probe(
            ProbeMode.HTTP, "http://frontend:8080/assets/missing.js"
        )
        assert isinstance(missing, HttpReply) and missing.status == 404
        assert missing.body != root.body
        inspected = release.require_running(release.frontend)
        assert inspected.limits.memory == release.config.frontend_memory
        assert inspected.limits.cpus == release.config.cpu_nanos

    def test_real_broker_delivery_and_prefork_worker_registration(
        self, release: ReleaseFixture
    ) -> None:
        release.wait_broker()
        broker = release.require_running(release.broker)
        assert broker.limits.memory == release.config.broker_memory
        assert broker.limits.cpus == release.config.cpu_nanos
        delivery = release.probe(ProbeMode.ROUTING)
        assert isinstance(delivery, RoutingReply)
        assert {message.job_kind for message in delivery.deliveries} == set(JobKind)
        assert len(delivery.deliveries) == len(JobKind)
        expected = {
            JobKind.INGEST: (TaskName.RUN_INGEST, release.queues.celery_ingest_queue),
            JobKind.INDEX: (TaskName.RUN_INDEX, release.queues.celery_index_queue),
            JobKind.RECONCILE: (
                TaskName.RUN_RECONCILIATION,
                release.queues.celery_index_queue,
            ),
            JobKind.GOVINFO_BULK: (
                TaskName.RUN_GOVINFO_BULK,
                release.queues.celery_bulk_queue,
            ),
            JobKind.GOVINFO_BULK_BATCH: (
                TaskName.RUN_GOVINFO_BATCH,
                release.queues.celery_bulk_queue,
            ),
            **{
                kind: (TaskName.RUN_ANALYTICS, release.queues.celery_analytics_queue)
                for kind in (
                    JobKind.TOPIC_TRAINING,
                    JobKind.MEMBER_GRAPH,
                    JobKind.PERSPECTIVES,
                )
            },
        }
        for message in delivery.deliveries:
            assert (message.task, message.queue) == expected[message.job_kind]
            assert message.arguments == [f"synthetic-{message.job_kind}"]
        queues = {
            release.queues.celery_task_queue,
            release.queues.celery_ingest_queue,
            release.queues.celery_bulk_queue,
            release.queues.celery_index_queue,
            release.queues.celery_maintenance_queue,
            release.queues.celery_analytics_queue,
        }
        release.start(
            release.worker,
            release.config.worker_image,
            release.config.backend_memory,
            release.application_options(),
            [
                "celery",
                "-A",
                "cdm.workers.celery_app:celery_app",
                "worker",
                "--pool=prefork",
                "--concurrency=1",
                "--max-tasks-per-child=1",
                "--loglevel=INFO",
                "--without-gossip",
                "--without-mingle",
                f"--queues={','.join(sorted(queues))}",
            ],
        )
        inspection = release.wait(ProbeMode.WORKER, target=release.worker)
        assert isinstance(inspection, WorkerReply)
        assert len(inspection.queues) == len(inspection.registered) == 1
        assert set(inspection.queues) == set(inspection.registered)
        assert set(inspection.queues) == set(inspection.stats)
        for active in inspection.queues.values():
            assert {queue.name for queue in active} == queues
        for registered in inspection.registered.values():
            assert set(TaskName) <= set(registered)
        for stats in inspection.stats.values():
            assert stats.pool.implementation == "celery.concurrency.prefork:TaskPool"
            assert stats.pool.maximum_concurrency == 1
            assert len(stats.pool.processes) == 1
        inspected = release.require_running(release.worker)
        assert inspected.limits.memory == release.config.backend_memory
        assert inspected.limits.cpus == release.config.cpu_nanos
