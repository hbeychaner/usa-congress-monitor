"""Analytics implementations registered at analytics-consuming worker startup."""

from functools import lru_cache

from cdm.config import get_config
from cdm.utils.json_types import JsonObject
from cdm.workers.celery_app import celery_app
from cdm.workers.dispatch import TaskName
from cdm.workers.runtime import WorkerContainer
from cdm.workers.tasks import _execute


@lru_cache(maxsize=1)
def _container() -> WorkerContainer:
    return WorkerContainer(get_config())


@celery_app.task(
    bind=True,
    name=TaskName.RUN_ANALYTICS.value,
    soft_time_limit=get_config().queue.celery_analytics_soft_time_limit,
    time_limit=get_config().queue.celery_analytics_time_limit,
)
def run_analytics_job(self: object, job_id: str) -> JsonObject:
    container = _container()
    return _execute(self, job_id, container.analytics_runner.run, container)
