"""Typed evidence for shadow reconciliation and honest coverage reporting."""

from datetime import datetime, timedelta
from enum import StrEnum
from xml.etree.ElementTree import Element

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    TypeAdapter,
    ValidationError,
    computed_field,
    field_serializer,
    model_validator,
)

from cdm.config.source_policy import FieldName, SourceName, SourcePolicy
from cdm.utils.json_types import JsonValue


class SnapshotEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    source: SourceName
    version: AwareDatetime
    complete_fields: frozenset[FieldName]
    checked_at: AwareDatetime | None = None

    @field_serializer("complete_fields")
    def sorted_fields(self, value: frozenset[FieldName]) -> list[FieldName]:
        return sorted(value)

    @model_validator(mode="after")
    def require_known_authority(self) -> "SnapshotEvidence":
        if self.source in (SourceName.UNKNOWN, SourceName.BILLS):
            raise ValueError(
                "An unknown or text-only source cannot certify a parent snapshot"
            )
        if self.checked_at is not None and self.version > self.checked_at:
            raise ValueError("Source version postdates its verified source check")
        return self


class SourceCheck(BaseModel):
    fetched_at: AwareDatetime | None = None


class BillStatusEvidence(BaseModel):
    snapshot: SnapshotEvidence | None = None
    reason: str | None = None

    @classmethod
    def from_element(cls, bill: Element, policy: SourcePolicy) -> "BillStatusEvidence":
        children = {
            FieldName(element.tag.rsplit("}", 1)[-1]): element for element in bill
        }
        update = children.get(FieldName("updateDate"))
        version = update.text if update is not None else None
        if not version:
            return cls(
                reason="No document-level source version; field completeness is unverified"
            )
        try:
            versions: list[datetime] = []
            for name in policy.version_fields:
                child = children.get(name)
                if child is not None and child.text is not None:
                    versions.append(
                        TypeAdapter(AwareDatetime).validate_python(child.text.strip())
                    )
            if not versions:
                return cls(reason="No comparable document-level source version")
            parsed = max(versions)
        except ValidationError:
            return cls(
                reason="Source version lacks an unambiguous timezone-aware timestamp"
            )
        return cls(
            snapshot=SnapshotEvidence(
                source=SourceName.BILLSTATUS,
                version=parsed,
                complete_fields=frozenset(
                    field
                    for field, container in policy.billstatus_fields.items()
                    if container in children
                ),
            )
        )


class SourceMetadata(BaseModel):
    model_config = ConfigDict(extra="allow")

    source: SourceName = SourceName.UNKNOWN
    package_id: str | None = None
    url: str | None = None
    sha256: str | None = None
    parser_version: str | None = None


class FieldConflict(BaseModel):
    field: FieldName
    selected: JsonValue
    discarded: JsonValue
    selected_source: SourceName
    discarded_source: SourceName


class CoverageState(StrEnum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"
    NOT_APPLICABLE = "not_applicable"
    FAILED = "failed"


class ReconciliationEvidence(BaseModel):
    status: CoverageState = CoverageState.PARTIAL
    sources: list[SourceName]
    source_count: int
    conflicts: list[FieldConflict]
    field_authority: dict[FieldName, SnapshotEvidence] = Field(default_factory=dict)
    unverified_fields: list[FieldName] = Field(default_factory=list)


class ExpectationKind(StrEnum):
    AUTHORITATIVE = "authoritative"
    ESTIMATED = "estimated"
    UNKNOWN = "unknown"


class StageCoverage(BaseModel):
    observed: int = Field(default=0, ge=0)
    expected: int | None = Field(default=None, ge=0)
    expectation: ExpectationKind = ExpectationKind.UNKNOWN
    identities_verified: bool = False
    reason: str = Field(min_length=1)
    unavailable: bool = False
    not_applicable: bool = False
    failed: bool = False

    @model_validator(mode="after")
    def require_consistent_evidence(self) -> "StageCoverage":
        if sum((self.unavailable, self.not_applicable, self.failed)) > 1:
            raise ValueError("Coverage dispositions are mutually exclusive")
        if self.expectation == ExpectationKind.AUTHORITATIVE and self.expected is None:
            raise ValueError(
                "Authoritative coverage requires an expected identity count"
            )
        return self

    @computed_field
    @property
    def state(self) -> CoverageState:
        if self.failed:
            return CoverageState.FAILED
        if self.not_applicable:
            return CoverageState.NOT_APPLICABLE
        if self.unavailable:
            return CoverageState.UNAVAILABLE
        if (
            self.expectation == ExpectationKind.AUTHORITATIVE
            and self.expected is not None
            and self.observed == self.expected
            and self.identities_verified
        ):
            return CoverageState.COMPLETE
        return CoverageState.PARTIAL


class FreshnessState(StrEnum):
    FRESH = "fresh"
    STALE = "stale"
    UNKNOWN = "unknown"


class ResourceCoverage(BaseModel):
    resource: str
    congress: int | None = None
    scope: str = "selected_archives"
    discovery: StageCoverage
    hydration: StageCoverage
    indexing: StageCoverage
    checked_at: AwareDatetime | None = None
    assessed_at: AwareDatetime
    freshness: FreshnessState = FreshnessState.UNKNOWN

    def assess_freshness(self, policy: SourcePolicy) -> None:
        self.freshness = FreshnessState.UNKNOWN
        if self.checked_at is not None and self.checked_at <= self.assessed_at:
            self.freshness = (
                FreshnessState.FRESH
                if self.assessed_at - self.checked_at
                <= timedelta(hours=policy.freshness_hours)
                else FreshnessState.STALE
            )


class BillCandidate(BaseModel):
    id: str
    fields: dict[FieldName, JsonValue]
    metadata: list[SourceMetadata]
    snapshot: SnapshotEvidence | None = None
    checked_at: AwareDatetime | None = None

    @property
    def source(self) -> SourceName:
        return (
            self.snapshot.source
            if self.snapshot
            else (self.metadata[0].source if self.metadata else SourceName.UNKNOWN)
        )
