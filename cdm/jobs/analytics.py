"""Typed analytics requests and their shared, durable submission/status surface."""

from datetime import UTC, datetime
from typing import Annotated, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, PositiveInt

from cdm.config.topic_analysis import TopicTrainingOptions
from cdm.contracts.api import TopicTrainingStatus
from cdm.graph.models import GraphBuildStatus, Signal
from cdm.ingest.voteview import current_congress
from cdm.jobs.store import JobKind, JobStatus, JobStore
from cdm.workers.dispatch import JobDispatcher


class AnalysisProgress(BaseModel):
    stage: str | None = None
    progress: float | None = Field(default=None, ge=0, le=1)
    message: str | None = None
    model_version: str | None = None
    versions: dict[Signal, str] = Field(default_factory=dict)


class TopicRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal[JobKind.TOPIC_TRAINING] = JobKind.TOPIC_TRAINING
    options: TopicTrainingOptions = Field(default_factory=TopicTrainingOptions)


class GraphRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal[JobKind.MEMBER_GRAPH] = JobKind.MEMBER_GRAPH
    signals: list[Signal] = Field(default_factory=list)


class PerspectiveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal[JobKind.PERSPECTIVES] = JobKind.PERSPECTIVES
    congresses: list[PositiveInt] = Field(
        default_factory=lambda: [current_congress(datetime.now(UTC).year)], min_length=1
    )
    top_topics: PositiveInt | None = 5
    topic_ids: list[int] | None = None
    no_llm_labels: bool = False
    dry_run: bool = False


type AnalysisRequest = Annotated[
    TopicRequest | GraphRequest | PerspectiveRequest, Field(discriminator="kind")
]


class AnalysisSubmission(BaseModel):
    job_id: str
    started: bool
    status: JobStatus


class AnalysisBusy(ValueError):
    """A different request already owns this analysis kind's active slot."""


class AnalyticsJobs:
    def __init__(self, store: JobStore, dispatcher: JobDispatcher) -> None:
        self.store = store
        self._dispatcher = dispatcher

    def submit(self, request: AnalysisRequest) -> AnalysisSubmission:
        identifier = f"{request.kind}:{uuid4().hex}"
        job = self.store.create(
            request.kind, identifier, request.model_dump(mode="json"), reuse_active=True
        )
        if job["payload"] != request.model_dump(mode="json"):
            raise AnalysisBusy(
                f"{request.kind} already has an active job with different options"
            )
        started = job["id"] == identifier
        if started:
            self._dispatcher.dispatch(job["kind"], job["id"])
        return AnalysisSubmission(
            job_id=job["id"], started=started, status=JobStatus(job["status"])
        )

    def status[Status: TopicTrainingStatus | GraphBuildStatus](
        self, kind: JobKind, schema: type[Status], *, job_id: str | None = None
    ) -> Status:
        job = self.store.get(job_id) if job_id else self.store.latest(kind)
        if job is None:
            return schema()
        progress = AnalysisProgress.model_validate(
            self.store.progress(job["id"])
        ).model_dump(mode="json")
        active = job["status"] in {
            JobStatus.QUEUED,
            JobStatus.RUNNING,
            JobStatus.RETRYING,
        }
        return schema.model_validate(
            {
                **progress,
                "job_id": job["id"],
                "state": "running"
                if active
                else (
                    "succeeded" if job["status"] == JobStatus.SUCCEEDED else "failed"
                ),
                "stage": job["status"]
                if active and job["status"] != JobStatus.RUNNING
                else progress["stage"],
                "message": job["last_error"] or progress["message"],
                "started_at": job["started_at"],
                "finished_at": job["finished_at"],
                "updated_at": job["updated_at"],
            }
        )

    def cancel(self, job_id: str) -> AnalysisSubmission:
        job = self.store.get(job_id)
        if job["kind"] not in {
            JobKind.TOPIC_TRAINING,
            JobKind.MEMBER_GRAPH,
            JobKind.PERSPECTIVES,
        }:
            raise ValueError("Not an analytics job")
        cancelled = self.store.cancel(job_id, "cancelled by operator")
        return AnalysisSubmission(
            job_id=job_id, started=False, status=JobStatus(cancelled["status"])
        )
