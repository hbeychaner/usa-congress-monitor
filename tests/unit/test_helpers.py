from src.data_collection.queueing.specs import (
    SPECS,
    prepare_api_meta,
    resolve_pagination_for_consumer,
)
from src.models import meta_models


def test_prepare_api_meta_with_meta_model_committee_report():
    spec = SPECS["committee-report"]
    raw_meta = {"offset": "0", "limit": "10", "congress": "118", "report_type": "hrpt"}
    api_meta, meta_obj, filtered_meta = prepare_api_meta(spec, raw_meta)
    assert meta_obj is not None
    # Expect aliased API key present
    assert "reportType" in api_meta
    assert api_meta["congress"] == 118 or api_meta["congress"] == "118"


def test_prepare_api_meta_fallback_treaty():
    spec = SPECS["treaty"]
    raw_meta = {"congress": 117, "page_size": 50}
    api_meta, meta_obj, filtered_meta = prepare_api_meta(spec, raw_meta)
    # treaty uses GenericChunkMeta, so meta_obj should be present
    assert meta_obj is not None
    # snake_case aliasing should still be present in dumped API meta
    assert "pageSize" in api_meta and api_meta["pageSize"] == 50


def test_resolve_pagination_for_consumer_from_meta_obj():
    spec = SPECS["bill"]
    raw_meta = {"offset": "5", "limit": "20"}
    api_meta, meta_obj, filtered_meta = prepare_api_meta(spec, raw_meta)
    offset, limit = resolve_pagination_for_consumer(
        "bill", spec, raw_meta, meta_obj, filtered_meta
    )
    assert offset == 5
    assert limit == 20


def test_resolve_pagination_for_consumer_congress():
    spec = SPECS["congress"]
    raw_meta = {"congress": 118}
    api_meta, meta_obj, filtered_meta = prepare_api_meta(spec, raw_meta)
    offset, limit = resolve_pagination_for_consumer(
        "congress", spec, raw_meta, meta_obj, filtered_meta
    )
    assert offset == 118
    assert limit == 1
