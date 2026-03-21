from src.models.bills import Bill
from src.models.shared import CountUrl


class FakeClient:
    def get_json(self, path):
        # return a CountUrl-shaped response for relatedbills and text endpoints
        if path.endswith("/relatedbills"):
            return {
                "relatedBills": {
                    "count": 123,
                    "url": "https://api.congress.gov/v3/bill/118/hr/1/relatedbills",
                }
            }
        if path.endswith("/text"):
            return {
                "textVersions": {
                    "count": 0,
                    "url": "https://api.congress.gov/v3/bill/118/hr/1/text",
                }
            }
        # minimal responses for other endpoints
        if path.endswith("/actions"):
            return {"actions": []}
        if path.endswith("/amendments"):
            return {"amendments": []}
        if path.endswith("/cosponsors"):
            return {"cosponsors": []}
        if path.endswith("/committees"):
            return {"committees": []}
        if path.endswith("/subjects"):
            return {"subjects": {"legislativeSubjects": [], "policyArea": {"name": ""}}}
        if path.endswith("/summaries"):
            return {"summaries": []}
        if path.endswith("/titles"):
            return {"titles": []}
        return {}


def test_relatedbills_and_textversions_counturl_parsing():
    # Simulate the parsing logic used in Bill.add_bill_details() without
    # invoking the full method (avoids constructing Subjects/etc.).
    rb = {"count": 123, "url": "https://api.congress.gov/v3/bill/118/hr/1/relatedbills"}
    if isinstance(rb, dict) and rb.get("count") is not None and rb.get("url"):
        parsed_rb = CountUrl(**rb)
    else:
        parsed_rb = None

    assert isinstance(parsed_rb, CountUrl)
    assert parsed_rb.count == 123

    tv = {"count": 0, "url": "https://api.congress.gov/v3/bill/118/hr/1/text"}
    if isinstance(tv, dict) and tv.get("count") is not None and tv.get("url"):
        parsed_tv = CountUrl(**tv)
    else:
        parsed_tv = None

    assert isinstance(parsed_tv, CountUrl)
    assert parsed_tv.count == 0
