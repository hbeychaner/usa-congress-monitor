import hashlib
from pathlib import Path

import pytest
from pydantic import AnyHttpUrl
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from cdm.config.statute_recovery import StatuteRecoverySettings
from cdm.ingest.statutes import StatuteIdentity, StatuteLawKind
from cdm.ingest.statutes_evidence import (
    CongressionalLawEvidence,
    SealedStatuteFile,
    StatuteCitationReader,
    StatuteMetadataLaw,
    StatuteMetadataReader,
    StatuteMetadataRejection,
    StatuteOcrPage,
    StatuteOcrWitness,
    StatutePdfReader,
)
from cdm.utils.json_types import JsonObject


class Fixture:
    @staticmethod
    def seal(path: Path, url: str) -> SealedStatuteFile:
        return SealedStatuteFile(
            path=path,
            url=AnyHttpUrl(url),
            sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        )

    @staticmethod
    def metadata(
        tmp_path: Path, *, replacement: tuple[str, str] | None = None
    ) -> SealedStatuteFile:
        content = """
        <mods xmlns="http://www.loc.gov/mods/v3" xmlns:xlink="http://www.w3.org/1999/xlink">
          <extension><collectionCode>STATUTE</collectionCode><accessId>STATUTE-90</accessId></extension>
          <relatedItem type="constituent" xlink:href="https://www.govinfo.gov/metadata/granule/STATUTE-90/STATUTE-90-Pg3/mods.xml">
            <titleInfo><title>An Act</title></titleInfo>
            <identifier type="Statute citation">90 Stat. 3</identifier>
            <identifier type="public law citation">Public Law 94-1</identifier>
            <part><extent><start>3</start><end>3</end></extent></part>
            <relatedItem type="otherFormat" xlink:href="https://www.govinfo.gov/content/pkg/STATUTE-90/pdf/STATUTE-90-Pg3.pdf"/>
            <extension><granuleClass>PUBLICLAW</granuleClass><accessId>STATUTE-90-Pg3</accessId>
              <congress>94</congress><number>1</number><volume>90</volume><totalPages>1</totalPages>
              <granuleDate>1976-01-28</granuleDate>
              <law congress="94" isPrivate="false" number="1"/>
              <bill congress="94" number="1" priority="primary" type="HR"/>
              <bill congress="94" number="2" priority="secondary" type="S"/>
            </extension>
          </relatedItem>
        </mods>
        """
        if replacement is not None:
            content = content.replace(*replacement)
        path = tmp_path / "source.mods.xml"
        path.write_text(content)
        return Fixture.seal(
            path, "https://www.govinfo.gov/metadata/pkg/STATUTE-90/mods.xml"
        )

    @staticmethod
    def law(tmp_path: Path) -> StatuteMetadataLaw:
        records = list(
            StatuteMetadataReader(StatuteRecoverySettings()).scan(
                Fixture.metadata(tmp_path), 90
            )
        )
        assert len(records) == 1 and isinstance(records[0], StatuteMetadataLaw)
        return records[0]

    @staticmethod
    def pdf(tmp_path: Path, text: str, *, complete: bool = True) -> SealedStatuteFile:
        if complete:
            text = text.replace("PUBLIC LAW 94-1", "PUBLIC LAW 94-1 94th Congress")
        writer = PdfWriter()
        page = writer.add_blank_page(width=612, height=792)
        page[NameObject("/Resources")] = DictionaryObject(
            {
                NameObject("/Font"): DictionaryObject(
                    {
                        NameObject("/F1"): DictionaryObject(
                            {
                                NameObject("/Type"): NameObject("/Font"),
                                NameObject("/Subtype"): NameObject("/Type1"),
                                NameObject("/BaseFont"): NameObject("/Helvetica"),
                            }
                        ),
                    }
                ),
            }
        )
        stream = DecodedStreamObject()
        stream.set_data(f"BT /F1 10 Tf 20 760 Td ({text}) Tj ET".encode("ascii"))
        page[NameObject("/Contents")] = stream
        path = tmp_path / "source.pdf"
        writer.write(path)
        return Fixture.seal(
            path,
            "https://www.govinfo.gov/content/pkg/STATUTE-90/pdf/STATUTE-90-Pg3.pdf",
        )

    @staticmethod
    def ocr(
        source: SealedStatuteFile, text: str, *, page_number: int = 1
    ) -> StatuteOcrWitness:
        image = source.path.with_suffix(".png")
        image.write_bytes(b"fixture rendered facsimile")
        return StatuteOcrWitness(
            source=source,
            engine="fixture-local-ocr",
            program_sha256="a" * 64,
            pages=[
                StatuteOcrPage(
                    page_number=page_number,
                    image=image,
                    image_sha256=hashlib.sha256(image.read_bytes()).hexdigest(),
                    text=text,
                )
            ],
        )


def test_metadata_requires_primary_not_secondary_bill(tmp_path: Path) -> None:
    law = Fixture.law(tmp_path)
    assert law.bill_id == "bill:94:hr:1"
    assert law.identity.number == 1
    assert law.first_page == "3" and law.source_volume == 90
    assert law.metadata_volume == 90


@pytest.mark.parametrize(
    "replacement",
    [
        ('priority="secondary"', 'priority="primary"'),
        ('priority="primary"', 'priority="secondary"'),
        ('isPrivate="false"', 'isPrivate="true"'),
        ("Public Law 94-1", "Public Law 94-2"),
        ('congress="94" number="1" priority', 'congress="95" number="1" priority'),
        ("<totalPages>1</totalPages>", "<totalPages>0</totalPages>"),
        ("https://www.govinfo.gov/content/pkg/STATUTE-90/pdf/", "https://example.com/"),
    ],
)
def test_metadata_conflicts_are_explicit_rejections(
    tmp_path: Path, replacement: tuple[str, str]
) -> None:
    records = list(
        StatuteMetadataReader(StatuteRecoverySettings()).scan(
            Fixture.metadata(tmp_path, replacement=replacement), 90
        )
    )
    assert len(records) == 1 and isinstance(records[0], StatuteMetadataRejection)
    assert records[0].error and len(records[0].component_sha256) == 64


def test_metadata_preserves_original_package_of_a_reprint(tmp_path: Path) -> None:
    source = Fixture.metadata(tmp_path)
    source.path.write_text(
        source.path.read_text()
        .replace("STATUTE-90-Pg3", "STATUTE-84-Pg3")
        .replace("<volume>90</volume>", "<volume>84</volume>")
        .replace("90 Stat. 3", "84 Stat. 3")
    )
    source = Fixture.seal(source.path, str(source.url))
    records = list(StatuteMetadataReader(StatuteRecoverySettings()).scan(source, 90))
    assert isinstance(records[0], StatuteMetadataLaw)
    assert records[0].source_volume == 90 and records[0].metadata_volume == 90
    assert records[0].citation_volume == 84


def test_pdf_corroborates_law_primary_bill_and_page_and_preserves_text(
    tmp_path: Path,
) -> None:
    text = "90 STAT. 3 PUBLIC LAW 94-1 H.R. 1 An Act."
    pdf = StatutePdfReader(StatuteRecoverySettings()).read(
        Fixture.pdf(tmp_path, text), Fixture.law(tmp_path)
    )
    assert pdf.text == "PUBLIC LAW 94-1 94th Congress H.R. 1 An Act."
    assert pdf.pages == 1


@pytest.mark.parametrize(
    ("congress", "ordinal"),
    [(101, "101st"), (102, "102nd"), (102, "102d"), (103, "103rd"),
     (103, "103d"), (104, "104th")],
)
def test_historical_congress_headings_preserve_law_boundaries(
    congress: int, ordinal: str,
) -> None:
    identity = StatuteIdentity(
        kind=StatuteLawKind.PUBLIC, congress=congress, number=1
    )
    text = (
        f"Public Law {congress}-1 {ordinal} Congress Selected law. "
        f"Public Law {congress}-2 {ordinal} Congress Adjacent law."
    )
    headings, selected = StatutePdfReader(
        StatuteRecoverySettings()
    ).selected_heading(text, identity)
    assert len(headings) == 2 and len(selected) == 1
    assert text[selected[0].start():headings[1].start()].strip().endswith(
        "Selected law."
    )


def test_law_heading_rejects_mismatched_congress() -> None:
    identity = StatuteIdentity(kind=StatuteLawKind.PUBLIC, congress=103, number=1)
    headings, selected = StatutePdfReader(
        StatuteRecoverySettings()
    ).selected_heading("Public Law 103-1 102nd Congress An Act.", identity)
    assert not headings and not selected


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("90 STAT. 3 PUBLIC LAW 94-2 H.R. 1", "complete enacted-law"),
        ("90 STAT. 3 PRIVATE LAW 94-1 H.R. 1", "complete enacted-law"),
        ("90 STAT. 3 PUBLIC LAW 94-1 S. 2", "primary bill"),
        ("90 STAT. 4 PUBLIC LAW 94-1 H.R. 1", "citation"),
        ("", "no extractable text"),
    ],
)
def test_pdf_never_accepts_unverified_identity_or_empty_pages(
    tmp_path: Path, text: str, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        StatutePdfReader(StatuteRecoverySettings()).read(
            Fixture.pdf(tmp_path, text), Fixture.law(tmp_path)
        )


def test_pdf_checks_page_counts_and_source_seals(tmp_path: Path) -> None:
    source = Fixture.pdf(tmp_path, "90 STAT. 3 PUBLIC LAW 94-1 H.R. 1")
    law = Fixture.law(tmp_path)
    with pytest.raises(ValueError, match="page count"):
        StatutePdfReader(StatuteRecoverySettings()).read(
            source, law.model_copy(update={"total_pages": 2})
        )
    source.path.write_bytes(source.path.read_bytes() + b"\nchanged")
    with pytest.raises(ValueError, match="changed"):
        StatutePdfReader(StatuteRecoverySettings()).read(source, law)


def test_pdf_excludes_adjacent_laws_on_shared_facsimile_pages(tmp_path: Path) -> None:
    source = Fixture.pdf(
        tmp_path,
        "90 STAT. 3 Private Law 94-8 94th Congress EARLIER. "
        "PUBLIC LAW 94-1 H.R. 1 TARGET. Public Law 94-2 94th Congress NEXT.",
    )
    pdf = StatutePdfReader(StatuteRecoverySettings()).read(
        source, Fixture.law(tmp_path)
    )
    assert "TARGET" in pdf.text and "EARLIER" not in pdf.text and "NEXT" not in pdf.text


def test_pdf_rejects_a_granule_starting_mid_act(tmp_path: Path) -> None:
    source = Fixture.pdf(
        tmp_path,
        "90 STAT. 3 PUBLIC LAW 94-1--JAN. 28, 1976 H.R. 1 Section 12.",
        complete=False,
    )
    with pytest.raises(ValueError, match="partial granule"):
        StatutePdfReader(StatuteRecoverySettings()).read(source, Fixture.law(tmp_path))


@pytest.mark.parametrize("text", ["Public law 94-1.", "Public Law No: 94-1"])
def test_captured_congress_law_action_is_exact_independent_primary_evidence(
    tmp_path: Path, text: str
) -> None:
    evidence = CongressionalLawEvidence.model_validate(
        {
            "id": "bill:94:hr:1",
            "source_type": "bill",
            "congress": 94,
            "number": 1,
            "type": "HR",
            "latest_action": {"text": text},
        }
    )
    assert evidence.confirms(Fixture.law(tmp_path))
    assert not evidence.confirms(
        Fixture.law(tmp_path).model_copy(update={"bill_id": "bill:94:s:1"})
    )


def test_publisher_bill_typo_requires_independent_captured_congress_evidence(
    tmp_path: Path,
) -> None:
    source = Fixture.pdf(tmp_path, "90 STAT. 3 PUBLIC LAW 94-1 H.R. 2")
    law = Fixture.law(tmp_path)
    evidence: JsonObject = {
        "id": "bill:94:hr:1",
        "source_type": "bill",
        "congress": 94,
        "number": 1,
        "type": "HR",
        "latest_action": {"text": "Public law 94-1."},
    }
    recovered = StatutePdfReader(StatuteRecoverySettings()).read(
        source, law, indexed_source=evidence
    )
    assert recovered.primary_bill_verified_by == "congress_law_action_and_mods"
    assert recovered.congressional_evidence_sha256
    with pytest.raises(ValueError, match="primary bill"):
        StatutePdfReader(StatuteRecoverySettings()).read(
            source,
            law,
            indexed_source={
                **evidence,
                "latest_action": {"text": "Public law 94-2."},
            },
        )


def test_code_citation_witness_requires_matching_identity_and_page(
    tmp_path: Path,
) -> None:
    path = tmp_path / "citation.htm"
    path.write_text(
        "<html><p>Pub. L. 94-1, \u00a71, January 28, 1976, 90 Stat. 3, provided that</p></html>"
    )
    source = Fixture.seal(
        path,
        "https://www.govinfo.gov/content/pkg/USCODE-2024-title15/html/USCODE-2024-title15-chap47-sec2051.htm",
    )
    reader = StatuteCitationReader(StatuteRecoverySettings())
    witness = reader.read(source, Fixture.law(tmp_path).identity, 90, "3")
    assert witness.first_page == "3" and witness.quotation
    with pytest.raises(ValueError, match="not found"):
        reader.read(source, Fixture.law(tmp_path).identity, 90, "4")


def test_full_facsimile_ocr_recovers_only_the_selected_damaged_law(
    tmp_path: Path,
) -> None:
    source = Fixture.pdf(tmp_path, "Damaged native opening.", complete=False)
    witness = Fixture.ocr(
        source,
        "90 STAT. 3 PUBLIC LAW 94-1 94th Congress H.R. 1 TARGET. "
        "Public Law 94-2 94th Congress NEIGHBOR.",
    )
    recovered = StatutePdfReader(StatuteRecoverySettings()).read(
        source, Fixture.law(tmp_path), witness
    )
    assert recovered.text_extracted_by == "facsimile_ocr"
    assert "TARGET" in recovered.text and "NEIGHBOR" not in recovered.text
    assert recovered.ocr_witness == witness


def test_damaged_opening_requires_ocr_for_every_pdf_page(tmp_path: Path) -> None:
    source = Fixture.pdf(tmp_path, "Damaged native opening.", complete=False)
    witness = Fixture.ocr(
        source, "90 STAT. 3 PUBLIC LAW 94-1 94th Congress H.R. 1", page_number=2
    )
    with pytest.raises(ValueError, match="Full-PDF OCR"):
        StatutePdfReader(StatuteRecoverySettings()).read(
            source, Fixture.law(tmp_path), witness
        )


def test_ocr_rejects_changed_images_and_different_source_pdf(tmp_path: Path) -> None:
    source = Fixture.pdf(tmp_path, "90 STAT. 3 PUBLIC LAW 94-1 H.R. 1")
    witness = Fixture.ocr(source, "verified facsimile")
    with pytest.raises(ValueError, match="different source PDF"):
        witness.verify(
            source.model_copy(
                update={
                    "url": AnyHttpUrl(
                        "https://www.govinfo.gov/content/pkg/STATUTE-90/pdf/STATUTE-90-Pg4.pdf"
                    )
                }
            )
        )
    witness.pages[0].image.write_bytes(b"changed")
    with pytest.raises(ValueError, match="image seal"):
        witness.verify(source)
