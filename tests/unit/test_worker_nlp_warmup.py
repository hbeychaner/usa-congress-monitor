import subprocess
import sys
import textwrap
from unittest.mock import MagicMock

import pytest
from celery import Celery
from celery.worker.worker import WorkController

from cdm.config import get_config
from cdm.workers import tasks
from cdm.workers.dispatch import TaskModule
from cdm.workers.runtime import WorkerContainer


@pytest.mark.parametrize("index_worker", [True, False])
def test_parent_warms_nlp_only_for_selected_index_queue(
    monkeypatch: pytest.MonkeyPatch, index_worker: bool,
) -> None:
    config = get_config()
    container = MagicMock(spec=WorkerContainer)
    sender = MagicMock(spec=WorkController)
    sender.app = MagicMock(spec=Celery)
    queue = (
        config.queue.celery_index_queue
        if index_worker else config.queue.celery_ingest_queue
    )
    sender.app.amqp.queues.consume_from = {queue: MagicMock()}
    warm = MagicMock()
    collect = MagicMock()
    freeze = MagicMock()
    calls = MagicMock()
    calls.attach_mock(warm, "warm")
    calls.attach_mock(collect, "collect")
    calls.attach_mock(freeze, "freeze")
    monkeypatch.setattr(tasks, "_container", lambda: container)
    monkeypatch.setattr(tasks, "warm_lemmatizer", warm)
    monkeypatch.setattr(tasks.gc, "collect", collect)
    monkeypatch.setattr(tasks.gc, "freeze", freeze)
    tasks.warm_store(sender=sender)
    container.job_store.repair_legacy_windows.assert_called_once_with()
    if index_worker:
        warm.assert_called_once_with()
        collect.assert_called_once_with()
        freeze.assert_called_once_with()
        assert [call[0] for call in calls.mock_calls] == ["warm", "collect", "freeze"]
    else:
        warm.assert_not_called()
        collect.assert_not_called()
        freeze.assert_not_called()
    sender.app.loader.import_task_module.assert_not_called()


def test_store_only_initialization_remains_valid_without_worker_sender(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    container = MagicMock(spec=WorkerContainer)
    warm = MagicMock()
    freeze = MagicMock()
    monkeypatch.setattr(tasks, "_container", lambda: container)
    monkeypatch.setattr(tasks, "warm_lemmatizer", warm)
    monkeypatch.setattr(tasks.gc, "freeze", freeze)
    tasks.warm_store()
    container.job_store.repair_legacy_windows.assert_called_once_with()
    warm.assert_not_called()
    freeze.assert_not_called()


def test_frozen_parent_heap_keeps_new_task_cycles_collectible() -> None:
    subprocess.run(
        [sys.executable, "-c", textwrap.dedent("""
            import gc
            import weakref

            gc.collect()
            gc.freeze()
            assert gc.isenabled()

            class Cycle:
                def __init__(self) -> None:
                    self.reference: Cycle | None = self

            value = Cycle()
            reference = weakref.ref(value)
            del value
            gc.collect()
            assert reference() is None
            assert gc.isenabled()
        """)],
        check=True, capture_output=True, text=True,
    )


def test_analytics_task_module_is_registered_before_analytics_worker_fork(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    container = MagicMock(spec=WorkerContainer)
    sender = MagicMock(spec=WorkController)
    sender.app = MagicMock(spec=Celery)
    sender.app.amqp.queues.consume_from = {get_config().queue.celery_analytics_queue: MagicMock()}
    warm = MagicMock()
    monkeypatch.setattr(tasks, "_container", lambda: container)
    monkeypatch.setattr(tasks, "warm_lemmatizer", warm)
    tasks.warm_store(sender)
    sender.app.loader.import_task_module.assert_called_once_with(TaskModule.ANALYTICS.value)
    container.job_store.repair_legacy_windows.assert_called_once_with()
    warm.assert_not_called()
