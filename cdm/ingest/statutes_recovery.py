"""Publish corroborated law text without rewriting conflicting source XML."""

from __future__ import annotations

from copy import deepcopy
from enum import StrEnum

from pydantic import BaseModel, TypeAdapter

from cdm.config.statute_recovery import StatuteRecoverySettings
from cdm.ingest.statute_text import (
    IndexedLaw,
    IndexedVersion,
    LawTextPayload,
    LawTextProjector,
    LawTextProvenance,
)
from cdm.ingest.statutes import StatuteLaw
from cdm.ingest.statutes_evidence import (
    CongressionalLawEvidence,
    PdfTextExtraction,
    SealedStatuteFile,
    StatuteCitationWitness,
    StatuteMetadataLaw,
    VerifiedStatutePdf,
)
from cdm.store.create_only import BillSourceIdentity
from cdm.utils.json_types import JsonObject


class StatuteTextFormat(StrEnum):
    XML = "uslm_xml"
    PDF = "publisher_pdf_text_layer"
    OCR = "on_device_facsimile_ocr"


class RecoveredStatuteText(BaseModel):
    metadata: StatuteMetadataLaw
    source: SealedStatuteFile
    xml: StatuteLaw | None = None
    pdf: VerifiedStatutePdf | None = None
    xml_differences: list[str]
    citation_witness: StatuteCitationWitness | None = None

    def content(self) -> tuple[str, StatuteTextFormat]:
        self.source.verify()
        meta = self.metadata
        if self.pdf is not None:
            if self.pdf.metadata != meta or self.pdf.source != self.source:
                raise ValueError(
                    "PDF verification differs from the publication evidence"
                )
            return self.pdf.text, (
                StatuteTextFormat.OCR
                if self.pdf.text_extracted_by is PdfTextExtraction.OCR
                else StatuteTextFormat.PDF
            )
        law = self.xml
        citation_confirmed = False
        if self.citation_witness is not None and law is not None:
            witness = self.citation_witness
            witness.source.verify()
            citation_confirmed = (
                witness.identity == law.identity
                and witness.volume == law.volume
                and witness.first_page == law.first_page
                and self.xml_differences == ["xml_citation"]
            )
        if (
            law is None
            or (self.xml_differences and not citation_confirmed)
            or law.identity != meta.identity
            or law.volume != meta.citation_volume
            or (law.first_page != meta.first_page and not citation_confirmed)
            or law.approved_date != meta.approved_date
            or f"/us/{meta.bill_id.replace(':', '/')}" not in law.bill_references
            or law.source_url != self.source.url
            or law.volume_sha256 != self.source.sha256
        ):
            raise ValueError(
                "XML and independent primary-bill/citation metadata disagree"
            )
        return law.text, StatuteTextFormat.XML


class RecoveredStatuteProvenance(LawTextProvenance):
    text_format: StatuteTextFormat
    metadata_url: str
    metadata_sha256: str
    metadata_component_sha256: str
    metadata_volume: int
    xml_component_sha256: str | None
    xml_differences: list[str]
    metadata_first_page: str
    citation_witness: StatuteCitationWitness | None
    ocr_program_sha256: str | None
    ocr_image_sha256s: list[str]
    primary_bill_verified_by: str
    congressional_evidence_sha256: str | None


class StatuteRecoveryEnricher:
    def __init__(
        self, settings: StatuteRecoverySettings, projector: LawTextProjector
    ) -> None:
        self.settings = settings
        self.projector = projector

    def build(self, before: JsonObject, recovered: RecoveredStatuteText) -> JsonObject:
        meta = recovered.metadata
        if BillSourceIdentity.model_validate(before).id != meta.bill_id:
            raise ValueError("Primary enacted bill and serving identity differ")
        content, kind = recovered.content()
        if (
            recovered.pdf is not None
            and recovered.pdf.congressional_evidence_sha256 is not None
            and not CongressionalLawEvidence.model_validate(before).confirms(meta)
        ):
            raise ValueError("Captured Congress law-association evidence changed")
        provenance = RecoveredStatuteProvenance(
            package_id=meta.granule_id,
            url=str(recovered.source.url),
            reference_url=str(meta.pdf_url),
            sha256=recovered.source.sha256,
            parser_version=self.settings.parser_version,
            law_kind=meta.identity.kind,
            congress=meta.identity.congress,
            law_number=meta.identity.number,
            citation_volume=meta.citation_volume,
            first_page=meta.first_page
            if recovered.citation_witness is None
            else recovered.citation_witness.first_page,
            source_volume=meta.source_volume,
            approved_date=meta.approved_date,
            text_format=kind,
            metadata_url=str(meta.package_metadata_url),
            metadata_sha256=meta.package_metadata_sha256,
            metadata_component_sha256=meta.component_sha256,
            metadata_volume=meta.metadata_volume,
            xml_component_sha256=None
            if recovered.xml is None
            else recovered.xml.component_sha256,
            xml_differences=recovered.xml_differences,
            metadata_first_page=meta.first_page,
            citation_witness=recovered.citation_witness,
            ocr_program_sha256=(
                recovered.pdf.ocr_witness.program_sha256
                if recovered.pdf is not None and recovered.pdf.ocr_witness is not None
                else None
            ),
            ocr_image_sha256s=(
                [page.image_sha256 for page in recovered.pdf.ocr_witness.pages]
                if recovered.pdf is not None and recovered.pdf.ocr_witness is not None
                else []
            ),
            primary_bill_verified_by=(
                recovered.pdf.primary_bill_verified_by.value
                if recovered.pdf is not None
                else "xml_and_mods"
            ),
            congressional_evidence_sha256=(
                recovered.pdf.congressional_evidence_sha256
                if recovered.pdf is not None
                else None
            ),
        )
        result = self.projector.build(
            before,
            LawTextPayload(
                bill_id=meta.bill_id,
                identity=meta.identity,
                text=content,
                provenance=provenance,
            ),
        )
        number = f"{meta.identity.congress}-{meta.identity.number}"
        label = f"{meta.identity.kind.value.title()} Law"
        raw_laws = before.get("laws")
        laws = (
            []
            if raw_laws is None
            else TypeAdapter(list[JsonObject]).validate_python(raw_laws)
        )
        existing = TypeAdapter(list[IndexedLaw]).validate_python(laws)
        if any(row.number != number or row.law_type.value != label for row in existing):
            raise ValueError(
                "Indexed law evidence disagrees with official primary bill"
            )
        if not existing:
            result["laws"] = [{"number": number, "law_type": label}]
        raw_versions = before.get("text_versions")
        versions = (
            []
            if raw_versions is None
            else TypeAdapter(list[JsonObject]).validate_python(raw_versions)
        )
        indexed = TypeAdapter(list[IndexedVersion]).validate_python(versions)
        if not any(
            version.type == label
            and any(
                fmt.url.rsplit("/", 1)[-1] == f"{meta.granule_id}.pdf"
                for fmt in version.formats
            )
            for version in indexed
        ):
            result["text_versions"] = deepcopy(versions) + [
                {
                    "type": label,
                    "date": meta.approved_date.isoformat(),
                    "formats": [
                        {
                            "type": "PDF",
                            "url": str(meta.pdf_url),
                            **(
                                {"coverage": "partial"}
                                if recovered.citation_witness is not None
                                else {}
                            ),
                        }
                    ],
                }
            ]
        return result
