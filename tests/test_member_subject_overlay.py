import pytest

from cdm.backend.services.member_subject_overlay import (
    MemberSubjectOverlayBuilder,
    OverlayResponse,
)


def _response() -> dict:
    def member(key: str, subjects: list[tuple[str, int]]) -> dict:
        buckets = [{"key": name, "doc_count": count} for name, count in subjects]
        return {"key": key, "subjects": {"names": {"buckets": buckets}}}

    return {
        "aggregations": {
            "members": {"buckets": [member("A", [("Health", 5), ("Taxes", 3), ("Parks", 1)]), member("B", [("Health", 2)])]}
        }
    }


def test_overlay_keeps_top_subjects_with_min_bills(monkeypatch: pytest.MonkeyPatch) -> None:
    builder = MemberSubjectOverlayBuilder(client=object())  # type: ignore[arg-type]
    monkeypatch.setattr(builder, "_search", lambda ids, congress: OverlayResponse.model_validate(_response()))

    overlay = builder.build(["A", "B"], None, 2)

    assert [(link.member, link.subject, link.bills) for link in overlay.links] == [
        ("A", "Health", 5),
        ("A", "Taxes", 3),
        ("B", "Health", 2),
    ]
    assert [node.name for node in overlay.nodes] == ["Health", "Taxes"]
