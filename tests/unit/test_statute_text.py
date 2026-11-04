from copy import deepcopy
from datetime import date

import pytest
from pydantic import AnyHttpUrl, ValidationError

from cdm.config.source_policy import SourceName
from cdm.config.statute_text import StatuteTextSettings
from cdm.ingest.source_contract import SourceMetadata
from cdm.ingest.statute_text import StatuteTextEnricher, VerifiedStatuteText
from cdm.ingest.statutes import StatuteIdentity, StatuteLaw, StatuteLawKind
from cdm.utils.json_types import JsonObject, JsonValue


class Fixture:
    @staticmethod
    def candidate(kind: StatuteLawKind = StatuteLawKind.PUBLIC) -> VerifiedStatuteText:
        return VerifiedStatuteText(
            bill_id="bill:94:hr:1",
            pdf_url=AnyHttpUrl(
                "https://www.congress.gov/94/statute/STATUTE-90/STATUTE-90-Pg3.pdf"
            ),
            bill_reference_verified=True,
            law=StatuteLaw(
                identity=StatuteIdentity(kind=kind, congress=94, number=1),
                volume=90,
                first_page="3",
                source_volume=90,
                approved_date=date(1976, 1, 28),
                title="An Act",
                text="An interventional program.\nA < B & C > D.",
                source_url=AnyHttpUrl(
                    "https://www.govinfo.gov/bulkdata/STATUTE/90/STATUTE-90.xml"
                ),
                volume_sha256="a" * 64,
                component_sha256="b" * 64,
                bill_references=["/us/bill/94/hr/1"],
            ),
        )

    @staticmethod
    def before(kind: StatuteLawKind = StatuteLawKind.PUBLIC) -> JsonObject:
        label = f"{kind.value.title()} Law"
        return {
            "id": "bill:94:hr:1",
            "source_type": "bill",
            "type": "HR",
            "congress": 94,
            "number": 1,
            "laws": [{"number": "94-1", "law_type": label}],
            "text_versions": [
                {
                    "type": label,
                    "formats": [
                        {
                            "type": "PDF",
                            "url": str(Fixture.candidate().pdf_url),
                        }
                    ],
                }
            ],
            "subjects": {"legislative_subjects": [{"name": "Preserve me"}]},
            "analysis": {"topics": ["unchanged"]},
            "hydration_status": "partial",
        }


@pytest.mark.parametrize("kind", list(StatuteLawKind))
def test_adds_law_text_and_truthful_provenance_without_changing_details(
    kind: StatuteLawKind,
) -> None:
    before = Fixture.before(kind)
    original = deepcopy(before)
    enricher = StatuteTextEnricher(StatuteTextSettings(), lambda texts: ["lemma"])
    after = enricher.build(before, Fixture.candidate(kind))
    assert before == original
    assert after["full_text"] == Fixture.candidate().law.text
    assert after["full_text_lemma"] == "lemma"
    assert after["full_text_version_code"] == f"{kind.value}-law-94-1"
    for key in original:
        assert after[key] == original[key]
    metadata = after["source_metadata"]
    assert isinstance(metadata, list)
    source = SourceMetadata.model_validate(metadata[0])
    assert source.source is SourceName.STATUTE
    assert source.sha256 == "b" * 64


@pytest.mark.parametrize("old", [None, "", " \n"])
def test_only_fills_absent_or_blank_text(old: str | None) -> None:
    before = Fixture.before()
    before["full_text"] = old
    assert StatuteTextEnricher(StatuteTextSettings(), lambda texts: ["lemma"]).build(
        before, Fixture.candidate()
    )["full_text"]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("full_text", "Existing richer draft text"),
        ("full_text", 3),
        ("full_text_lemma", "unassessed"),
        ("full_text_version_code", "ih"),
        ("source_metadata", "invalid"),
        ("source_package_ids", "invalid"),
        ("source_urls", "invalid"),
        ("laws", []),
        ("text_versions", []),
        ("congress", 95),
        ("number", 2),
    ],
)
def test_refuses_changed_evidence_or_unassessed_existing_content(
    field: str, value: JsonValue
) -> None:
    before = Fixture.before()
    before[field] = value
    with pytest.raises((ValueError, ValidationError)):
        StatuteTextEnricher(StatuteTextSettings(), lambda texts: ["lemma"]).build(
            before, Fixture.candidate()
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("bill_references", ["/us/bill/94/hr/2"]),
        ("first_page", "4"),
        ("volume", 89),
        ("source_url", "https://example.com/STATUTE-90.xml"),
        ("text", " \n"),
    ],
)
def test_refuses_disagreement_between_staged_law_and_indexed_reference(
    field: str, value: str | int | list[str]
) -> None:
    raw = Fixture.candidate().model_dump(mode="json")
    raw["law"][field] = value
    candidate = VerifiedStatuteText.model_validate(raw)
    with pytest.raises(ValueError):
        StatuteTextEnricher(StatuteTextSettings(), lambda texts: ["lemma"]).build(
            Fixture.before(), candidate
        )


def test_preserves_existing_provenance_and_refuses_a_second_publication() -> None:
    before = Fixture.before()
    previous: JsonObject = {"source": "congress.gov_api", "package_id": "original"}
    before["source_metadata"] = previous
    before["source_package_ids"] = ["original"]
    before["source_urls"] = ["https://www.congress.gov/original"]
    enricher = StatuteTextEnricher(StatuteTextSettings(), lambda texts: ["lemma"])
    after = enricher.build(before, Fixture.candidate())
    metadata = after["source_metadata"]
    assert isinstance(metadata, list) and metadata[0] == previous
    assert after["source_package_ids"] == ["original", "STATUTE-90-Pg3"]
    with pytest.raises(ValueError, match="must be preserved"):
        enricher.build(after, Fixture.candidate())


@pytest.mark.parametrize("lemmas", [[], [""], ["a", "b"]])
def test_refuses_invalid_search_projection(lemmas: list[str]) -> None:
    with pytest.raises(ValueError, match="text lemma"):
        StatuteTextEnricher(StatuteTextSettings(), lambda texts: lemmas).build(
            Fixture.before(), Fixture.candidate()
        )
