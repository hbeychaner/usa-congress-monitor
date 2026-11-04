"""Independent official volume metadata and PDF text corroboration."""

from __future__ import annotations

import hashlib
import re
import xml.etree.ElementTree as ET
from collections.abc import Iterator
from datetime import date
from enum import StrEnum
from pathlib import Path

from bs4 import BeautifulSoup
from pydantic import AnyHttpUrl, BaseModel, Field
from pypdf import PdfReader

from cdm.config.statute_recovery import StatuteRecoverySettings
from cdm.ingest.statute_text import IndexedLaw
from cdm.ingest.statutes import StatuteIdentity, StatuteLawKind
from cdm.store.create_only import BillId, BillSourceIdentity, MeasureType, SourceDigest
from cdm.utils.json_types import JsonObject


class CongressionalAction(BaseModel):
    text: str | None = None


class CongressionalLawEvidence(BillSourceIdentity):
    laws: list[IndexedLaw] | None = None
    latest_action: CongressionalAction | None = None

    def confirms(self, law: StatuteMetadataLaw) -> bool:
        if self.id != law.bill_id or self.congress != law.identity.congress:
            return False
        number = f"{law.identity.congress}-{law.identity.number}"
        label = f"{law.identity.kind.value.title()} Law"
        if any(
            row.number == number and row.law_type.value == label
            for row in self.laws or []
        ):
            return True
        action = None if self.latest_action is None else self.latest_action.text
        return (
            action is not None
            and re.fullmatch(
                rf"{law.identity.kind.value}\s+law(?:\s+no:?)?\s+"
                rf"{law.identity.congress}[-\u2013\u2014]{law.identity.number}\.?",
                action.strip(),
                re.IGNORECASE,
            )
            is not None
        )


class SealedStatuteFile(BaseModel):
    path: Path
    url: AnyHttpUrl
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")

    def verify(self) -> None:
        if self.path.is_symlink() or not self.path.is_file():
            raise ValueError(f"Sealed source is missing or a symlink: {self.path}")
        with self.path.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        if digest != self.sha256:
            raise ValueError(f"Sealed source changed: {self.path}")


class StatuteMetadataLaw(BaseModel):
    identity: StatuteIdentity
    bill_id: BillId
    source_volume: int = Field(gt=0)
    metadata_volume: int = Field(gt=0)
    citation_volume: int = Field(gt=0)
    first_page: str
    last_page: str
    total_pages: int = Field(gt=0)
    title: str = Field(min_length=1)
    approved_date: date
    granule_id: str
    pdf_url: AnyHttpUrl
    metadata_url: AnyHttpUrl
    package_metadata_url: AnyHttpUrl
    package_metadata_sha256: str
    component_sha256: str


class StatuteMetadataRejection(BaseModel):
    granule_id: str | None
    component_sha256: str
    error: str


class StatuteMetadataReader:
    def __init__(self, settings: StatuteRecoverySettings) -> None:
        self.settings = settings
        self.citation = re.compile(settings.citation_pattern)
        self.law_citation = re.compile(settings.law_pattern)

    def tag(self, local: str) -> str:
        return f"{{{self.settings.mods_namespace}}}{local}"

    def required(self, element: ET.Element, path: str) -> str:
        value = element.findtext("/".join(self.tag(part) for part in path.split("/")))
        if value is None or not value.strip():
            raise ValueError(f"Missing MODS field: {path}")
        return value.strip()

    def law(
        self, element: ET.Element, source: SealedStatuteFile, volume: int
    ) -> StatuteMetadataLaw:
        extension = element.find(self.tag("extension"))
        if extension is None:
            raise ValueError("Missing granule extension")
        kind = {
            "PUBLICLAW": StatuteLawKind.PUBLIC,
            "PRIVATELAW": StatuteLawKind.PRIVATE,
        }[self.required(extension, "granuleClass")]
        identity = StatuteIdentity(
            kind=kind,
            congress=int(self.required(extension, "congress")),
            number=int(self.required(extension, "number")),
        )
        laws = extension.findall(self.tag("law"))
        if len(laws) != 1 or laws[0].attrib != {
            "congress": str(identity.congress),
            "isPrivate": str(kind is StatuteLawKind.PRIVATE).lower(),
            "number": str(identity.number),
        }:
            raise ValueError("MODS law identity disagrees with granule metadata")
        primary = [
            bill
            for bill in extension.findall(self.tag("bill"))
            if bill.get("priority") == "primary"
        ]
        if len(primary) != 1:
            raise ValueError(
                "Expected one primary enacted bill, not secondary references"
            )
        bill = primary[0]
        measure = MeasureType(bill.attrib["type"].lower())
        bill_congress = int(bill.attrib["congress"])
        bill_number = int(bill.attrib["number"])
        if bill_congress != identity.congress or bill_number < 1:
            raise ValueError("Primary bill and law congress differ")
        citations: set[tuple[int, str]] = set()
        law_citations: set[tuple[StatuteLawKind, int, int]] = set()
        for item in element.findall(self.tag("identifier")):
            value = (item.text or "").strip().replace("\u2013", "-")
            if item.get("type") == "Statute citation":
                match = self.citation.fullmatch(value)
                if match is None:
                    raise ValueError("Invalid MODS Statute citation")
                citations.add((int(match["volume"]), match["page"]))
            if item.get("type") in ("public law citation", "private law citation"):
                match = self.law_citation.fullmatch(value)
                if match is None:
                    raise ValueError("Invalid MODS law citation")
                law_citations.add(
                    (
                        StatuteLawKind(match["kind"].lower()),
                        int(match["congress"]),
                        int(match["number"]),
                    )
                )
        if (
            law_citations != {(kind, identity.congress, identity.number)}
            or len(citations) != 1
        ):
            raise ValueError("Missing or conflicting independent MODS citations")
        citation_volume, page = next(iter(citations))
        granule = self.required(extension, "accessId")
        granule_match = re.fullmatch(r"STATUTE-(\d+)-Pg\d+(?:-\d+)?", granule)
        if granule_match is None:
            raise ValueError("Invalid Statutes granule identifier")
        source_volume = volume
        if (
            int(self.required(extension, "volume")) not in (volume, citation_volume)
            or str(source.url)
            != f"{self.settings.metadata_base}/pkg/STATUTE-{volume}/mods.xml"
        ):
            raise ValueError("Wrong official MODS package/volume")
        metadata_url = f"{self.settings.metadata_base}/granule/STATUTE-{source_volume}/{granule}/mods.xml"
        if element.get(f"{{{self.settings.xlink_namespace}}}href") != metadata_url:
            raise ValueError("Granule metadata URL differs")
        pdf_url = (
            f"{self.settings.content_base}/STATUTE-{source_volume}/pdf/{granule}.pdf"
        )
        if not any(
            item.get("type") == "otherFormat"
            and item.get(f"{{{self.settings.xlink_namespace}}}href") == pdf_url
            for item in element.findall(self.tag("relatedItem"))
        ):
            raise ValueError("Missing official granule PDF URL")
        return StatuteMetadataLaw(
            identity=identity,
            bill_id=f"bill:{bill_congress}:{measure.value}:{bill_number}",
            source_volume=source_volume,
            metadata_volume=volume,
            citation_volume=citation_volume,
            first_page=page,
            last_page=self.required(element, "part/extent/end"),
            total_pages=int(self.required(extension, "totalPages")),
            title=self.required(element, "titleInfo/title"),
            approved_date=date.fromisoformat(self.required(extension, "granuleDate")),
            granule_id=granule,
            pdf_url=AnyHttpUrl(pdf_url),
            metadata_url=AnyHttpUrl(metadata_url),
            package_metadata_url=source.url,
            package_metadata_sha256=source.sha256,
            component_sha256=hashlib.sha256(ET.tostring(element)).hexdigest(),
        )

    def scan(
        self, source: SealedStatuteFile, volume: int
    ) -> Iterator[StatuteMetadataLaw | StatuteMetadataRejection]:
        source.verify()
        root = ET.parse(source.path).getroot()
        if root.tag != self.tag("mods"):
            raise ValueError("Wrong MODS root/namespace")
        if (
            self.required(root, "extension/collectionCode") != "STATUTE"
            or self.required(root, "extension/accessId") != f"STATUTE-{volume}"
        ):
            raise ValueError("Wrong Statutes metadata package")
        for element in root.findall(self.tag("relatedItem")):
            if element.get("type") != "constituent":
                continue
            extension = element.find(self.tag("extension"))
            kind = (
                None
                if extension is None
                else extension.findtext(self.tag("granuleClass"))
            )
            if kind not in ("PUBLICLAW", "PRIVATELAW"):
                continue
            try:
                yield self.law(element, source, volume)
            except (ValueError, KeyError) as error:
                yield StatuteMetadataRejection(
                    granule_id=None
                    if extension is None
                    else extension.findtext(self.tag("accessId")),
                    component_sha256=hashlib.sha256(ET.tostring(element)).hexdigest(),
                    error=str(error),
                )
        source.verify()


class StatuteOcrPage(BaseModel):
    page_number: int = Field(ge=1, le=1000)
    image: Path
    image_sha256: str
    text: str


class StatuteCitationWitness(BaseModel):
    source: SealedStatuteFile
    identity: StatuteIdentity
    volume: int
    first_page: str
    quotation: str


class StatuteCitationReader:
    def __init__(self, settings: StatuteRecoverySettings) -> None:
        self.settings = settings

    def read(
        self,
        source: SealedStatuteFile,
        identity: StatuteIdentity,
        volume: int,
        first_page: str,
    ) -> StatuteCitationWitness:
        source.verify()
        if not re.fullmatch(
            r"https://www\.govinfo\.gov/content/pkg/USCODE-\d{4}-title\d+/"
            r"html/USCODE-[A-Za-z0-9-]+\.htm",
            str(source.url),
        ):
            raise ValueError("Citation witness is not an official Code publication")
        text = BeautifulSoup(source.path.read_bytes(), "html.parser").get_text(
            " ", strip=True
        )
        match = re.search(
            rf"Pub\.\s*L\.\s*{identity.congress}[-\u2013\u2014]{identity.number},\s*"
            rf"\u00a7\s*1,\s*[A-Za-z]+\s+\d{{1,2}},\s*\d{{4}},\s*"
            rf"{volume}\s+Stat\.\s*{re.escape(first_page)}\b",
            text,
        )
        if match is None or identity.kind is not StatuteLawKind.PUBLIC:
            raise ValueError("Independent Code law/citation witness was not found")
        source.verify()
        return StatuteCitationWitness(
            source=source,
            identity=identity,
            volume=volume,
            first_page=first_page,
            quotation=match.group(),
        )


class StatuteOcrWitness(BaseModel):
    source: SealedStatuteFile
    engine: str
    program_sha256: str
    pages: list[StatuteOcrPage]

    def verify(self, source: SealedStatuteFile) -> str:
        self.source.verify()
        if self.source.sha256 != source.sha256 or self.source.url != source.url:
            raise ValueError("Facsimile OCR belongs to a different source PDF")
        if not self.pages or len({page.page_number for page in self.pages}) != len(
            self.pages
        ):
            raise ValueError("Missing or repeated facsimile OCR pages")
        for page in self.pages:
            with page.image.open("rb") as stream:
                digest = hashlib.file_digest(stream, "sha256").hexdigest()
            if digest != page.image_sha256:
                raise ValueError("Facsimile OCR image seal differs")
        return "\n".join(page.text for page in self.pages)


class PdfBillVerification(StrEnum):
    TEXT = "pdf_text"
    OCR = "facsimile_ocr"
    CONGRESS = "congress_law_action_and_mods"


class PdfTextExtraction(StrEnum):
    LAYER = "pdf_text_layer"
    OCR = "facsimile_ocr"


class VerifiedStatutePdf(BaseModel):
    source: SealedStatuteFile
    metadata: StatuteMetadataLaw
    text: str = Field(min_length=1)
    pages: int = Field(gt=0)
    ocr_witness: StatuteOcrWitness | None = None
    congressional_evidence_sha256: str | None = None
    primary_bill_verified_by: PdfBillVerification = PdfBillVerification.TEXT
    text_extracted_by: PdfTextExtraction = PdfTextExtraction.LAYER


class StatutePdfReader:
    def __init__(self, settings: StatuteRecoverySettings) -> None:
        self.settings = settings
        self.heading_pattern = re.compile(settings.body_heading_pattern, re.IGNORECASE)

    def selected_heading(
        self, text: str, identity: StatuteIdentity
    ) -> tuple[list[re.Match[str]], list[re.Match[str]]]:
        headings = list(self.heading_pattern.finditer(text))
        selected = [
            item
            for item in headings
            if item["kind"].lower() == identity.kind.value
            and int(item["congress"]) == identity.congress
            and int(item["number"]) == identity.number
        ]
        return headings, selected

    def read(
        self,
        source: SealedStatuteFile,
        metadata: StatuteMetadataLaw,
        witness: StatuteOcrWitness | None = None,
        indexed_source: JsonObject | None = None,
    ) -> VerifiedStatutePdf:
        source.verify()
        if (
            source.url != metadata.pdf_url
            or source.path.stat().st_size > self.settings.maximum_pdf_bytes
        ):
            raise ValueError("PDF URL or size differs from the verified bound")
        with source.path.open("rb") as stream:
            reader = PdfReader(stream, strict=True)
            pages = len(reader.pages)
            if pages != metadata.total_pages or pages > self.settings.maximum_pdf_pages:
                raise ValueError("PDF page count differs or exceeds the safe bound")
            texts: list[str] = []
            total = 0
            for page in reader.pages:
                text = page.extract_text()
                if not text.strip():
                    raise ValueError(
                        "A law PDF page has no extractable text; OCR is required"
                    )
                total += len(text)
                if total > self.settings.maximum_text_characters:
                    raise ValueError("PDF text exceeds the safe bound")
                texts.append(text)
        raw_text = "\n\n".join(texts)
        identity = metadata.identity
        extraction = PdfTextExtraction.LAYER
        main_headings, selected = self.selected_heading(raw_text, identity)
        if len(selected) != 1 and witness is not None:
            if {page.page_number for page in witness.pages} != set(range(1, pages + 1)):
                raise ValueError(
                    "Full-PDF OCR is required to recover a damaged law opening"
                )
            raw_text = witness.verify(source)
            main_headings, selected = self.selected_heading(raw_text, identity)
            extraction = PdfTextExtraction.OCR
        if len(selected) != 1:
            raise ValueError(
                "PDF lacks one complete enacted-law opening; it may be a partial granule"
            )
        beginning = selected[0].start()
        ending = next(
            (item.start() for item in main_headings if item.start() > beginning),
            len(raw_text),
        )
        content = raw_text[beginning:ending].strip()
        header_text = (
            texts[0][: self.settings.header_characters]
            + content[: self.settings.header_characters]
        )
        citation_header = " ".join((texts[0][:400] + header_text).split())
        if witness is not None:
            header_text = witness.verify(source)
            if any(page.page_number > pages for page in witness.pages):
                raise ValueError("Facsimile OCR page exceeds the source PDF")
            citation_header = " ".join(header_text.split())
        header = " ".join(header_text.split())
        if not re.search(
            rf"\b{identity.kind.value}\s+law\s*{identity.congress}\s*[-\u2013\u2014]\s*"
            rf"{identity.number}\b",
            header,
            re.IGNORECASE,
        ):
            raise ValueError(
                "PDF first-page law identity is not independently confirmed"
            )
        _, congress, measure, number = metadata.bill_id.split(":")
        pattern = self.settings.bill_patterns[MeasureType(measure)]
        primary_verified_by = (
            PdfBillVerification.TEXT if witness is None else PdfBillVerification.OCR
        )
        evidence_sha256 = None
        if int(congress) != identity.congress or not re.search(
            rf"\b{pattern}\s*{number}\b", header, re.IGNORECASE
        ):
            if indexed_source is None or not CongressionalLawEvidence.model_validate(
                indexed_source
            ).confirms(metadata):
                raise ValueError(
                    "PDF primary bill lacks matching facsimile or captured Congress law evidence"
                )
            primary_verified_by = PdfBillVerification.CONGRESS
            evidence_sha256 = SourceDigest.of(indexed_source)
        if not re.search(
            rf"\b{metadata.citation_volume}\s+STAT\.\s*"
            rf"{re.escape(metadata.first_page.split('-')[0])}\b",
            citation_header,
            re.IGNORECASE,
        ):
            raise ValueError("PDF first-page Statutes citation is not confirmed")
        source.verify()
        return VerifiedStatutePdf(
            source=source,
            metadata=metadata,
            text=content,
            pages=pages,
            ocr_witness=witness,
            congressional_evidence_sha256=evidence_sha256,
            primary_bill_verified_by=primary_verified_by,
            text_extracted_by=extraction,
        )
