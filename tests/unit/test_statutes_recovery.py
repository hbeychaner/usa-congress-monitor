from pathlib import Path

import pytest
from pydantic import AnyHttpUrl
from test_statutes_evidence import Fixture

from cdm.config.statute_recovery import StatuteRecoverySettings
from cdm.ingest.statute_text import LawTextProjector
from cdm.ingest.statutes import StatuteLaw
from cdm.ingest.statutes_evidence import StatuteCitationReader, StatutePdfReader
from cdm.ingest.statutes_recovery import RecoveredStatuteText, StatuteRecoveryEnricher
from cdm.utils.json_types import JsonObject, JsonValue


class RecoveryFixture:
    @staticmethod
    def recovered(tmp_path: Path) -> RecoveredStatuteText:
        meta = Fixture.law(tmp_path)
        source = Fixture.pdf(tmp_path, "90 STAT. 3 PUBLIC LAW 94-1 H.R. 1 An Act.")
        pdf = StatutePdfReader(StatuteRecoverySettings()).read(source, meta)
        return RecoveredStatuteText(
            metadata=meta,
            source=source,
            pdf=pdf,
            xml_differences=["source_xml_bill_reference_conflicts"],
        )

    @staticmethod
    def before() -> JsonObject:
        return {
            "id": "bill:94:hr:1",
            "source_type": "bill",
            "type": "HR",
            "congress": 94,
            "number": 1,
            "laws": [],
            "text_versions": [],
            "hydration_status": "unknown",
            "analysis": {"topics": ["unchanged"]},
        }

    @staticmethod
    def enricher() -> StatuteRecoveryEnricher:
        return StatuteRecoveryEnricher(
            StatuteRecoverySettings(),
            LawTextProjector(lambda texts: ["lemma"]),
        )


def test_recovery_adds_only_corroborated_metadata_without_claiming_hydration(
    tmp_path: Path,
) -> None:
    before = RecoveryFixture.before()
    after = RecoveryFixture.enricher().build(
        before, RecoveryFixture.recovered(tmp_path)
    )
    assert before["laws"] == [] and before["text_versions"] == []
    assert after["laws"] == [{"number": "94-1", "law_type": "Public Law"}]
    assert after["full_text_version_code"] == "public-law-94-1"
    assert after["analysis"] == before["analysis"]
    assert after["hydration_status"] == "unknown"
    metadata = after["source_metadata"]
    assert isinstance(metadata, list) and isinstance(metadata[0], dict)
    assert metadata[0]["text_format"] == "publisher_pdf_text_layer"
    assert metadata[0]["xml_differences"] == ["source_xml_bill_reference_conflicts"]
    assert metadata[0]["metadata_sha256"]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("full_text", "Existing richer content"),
        ("full_text_version_code", "enr"),
        ("full_text_version_rank", 3),
        ("laws", [{"number": "94-2", "law_type": "Public Law"}]),
        ("text_versions", {"count": 1, "url": "https://www.congress.gov/unknown"}),
    ],
)
def test_recovery_preserves_conflicting_or_unassessed_existing_data(
    tmp_path: Path, field: str, value: JsonValue
) -> None:
    before = RecoveryFixture.before()
    before[field] = value
    with pytest.raises(ValueError):
        RecoveryFixture.enricher().build(before, RecoveryFixture.recovered(tmp_path))


def test_recovery_preserves_existing_law_and_pdf_details(tmp_path: Path) -> None:
    row = RecoveryFixture.recovered(tmp_path)
    before = RecoveryFixture.before()
    before["laws"] = [
        {"number": "94-1", "law_type": "Public Law", "extra": "preserved"}
    ]
    before["text_versions"] = [
        {
            "type": "Public Law",
            "extra": "preserved",
            "formats": [{"type": "PDF", "url": str(row.metadata.pdf_url)}],
        }
    ]
    after = RecoveryFixture.enricher().build(before, row)
    assert after["laws"] == before["laws"]
    assert after["text_versions"] == before["text_versions"]


def test_recovery_refuses_to_pretend_conflicting_xml_was_verified(
    tmp_path: Path,
) -> None:
    row = RecoveryFixture.recovered(tmp_path).model_copy(update={"pdf": None})
    with pytest.raises(ValueError, match="disagree"):
        RecoveryFixture.enricher().build(RecoveryFixture.before(), row)


def test_independent_code_witness_preserves_the_partial_pdf_discrepancy(
    tmp_path: Path,
) -> None:
    metadata = Fixture.law(tmp_path).model_copy(update={"first_page": "4"})
    xml_path = tmp_path / "source.xml"
    xml_path.write_text("<law>Complete law text.</law>")
    source = Fixture.seal(
        xml_path, "https://www.govinfo.gov/bulkdata/STATUTE/90/STATUTE-90.xml"
    )
    citation_path = tmp_path / "citation.htm"
    citation_path.write_text(
        "<p>Pub. L. 94-1, \u00a71, January 28, 1976, 90 Stat. 3</p>"
    )
    witness = StatuteCitationReader(StatuteRecoverySettings()).read(
        Fixture.seal(
            citation_path,
            "https://www.govinfo.gov/content/pkg/USCODE-2024-title15/html/USCODE-2024-title15-chap47-sec2051.htm",
        ),
        metadata.identity,
        90,
        "3",
    )
    recovered = RecoveredStatuteText(
        metadata=metadata,
        source=source,
        xml=StatuteLaw(
            identity=metadata.identity,
            volume=90,
            first_page="3",
            source_volume=90,
            approved_date=metadata.approved_date,
            title="An Act",
            text="Complete law text.",
            source_url=AnyHttpUrl(str(source.url)),
            volume_sha256=source.sha256,
            component_sha256="b" * 64,
            bill_references=["/us/bill/94/hr/1"],
        ),
        xml_differences=["xml_citation"],
        citation_witness=witness,
    )
    after = RecoveryFixture.enricher().build(RecoveryFixture.before(), recovered)
    assert after["full_text"] == "Complete law text."
    provenance = after["source_metadata"]
    assert isinstance(provenance, list) and isinstance(provenance[0], dict)
    assert provenance[0]["first_page"] == "3"
    assert provenance[0]["metadata_first_page"] == "4"
    versions = after["text_versions"]
    assert isinstance(versions, list) and isinstance(versions[0], dict)
    formats = versions[0]["formats"]
    assert isinstance(formats, list) and isinstance(formats[0], dict)
    assert formats[0]["coverage"] == "partial"
    with pytest.raises(ValueError, match="disagree"):
        RecoveryFixture.enricher().build(
            RecoveryFixture.before(),
            recovered.model_copy(
                update={"xml_differences": ["xml_citation", "xml_bill_reference"]}
            ),
        )
