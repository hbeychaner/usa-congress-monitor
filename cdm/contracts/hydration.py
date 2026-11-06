"""Validated bill-detail retrieval evidence, not a global coverage certificate."""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Mapping
from datetime import UTC, date, datetime
from enum import StrEnum
from typing import Literal, NewType, Protocol

from pydantic import (
    AliasChoices,
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    TypeAdapter,
    field_validator,
    model_validator,
)

from cdm.config.source_policy import SourceName
from cdm.utils.json_types import JsonObject

DetailIdentity = NewType("DetailIdentity", str)


class FullTextDownloadError(RuntimeError):
    """Full-text retrieval failed; the chained request exception owns retryability."""


class BillDetailKind(StrEnum):
    ACTIONS = "actions"
    AMENDMENTS = "amendments"
    COMMITTEES = "committees"
    COSPONSORS = "cosponsors"
    RELATED_BILLS = "relatedBills"
    SUBJECTS = "subjects"
    SUMMARIES = "summaries"
    TEXT_VERSIONS = "textVersions"
    TITLES = "titles"

    @property
    def endpoint(self) -> str:
        return "text" if self is self.TEXT_VERSIONS else self.value.lower()

    @property
    def attribute(self) -> str:
        if self is self.RELATED_BILLS:
            return "related_bills"
        if self is self.TEXT_VERSIONS:
            return "text_versions"
        return self.value


class HydrationStatus(StrEnum):
    UNKNOWN = "unknown"
    PARTIAL = "partial"
    COMPLETE = "complete"


class DetailState(StrEnum):
    EXPANDED = "expanded"
    OBJECT = "object"
    ENVELOPE = "envelope"


class RepeatedDetailRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    record: JsonObject
    occurrences: int = Field(ge=2)


class RepeatedAction(RepeatedDetailRecord):
    """Source multiplicity of an anonymous action body."""


class DetailEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    page_count: int = Field(ge=1)
    expected_count: int | None = Field(
        default=None,
        ge=0,
        description="Expected source-counted entries: action rows, related-bill relationships, co-sponsorship episodes, or subject entries including policy area.",
    )
    fetched_count: int = Field(
        ge=0,
        description="Retrieved source-counted entries; action, text-version and nested relationship rows retain anonymous duplicates, while top-level records remain distinct.",
    )
    fetched_record_count: int | None = Field(
        default=None,
        ge=0,
        description="Distinct top-level collection records before counting nested relationships or policy area.",
    )
    fetched_relationship_count: int | None = Field(
        default=None,
        ge=0,
        description="Distinct nested related-bill relationships, deduplicated within each related bill; source row counts can include repeated anonymous relationships.",
    )
    repeated_actions: list[RepeatedAction] = Field(
        default_factory=list,
        description="Repeated anonymous action bodies and their source-row multiplicities, not a count of separate real-world events.",
    )
    repeated_text_versions: list[RepeatedDetailRecord] = Field(
        default_factory=list,
        description="Repeated anonymous text-version rows and their exact source multiplicities; download each distinct version only once.",
    )
    expected_active_count: int | None = Field(
        default=None,
        ge=0,
        description="Source-reported active co-sponsorship count, when available.",
    )
    fetched_active_count: int | None = Field(
        default=None,
        ge=0,
        description="Retrieved co-sponsorship episodes without a withdrawal date.",
    )
    state: DetailState
    complete: bool
    reason: str = Field(min_length=1)

    @model_validator(mode="after")
    def require_consistent_counts(self) -> DetailEvidence:
        if (
            self.fetched_relationship_count is not None
            and self.fetched_relationship_count > self.fetched_count
        ):
            raise ValueError("Distinct relationships cannot exceed source rows")
        for repeated in (self.repeated_actions, self.repeated_text_versions):
            if repeated and (
                self.fetched_record_count is None
                or (
                    self.fetched_record_count
                    + sum(record.occurrences - 1 for record in repeated)
                    > self.fetched_count
                )
                or self.complete
                and self.fetched_record_count
                + sum(record.occurrences - 1 for record in repeated)
                != self.fetched_count
            ):
                raise ValueError("Repeated detail evidence must reconcile row counts")
        if (
            self.fetched_active_count is not None
            and self.fetched_active_count > self.fetched_count
            or self.expected_active_count is not None
            and self.expected_count is not None
            and self.expected_active_count > self.expected_count
        ):
            raise ValueError("Active counts cannot exceed total detail counts")
        if self.complete and (
            self.state is DetailState.ENVELOPE
            or self.expected_count is not None
            and self.fetched_count != self.expected_count
            or self.expected_active_count is not None
            and self.fetched_active_count != self.expected_active_count
        ):
            raise ValueError("Complete detail evidence requires expanded, exact counts")
        return self


class HydrationAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    status: HydrationStatus = HydrationStatus.UNKNOWN
    source: SourceName = SourceName.UNKNOWN
    assessed_at: AwareDatetime | None = None
    details: dict[BillDetailKind, DetailEvidence] = Field(default_factory=dict)
    reason: str = Field(
        default="No versioned bill-detail hydration evidence is available.",
        min_length=1,
    )

    @model_validator(mode="after")
    def require_evidence(self) -> HydrationAssessment:
        if self.status is not HydrationStatus.UNKNOWN:
            if self.source is not SourceName.CONGRESS or self.assessed_at is None:
                raise ValueError(
                    "Assessed bill details require their source and assessment time"
                )
            complete = set(self.details) == set(BillDetailKind) and all(
                detail.complete for detail in self.details.values()
            )
            if (self.status is HydrationStatus.COMPLETE) != complete:
                raise ValueError(
                    "Hydration status disagrees with required detail evidence"
                )
            if not self.details:
                raise ValueError("An assessed status requires detail evidence")
        return self

    @classmethod
    def assess(
        cls, details: Mapping[BillDetailKind, DetailEvidence]
    ) -> HydrationAssessment:
        if not details:
            return cls(source=SourceName.CONGRESS)
        complete = set(details) == set(BillDetailKind) and all(
            detail.complete for detail in details.values()
        )
        return cls(
            status=HydrationStatus.COMPLETE if complete else HydrationStatus.PARTIAL,
            source=SourceName.CONGRESS,
            assessed_at=datetime.now(UTC),
            details=dict(details),
            reason=(
                "All required Congress API detail collections were retrieved; "
                "this does not certify full text, other sources or historical coverage."
                if complete
                else "One or more required Congress API detail collections remain unresolved."
            ),
        )

    @classmethod
    def from_record(cls, record: Mapping[str, object]) -> HydrationAssessment:
        return HydrationRecord.model_validate(record).hydration_assessment or cls()


class HydrationRecord(BaseModel):
    hydration_assessment: HydrationAssessment | None = None


class BillDetailClient(Protocol):
    def get_json(self, endpoint: str) -> Mapping[str, object]: ...


class Pagination(BaseModel):
    total: int | None = Field(default=None, ge=0, strict=True)
    count: int | None = Field(default=None, ge=0, strict=True)
    including_withdrawn: int | None = Field(
        default=None, alias="countIncludingWithdrawnCosponsors", ge=0, strict=True
    )
    next: str | None = Field(default=None, min_length=1)

    def expected_total(self, kind: BillDetailKind) -> int | None:
        counts = (
            (self.total, self.including_withdrawn)
            if kind is BillDetailKind.COSPONSORS
            else (self.total, self.count)
        )
        known = {value for value in counts if value is not None}
        if len(known) > 1:
            raise ValueError(f"Conflicting pagination count aliases for {kind}")
        total = next(iter(known), None)
        if (
            kind is BillDetailKind.COSPONSORS
            and total is not None
            and self.count is not None
            and self.count > total
        ):
            raise ValueError(
                "Active cosponsor count exceeds total including withdrawals"
            )
        return total


class CosponsorshipEpisode(BaseModel):
    sponsorship_date: date | None = Field(
        default=None,
        validation_alias=AliasChoices("sponsorshipDate", "sponsorship_date"),
    )
    withdrawn_date: date | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "sponsorshipWithdrawnDate",
            "sponsorship_withdrawn_date",
            "sponsorship_withrawn_date",
        ),
    )

    @field_validator("sponsorship_date", "withdrawn_date", mode="before")
    @classmethod
    def normalize_blank_date(cls, value: object) -> object:
        return None if value == "" else value


class CountEnvelope(BaseModel):
    count: int = Field(ge=0, strict=True)
    url: str = Field(min_length=1)


class RelatedBillRelationships(BaseModel):
    relationship_details: list[JsonObject] | None = Field(
        default=None,
        validation_alias=AliasChoices("relationshipDetails", "relationship_details"),
    )


class DetailResult(BaseModel):
    data: list[JsonObject] | JsonObject
    evidence: DetailEvidence


class BillDetailFetcher:
    """Validate response shapes and pagination before certifying a detail field."""

    def __init__(self, client: BillDetailClient, max_pages: int) -> None:
        if max_pages < 1:
            raise ValueError("max_pages must be positive")
        self._client = client
        self._max_pages = max_pages

    @staticmethod
    def distinct(
        records: list[JsonObject], kind: BillDetailKind | None = None
    ) -> list[JsonObject]:
        seen: dict[DetailIdentity, JsonObject] = {}
        result: list[JsonObject] = []
        for record in records:
            identity = record.get("id")
            if identity is None:
                identity = record.get("url")
            if identity is not None and (
                isinstance(identity, bool)
                or not isinstance(identity, (str, int))
                or isinstance(identity, str)
                and not identity.strip()
            ):
                raise ValueError("Bill-detail identity must be a string or integer")
            key = DetailIdentity(
                f"id:{identity}"
                if identity is not None
                else json.dumps(record, sort_keys=True, separators=(",", ":"))
            )
            if kind is BillDetailKind.COSPONSORS and identity is not None:
                episode = CosponsorshipEpisode.model_validate(record)
                if episode.sponsorship_date is not None:
                    key = DetailIdentity(
                        "cosponsor:"
                        + json.dumps(
                            [str(identity), episode.sponsorship_date.isoformat()],
                            separators=(",", ":"),
                        )
                    )
            if key in seen and seen[key] != record:
                raise RuntimeError("Conflicting records share a bill-detail identity")
            if key not in seen:
                seen[key] = record
                result.append(record)
        return result

    def fetch(self, endpoint: str, kind: BillDetailKind) -> DetailResult:
        records: list[JsonObject] = []
        subjects: JsonObject = {}
        visited: set[str] = set()
        expected: int | None = None
        expected_active: int | None = None
        next_endpoint: str | None = endpoint
        object_complete = True
        subjects_list_present = False
        for page_count in range(1, self._max_pages + 1):
            if next_endpoint in visited:
                raise RuntimeError(f"Pagination loop detected for {kind}")
            if next_endpoint is None:
                raise RuntimeError(f"Missing next endpoint for {kind}")
            visited.add(next_endpoint)
            response = TypeAdapter(JsonObject).validate_python(
                self._client.get_json(next_endpoint)
            )
            if kind not in response:
                raise ValueError(f"Missing {kind} in bill detail response")
            value = response[kind]
            raw_pagination = response.get("pagination")
            pagination = Pagination.model_validate(
                {} if raw_pagination is None else raw_pagination
            )
            page_expected = pagination.expected_total(kind)
            if page_expected is not None:
                if expected is not None and expected != page_expected:
                    raise RuntimeError(f"Source count changed during {kind} pagination")
                expected = page_expected
            if kind is BillDetailKind.COSPONSORS and pagination.count is not None:
                if expected_active is not None and expected_active != pagination.count:
                    raise RuntimeError(
                        "Active cosponsor count changed during pagination"
                    )
                expected_active = pagination.count
            if isinstance(value, dict) and ("count" in value or "url" in value):
                envelope = CountEnvelope.model_validate(value)
                if expected is not None and expected != envelope.count:
                    raise RuntimeError(f"Conflicting source counts for {kind}")
                if records or pagination.next:
                    raise ValueError(
                        f"Unexpected count envelope within {kind} pagination"
                    )
                empty = envelope.count == 0
                return DetailResult(
                    data=(
                        {"legislativeSubjects": []}
                        if kind is BillDetailKind.SUBJECTS
                        else []
                    )
                    if empty
                    else value,
                    evidence=DetailEvidence(
                        page_count=page_count,
                        expected_count=envelope.count,
                        fetched_count=0,
                        fetched_record_count=0,
                        expected_active_count=expected_active,
                        fetched_active_count=0
                        if kind is BillDetailKind.COSPONSORS
                        else None,
                        state=DetailState.EXPANDED if empty else DetailState.ENVELOPE,
                        complete=empty,
                        reason="Authoritative empty collection."
                        if empty
                        else "Count/URL envelope was not expanded.",
                    ),
                )
            if kind is BillDetailKind.SUBJECTS:
                if not isinstance(value, dict):
                    raise ValueError(
                        "Subjects must be an object, not a collection envelope"
                    )
                if "legislativeSubjects" not in value:
                    object_complete = False
                else:
                    subjects_list_present = True
                    records.extend(
                        TypeAdapter(list[JsonObject]).validate_python(
                            value["legislativeSubjects"]
                        )
                    )
                if "policyArea" in value:
                    area = value["policyArea"]
                    if area is not None:
                        TypeAdapter(JsonObject).validate_python(area)
                    if "policyArea" in subjects and subjects["policyArea"] != area:
                        raise RuntimeError(
                            "Policy area changed during subjects pagination"
                        )
                    subjects["policyArea"] = area
            else:
                records.extend(TypeAdapter(list[JsonObject]).validate_python(value))
            next_endpoint = pagination.next
            if not next_endpoint:
                break
        else:
            raise RuntimeError(
                f"Pagination limit of {self._max_pages} pages exceeded for {kind}"
            )
        distinct = self.distinct(records, kind)
        active = (
            sum(
                CosponsorshipEpisode.model_validate(record).withdrawn_date is None
                for record in distinct
            )
            if kind is BillDetailKind.COSPONSORS
            else None
        )
        fetched = len(distinct) + (
            int(bool(subjects.get("policyArea")))
            if kind is BillDetailKind.SUBJECTS
            else 0
        )
        fetched_relationship_count: int | None = None
        if kind is BillDetailKind.RELATED_BILLS:
            fetched = 0
            fetched_relationship_count = 0
            for record in distinct:
                relationships = RelatedBillRelationships.model_validate(
                    record
                ).relationship_details
                if relationships is None:
                    object_complete = False
                else:
                    distinct_relationships = self.distinct(relationships)
                    fetched += len(relationships)
                    fetched_relationship_count += len(distinct_relationships)
                    identified = [
                        relationship
                        for relationship in relationships
                        if relationship.get("id") is not None
                        or relationship.get("url") is not None
                    ]
                    if len(identified) != len(self.distinct(identified)):
                        object_complete = False
        repeated_records: list[RepeatedDetailRecord] = []
        if kind in (BillDetailKind.ACTIONS, BillDetailKind.TEXT_VERSIONS):
            frequencies = Counter(
                DetailIdentity(
                    json.dumps(record, sort_keys=True, separators=(",", ":"))
                )
                for record in records
                if record.get("id") is None and record.get("url") is None
            )
            repeated_records = [
                RepeatedDetailRecord(
                    record=TypeAdapter(JsonObject).validate_json(body),
                    occurrences=count,
                )
                for body, count in frequencies.items()
                if count > 1
            ]
            fetched = len(records)
            object_complete = fetched == len(distinct) + sum(
                record.occurrences - 1 for record in repeated_records
            )
        complete = (
            object_complete
            and (expected is None or fetched == expected)
            and (expected_active is None or active == expected_active)
        )
        if kind is BillDetailKind.SUBJECTS:
            if subjects_list_present:
                subjects["legislativeSubjects"] = distinct
            data: list[JsonObject] | JsonObject = subjects
        else:
            data = distinct
        return DetailResult(
            data=data,
            evidence=DetailEvidence(
                page_count=page_count,
                expected_count=expected,
                fetched_count=fetched,
                fetched_record_count=len(distinct),
                fetched_relationship_count=fetched_relationship_count,
                repeated_actions=[
                    RepeatedAction.model_validate(record.model_dump())
                    for record in repeated_records
                ] if kind is BillDetailKind.ACTIONS else [],
                repeated_text_versions=repeated_records
                if kind is BillDetailKind.TEXT_VERSIONS else [],
                expected_active_count=expected_active,
                fetched_active_count=active,
                state=DetailState.OBJECT
                if kind is BillDetailKind.SUBJECTS
                else DetailState.EXPANDED,
                complete=complete,
                reason="Response shape validated and pagination exhausted."
                if complete
                else "Missing required nested collection or source-counted/active entries disagree with source expectation.",
            ),
        )
