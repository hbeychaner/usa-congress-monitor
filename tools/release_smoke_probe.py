"""Test-only probes streamed into a built image; never copied into that image."""

from __future__ import annotations

import argparse
import subprocess
import sys
from enum import StrEnum
from http.client import HTTPConnection
from pathlib import Path
from socket import gaierror
from typing import Annotated, Literal, NewType

from celery import Celery
from pydantic import BaseModel, Field, HttpUrl

from cdm.config.app_config import QueueConfig
from cdm.jobs.store import JobKind
from cdm.store.index_manager import load_definitions
from cdm.workers.celery_app import celery_app
from cdm.workers.dispatch import JobDispatcher, TaskName

WorkerName = NewType("WorkerName", str)


class ProbeMode(StrEnum):
    HTTP = "http"
    ROUTING = "routing"
    WORKER = "worker"
    MAPPINGS = "mappings"
    RUNTIME = "runtime"


class ProbeArguments(BaseModel):
    mode: ProbeMode
    url: HttpUrl | None = None


class ProbeUnavailable(BaseModel):
    kind: Literal["unavailable"] = "unavailable"
    error: str


class HttpReply(BaseModel):
    kind: Literal["http"] = "http"
    status: int
    content_type: str
    cache_control: str | None
    body: str


class DeliveredJob(BaseModel):
    job_kind: JobKind
    task: TaskName
    queue: str
    arguments: list[str]


class RoutingReply(BaseModel):
    kind: Literal["routing"] = "routing"
    deliveries: list[DeliveredJob]


class ActiveQueue(BaseModel):
    name: str


class WorkerPool(BaseModel):
    implementation: str
    maximum_concurrency: int = Field(alias="max-concurrency")
    processes: list[int]


class WorkerStats(BaseModel):
    pool: WorkerPool


class WorkerReply(BaseModel):
    kind: Literal["worker"] = "worker"
    queues: dict[WorkerName, list[ActiveQueue]]
    registered: dict[WorkerName, list[str]]
    stats: dict[WorkerName, WorkerStats]


class MappingReply(BaseModel):
    kind: Literal["mappings"] = "mappings"
    names: list[str]
    installer_cache_exists: bool


class RuntimeReply(BaseModel):
    kind: Literal["runtime"] = "runtime"
    loaded_training_modules: list[str]
    installed_training_packages: list[str]
    normalized_queries: list[str]
    contract_hash: str
    import_seconds: float
    import_peak_bytes: int


ProbeReply = Annotated[
    ProbeUnavailable
    | HttpReply
    | RoutingReply
    | WorkerReply
    | MappingReply
    | RuntimeReply,
    Field(discriminator="kind"),
]


class ReleaseProbe:
    def __init__(self, app: Celery, queues: QueueConfig) -> None:
        self.app = app
        self.queues = queues

    def run(self, arguments: ProbeArguments) -> ProbeReply:
        match arguments.mode:
            case ProbeMode.HTTP:
                if arguments.url is None or arguments.url.scheme != "http":
                    raise ValueError("The HTTP probe requires an http:// URL")
                return self.http(arguments.url)
            case ProbeMode.ROUTING:
                return self.routing()
            case ProbeMode.WORKER:
                inspector = self.app.control.inspect(timeout=2)
                queues = inspector.active_queues()
                registered = inspector.registered()
                stats = inspector.stats()
                if queues is None or registered is None or stats is None:
                    return ProbeUnavailable(error="Worker inspection has no reply yet")
                return WorkerReply.model_validate(
                    {"queues": queues, "registered": registered, "stats": stats}
                )
            case ProbeMode.MAPPINGS:
                return MappingReply(
                    names=sorted(load_definitions()),
                    installer_cache_exists=Path("/root/.cache/uv").exists(),
                )
            case ProbeMode.RUNTIME:
                result = subprocess.run(
                    [
                        sys.executable,
                        "-W",
                        "error::UserWarning",
                        "-c",
                        self.runtime_source,
                    ],
                    stdout=subprocess.PIPE,
                    text=True,
                    check=True,
                    timeout=90,
                )
                return RuntimeReply.model_validate_json(result.stdout)

    runtime_source: str = """
import hashlib
import json
import resource
import sys
import time
from importlib.util import find_spec

started = time.perf_counter()
from cdm.backend.app import app
elapsed = time.perf_counter() - started
peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
from cdm.utils.lemmatize import lemmatize_texts

packages = ("bertopic", "sentence_transformers", "scipy", "sklearn", "torch")
print(json.dumps({
    "kind": "runtime",
    "loaded_training_modules": [name for name in packages if name in sys.modules],
    "installed_training_packages": [name for name in packages if find_spec(name)],
    "normalized_queries": lemmatize_texts(
        ["Workers were funding schools.", "TAXES, and regulations!", ""]
    ),
    "contract_hash": hashlib.sha256(
        json.dumps(app.openapi(), sort_keys=True).encode()
    ).hexdigest(),
    "import_seconds": elapsed,
    "import_peak_bytes": peak * (1 if sys.platform == "darwin" else 1024),
}))
"""

    @staticmethod
    def http(url: HttpUrl) -> HttpReply | ProbeUnavailable:
        if url.host is None:
            raise ValueError("The HTTP probe requires a host")
        connection = HTTPConnection(url.host, url.port, timeout=3)
        try:
            connection.request("GET", url.path or "/")
            response = connection.getresponse()
            return HttpReply(
                status=response.status,
                content_type=response.getheader("Content-Type", ""),
                cache_control=response.getheader("Cache-Control"),
                body=response.read().decode(),
            )
        except (ConnectionError, TimeoutError, gaierror) as exc:
            return ProbeUnavailable(error=f"{type(exc).__name__}: {exc}")
        finally:
            connection.close()

    def routing(self) -> RoutingReply:
        # Consume envelopes before starting a worker: no source task is executed.
        dispatcher = JobDispatcher(self.app, self.queues)
        deliveries: list[DeliveredJob] = []
        with self.app.connection_for_read() as connection:
            for kind in JobKind:
                expected_queue = {
                    JobKind.INGEST: self.queues.celery_ingest_queue,
                    JobKind.INDEX: self.queues.celery_index_queue,
                    JobKind.RECONCILE: self.queues.celery_index_queue,
                    JobKind.GOVINFO_BULK: self.queues.celery_bulk_queue,
                    JobKind.GOVINFO_BULK_BATCH: self.queues.celery_bulk_queue,
                    JobKind.TOPIC_TRAINING: self.queues.celery_analytics_queue,
                    JobKind.MEMBER_GRAPH: self.queues.celery_analytics_queue,
                    JobKind.PERSPECTIVES: self.queues.celery_analytics_queue,
                }[kind]
                queue = connection.SimpleQueue(self.app.amqp.queues[expected_queue])
                try:
                    dispatcher.dispatch(kind, f"synthetic-{kind}")
                    message = queue.get(block=True, timeout=5)
                    delivery = DeliveredJob.model_validate(
                        {
                            "job_kind": kind,
                            "task": message.headers["task"],
                            "queue": expected_queue,
                            "arguments": message.payload[0],
                        }
                    )
                    message.ack()
                    deliveries.append(delivery)
                finally:
                    queue.close()
        return RoutingReply(deliveries=deliveries)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=list(ProbeMode))
    parser.add_argument("--url")
    arguments = ProbeArguments.model_validate(vars(parser.parse_args()))
    queues = QueueConfig()
    reply = ReleaseProbe(celery_app, queues).run(arguments)
    print(reply.model_dump_json(by_alias=True))
