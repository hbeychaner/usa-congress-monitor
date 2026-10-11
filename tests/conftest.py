from __future__ import annotations

import os

import pytest

RUN_INTEGRATION_ENV = "RUN_INTEGRATION_TESTS"


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    if os.environ.get(RUN_INTEGRATION_ENV):
        return
    skip = pytest.mark.skip(
        reason=f"integration tests spend API budget; set {RUN_INTEGRATION_ENV}=1"
    )
    for item in items:
        if "integration" in item.path.parts:
            item.add_marker(skip)
