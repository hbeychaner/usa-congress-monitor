"""Bounded real-data proof for one Congress and three measure families."""

import os
from typing import Any, cast

import pytest

from cdm.data_collection.client import get_client
from cdm.data_collection.specs.bill_specs import BILL_ITEM_SPEC
from cdm.ingest.govinfo import (
    GovInfoBillsParser,
    GovInfoBillStatusParser,
    GovInfoBillSummaryParser,
    GovInfoDiscovery,
    GovInfoDownloader,
)
from cdm.store.client import get_opensearch_client
from cdm.store.index_manager import IndexManager
from cdm.store.indexer import to_document
from cdm.store.opensearch import bulk_upsert, index_name, read_alias, write_alias

pytestmark = pytest.mark.integration


def _delete_from_alias_targets(client, alias, document_id):
    for physical_index in client.indices.get_alias(name=alias, ignore=404):
        client.delete(index=physical_index, id=document_id, ignore=[404], refresh=True)


def _api_bill(client, measure_type, number):
    params = {"congress": 118, "type": measure_type, "number": number}
    response = client.request_for_spec(BILL_ITEM_SPEC, params)
    records = client._extract_records_from_response(BILL_ITEM_SPEC, response)
    models = client.coerce_records(
        client._resolve_response_model(BILL_ITEM_SPEC), records, spec=BILL_ITEM_SPEC
    )
    assert len(models) == 1
    return cast(dict[str, Any], records[0]), cast(
        dict[str, Any], models[0].model_dump(mode="json")
    )


def _record_list(record: dict[str, Any], field: str) -> list[Any]:
    value = record.get(field)
    return value if isinstance(value, list) else []


def _record_count(record: dict[str, Any], field: str) -> int:
    value = record.get(field)
    if isinstance(value, dict) and isinstance(value.get("count"), int):
        return value["count"]
    return len(value) if isinstance(value, list) else 0


@pytest.mark.parametrize(
    ("measure_type", "number", "session", "version"),
    [("hr", 184, 1, "ih"), ("s", 1, 1, "is"), ("hres", 11, 1, "eh")],
    ids=("house-bill", "senate-bill", "house-resolution"),
)
def test_live_one_congress_govinfo_proof(
    tmp_path, measure_type, number, session, version
):
    if os.getenv("OPENSEARCH_INTEGRATION") != "1":
        pytest.skip("Set OPENSEARCH_INTEGRATION=1 to test live OpenSearch")

    discovery = GovInfoDiscovery(timeout=60)
    downloader = GovInfoDownloader(tmp_path / "govinfo", timeout=120)
    status_package = discovery.measure_package("BILLSTATUS", 118, measure_type, number)
    summary_package = discovery.measure_package("BILLSUM", 118, measure_type, number)
    text_package = discovery.text_package(118, session, measure_type, number, version)

    status = GovInfoBillStatusParser().parse(
        downloader.download(status_package).read_bytes(), status_package
    )
    summary = GovInfoBillSummaryParser().parse(
        downloader.download(summary_package).read_bytes(), summary_package
    )
    text = GovInfoBillsParser().parse(
        downloader.download(text_package).read_bytes(), text_package
    )

    expected_id = f"bill:118:{measure_type}:{number}"
    assert {status["id"], summary["id"]} == {expected_id}
    assert text["id"].startswith(f"bill-text:118:{measure_type}:{number}:")
    assert text["full_text"].strip()
    assert {
        status["source_metadata"]["package_id"],
        summary["source_metadata"]["package_id"],
        text["source_metadata"]["package_id"],
    } == {
        status_package.package_id,
        summary_package.package_id,
        text_package.package_id,
    }

    api_record, api_bill = _api_bill(get_client(), measure_type, number)
    assert api_bill["congress"] == 118
    assert str(api_bill["type"]).lower() == measure_type
    assert str(api_bill["number"]) == str(number)
    assert str(api_bill["title"]).strip()
    assert status["title"].strip()
    assert " ".join(status["title"].split()) == " ".join(
        str(api_bill["title"]).split()
    )
    for field in ("actions", "committees", "summaries"):
        assert len(_record_list(status, field)) == _record_count(api_record, field)
    assert len(_record_list(status, "sponsors")) == len(
        _record_list(api_record, "sponsors")
    )
    assert len(_record_list(status, "text_versions")) <= _record_count(
        api_record, "textVersions"
    )

    client = get_opensearch_client()
    manager = IndexManager(client)
    staging_index = manager.create_versioned("legislation", 98)
    original_write_alias = write_alias("legislation")
    original_read_alias = read_alias("legislation")
    documents = [
        to_document(status, "bill"),
        to_document(summary, "bill"),
        to_document(text, "bill_text"),
    ]
    try:
        client.reindex(
            body={
                "source": {"index": index_name("legislation")},
                "dest": {"index": staging_index},
            },
            wait_for_completion=True,
            refresh=True,
        )
        client.indices.update_aliases(
            body={
                "actions": [
                    {
                        "remove": {
                            "index": index_name("legislation"),
                            "alias": original_read_alias,
                        }
                    },
                    {
                        "remove": {
                            "index": index_name("legislation"),
                            "alias": original_write_alias,
                        }
                    },
                    {"add": {"index": staging_index, "alias": original_read_alias}},
                    {"add": {"index": staging_index, "alias": original_write_alias}},
                ]
            }
        )
        result = bulk_upsert(client, "bill", documents[:2])
        text_result = bulk_upsert(client, "bill_text", [documents[2]])
        client.indices.refresh(index=staging_index)
        assert not result["errors"]
        assert not text_result["errors"]
        stored = client.get(index=original_read_alias, id=expected_id)["_source"]
        stored_text = client.get(index=original_read_alias, id=text["id"])["_source"]
        assert stored["source_package_ids"] == [
            status_package.package_id,
            summary_package.package_id,
        ]
        assert {entry["package_id"] for entry in stored["source_metadata"]} == {
            status_package.package_id,
            summary_package.package_id,
        }
        assert stored_text["full_text"].strip() == text["full_text"].strip()
    finally:
        for document in documents:
            _delete_from_alias_targets(client, original_write_alias, document["id"])
        manager.ensure_aliases("legislation")
        client.indices.delete(index=staging_index, ignore_unavailable=True)
