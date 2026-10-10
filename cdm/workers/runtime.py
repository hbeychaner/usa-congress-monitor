"""Composition root for Celery workers and job-submitting scripts."""

from __future__ import annotations

from functools import cached_property

import requests
from redis import Redis

from cdm.container import Container
from cdm.ingest.govinfo import GovInfoDiscovery
from cdm.jobs.store import JobStore
from cdm.utils.rate_limiter import TokenBucket
from cdm.workers.celery_app import celery_app
from cdm.workers.dispatch import JobDispatcher, JobSubmitter
from cdm.workers.failures import FailureClassifier
from cdm.workers.govinfo_runner import (
    GovInfoBatchRunner,
    GovInfoPackageRunner,
    ReconciliationRunner,
)
from cdm.workers.index_runner import IndexJobRunner
from cdm.workers.ingest_runner import IngestJobRunner
from cdm.workers.maintenance import (
    GovInfoRefreshScheduler,
    JobRecoveryService,
    QueueDepthProbe,
    RetentionService,
)
from cdm.workers.planners import (
    CoverageGapPlanner,
    DailyIngestPlanner,
    StaticRefreshPlanner,
)
from cdm.workers.results import TaskRetrier


class WorkerContainer(Container):
    """Adds the ledger, broker, and job runners to the shared container."""

    # Legacy-window repair scans the whole ledger under a global lock, so it
    # runs once per worker boot (see tasks.warm_store), never per task.
    @cached_property
    def job_store(self) -> JobStore:
        return JobStore(self.config.ledger.job_db_path, repair=False)

    @cached_property
    def redis_client(self) -> Redis:
        return Redis.from_url(self.config.redis.redis_url)

    @cached_property
    def job_dispatcher(self) -> JobDispatcher:
        return JobDispatcher(celery_app, self.config.queue)

    @cached_property
    def job_submitter(self) -> JobSubmitter:
        return JobSubmitter(self.job_store, self.job_dispatcher)

    @cached_property
    def failure_classifier(self) -> FailureClassifier:
        return FailureClassifier()

    @cached_property
    def task_retrier(self) -> TaskRetrier:
        return TaskRetrier(
            self.job_store, self.config.queue, self.failure_classifier
        )

    @cached_property
    def govinfo_session(self) -> requests.Session:
        return requests.Session()

    @cached_property
    def govinfo_rate_limiter(self) -> TokenBucket:
        return TokenBucket(
            rate_per_hour=self.config.govinfo.govinfo_rate_limit_per_hour
        )

    @cached_property
    def ingest_runner(self) -> IngestJobRunner:
        return IngestJobRunner(
            self.job_store,
            self.redis_client,
            self.job_submitter,
            self.config.redis,
            self.config.congress_api,
        )

    @cached_property
    def govinfo_package_runner(self) -> GovInfoPackageRunner:
        return GovInfoPackageRunner(
            self.job_store,
            self.redis_client,
            self.job_submitter,
            self.job_dispatcher,
            self.config.redis,
            self.govinfo_session,
            self.govinfo_rate_limiter,
        )

    @cached_property
    def govinfo_batch_runner(self) -> GovInfoBatchRunner:
        return GovInfoBatchRunner(self.job_store, self.job_dispatcher)

    @cached_property
    def reconciliation_runner(self) -> ReconciliationRunner:
        return ReconciliationRunner(self.job_store, self.elastic_client)

    @cached_property
    def index_runner(self) -> IndexJobRunner:
        return IndexJobRunner(
            self.job_store,
            self.redis_client,
            self.elastic_client,
            self.config.indexing,
            self.config.redis.redis_consumer_group,
        )

    @cached_property
    def daily_ingest_planner(self) -> DailyIngestPlanner:
        return DailyIngestPlanner()

    @cached_property
    def coverage_gap_planner(self) -> CoverageGapPlanner:
        return CoverageGapPlanner(self.job_store, self.config.ledger)

    @cached_property
    def static_refresh_planner(self) -> StaticRefreshPlanner:
        return StaticRefreshPlanner()

    @cached_property
    def queue_depth_probe(self) -> QueueDepthProbe:
        return QueueDepthProbe(celery_app)

    @cached_property
    def recovery_service(self) -> JobRecoveryService:
        return JobRecoveryService(
            self.job_store,
            self.redis_client,
            self.job_dispatcher,
            self.queue_depth_probe,
            self.failure_classifier,
            self.config.queue,
        )

    @cached_property
    def retention_service(self) -> RetentionService:
        return RetentionService(
            self.job_store,
            self.redis_client,
            self.config.ledger,
            self.config.govinfo,
        )

    @cached_property
    def govinfo_refresh_scheduler(self) -> GovInfoRefreshScheduler:
        return GovInfoRefreshScheduler(self.job_submitter, GovInfoDiscovery())
