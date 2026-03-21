from src.models.bills import CommitteeReport
from src.data_collection.client import get_client
from src.data_collection.endpoint_registry import get_spec
import src.data_collection.specs.committee_report_specs


def test_committee_report_model_accepts_missing_url():
    # API item payloads sometimes omit an absolute `url` field; model should accept it
    sample = {
        "committeeReports": [
            {
                "congress": 119,
                "chamber": "House",
                "citation": "H. Rept. 119-1",
                "number": 1,
                "part": 1,
                "reportType": "H.Rept.",
                "issueDate": "2025-01-21T05:00:00Z",
                "title": "Some Report Title",
                "type": "HRPT",
                "updateDate": "2025-05-27T14:12:39Z",
            }
        ]
    }
    # The inner record is what the response model should validate
    inner = sample["committeeReports"][0]
    inst = CommitteeReport.model_validate(inner)
    assert inst.citation == "H. Rept. 119-1"
    # `url` is optional and should be None when absent
    assert getattr(inst, "url", None) is None


def test_slug_extraction_from_list_url():
    # Ensure runtime param resolution extracts the URL tail slug for item fetches
    client = get_client()
    spec = get_spec("committee_report_item")
    list_record = {
        "url": "https://api.congress.gov/v3/committee-report/119/HRPT/1?format=json",
        "id": "bill:119:hrpt:1",
    }
    params = client.resolve_runtime_params_from_record(spec, list_record)
    # slug should be extracted and lowercased to match path template
    assert params.get("slug") == "119/hrpt/1"
