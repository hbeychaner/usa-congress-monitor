import json
from src.data_collection.id_utils import canonical_id, parse_url_to_id


def test_parse_url_to_id():
    url = "https://api.congress.gov/v3/bill/110/hconres/10?format=json"
    assert parse_url_to_id(url) == "bill:110:hconres:10"


def test_canonical_id_from_bill_item():
    with open("data/bills_ingest2/items.json") as f:
        items = json.load(f)
    assert len(items) > 0
    first = items[0]
    assert canonical_id(first) == "bill:110:hconres:10"


def test_canonical_id_person_bioguide():
    rec = {"bioguide_id": "L000551", "full_name": "Rep. Lee"}
    assert canonical_id(rec) == "person:L000551"


def test_canonical_id_amendment_like():
    rec = {"congress": 110, "number": "1", "purpose": "test", "type": "HAMDT"}
    # amendment fallback path should produce amendment:... id
    cid = canonical_id(rec)
    # allow either amendment: or bill: (some records normalize to bill composite)
    assert cid.startswith("amendment:110:") or cid.startswith("bill:110:")


def test_canonical_id_fallback_record():
    # empty/unknown records should return a record: fallback id
    rec = {"foo": "bar"}
    cid = canonical_id(rec)
    assert cid.startswith("record:")
