import pytest

from cdm.ingest.resource_config import (
    RESOURCE_CONFIGS,
    ResourceConfig,
    validate_scope_catalog,
)
from cdm.ingest.runner import Resource


def test_registered_scope_catalog_is_valid():
    validate_scope_catalog()


def test_static_resource_cannot_define_date_parameters():
    original = RESOURCE_CONFIGS[Resource.CONGRESS]
    RESOURCE_CONFIGS[Resource.CONGRESS] = ResourceConfig(
        resource=Resource.CONGRESS,
        scope="static",
        from_date_param="fromDateTime",
    )
    try:
        with pytest.raises(ValueError, match="cannot define date parameters"):
            validate_scope_catalog()
    finally:
        RESOURCE_CONFIGS[Resource.CONGRESS] = original
