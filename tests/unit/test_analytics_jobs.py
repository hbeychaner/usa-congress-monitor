from collections.abc import AsyncIterator, Callable
from concurrent.futures import ProcessPoolExecutor
from datetime import UTC, datetime, timedelta
from itertools import repeat
from multiprocessing import get_context
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, patch

import pytest
import pytest_asyncio
import requests
from celery import Celery
from celery.exceptions import MaxRetriesExceededError
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from cdm.backend.api.routes import admin
from cdm.backend.dependencies import get_analytics_jobs
from cdm.config.app_config import QueueConfig
from cdm.config.topic_analysis import TopicTrainingOptions
from cdm.container import Container
from cdm.contracts.api import TopicTrainingStatus, TrainingState
from cdm.graph.job import GraphBuildJob
from cdm.graph.models import GraphBuildStatus, Signal
from cdm.graph.store import BillSignatureReader, GraphStore, RollCallReader
from cdm.graph.topics import TopicModelReader
from cdm.jobs.analytics import (
    AnalysisBusy,
    AnalysisProgress,
    AnalysisRequest,
    AnalysisSubmission,
    AnalyticsJobs,
    GraphRequest,
    PerspectiveRequest,
    TopicRequest,
)
from cdm.jobs.store import JobKind, JobStatus, JobStore
from cdm.perspectives.job import PerspectiveBuildJob
from cdm.perspectives.models import TopicPerspectives
from cdm.perspectives.runner import PerspectiveRunner
from cdm.store.perspective_repository import PerspectiveRepository
from cdm.topics.training import TopicTrainingJob
from cdm.utils.json_types import JsonObject
from cdm.workers import analytics_tasks, tasks
from cdm.workers.analytics_runner import AnalysisCancelled, AnalyticsJobRunner
from cdm.workers.dispatch import JobDispatcher, TaskName
from cdm.workers.failures import FailureClassifier
from cdm.workers.heartbeat import JobHeartbeat
from cdm.workers.maintenance import JobRecoveryService
from cdm.workers.results import TaskRetrier
from scripts import build_member_graph, build_perspectives, train_topic_model


def _submit_from_process(path: str) -> tuple[str, bool]:
    store = JobStore(path, repair=False)
    jobs = AnalyticsJobs(store, JobDispatcher(Mock(spec=Celery), QueueConfig()))
    result = jobs.submit(TopicRequest())
    store.engine.dispose()
    return result.job_id, result.started


@pytest.fixture
def jobs(tmp_path: Path) -> AnalyticsJobs:
    return AnalyticsJobs(
        JobStore(tmp_path / "jobs.sqlite3", repair=False),
        JobDispatcher(Mock(spec=Celery), QueueConfig()),
    )


class RunnerHarness:
    def __init__(self, jobs: AnalyticsJobs) -> None:
        self.store = jobs.store
        self.training = Mock(spec=TopicTrainingJob)
        self.graph = Mock(spec=GraphBuildJob)
        self.perspectives = Mock(spec=PerspectiveBuildJob)
        self.training_effect: Callable[[Callable[[AnalysisProgress], None]], None] = (
            self._train
        )
        self.runner = AnalyticsJobRunner(
            self.store, self.make_training, self.make_graph, self.make_perspectives
        )

    def _train(self, report: Callable[[AnalysisProgress], None]) -> None:
        report(AnalysisProgress(stage="done", progress=1.0, model_version="validated"))

    def make_training(
        self, options: TopicTrainingOptions, report: Callable[[AnalysisProgress], None]
    ) -> TopicTrainingJob:
        self.training.execute.side_effect = lambda: self.training_effect(report)
        return self.training

    def make_graph(self, report: Callable[[AnalysisProgress], None]) -> GraphBuildJob:
        self.graph.run.side_effect = lambda signals: report(
            AnalysisProgress(stage="done", versions={Signal.VOTING: "graph-v1"})
        )
        return self.graph

    def make_perspectives(
        self, request: PerspectiveRequest, report: Callable[[AnalysisProgress], None]
    ) -> PerspectiveBuildJob:
        self.perspectives.run.side_effect = lambda options: report(
            AnalysisProgress(stage="done", message="perspectives written")
        )
        return self.perspectives

    def execute(self, monkeypatch: pytest.MonkeyPatch, job_id: str) -> JsonObject:
        container = Mock(
            analytics_runner=self.runner,
            job_heartbeat=JobHeartbeat(self.store, 0.01),
            task_retrier=TaskRetrier(self.store, QueueConfig(), FailureClassifier()),
        )
        monkeypatch.setattr(analytics_tasks, "_container", lambda: container)
        task = tasks.celery_app.tasks[TaskName.RUN_ANALYTICS.value]
        return task.apply(args=[job_id], throw=True).get(propagate=True)


class TestAdmissionAndStatus:
    def test_idle_without_any_legacy_status_file(self, jobs: AnalyticsJobs) -> None:
        assert (
            jobs.status(JobKind.TOPIC_TRAINING, TopicTrainingStatus)
            == TopicTrainingStatus()
        )
        assert jobs.status(JobKind.MEMBER_GRAPH, GraphBuildStatus) == GraphBuildStatus()

    def test_concurrent_processes_admit_exactly_one_job(self, tmp_path: Path) -> None:
        path = str(tmp_path / "concurrent.sqlite3")
        with ProcessPoolExecutor(
            max_workers=4, mp_context=get_context("spawn")
        ) as pool:
            results = list(pool.map(_submit_from_process, repeat(path, 8)))

        assert len({identifier for identifier, _ in results}) == 1
        assert sum(started for _, started in results) == 1
        assert len(JobStore(path, repair=False).jobs()) == 1

    def test_different_active_options_are_not_silently_substituted(
        self, jobs: AnalyticsJobs
    ) -> None:
        original = jobs.submit(TopicRequest())

        with pytest.raises(AnalysisBusy, match="different options"):
            jobs.submit(TopicRequest(options=TopicTrainingOptions(max_docs=1)))

        latest = jobs.store.latest(JobKind.TOPIC_TRAINING)
        assert latest is not None and latest["id"] == original.job_id

    def test_progress_and_terminal_state_survive_a_new_service_instance(
        self, jobs: AnalyticsJobs
    ) -> None:
        job = jobs.submit(TopicRequest())
        jobs.store.mark_running(job.job_id)
        jobs.store.report_progress(
            job.job_id,
            AnalysisProgress(stage="fitting", progress=0.5).model_dump(mode="json"),
        )
        restarted = AnalyticsJobs(
            JobStore(jobs.store.path, repair=False), Mock(spec=JobDispatcher)
        )
        status = restarted.status(JobKind.TOPIC_TRAINING, TopicTrainingStatus)
        assert status.job_id == job.job_id
        assert status.state == TrainingState.RUNNING
        assert status.stage == "fitting" and status.progress == 0.5
        assert status.started_at is not None
        assert status.pid is None

        jobs.store.mark_failed(job.job_id, "model failed")
        failed = restarted.status(JobKind.TOPIC_TRAINING, TopicTrainingStatus)
        assert failed.state == TrainingState.FAILED
        assert failed.message == "model failed"
        assert failed.finished_at is not None
        assert jobs.submit(TopicRequest()).job_id != job.job_id

    def test_progress_cannot_override_lifecycle_state(
        self, jobs: AnalyticsJobs
    ) -> None:
        job = jobs.submit(TopicRequest())
        jobs.store.report_progress(
            job.job_id, {"state": "succeeded", "stage": "fitting"}
        )

        status = jobs.status(JobKind.TOPIC_TRAINING, TopicTrainingStatus)

        assert status.state == TrainingState.RUNNING
        assert status.stage == "queued"

    def test_retention_removes_progress_with_its_terminal_job(
        self, jobs: AnalyticsJobs
    ) -> None:
        job = jobs.submit(TopicRequest())
        jobs.store.mark_running(job.job_id)
        jobs.store.report_progress(job.job_id, {"stage": "done"})
        jobs.store.mark_succeeded(job.job_id)

        pruned = jobs.store.prune_terminal_jobs(
            older_than=(datetime.now(UTC) + timedelta(days=1)).isoformat()
        )

        assert [row["id"] for row in pruned] == [job.job_id]
        assert jobs.store.progress(job.job_id) == {}


class TestWorkerOwnedLifecycle:
    def test_exhausted_transient_retries_are_terminal(
        self, jobs: AnalyticsJobs
    ) -> None:
        job = jobs.submit(TopicRequest())
        jobs.store.mark_running(job.job_id)
        task = Mock(request=Mock(retries=24))
        task.retry.side_effect = MaxRetriesExceededError("retry limit")
        retrier = TaskRetrier(jobs.store, QueueConfig(), FailureClassifier())

        with pytest.raises(MaxRetriesExceededError):
            retrier.handle(task, job.job_id, requests.ConnectionError("disconnected"))

        assert jobs.store.get(job.job_id)["status"] == JobStatus.FAILED

    @pytest.mark.parametrize(
        "analysis",
        [
            TopicRequest(),
            GraphRequest(signals=[Signal.VOTING]),
            PerspectiveRequest(),
        ],
    )
    def test_each_kind_runs_once_and_preserves_progress(
        self,
        jobs: AnalyticsJobs,
        monkeypatch: pytest.MonkeyPatch,
        analysis: AnalysisRequest,
    ) -> None:
        job = jobs.submit(analysis)
        harness = RunnerHarness(jobs)

        assert harness.execute(monkeypatch, job.job_id)["status"] == JobStatus.SUCCEEDED
        assert harness.execute(monkeypatch, job.job_id)["skipped"] is True
        assert jobs.store.get(job.job_id)["attempts"] == 1
        assert jobs.store.progress(job.job_id)["stage"] == "done"
        assert (
            sum(
                mock.call_count
                for mock in (
                    harness.training.execute,
                    harness.graph.run,
                    harness.perspectives.run,
                )
            )
            == 1
        )

    def test_error_is_failed_not_success_shaped(
        self, jobs: AnalyticsJobs, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        job = jobs.submit(TopicRequest())
        harness = RunnerHarness(jobs)

        def fail(report: Callable[[AnalysisProgress], None]) -> None:
            report(AnalysisProgress(stage="fitting"))
            raise ValueError("invalid model")

        harness.training_effect = fail
        with pytest.raises(ValueError, match="invalid model"):
            harness.execute(monkeypatch, job.job_id)
        row = jobs.store.get(job.job_id)
        assert row["status"] == JobStatus.FAILED
        assert row["last_error"] == "invalid model"
        assert jobs.store.progress(job.job_id)["progress"] is None

    def test_queued_cancellation_never_constructs_training(
        self, jobs: AnalyticsJobs, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        job = jobs.submit(TopicRequest())
        harness = RunnerHarness(jobs)
        jobs.cancel(job.job_id)

        assert harness.execute(monkeypatch, job.job_id)["skipped"] is True
        harness.training.execute.assert_not_called()
        assert jobs.store.get(job.job_id)["status"] == JobStatus.CANCELLED

    @pytest.mark.parametrize("transient_error", [False, True])
    def test_running_cancellation_is_not_resurrected_by_late_failure(
        self,
        jobs: AnalyticsJobs,
        monkeypatch: pytest.MonkeyPatch,
        transient_error: bool,
    ) -> None:
        job = jobs.submit(TopicRequest())
        harness = RunnerHarness(jobs)

        def cancel(report: Callable[[AnalysisProgress], None]) -> None:
            jobs.cancel(job.job_id)
            if transient_error:
                raise requests.ConnectionError("disconnected")
            report(AnalysisProgress(stage="publishing"))

        harness.training_effect = cancel
        with pytest.raises((AnalysisCancelled, requests.ConnectionError)):
            harness.execute(monkeypatch, job.job_id)
        assert jobs.store.get(job.job_id)["status"] == JobStatus.CANCELLED


class TestRecovery:
    def service(self, jobs: AnalyticsJobs) -> JobRecoveryService:
        redis = Mock()
        redis.lock.return_value.acquire.return_value = True
        return JobRecoveryService(
            jobs.store,
            redis,
            Mock(spec=JobDispatcher),
            Mock(depth=Mock(return_value=0)),
            FailureClassifier(),
            QueueConfig(),
            Mock(job_ids=Mock(return_value=set())),
        )

    def test_crashed_execution_is_requeued_but_terminal_failures_are_not(
        self, jobs: AnalyticsJobs
    ) -> None:
        failed = jobs.submit(TopicRequest())
        jobs.store.mark_running(failed.job_id)
        jobs.store.mark_failed(failed.job_id, "Connection closed by server.")
        active = jobs.submit(TopicRequest())
        jobs.store.mark_running(active.job_id)
        service = self.service(jobs)
        with patch("cdm.workers.maintenance.datetime") as clock:
            clock.now.return_value = datetime.now(UTC) + timedelta(days=2)
            result = service.recover()

        assert result.recovered == [active.job_id]
        assert jobs.store.get(active.job_id)["status"] == JobStatus.QUEUED
        assert jobs.store.get(failed.job_id)["status"] == JobStatus.FAILED

    def test_orphaned_queued_analytics_are_redispatched(
        self, jobs: AnalyticsJobs
    ) -> None:
        queued = jobs.submit(GraphRequest())
        with patch("cdm.workers.maintenance.datetime") as clock:
            clock.now.return_value = datetime.now(UTC) + timedelta(hours=2)
            result = self.service(jobs).recover()
        assert result.recovered == [queued.job_id]

    def test_repeated_worker_crashes_have_a_terminal_attempt_limit(
        self, jobs: AnalyticsJobs
    ) -> None:
        job = jobs.submit(TopicRequest())
        for attempt in range(QueueConfig().celery_retry_max):
            if attempt:
                jobs.store.requeue(job.job_id)
            jobs.store.mark_running(job.job_id)
        with patch("cdm.workers.maintenance.datetime") as clock:
            clock.now.return_value = datetime.now(UTC) + timedelta(days=2)
            result = self.service(jobs).recover()

        assert result.recovered == []
        assert jobs.store.get(job.job_id)["status"] == JobStatus.FAILED


class TestAdminCompatibility:
    @pytest_asyncio.fixture
    async def client(self, jobs: AnalyticsJobs) -> AsyncIterator[AsyncClient]:
        app = FastAPI()
        app.include_router(admin.router)
        app.dependency_overrides[get_analytics_jobs] = lambda: jobs
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            yield client

    @pytest.mark.asyncio
    @pytest.mark.parametrize("path", ["topic-training", "member-graph", "perspectives"])
    async def test_existing_start_and_status_shapes_use_the_ledger(
        self, client: AsyncClient, path: str
    ) -> None:
        assert (await client.get(f"/admin/{path}")).json()["state"] == "idle"
        started = (await client.post(f"/admin/{path}")).json()
        assert started["started"] is True and started["job_id"]
        assert started["state"] == "running" and started["stage"] == "queued"
        assert (await client.post(f"/admin/{path}")).json()["started"] is False
        assert (await client.get(f"/admin/{path}")).json()["job_id"] == started[
            "job_id"
        ]

    @pytest.mark.asyncio
    async def test_conflicting_cli_preview_is_an_explicit_conflict(
        self, jobs: AnalyticsJobs, client: AsyncClient
    ) -> None:
        jobs.submit(TopicRequest(options=TopicTrainingOptions(max_docs=1)))
        assert (await client.post("/admin/topic-training")).status_code == 409

    @pytest.mark.asyncio
    async def test_cancel_is_exposed_without_a_pid(self, client: AsyncClient) -> None:
        job_id = (await client.post("/admin/topic-training")).json()["job_id"]
        response = await client.post(f"/admin/analytics/{job_id}/cancel")
        assert response.status_code == 200
        assert response.json()["status"] == "cancelled"
        assert (await client.get("/admin/topic-training")).json()["state"] == "failed"
        assert (await client.post("/admin/analytics/missing/cancel")).status_code == 404


def test_analytics_routing_and_time_limits_are_explicit() -> None:
    app = Mock(spec=Celery)
    queues = QueueConfig()
    dispatcher = JobDispatcher(app, queues)
    for kind in (JobKind.TOPIC_TRAINING, JobKind.MEMBER_GRAPH, JobKind.PERSPECTIVES):
        dispatcher.dispatch(kind, "job")
        app.send_task.assert_called_with(
            TaskName.RUN_ANALYTICS.value,
            args=["job"],
            queue=queues.celery_analytics_queue,
        )
    task = tasks.celery_app.tasks[TaskName.RUN_ANALYTICS.value]
    assert task.soft_time_limit == queues.celery_analytics_soft_time_limit
    assert task.time_limit == queues.celery_analytics_time_limit
    assert task.time_limit > queues.celery_task_time_limit


@pytest.mark.parametrize(
    ("script", "arguments", "kind"),
    [
        (train_topic_model, ["--max-docs", "1"], JobKind.TOPIC_TRAINING),
        (build_member_graph, ["voting"], JobKind.MEMBER_GRAPH),
        (
            build_perspectives,
            ["--congress", "118", "--all-topics"],
            JobKind.PERSPECTIVES,
        ),
    ],
)
def test_clis_submit_validated_jobs_and_return_immediately(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    script: ModuleType,
    arguments: list[str],
    kind: JobKind,
) -> None:
    container = Mock(spec=Container)
    container.analytics_jobs.submit.return_value = AnalysisSubmission(
        job_id="test-job", started=True, status=JobStatus.QUEUED
    )
    monkeypatch.setattr(script, "Container", lambda config: container)
    monkeypatch.setattr("sys.argv", [script.__name__, *arguments])

    script.main()

    request = container.analytics_jobs.submit.call_args.args[0]
    assert request.kind == kind
    output = AnalysisSubmission.model_validate_json(capsys.readouterr().out)
    assert output.job_id == "test-job" and output.started
    assert not hasattr(Container, "topic_training_job")
    assert not hasattr(Container, "graph_build_job")
    assert not hasattr(Container, "perspective_build_job")


@pytest.mark.parametrize(
    "script", [train_topic_model, build_member_graph, build_perspectives]
)
def test_cli_help_does_not_open_the_ledger(
    monkeypatch: pytest.MonkeyPatch, script: ModuleType
) -> None:
    constructor = Mock(spec=Container)
    monkeypatch.setattr(script, "Container", constructor)
    monkeypatch.setattr(script, "get_config", Mock())
    monkeypatch.setattr("sys.argv", [script.__name__, "--help"])

    with pytest.raises(SystemExit) as result:
        script.main()

    assert result.value.code == 0
    constructor.assert_not_called()


@pytest.mark.parametrize(
    ("task_name", "kind"),
    [
        ("schedule_topic_training", JobKind.TOPIC_TRAINING),
        ("schedule_member_graph_build", JobKind.MEMBER_GRAPH),
        ("schedule_perspective_build", JobKind.PERSPECTIVES),
    ],
)
def test_existing_schedule_task_names_submit_the_same_durable_requests(
    jobs: AnalyticsJobs, monkeypatch: pytest.MonkeyPatch, task_name: str, kind: JobKind
) -> None:
    monkeypatch.setattr(tasks, "_container", lambda: Mock(analytics_jobs=jobs))
    task = tasks.celery_app.tasks[f"cdm.workers.tasks.{task_name}"]

    first = AnalysisSubmission.model_validate(
        task.apply(throw=True).get(propagate=True)
    )
    second = AnalysisSubmission.model_validate(
        task.apply(throw=True).get(propagate=True)
    )

    assert first.started and not second.started
    assert first.job_id == second.job_id
    assert jobs.store.get(first.job_id)["kind"] == kind


@pytest.mark.parametrize("dry_run", [True, False])
def test_perspective_worker_honors_scope_and_preview_writes(dry_run: bool) -> None:
    runner = Mock(spec=PerspectiveRunner)
    repository = Mock(spec=PerspectiveRepository)
    repository.replace.return_value = 1
    result = TopicPerspectives(congress=118, topic_id=0, topic_label="Health", bills=1)
    runner.source_version.return_value = "published"
    runner.run.return_value = [result]
    progress: list[AnalysisProgress] = []
    job = PerspectiveBuildJob(runner, repository, progress.append)
    analysis = PerspectiveRequest(congresses=[118], top_topics=None, dry_run=dry_run)

    job.run(analysis)

    runner.run.assert_called_once()
    assert runner.run.call_args.args[0] == 118
    assert runner.run.call_args.kwargs["top_topics"] is None
    assert repository.replace.call_count == (0 if dry_run else 1)
    if not dry_run:
        assert repository.replace.call_args.args[:2] == (118, "published")
    assert progress[-1].progress == 1.0
    assert any(update.model_version == "published" for update in progress)


def test_graph_checks_cancellation_before_publishing_staged_edges() -> None:
    store = Mock(spec=GraphStore)
    store.write_edges.return_value = 1

    def report(progress: AnalysisProgress) -> None:
        if progress.stage == "publishing":
            raise AnalysisCancelled()

    job = GraphBuildJob(
        store,
        Mock(spec=BillSignatureReader),
        Mock(spec=RollCallReader),
        Mock(spec=TopicModelReader),
        report,
    )
    with (
        patch.object(job, "_build", return_value=iter(())),
        pytest.raises(AnalysisCancelled),
    ):
        job.run([Signal.VOTING])

    store.write_edges.assert_called_once()
    store.publish.assert_not_called()
