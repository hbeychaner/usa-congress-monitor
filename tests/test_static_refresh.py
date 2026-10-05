from datetime import date

from cdm.data_collection.endpoint_registry import get_spec
from cdm.data_collection.specs.congress_list_specs import CONGRESS_LISTABLE
from cdm.workers.tasks import static_refresh_payloads


def test_by_congress_specs_render_congress_path():
    for resource in CONGRESS_LISTABLE:
        spec = get_spec(f"{resource}_list_by_congress")
        assert "congress" in spec._param_map
        assert spec.render_path("https://x", {"congress": 119}).endswith("/119")


def test_static_refresh_payloads_are_weekly_and_scoped():
    payloads = static_refresh_payloads(date(2026, 10, 4))
    assert all(p["schedule_week"] == "2026-W40" for p in payloads)
    scoped = [p for p in payloads if p.get("congress") == 119]
    assert {p["resources"][0] for p in scoped} <= set(CONGRESS_LISTABLE)
    assert any(p["resources"] == ["amendment"] for p in scoped)
    assert all(p["fetch_items"] is False for p in payloads if "congress" not in p)
