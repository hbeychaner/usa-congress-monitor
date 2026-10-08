from cdm.backend.services.member_service import _member_detail


def test_terms_expand_to_congresses_with_state():
    source = {
        "bioguide_id": "S000033",
        "name": "Sanders, Bernard",
        "state": "Vermont",
        "terms": {
            "item": [
                {"chamber": "House of Representatives", "start_year": 1991, "end_year": 2007},
                {"chamber": "Senate", "start_year": 2007, "end_year": 2013},
            ]
        },
    }
    terms = _member_detail(source).terms
    house = [t.congress for t in terms if t.chamber == "House of Representatives"]
    senate = [t.congress for t in terms if t.chamber == "Senate"]
    assert house == list(range(102, 110))
    assert senate == [110, 111, 112]
    assert all(t.state_name == "Vermont" for t in terms)
