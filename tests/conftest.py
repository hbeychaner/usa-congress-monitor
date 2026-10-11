from __future__ import annotations

import pytest

from cdm.config import get_config


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    if get_config().congress_api.congress_api_key:
        return
    skip = pytest.mark.skip(reason="CONGRESS_API_KEY is not configured")
    for item in items:
        if "integration" in item.path.parts:
            item.add_marker(skip)
