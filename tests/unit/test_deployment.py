import os
import plistlib
import re
import shlex
import shutil
import subprocess
from pathlib import Path
from typing import NewType
from unittest.mock import Mock

import pytest
import yaml
from celery import Celery
from pydantic import BaseModel, ConfigDict, Field

from cdm.config.app_config import QueueConfig
from cdm.jobs.store import JobKind
from cdm.workers.dispatch import JobDispatcher, TaskName

ServiceName = NewType("ServiceName", str)


class ComposeService(BaseModel):
    command: str | list[str] = ""
    cpus: str | float | None = None
    mem_limit: str | int | None = None
    profiles: list[str] = Field(default_factory=list)
    volumes: list["str | ComposeVolume"] = Field(default_factory=list)
    restart: str | None = None
    healthcheck: "ComposeHealth | None" = None
    depends_on: dict[ServiceName, "ComposeDependency"] | list[ServiceName] = Field(
        default_factory=dict
    )


class ComposeHealth(BaseModel):
    test: list[str]


class ComposeVolume(BaseModel):
    model_config = ConfigDict(frozen=True)
    source: str | None = None
    target: str


class ComposeDependency(BaseModel):
    condition: str


class ComposeFile(BaseModel):
    services: dict[ServiceName, ComposeService]

    def worker_queues(self) -> set[str]:
        queues: set[str] = set()
        for service in self.services.values():
            command = (
                service.command
                if isinstance(service.command, str)
                else shlex.join(service.command)
            )
            command = re.sub(r"\$\{[A-Z_]+:-([^}]+)\}", r"\1", command)
            for match in re.finditer(r"--queues=([^\s\"']+)", command):
                queues.update(match.group(1).split(","))
        return queues


class TestDeployment:
    root = Path(__file__).resolve().parents[2]

    @pytest.mark.parametrize(
        "filename",
        ["docker-compose.fullstack.yml", "deploy/gcp/docker-compose.worker.yml"],
    )
    def test_all_configured_queues_have_consumers(self, filename: str) -> None:
        compose = ComposeFile.model_validate(
            yaml.safe_load((self.root / filename).read_text())
        )
        defaults = QueueConfig.model_construct()
        expected = {
            defaults.celery_task_queue,
            defaults.celery_ingest_queue,
            defaults.celery_bulk_queue,
            defaults.celery_index_queue,
            defaults.celery_maintenance_queue,
            defaults.celery_analytics_queue,
        }

        assert not (expected - compose.worker_queues()), "Missing queue consumers"

    def test_production_image_copies_runtime_mappings(self) -> None:
        mappings = Path("documentation/opensearch_mappings.yaml")
        instructions = [
            shlex.split(line)
            for line in (self.root / "Dockerfile.prod").read_text().splitlines()
            if line.startswith("COPY ")
        ]

        assert any(
            str(mappings) in instruction[1:-1]
            and Path(instruction[-1]) in {mappings, mappings.parent}
            for instruction in instructions
        ), "The image must include the mapping loader's runtime YAML resource"
        assert (self.root / mappings).is_file()

    @pytest.mark.parametrize(
        "filename",
        ["docker-compose.fullstack.yml", "deploy/gcp/docker-compose.worker.yml"],
    )
    def test_analytics_worker_is_bounded_and_shares_the_api_ledger(
        self, filename: str
    ) -> None:
        compose = ComposeFile.model_validate(
            yaml.safe_load((self.root / filename).read_text())
        )
        worker = compose.services[ServiceName("worker-analytics")]
        backend = compose.services[ServiceName("backend")]
        command = (
            worker.command
            if isinstance(worker.command, str)
            else shlex.join(worker.command)
        )
        assert "--pool=prefork" in command
        assert "--concurrency=1" in command
        assert "--max-tasks-per-child=1" in command
        assert worker.cpus is not None and worker.mem_limit is not None
        assert backend.volumes and set(backend.volumes) <= set(worker.volumes)

    def test_production_install_uses_the_lock_without_conflicting_flags(self) -> None:
        instructions = [
            shlex.split(line)
            for line in (self.root / "Dockerfile.prod").read_text().splitlines()
            if line.startswith("RUN uv sync ")
        ]

        assert len(instructions) == 2
        for instruction in instructions:
            assert {"--frozen", "--no-dev", "--no-cache"} <= set(instruction)
            assert "--no-sources" not in instruction
        assert "--no-default-groups" in instructions[0]
        assert instructions[1][-2:] == ["--group", "analysis"]
        stages = [
            shlex.split(line)
            for line in (self.root / "Dockerfile.prod").read_text().splitlines()
            if line.startswith("FROM ")
        ]
        assert stages[0][-2:] == ["AS", "api"]
        assert stages[-1] == ["FROM", "api", "AS", "analysis"]


class TestJobRouting:
    @pytest.mark.parametrize("kind", list(JobKind))
    @pytest.mark.parametrize("countdown", [None, 7])
    def test_every_job_has_an_explicit_configurable_delivery_route(
        self, kind: JobKind, countdown: int | None
    ) -> None:
        queues = QueueConfig.model_construct(
            celery_ingest_queue="release-ingest",
            celery_index_queue="release-index",
            celery_bulk_queue="release-bulk",
            celery_analytics_queue="release-analytics",
        )
        expected = {
            JobKind.INGEST: (TaskName.RUN_INGEST, queues.celery_ingest_queue),
            JobKind.INDEX: (TaskName.RUN_INDEX, queues.celery_index_queue),
            JobKind.GOVINFO_BULK: (
                TaskName.RUN_GOVINFO_BULK,
                queues.celery_bulk_queue,
            ),
            JobKind.GOVINFO_BULK_BATCH: (
                TaskName.RUN_GOVINFO_BATCH,
                queues.celery_bulk_queue,
            ),
            JobKind.RECONCILE: (
                TaskName.RUN_RECONCILIATION,
                queues.celery_index_queue,
            ),
            JobKind.TOPIC_TRAINING: (
                TaskName.RUN_ANALYTICS,
                queues.celery_analytics_queue,
            ),
            JobKind.MEMBER_GRAPH: (
                TaskName.RUN_ANALYTICS,
                queues.celery_analytics_queue,
            ),
            JobKind.PERSPECTIVES: (
                TaskName.RUN_ANALYTICS,
                queues.celery_analytics_queue,
            ),
        }
        app = Mock(spec=Celery)

        JobDispatcher(app, queues).dispatch(kind, "synthetic-job", countdown=countdown)

        task, queue = expected[kind]
        if countdown is None:
            app.send_task.assert_called_once_with(
                task.value, args=["synthetic-job"], queue=queue
            )
        else:
            app.send_task.assert_called_once_with(
                task.value, args=["synthetic-job"], queue=queue, countdown=countdown
            )


class TestComposeOperations:
    root = Path(__file__).resolve().parents[2]

    def test_controlled_profile_excludes_acquisition_publication_and_scheduling(
        self,
    ) -> None:
        compose = ComposeFile.model_validate(
            yaml.safe_load((self.root / "docker-compose.fullstack.yml").read_text())
        )
        enabled = {
            name: service
            for name, service in compose.services.items()
            if not service.profiles or "operations" in service.profiles
        }
        assert set(enabled) == {"backend", "frontend", "worker-operations"}
        queues = ComposeFile(services=enabled).worker_queues()
        defaults = QueueConfig.model_construct()
        assert queues == {
            defaults.celery_index_queue,
            defaults.celery_maintenance_queue,
        }
        worker = enabled[ServiceName("worker-operations")]
        assert "--concurrency=1" in worker.command
        assert worker.mem_limit is not None
        assert "STACK_PROFILES ?= operations" in (self.root / "Makefile").read_text()

    @pytest.mark.parametrize("custom_queues", [False, True])
    def test_real_compose_render_preserves_supervision_state_and_queue_coverage(
        self, tmp_path: Path, custom_queues: bool
    ) -> None:
        if shutil.which("docker") is None:
            pytest.skip(
                "Docker Compose CLI is required for offline configuration rendering"
            )
        queues = QueueConfig.model_construct()
        names = [
            "celery_task_queue",
            "celery_ingest_queue",
            "celery_bulk_queue",
            "celery_index_queue",
            "celery_maintenance_queue",
            "celery_analytics_queue",
        ]
        values = {
            name.upper(): f"isolated-{name}" if custom_queues else getattr(queues, name)
            for name in names
        }
        environment = (
            os.environ
            | values
            | {
                "PWD": str(tmp_path),
                "CONTAINER_RABBITMQ_URL": "amqp://synthetic:synthetic@broker:5672//",
                "COMPOSE_DISABLE_ENV_FILE": "1",
                "COMPOSE_PROFILES": "operations,acquisition,dedicated,analytics,scheduler",
            }
        )
        env_file = tmp_path / ".env"
        env_file.write_text("ES_LOCAL_API_KEY=synthetic\n")
        result = subprocess.run(
            [
                "docker",
                "compose",
                "--project-directory",
                str(tmp_path),
                "--env-file",
                str(env_file),
                "-f",
                str(self.root / "docker-compose.fullstack.yml"),
                "config",
                "--format",
                "json",
            ],
            env=environment,
            text=True,
            capture_output=True,
            check=True,
            timeout=30,
        )
        compose = ComposeFile.model_validate_json(result.stdout)
        assert compose.worker_queues() == set(values.values())
        backend = compose.services[ServiceName("backend")]
        assert backend.healthcheck is not None
        assert "/ready" in shlex.join(backend.healthcheck.test)
        for name, service in compose.services.items():
            assert service.restart == "unless-stopped"
            command = (
                service.command
                if isinstance(service.command, str)
                else shlex.join(service.command)
            )
            assert "uv sync" not in command and "npm install" not in command
            if name != "backend":
                assert isinstance(service.depends_on, dict)
                assert (
                    service.depends_on[ServiceName("backend")].condition
                    == "service_healthy"
                )
        mounts = backend.volumes
        assert any(
            isinstance(mount, ComposeVolume)
            and mount.source == str(tmp_path)
            and mount.target == str(tmp_path)
            for mount in mounts
        )
        for name in (
            "worker",
            "worker-bulk",
            "worker-index",
            "worker-maintenance",
            "worker-analytics",
            "beat",
        ):
            assert compose.services[ServiceName(name)].volumes == mounts
        command = compose.services[ServiceName("beat")].command
        arguments = shlex.split(command) if isinstance(command, str) else command
        assert "--schedule=data/celerybeat-schedule" in arguments

    @pytest.mark.parametrize("registered", [False, True])
    def test_legacy_registration_blocks_start_without_stopping_any_process(
        self, tmp_path: Path, registered: bool
    ) -> None:
        binaries = tmp_path / "bin"
        binaries.mkdir()
        (binaries / "uname").write_text("#!/bin/sh\nprintf Darwin\n")
        (binaries / "launchctl").write_text(
            '#!/bin/sh\n[ "$1" = print ] || exit 99\n'
            + ("exit 0\n" if registered else "exit 1\n")
        )
        for executable in binaries.iterdir():
            executable.chmod(0o755)
        result = subprocess.run(
            ["sh", str(self.root / "scripts/stack.sh"), "check"],
            env=os.environ
            | {
                "HOME": str(tmp_path),
                "PATH": f"{binaries}:{os.environ['PATH']}",
            },
            text=True,
            capture_output=True,
            check=False,
            timeout=10,
        )
        assert result.returncode == (1 if registered else 0)
        if registered:
            assert "Legacy agent" in result.stderr

    def test_unloaded_agent_plist_also_blocks_start(self, tmp_path: Path) -> None:
        agents = tmp_path / "Library/LaunchAgents"
        agents.mkdir(parents=True)
        plist = agents / "com.congress-tracker.beat.plist"
        plist.write_text("retained legacy registration")
        binaries = tmp_path / "bin"
        binaries.mkdir()
        uname = binaries / "uname"
        uname.write_text("#!/bin/sh\nprintf Darwin\n")
        uname.chmod(0o755)
        launchctl = binaries / "launchctl"
        launchctl.write_text('#!/bin/sh\n[ "$1" = print ] || exit 99\nexit 1\n')
        launchctl.chmod(0o755)
        result = subprocess.run(
            ["sh", str(self.root / "scripts/stack.sh"), "check"],
            env=os.environ
            | {"HOME": str(tmp_path), "PATH": f"{binaries}:{os.environ['PATH']}"},
            text=True,
            capture_output=True,
            check=False,
            timeout=10,
        )
        assert result.returncode == 1
        assert "com.congress-tracker.beat" in result.stderr
        assert plist.read_text() == "retained legacy registration"

    def test_managed_entry_points_do_not_spawn_or_kill_native_processes(self) -> None:
        makefile = (self.root / "Makefile").read_text()
        wrapper = (self.root / "scripts/stack.sh").read_text()
        assert not (self.root / "scripts/ingest_launch_agent.sh").exists()
        for forbidden in (
            "pkill",
            "pgrep",
            "nohup",
            "launchctl bootout",
            "launchctl bootstrap",
        ):
            assert forbidden not in makefile + wrapper
        assert "up start services: stack-up" in makefile
        assert "down stop: stack-down" in makefile
        assert "--wait --wait-timeout 180" in makefile
        assert (
            "down --volumes"
            not in makefile.split("stack-down:", 1)[1].split("stack-logs:", 1)[0]
        )

    @pytest.mark.parametrize(
        "target", ["up", "start", "services", "down", "stop", "restart", "stack-status"]
    )
    def test_make_operational_aliases_use_only_compose(
        self,
        tmp_path: Path,
        target: str,
    ) -> None:
        binaries = tmp_path / "bin"
        binaries.mkdir()
        calls = tmp_path / "calls"
        for name in ("docker", "uv"):
            executable = binaries / name
            executable.write_text(
                '#!/bin/sh\nprintf \'%s:%s\\n\' "$(basename "$0")" "$*" >> "$OPERATIONS_CALLS"\n'
            )
            executable.chmod(0o755)
        uname = binaries / "uname"
        uname.write_text("#!/bin/sh\nprintf Linux\n")
        uname.chmod(0o755)
        subprocess.run(
            ["make", "-f", str(self.root / "Makefile"), target],
            cwd=self.root,
            env=os.environ
            | {
                "HOME": str(tmp_path),
                "PATH": f"{binaries}:{os.environ['PATH']}",
                "OPERATIONS_CALLS": str(calls),
            },
            text=True,
            capture_output=True,
            check=True,
            timeout=30,
        )
        recorded = calls.read_text()
        if target in {"up", "start", "services", "restart"}:
            assert "up -d --wait --wait-timeout 180" in recorded
            assert "up -d --build --wait --wait-timeout 180" in recorded
        if target in {"down", "stop", "restart"}:
            assert "down --remove-orphans" in recorded and "compose stop" in recorded
            assert "--volumes" not in recorded
        if target == "stack-status":
            assert recorded.count(" ps\n") == 2
            assert " up " not in recorded and "uv:" not in recorded

    def test_stack_status_resolves_the_same_infrastructure_environment_as_startup(
        self,
        tmp_path: Path,
    ) -> None:
        docker = tmp_path / "docker"
        docker.write_text(
            '#!/bin/sh\ncase "$*" in\n'
            '"compose ps") [ "$(basename "$PWD")" = elastic-start-local ] ;;\n'
            "*) exit 0 ;;\nesac\n"
        )
        docker.chmod(0o755)
        subprocess.run(
            ["make", "stack-status"],
            cwd=self.root,
            env=os.environ | {"PATH": f"{tmp_path}:{os.environ['PATH']}"},
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )

    @pytest.mark.parametrize("unavailable", ["compose", "daemon"])
    def test_shutdown_missing_prerequisites_fail_without_starting_docker(
        self, tmp_path: Path, unavailable: str
    ) -> None:
        executable = tmp_path / "docker"
        executable.write_text(
            '#!/bin/sh\ncase "$*" in\n'
            f'"compose version") {"exit 1" if unavailable == "compose" else "exit 0"} ;;\n'
            '"info") exit 1 ;;\n*) exit 99 ;;\nesac\n'
        )
        executable.chmod(0o755)
        result = subprocess.run(
            ["make", "down"],
            cwd=self.root,
            env=os.environ | {"PATH": f"{tmp_path}:{os.environ['PATH']}"},
            text=True,
            capture_output=True,
            check=False,
            timeout=10,
        )
        assert result.returncode != 0
        expected = (
            "Docker Compose v2 is required."
            if unavailable == "compose"
            else "Docker is not running."
        )
        assert expected in result.stdout

    @pytest.mark.skipif(
        not Path("/usr/libexec/PlistBuddy").exists(), reason="macOS migration"
    )
    @pytest.mark.parametrize("owned", [True, False])
    def test_documented_retirement_preserves_plists_and_refuses_other_checkouts(
        self, tmp_path: Path, owned: bool
    ) -> None:
        agents = tmp_path / "Library/LaunchAgents"
        agents.mkdir(parents=True)
        plist = agents / "com.congress-tracker.ingest-recovery.plist"
        contents = plistlib.dumps(
            {"WorkingDirectory": str(tmp_path if owned else self.root)}
        )
        plist.write_bytes(contents)
        calls = tmp_path / "calls"
        launchctl = tmp_path / "launchctl"
        launchctl.write_text(
            '#!/bin/sh\nprintf \'%s\\n\' "$*" >> "$OPERATIONS_CALLS"\n'
            'case "$*" in\n'
            '"print "*"/com.congress-tracker.ingest-recovery") exit 0 ;;\n'
            '"bootout "*"/com.congress-tracker.ingest-recovery") exit 0 ;;\n'
            '"print "*) exit 1 ;;\n*) exit 99 ;;\nesac\n'
        )
        launchctl.chmod(0o755)
        runbook = (self.root / "documentation/OPERATIONS_RUNBOOK.md").read_text()
        match = re.search(
            r"```sh\n(# Retire legacy agents.*?)\n```", runbook, re.DOTALL
        )
        assert match is not None
        result = subprocess.run(
            ["sh", "-c", match.group(1)],
            cwd=tmp_path,
            env=os.environ
            | {
                "HOME": str(tmp_path),
                "PATH": f"{tmp_path}:{os.environ['PATH']}",
                "OPERATIONS_CALLS": str(calls),
            },
            text=True,
            capture_output=True,
            check=False,
            timeout=10,
        )
        assert result.returncode == (0 if owned else 1), result.stderr
        if owned:
            assert not plist.exists()
            backups = list(agents.glob(f"retired-congress-tracker-*/{plist.name}"))
            assert len(backups) == 1 and backups[0].read_bytes() == contents
            assert calls.read_text().count("bootout ") == 1
        else:
            assert plist.read_bytes() == contents
            assert not calls.exists()
