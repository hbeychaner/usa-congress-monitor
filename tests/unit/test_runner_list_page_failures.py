import json

from cdm.ingest.runner import IngestRunner, Resource


def test_append_list_page_failure_writes_jsonl(tmp_path):
    runner = IngestRunner(outdir=tmp_path, resource=Resource.BILL)
    resource_dir = tmp_path / "bill"

    runner._append_list_page_failure(
        resource_dir,
        list_url="https://api.congress.gov/v3/bill",
        params={
            "offset": 3246,
            "limit": 1,
            "fromDateTime": "2022-11-06T00:00:00Z",
            "toDateTime": "2023-11-05T23:59:59Z",
        },
        status_code=500,
        error="server error: 500",
    )

    failure_log = resource_dir / "list_page_failures.jsonl"
    assert failure_log.exists()

    record = json.loads(failure_log.read_text(encoding="utf-8").strip())
    assert record["resource"] == "bill"
    assert record["offset"] == 3246
    assert record["limit"] == 1
    assert record["status_code"] == 500
    assert record["error"] == "server error: 500"
