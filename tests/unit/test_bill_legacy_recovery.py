from pathlib import Path

from cdm.ingest.archive import SQLiteListCache
from cdm.ingest.runner import IngestRunner, Resource
from cdm.models.bills import BillMetadata


def test_bill_metadata_identity_preserves_historical_entries(tmp_path: Path):
    first = BillMetadata.model_validate(
        {
            "congress": 13,
            "type": "HR",
            "number": "60",
            "introducedDate": "1814-02-19",
            "title": "First bill",
            "url": "https://api.congress.gov/v3/bill/13/hr/60?format=json",
        }
    )
    second = BillMetadata.model_validate(
        {
            "congress": 13,
            "type": "HR",
            "number": "60",
            "introducedDate": "1815-01-24",
            "title": "Second bill",
            "url": "https://api.congress.gov/v3/bill/13/hr/60?format=json",
        }
    )

    cache = SQLiteListCache(tmp_path / "list_records.sqlite3")
    cache.write_many(
        [
            (0, first.model_dump(mode="json", exclude_none=True)),
            (0, second.model_dump(mode="json", exclude_none=True)),
        ]
    )

    assert first.id == second.id == "bill:13:hr:60"
    assert len(cache.load(BillMetadata, -1)) == 2


class _FakeItem:
    def model_dump(self, **kwargs):
        return {"id": "bill:13:hr:60", "title": "Selected version"}


class _FakeClient:
    def resolve_runtime_params_from_record(self, spec, record):
        return {"congress": 13, "type": "hr", "number": "60"}

    def request_for_spec(self, spec, params):
        return {
            "bill": [
                {
                    "introducedDate": "1814-02-19",
                    "detailUrl": "https://api.congress.gov/v3/bill/13/hr/60/1814/2/19?format=json",
                },
                {
                    "introducedDate": "1815-01-24",
                    "detailUrl": "https://api.congress.gov/v3/bill/13/hr/60/1815/1/24?format=json",
                },
            ]
        }

    def get_json(self, url):
        assert url.endswith("/1815/1/24?format=json")
        return {"bill": {"title": "Selected version"}}

    def _extract_records_from_response(self, spec, response):
        value = response["bill"]
        return value if isinstance(value, list) else [value]

    def _resolve_response_model(self, spec):
        return object

    def coerce_records(self, model_cls, records):
        return [_FakeItem()]

    def fetch_one(self, spec, params):
        raise AssertionError("legacy list response should use detailUrl")


def test_legacy_bill_fetch_selects_matching_detail_url(monkeypatch, tmp_path: Path):
    runner = IngestRunner(outdir=tmp_path, resource=Resource.BILL)
    monkeypatch.setattr(runner, "_client", lambda: _FakeClient())

    result = runner._fetch_single_item(
        BillMetadata.model_validate(
            {
                "congress": 13,
                "type": "HR",
                "number": "60",
                "introducedDate": "1815-01-24",
                "title": "Second bill",
                "url": "https://api.congress.gov/v3/bill/13/hr/60?format=json",
            }
        ),
        object(),
        tmp_path,
    )

    assert result["id"] == "bill:13:hr:60:1815-01-24"
    assert result["title"] == "Selected version"
