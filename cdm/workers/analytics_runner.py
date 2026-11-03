"""Execute analytics inside a bounded Celery child, not a detached subprocess."""

from collections.abc import Callable

from pydantic import TypeAdapter

from cdm.config.topic_analysis import TopicTrainingOptions
from cdm.graph.job import GraphBuildJob
from cdm.jobs.analytics import (
    AnalysisProgress,
    AnalysisRequest,
    GraphRequest,
    PerspectiveRequest,
    TopicRequest,
)
from cdm.jobs.store import JobStatus, JobStore
from cdm.perspectives.job import PerspectiveBuildJob
from cdm.topics.training import TopicTrainingJob
from cdm.workers.results import JobResult, SkippedClaim


class AnalysisCancelled(Exception):
    """Cancellation is observed at the next computation/publication boundary."""


class AnalyticsJobRunner:
    def __init__(
        self,
        store: JobStore,
        training: Callable[
            [TopicTrainingOptions, Callable[[AnalysisProgress], None]], TopicTrainingJob
        ],
        graph: Callable[[Callable[[AnalysisProgress], None]], GraphBuildJob],
        perspectives: Callable[
            [PerspectiveRequest, Callable[[AnalysisProgress], None]],
            PerspectiveBuildJob,
        ],
    ) -> None:
        self._store = store
        self._training = training
        self._graph = graph
        self._perspectives = perspectives

    def run(self, job_id: str) -> JobResult:
        row = self._store.mark_running(job_id, update_windows=False, max_active=1)
        if row is None:
            return SkippedClaim(self._store).result(job_id)
        request = TypeAdapter(AnalysisRequest).validate_python(row["payload"])
        if request.kind != row["kind"]:
            raise ValueError("Analytics job kind does not match its payload")
        progress = AnalysisProgress(stage="starting")

        def report(update: AnalysisProgress) -> None:
            nonlocal progress
            if self._store.get(job_id)["status"] == JobStatus.CANCELLED:
                raise AnalysisCancelled(job_id)
            progress = AnalysisProgress.model_validate(
                {
                    **progress.model_dump(),
                    **update.model_dump(exclude_unset=True),
                }
            )
            self._store.report_progress(job_id, progress.model_dump(mode="json"))

        report(progress)
        if isinstance(request, TopicRequest):
            self._training(request.options, report).execute()
        elif isinstance(request, GraphRequest):
            self._graph(report).run(request.signals)
        else:
            self._perspectives(request, report).run(request)
        report(AnalysisProgress(progress=1.0))
        completed = self._store.mark_succeeded(job_id)
        return JobResult(job_id=job_id, status=completed["status"])
