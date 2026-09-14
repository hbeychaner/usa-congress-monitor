import cdm.backend.services.member_service as member_service
from cdm.backend.services.member_service import list_member_activity


class FakeSearchClient:
    def __init__(self, responses_by_index):
        self.responses_by_index = responses_by_index
        self.calls = []

    def search(self, index, body):
        self.calls.append((index, body))
        hits = self.responses_by_index.get(index, [])
        return {
            "hits": {
                "total": {"value": len(hits)},
                "hits": [{"_source": source} for source in hits],
            }
        }


def _install(monkeypatch, responses):
    client = FakeSearchClient(responses)
    monkeypatch.setattr(member_service, "get_opensearch_client", lambda: client)
    return client


def test_list_member_activity_merges_types_sorted_by_date(monkeypatch):
    client = _install(monkeypatch, {
        "congress-legislation-read": [
            {
                "id": "bill:118:hr:1",
                "title": "A Bill",
                "congress": 118,
                "update_date": "2024-01-10",
                "sponsor_bioguide_ids": ["A000001"],
            },
        ],
        "congress-amendment-read": [
            {
                "id": "amendment:118:samdt:5",
                "type": "SAMDT",
                "number": 5,
                "congress": 118,
                "purpose": "To fix things",
                "submitted_date": "2024-03-01",
                "amended_bill": {"id": "bill:118:s:2", "title": "Parent"},
                "sponsor_bioguide_ids": [],
            },
        ],
    })

    response = list_member_activity("a000001", None, 1, 25)

    assert response.total == 2
    assert response.counts == {"bill": 1, "amendment": 1}
    assert [item.document_type for item in response.items] == ["amendment", "bill"]
    amendment, bill = response.items
    assert amendment.activity_type == "Cosponsor"
    assert amendment.title == "SAMDT 5: To fix things"
    assert amendment.bill_id == "bill:118:s:2"
    assert bill.activity_type == "Sponsor"
    assert bill.bill_id == "bill:118:hr:1"
    # bioguide id was normalized to uppercase in the queries
    for _, body in client.calls:
        assert "A000001" in str(body)


def test_list_member_activity_type_filter_and_pagination(monkeypatch):
    amendments = [
        {
            "id": f"amendment:118:samdt:{n}",
            "type": "SAMDT",
            "number": n,
            "submitted_date": f"2024-01-{n:02d}",
            "sponsor_bioguide_ids": ["A000001"],
        }
        for n in range(1, 8)
    ]
    _install(monkeypatch, {"congress-amendment-read": amendments})

    page2 = list_member_activity("A000001", "amendment", 2, 3)

    assert page2.counts == {"amendment": 7}
    assert len(page2.items) == 3
    # sorted desc by date: page 2 of 3 -> items 4..6 (dates 04..02)
    assert [item.date for item in page2.items] == ["2024-01-04", "2024-01-03", "2024-01-02"]


def test_list_member_activity_ignores_unknown_types(monkeypatch):
    client = _install(monkeypatch, {})

    response = list_member_activity("A000001", "nonsense", 1, 10)

    assert response.total == 0
    assert set(response.counts) == {"bill", "amendment"}
    assert len(client.calls) == 2
