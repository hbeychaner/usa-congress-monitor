"""Stream individual enacted laws from sealed official Statutes volumes."""

from __future__ import annotations

import hashlib
import re
import xml.etree.ElementTree as ET
from collections.abc import Iterator
from datetime import date
from enum import StrEnum
from pathlib import Path

from pydantic import AnyHttpUrl, BaseModel, Field

from cdm.config.statutes import StatutesSettings


class StatuteLawKind(StrEnum):
    PUBLIC = "public"
    PRIVATE = "private"


class StatuteIdentity(BaseModel):
    kind: StatuteLawKind
    congress: int = Field(gt=0)
    number: int = Field(gt=0)


class StatuteVolume(BaseModel):
    path: Path
    volume: int = Field(gt=0)
    congress: int = Field(gt=0)
    session: int = Field(ge=1, le=2)
    source_url: AnyHttpUrl
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")

    def verify(self) -> None:
        if self.path.is_symlink() or not self.path.is_file():
            raise StatutesParseError("Statutes volume is missing or is a symlink")
        with self.path.open("rb") as source:
            actual = hashlib.file_digest(source, "sha256").hexdigest()
        if actual != self.sha256:
            raise StatutesParseError("Sealed Statutes volume checksum differs")


class StatuteLaw(BaseModel):
    identity: StatuteIdentity
    volume: int = Field(gt=0)
    first_page: str = Field(pattern=r"^\d+(?:-\d+)?$")
    source_volume: int = Field(gt=0)
    session: int | None = Field(default=None, ge=1, le=2)
    approved_date: date
    title: str = Field(min_length=1)
    text: str = Field(min_length=1)
    source_url: AnyHttpUrl
    volume_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    component_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    bill_references: list[str] = Field(default_factory=list)


class StatutesParseError(ValueError):
    """Official XML does not match the sealed source contract."""


class StatuteRejectedLaw(BaseModel):
    source_volume: int = Field(gt=0)
    source_url: AnyHttpUrl
    component_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    congress_raw: str | None
    number_raw: str | None
    kind_raw: str | None
    error: str


class StatutesReader:
    def __init__(self, settings: StatutesSettings) -> None:
        self.settings = settings
        self.citation_pattern = re.compile(settings.citation_pattern)
        self.law_citation_pattern = re.compile(settings.law_citation_pattern)
        self.page_pattern = re.compile(settings.page_identifier_pattern)

    def tag(self, name: str) -> str:
        return f"{{{self.settings.namespace}}}{name}"

    def required(self, parent: ET.Element, name: str) -> str:
        value = parent.findtext(self.tag(name))
        if value is None or not value.strip():
            raise StatutesParseError(f"Missing Statutes metadata: {name}")
        return value.strip()

    def text(self, element: ET.Element) -> str:
        pieces = [element.text or ""]
        for child in element:
            block = child.tag.rsplit("}", 1)[-1] in self.settings.block_elements
            if block:
                pieces.append("\n")
            pieces.append(self.text(child))
            if block:
                pieces.append("\n")
            pieces.append(child.tail or "")
        return "".join(pieces)

    def law(self, element: ET.Element, volume: StatuteVolume) -> StatuteLaw:
        meta = element.find(self.tag("meta"))
        main = element.find(self.tag("main"))
        if meta is None or main is None:
            raise StatutesParseError("Enacted law lacks metadata or main text")
        congress = int(self.required(meta, "congress"))
        identity = StatuteIdentity(
            kind=StatuteLawKind(self.required(meta, "publicPrivate")),
            congress=congress,
            number=int(self.required(meta, "docNumber")),
        )
        raw_session = meta.findtext(self.tag("session"))
        session = (
            int(raw_session)
            if raw_session is not None and raw_session.strip()
            else None
        )
        citations: set[tuple[int, str]] = set()
        identity_citations: set[tuple[StatuteLawKind, int, int]] = set()
        for citation in meta.findall(self.tag("citableAs")):
            value = (citation.text or "").strip().replace("\u2013", "-")
            law_match = self.law_citation_pattern.fullmatch(value)
            if law_match is not None:
                identity_citations.add(
                    (
                        StatuteLawKind(law_match["kind"].lower()),
                        int(law_match["congress"]),
                        int(law_match["number"]),
                    )
                )
            match = self.citation_pattern.fullmatch(value)
            if match is not None:
                citations.add((int(match["volume"]), match["page"]))
        if identity_citations != {(identity.kind, identity.congress, identity.number)}:
            raise StatutesParseError("Missing or conflicting enacted-law identity")
        preface = element.find(self.tag("preface"))
        if preface is not None:
            page = preface.find(self.tag("page"))
            if page is not None:
                match = self.page_pattern.fullmatch(page.get("identifier", ""))
                if match is not None:
                    citations.add((int(match["volume"]), match["page"]))
        if len(citations) != 1:
            raise StatutesParseError("Missing or conflicting enacted-law citation")
        citation_volume, first_page = next(iter(citations))
        title = meta.findtext(f"{{{self.settings.dc_namespace}}}title")
        if title is None or not title.strip():
            raise StatutesParseError("Enacted law lacks its official title")
        text = "\n".join(
            " ".join(line.split())
            for line in self.text(main).splitlines()
            if line.strip()
        )
        if not text:
            raise StatutesParseError("Enacted law contains no nonblank main text")
        references: list[str] = []
        long_title = main.find(self.tag("longTitle"))
        if long_title is not None:
            for reference in long_title.iter(self.tag("ref")):
                href = reference.get("href")
                if (
                    href is not None
                    and href.startswith("/us/bill/")
                    and href not in references
                ):
                    references.append(href)
        return StatuteLaw(
            identity=identity,
            volume=citation_volume,
            first_page=first_page,
            source_volume=volume.volume,
            session=session,
            approved_date=date.fromisoformat(self.required(meta, "approvedDate")),
            title=title.strip(),
            text=text,
            source_url=volume.source_url,
            volume_sha256=volume.sha256,
            component_sha256=hashlib.sha256(ET.tostring(element)).hexdigest(),
            bill_references=references,
        )

    def scan(self, volume: StatuteVolume) -> Iterator[StatuteLaw | StatuteRejectedLaw]:
        volume.verify()
        seen: set[tuple[StatuteLawKind, int, int]] = set()
        processed = 0
        root: ET.Element | None = None
        scope_checked = False
        with volume.path.open("rb") as source:
            for event, element in ET.iterparse(source, events=("start", "end")):
                if root is None:
                    root = element
                    if element.tag != self.tag(self.settings.root_tag):
                        raise StatutesParseError(
                            "Unexpected Statutes root or namespace"
                        )
                if (
                    event == "end"
                    and element.tag == self.tag("meta")
                    and not scope_checked
                    and root is not None
                    and element is root.find(self.tag("meta"))
                ):
                    expected = (
                        ("volume", volume.volume),
                        ("congress", volume.congress),
                        ("session", volume.session),
                    )
                    if any(
                        int(self.required(element, name)) != value
                        for name, value in expected
                    ):
                        raise StatutesParseError("Statutes volume metadata differs")
                    scope_checked = True
                if event != "end":
                    continue
                if element.tag == self.tag(self.settings.law_tag):
                    if not scope_checked:
                        raise StatutesParseError("Volume scope was not established")
                    processed += 1
                    try:
                        record = self.law(element, volume)
                        identity = record.identity
                        key = (identity.kind, identity.congress, identity.number)
                        if key in seen:
                            raise StatutesParseError("Repeated enacted-law identity")
                    except ValueError as error:
                        meta = element.find(self.tag("meta"))
                        yield StatuteRejectedLaw(
                            source_volume=volume.volume,
                            source_url=volume.source_url,
                            component_sha256=hashlib.sha256(
                                ET.tostring(element)
                            ).hexdigest(),
                            congress_raw=None
                            if meta is None
                            else meta.findtext(self.tag("congress")),
                            number_raw=None
                            if meta is None
                            else meta.findtext(self.tag("docNumber")),
                            kind_raw=None
                            if meta is None
                            else meta.findtext(self.tag("publicPrivate")),
                            error=str(error),
                        )
                    else:
                        seen.add(key)
                        yield record
                    element.clear()
                elif element.tag == self.tag("component"):
                    element.clear()
        if not scope_checked or not processed:
            raise StatutesParseError(
                "Statutes volume contains no verified enacted laws"
            )
        volume.verify()

    def records(self, volume: StatuteVolume) -> Iterator[StatuteLaw]:
        for record in self.scan(volume):
            if isinstance(record, StatuteRejectedLaw):
                raise StatutesParseError(record.error)
            yield record
