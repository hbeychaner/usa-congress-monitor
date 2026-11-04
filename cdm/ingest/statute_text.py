"""Preservation-aware publication of independently matched enacted-law text."""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from copy import deepcopy
from datetime import date
from enum import StrEnum
from typing import Literal

from pydantic import AnyHttpUrl, BaseModel, TypeAdapter

from cdm.config.source_policy import SourceName
from cdm.config.statute_text import StatuteTextSettings
from cdm.ingest.statutes import StatuteIdentity, StatuteLaw, StatuteLawKind
from cdm.store.create_only import BillId, BillSourceIdentity
from cdm.utils.json_types import JsonObject


class IndexedLawKind(StrEnum):
    PUBLIC = "Public Law"
    PRIVATE = "Private Law"


class IndexedLaw(BaseModel):
    number: str
    law_type: IndexedLawKind


class IndexedFormat(BaseModel):
    type: str
    url: str


class IndexedVersion(BaseModel):
    type: str
    formats: list[IndexedFormat]


class VerifiedStatuteText(BaseModel):
    bill_id: BillId
    pdf_url: AnyHttpUrl
    law: StatuteLaw
    bill_reference_verified: Literal[True]


class LawTextProvenance(BaseModel):
    source: Literal[SourceName.STATUTE] = SourceName.STATUTE
    collection: Literal["STATUTE"] = "STATUTE"
    package_id: str
    url: str
    reference_url: str
    sha256: str
    parser_version: str
    law_kind: StatuteLawKind
    congress: int
    law_number: int
    citation_volume: int
    first_page: str
    source_volume: int
    approved_date: date


class StatuteProvenance(LawTextProvenance):
    volume_sha256: str


class LawTextPayload(BaseModel):
    bill_id: BillId
    identity: StatuteIdentity
    text: str
    provenance: LawTextProvenance


class StatuteTextEnricher:
    def __init__(
        self,
        settings: StatuteTextSettings,
        lemmatizer: Callable[[Sequence[str]], list[str]],
    ) -> None:
        self.settings = settings
        self.lemmatizer = lemmatizer
        self.pdf_pattern = re.compile(settings.pdf_pattern)
        self.projector = LawTextProjector(lemmatizer)

    def build(self, before: JsonObject, text: VerifiedStatuteText) -> JsonObject:
        identity = BillSourceIdentity.model_validate(before)
        law = text.law
        if (
            identity.id != text.bill_id
            or identity.congress != law.identity.congress
            or f"/us/{identity.id.replace(':', '/')}" not in law.bill_references
        ):
            raise ValueError("Bill and independently verified law identity differ")
        match = self.pdf_pattern.fullmatch(str(text.pdf_url))
        if (
            match is None
            or int(match["congress"]) != identity.congress
            or int(match["volume"]) != law.volume
            or match["page"] != law.first_page.split("-")[0]
            or str(law.source_url)
            != f"{self.settings.volume_base_url}/{law.source_volume}/"
            f"STATUTE-{law.source_volume}.xml"
        ):
            raise ValueError("Law/PDF citation or official XML source differs")
        kind = (
            IndexedLawKind.PUBLIC
            if law.identity.kind is StatuteLawKind.PUBLIC
            else IndexedLawKind.PRIVATE
        )
        laws = TypeAdapter(list[IndexedLaw]).validate_python(before.get("laws"))
        versions = TypeAdapter(list[IndexedVersion]).validate_python(
            before.get("text_versions")
        )
        if not any(
            row.law_type is kind
            and row.number == f"{law.identity.congress}-{law.identity.number}"
            for row in laws
        ) or not any(
            version.type == kind.value
            and any(
                fmt.type == "PDF" and fmt.url == str(text.pdf_url)
                for fmt in version.formats
            )
            for version in versions
        ):
            raise ValueError("Indexed law or PDF evidence changed")
        provenance = StatuteProvenance(
            package_id=match["package_id"],
            url=str(law.source_url),
            reference_url=str(text.pdf_url),
            sha256=law.component_sha256,
            volume_sha256=law.volume_sha256,
            parser_version=self.settings.parser_version,
            law_kind=law.identity.kind,
            congress=law.identity.congress,
            law_number=law.identity.number,
            citation_volume=law.volume,
            first_page=law.first_page,
            source_volume=law.source_volume,
            approved_date=law.approved_date,
        )
        return self.projector.build(
            before,
            LawTextPayload(
                bill_id=text.bill_id,
                identity=law.identity,
                text=law.text,
                provenance=provenance,
            ),
        )


class LawTextProjector:
    def __init__(self, lemmatizer: Callable[[Sequence[str]], list[str]]) -> None:
        self.lemmatizer = lemmatizer

    def build(self, before: JsonObject, payload: LawTextPayload) -> JsonObject:
        identity = BillSourceIdentity.model_validate(before)
        law = payload.identity
        provenance = payload.provenance
        if (
            identity.id != payload.bill_id
            or identity.congress != law.congress
            or provenance.law_kind is not law.kind
            or provenance.congress != law.congress
            or provenance.law_number != law.number
        ):
            raise ValueError(
                "Publication payload and source identity/provenance differ"
            )
        old_text = before.get("full_text")
        if old_text is not None and (not isinstance(old_text, str) or old_text.strip()):
            raise ValueError("Existing nonblank or invalid full text must be preserved")
        if before.get("full_text_lemma") not in (None, ""):
            raise ValueError("Existing text lemma requires independent reconciliation")
        code = f"{law.kind.value}-law-{law.congress}-{law.number}"
        if before.get("full_text_version_code") not in (None, "", code):
            raise ValueError("Existing text-version evidence must be preserved")
        if before.get("full_text_version_rank") is not None:
            raise ValueError("Existing ranked text evidence requires reconciliation")
        if not payload.text.strip():
            raise ValueError("Verified law text is blank")
        lemmas = self.lemmatizer([payload.text])
        if len(lemmas) != 1 or not lemmas[0].strip():
            raise ValueError("Expected one nonblank indexed text lemma")
        after = deepcopy(before)
        raw_metadata = before.get("source_metadata")
        metadata = (
            []
            if raw_metadata is None
            else TypeAdapter(list[JsonObject]).validate_python(
                [raw_metadata] if isinstance(raw_metadata, dict) else raw_metadata
            )
        )
        entry = TypeAdapter(JsonObject).validate_python(
            provenance.model_dump(mode="json")
        )
        if entry not in metadata:
            metadata.append(entry)
        after["source_metadata"] = metadata
        for field, value in (
            ("source_package_ids", provenance.package_id),
            ("source_urls", provenance.url),
        ):
            previous = before.get(field)
            values = (
                []
                if previous is None
                else TypeAdapter(list[str]).validate_python(previous)
            )
            if value not in values:
                values.append(value)
            after[field] = values
        after["full_text"] = payload.text
        after["full_text_lemma"] = lemmas[0]
        after["full_text_version_code"] = code
        return after
