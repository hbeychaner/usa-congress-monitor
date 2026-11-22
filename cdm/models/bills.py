"""Pydantic models for bills, amendments, laws, committees, and related metadata."""

from __future__ import annotations

import logging
from datetime import datetime, time
from enum import StrEnum
from typing import Any

import requests
from bs4 import BeautifulSoup
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    TypeAdapter,
    ValidationError,
    field_validator,
    model_validator,
)

from cdm.contracts.hydration import (
    BillDetailClient,
    BillDetailFetcher,
    BillDetailKind,
    DetailEvidence,
    FullTextDownloadError,
    HydrationAssessment,
)
from cdm.data_collection.client import CDGClient
from cdm.data_collection.id_utils import UrlIdParser
from cdm.models.people import Chamber, Member, Sponsor, SponsorRef
from cdm.models.shared import (
    Activity,
    CountUrl,
    EntityBase,
    Format,
    LawType,
    Note,
    SourceSystem,
    Title,
)
from cdm.models.validators import convert_law_type, normalize_chamber
from cdm.utils.json_types import JsonObject

logger = logging.getLogger(__name__)


def _normalize_committee_codes(items: list) -> list:
    for sc in items:
        if isinstance(sc, dict):
            if sc.get("systemCode") and not sc.get("system_code"):
                sc["system_code"] = sc["systemCode"]
            if sc.get("system_code") and not sc.get("systemCode"):
                sc["systemCode"] = sc["system_code"]
    return items


def _url_or_hash_id(entity: BaseModel, fallback_token: str) -> str:
    try:
        url = getattr(entity, "url", None)
        if url:
            try:
                return UrlIdParser.parse(str(url))
            except (TypeError, ValueError):
                logger.exception("Failed to parse URL to id in build_id")
        return f"record:{abs(hash(str(entity.model_dump()))) % (10**12)}"
    except (AttributeError, TypeError, ValueError):
        return f"record:{abs(hash(fallback_token)) % (10**12)}"


class Hearing(BaseModel):
    """Hearing metadata with title, chamber, committee, and timing details."""

    title: str | None = None
    url: HttpUrl | None = None
    chamber: Chamber | None = None
    committee_name: str | None = None
    hearing_date: datetime | None = None
    type: str | None = None
    citation: str | None = None
    jacket_number: int | None = Field(default=None, alias="jacketNumber")
    library_of_congress_identifier: str | None = Field(
        default=None, alias="libraryOfCongressIdentifier"
    )
    congress: int | None = None
    dates: list[dict] | None = None
    formats: list[dict] | None = None
    associated_meeting: dict | None = Field(default=None, alias="associatedMeeting")
    part: int | None = None
    number: int | None = None
    update_date: datetime | None = Field(default=None, alias="updateDate")
    committees: list[dict] | None = None
    hearing: dict | None = Field(default=None, alias="hearing")

    @model_validator(mode="before")
    def _populate_url_from_formats(cls, values: dict):
        if not values.get("url"):
            fmts = values.get("formats")
            if isinstance(fmts, list) and fmts and isinstance(fmts[0], dict):
                if fmts[0].get("url"):
                    values["url"] = fmts[0]["url"]
        return values

    @model_validator(mode="before")
    def _extract_from_envelope(cls, values: dict):
        env = values.get("hearing")
        if not isinstance(env, dict) and any(
            k in values for k in ("committees", "dates", "title", "formats")
        ):
            env = values
            if "hearing" not in values:
                values["hearing"] = dict(values)
        if isinstance(env, dict):
            for key in ("title", "url", "chamber"):
                if not values.get(key) and env.get(key):
                    values[key] = env[key]

            if not values.get("committee_name"):
                comm = env.get("committee")
                comms = env.get("committees")
                if isinstance(comm, dict) and comm.get("name"):
                    values["committee_name"] = comm["name"]
                elif isinstance(comms, list) and comms and isinstance(comms[0], dict):
                    if comms[0].get("name"):
                        values["committee_name"] = comms[0]["name"]

            if isinstance(env.get("committees"), list):
                values["committees"] = _normalize_committee_codes(
                    env.get("committees", [])
                )

            if not values.get("hearing_date"):
                dates = env.get("dates")
                if isinstance(dates, list) and dates and isinstance(dates[0], dict):
                    if dates[0].get("date"):
                        values["hearing_date"] = dates[0]["date"]
                elif env.get("date"):
                    values["hearing_date"] = env["date"]
                elif env.get("hearingDate"):
                    values["hearing_date"] = env["hearingDate"]
        return values

    @field_validator("chamber", mode="before")
    def _normalize_chamber(cls, v):
        return normalize_chamber(v)


class BehalfType(StrEnum):
    """Enumeration for on-behalf-of sponsorship types."""

    SUBMITTED = "Submitted"
    PROPOSED = "Proposed"

    @property
    def type_url(self) -> str:
        return self.value.split()[0]


class TextVersion(BaseModel):
    """Text version for a bill or amendment, including formats and publish date."""

    date: datetime | None = None
    formats: list[Format]
    type: str


class PolicyArea(BaseModel):
    """Policy area classification assigned to a bill."""

    name: str
    update_date: datetime | None = Field(default=None, alias="updateDate")


class LegislativeSubject(BaseModel):
    """Legislative subject classification assigned to a bill."""

    name: str
    update_date: datetime | None = Field(default=None, alias="updateDate")


class LatestAction(BaseModel):
    """Latest action metadata with date and action text."""

    action_date: datetime | None = Field(default=None, alias="actionDate")
    text: str


class Summary(BaseModel):
    """Bill summary metadata including action and version information."""

    action_date: datetime = Field(alias="actionDate")
    action_desc: str = Field(alias="actionDesc")
    text: str
    updateDate: datetime = Field(alias="updateDate")
    version_code: str = Field(alias="versionCode")


class IdentifyingEntity(StrEnum):
    """Enumeration of entities that identify relationships between bills."""

    HOUSE = "House"
    SENATE = "Senate"
    CRS = "CRS"
    LIBRARY_OF_CONGRESS = "Library of Congress"
    GOVERNMENT_PUBLISHING_OFFICE = "U.S. Government Publishing Office"


class RelationshipDetail(BaseModel):
    """Details describing how a relationship between bills was identified."""

    identified_by: IdentifyingEntity | None = Field(default=None, alias="identifiedBy")
    type: str


class ChamberCode(StrEnum):
    """Chamber code values used in API responses."""

    house = "H"
    senate = "S"


class BillType(StrEnum):
    """Enumeration of bill types with API slug helpers."""

    def __init__(self, value: str) -> None:
        self._value_ = value
        self.type_url = value.lower()

    HR = "HR"
    S = "S"
    HJRES = "HJRES"
    SJRES = "SJRES"
    HCONRES = "HCONRES"
    SCONRES = "SCONRES"
    HRES = "HRES"
    SRES = "SRES"


class LawMetadata(BaseModel):
    """Law metadata attached to a bill (law number and type)."""

    number: str
    law_type: LawType = Field(alias="type")

    @field_validator("law_type", mode="before")
    def convert_law_type(cls, value: str):
        return convert_law_type(value)


class Committee(BaseModel):
    """Committee entity with activities and subcommittee hierarchy."""

    name: str
    chamber: str | None = None
    type: str | None = None
    system_code: str = Field(alias="systemCode")
    url: HttpUrl
    history: list[dict] = Field(default_factory=list)
    is_current: bool | None = Field(default=None, alias="isCurrent")
    update_date: datetime | None = Field(default=None, alias="updateDate")
    activities: list[Activity] = Field(default_factory=list)
    subcommittees: list[Committee] = Field(default_factory=list)
    bills: CountUrl | None = None
    committee_website_url: HttpUrl | None = Field(
        default=None, alias="committeeWebsiteUrl"
    )
    communications: CountUrl | None = None
    nominations: CountUrl | None = None
    parent: dict | None = None
    reports: CountUrl | None = None

    def __init__(self, **data):
        super().__init__(**data)
        self.subcommittees = [
            Committee(**sc) if isinstance(sc, dict) else sc for sc in self.subcommittees
        ]

    @model_validator(mode="before")
    def _normalize_api_payload(cls, values: dict):
        if not values.get("name"):
            hist = values.get("history")
            if isinstance(hist, list) and hist and isinstance(hist[0], dict):
                name = hist[0].get("officialName") or hist[0].get(
                    "libraryOfCongressName"
                )
                if name:
                    values["name"] = name

        if not values.get("chamber") and isinstance(values.get("type"), str):
            values["chamber"] = values["type"]

        if not values.get("url"):
            system_code = values.get("systemCode") or values.get("system_code")
            if system_code and not values.get("system_code"):
                values["system_code"] = system_code
            chamber = values.get("chamber") or (
                values.get("type") if isinstance(values.get("type"), str) else None
            )
            if system_code and chamber:
                values["url"] = (
                    f"https://api.congress.gov/v3/committee/{str(chamber).lower()}/{system_code}"
                )

        parent_chamber = values.get("chamber")
        parent_type = values.get("type")
        subs = values.get("subcommittees")
        if isinstance(subs, list) and subs:
            _normalize_committee_codes(subs)
            for sc in subs:
                if not isinstance(sc, dict):
                    continue
                if not sc.get("chamber") and parent_chamber:
                    sc["chamber"] = parent_chamber
                if not sc.get("type") and parent_type:
                    sc["type"] = parent_type
                system_id = sc.get("systemCode") or sc.get("system_code")
                if not sc.get("url") and system_id and sc.get("chamber"):
                    sc["url"] = (
                        f"https://api.congress.gov/v3/committee/{str(sc['chamber']).lower()}/{system_id}"
                    )

        for envelope_field in ("bills", "communications", "nominations", "reports"):
            val = values.get(envelope_field)
            if isinstance(val, dict) and {"count", "url"}.issubset(val):
                try:
                    values[envelope_field] = CountUrl(**val)
                except ValidationError:
                    logger.debug("Invalid CountUrl envelope for %s", envelope_field)
        return values


class CommitteeMetadata(BaseModel):
    """List-level committee metadata used in related records."""

    activities: list[Activity] | None = None
    chamber: str | None = None
    name: str
    system_code: str | None = Field(default=None, alias="systemCode")
    type: str | None = None
    url: HttpUrl | None = None


class RecordedVote(BaseModel):
    """Recorded vote metadata tied to actions or roll calls."""

    roll_number: int = Field(alias="rollNumber")
    url: HttpUrl | None = None
    chamber: Chamber = Field(alias="chamber")
    congress: int
    date: datetime
    session_number: int = Field(alias="sessionNumber")


class Action(BaseModel):
    """Action entry for a bill or amendment, including timing and committees."""

    action_date: datetime | None = Field(default=None, alias="actionDate")
    action_code: str = Field(default="", alias="actionCode")
    source_system: SourceSystem | None = Field(default=None, alias="sourceSystem")
    text: str = ""
    type: str | None = ""
    committees: list[CommitteeMetadata] | None = Field(default_factory=list)
    action_time: datetime | time | None = Field(default=None, alias="actionTime")
    recorded_votes: list[RecordedVote] = Field(
        default_factory=list, alias="recordedVotes"
    )

    @model_validator(mode="after")
    def _combine_time_only_action_time(self):
        if isinstance(self.action_time, time) and self.action_date:
            self.action_time = datetime.combine(
                self.action_date.date(),
                self.action_time,
                tzinfo=self.action_date.tzinfo,
            )
        return self


class AmendmentMetadata(BaseModel):
    """List-level metadata describing an amendment reference."""

    congress: int
    latest_action: LatestAction | None = Field(default=None, alias="latestAction")
    number: int
    purpose: str
    type: str
    update_date: datetime = Field(alias="updateDate")
    url: HttpUrl


class Treaty(BaseModel):
    """Treaty reference used in amendment or bill metadata."""

    congress: int | None = None
    treaty_number: str | None = Field(default=None, alias="treatyNumber")
    url: HttpUrl | None = None
    congress_received: int | None = Field(default=None, alias="congressReceived")
    congress_considered: int | None = Field(default=None, alias="congressConsidered")
    number: int | None = None
    countries_parties: list[JsonObject] = Field(
        default_factory=list, alias="countriesParties"
    )
    in_force_date: str | None = Field(default=None, alias="inForceDate")
    index_terms: list[JsonObject] = Field(default_factory=list, alias="indexTerms")
    old_number: str | None = Field(default=None, alias="oldNumber")
    old_number_display_name: str | None = Field(
        default=None, alias="oldNumberDisplayName"
    )
    parts: JsonObject = Field(default_factory=dict)
    related_docs: list[JsonObject] = Field(default_factory=list)
    resolution_text: str | None = None
    suffix: str | None = None
    topic: str | None = None
    titles: list[JsonObject] = Field(default_factory=list)
    transmitted_date: str | None = Field(default=None, alias="transmittedDate")
    update_date: str | None = Field(default=None, alias="updateDate")


class Subjects(BaseModel):
    """Subject bundle containing legislative subjects and policy area."""

    legislative_subjects: list[LegislativeSubject] = Field(
        default_factory=list, alias="legislativeSubjects"
    )
    policy_area: PolicyArea | None = Field(default=None, alias="policyArea")


class BillMetadata(EntityBase):
    """List-level bill metadata used for related bill references."""

    congress: int
    latest_action: LatestAction | None = Field(default=None, alias="latestAction")
    introduced_date: str | None = Field(default=None, alias="introducedDate")
    number: str
    relationship_details: list[RelationshipDetail] = Field(
        default_factory=list, alias="relationshipDetails"
    )
    title: str
    type: str
    url: HttpUrl
    origin_chamber: str | None = Field(default=None, alias="originChamber")
    origin_chamber_code: str | None = Field(default=None, alias="originChamberCode")
    update_date_including_text: str | None = Field(
        default=None, alias="updateDateIncludingText"
    )
    update_date: str | None = Field(default=None, alias="updateDate")

    @field_validator("number", mode="before")
    @classmethod
    def _coerce_number_to_string(cls, value: Any) -> str:
        return str(value)

    @model_validator(mode="after")
    def _populate_id_if_missing(self):
        if not getattr(self, "id", None):
            try:
                self.id = self.build_id()
            except ValueError:
                logger.debug("Could not build an id for BillMetadata")
        return self

    def build_id(self) -> str:
        """Return a canonical id for this bill metadata entry."""
        congress = getattr(self, "congress", None)
        bill_type = getattr(self, "type", None)
        number = getattr(self, "number", None)
        if congress and bill_type and number:
            return f"bill:{congress}:{str(bill_type).lower()}:{number}"
        url = getattr(self, "url", None)
        if url:
            return UrlIdParser.parse(str(url))
        raise ValueError(
            "Could not build canonical id for BillMetadata: missing congress/type/number/url"
        )


class Amendment(BaseModel):
    """Amendment record with sponsors, actions, and text versions."""

    actions: list[Action] | CountUrl | None = None
    cosponsors: list[Member] | CountUrl | None = None
    text_versions: list[TextVersion] | CountUrl | None = Field(
        default=None, alias="textVersions"
    )
    congress: int
    description: str | None = None
    purpose: str | None = None
    latest_action: LatestAction | None = Field(default=None, alias="latestAction")
    number: int
    type: str
    update_date: datetime = Field(alias="updateDate")
    url: HttpUrl | None = None
    sponsors: list[Member | SponsorRef] = Field(default_factory=list)
    on_behalf_of_sponsor: list[Member | SponsorRef] | None = Field(
        default=None, alias="onBehalfOfSponsor"
    )
    behalf_type: BehalfType | None = Field(default=None, alias="behalfType")
    proposed_date: datetime | None = Field(default=None, alias="proposedDate")
    submitted_date: datetime | None = Field(default=None, alias="submittedDate")
    chamber: Chamber | None = Field(default=None, alias="chamber")
    amended_bill: BillMetadata | None = Field(default=None, alias="amendedBill")
    links: list[dict] | None = Field(default=None, alias="links")
    full_text: str = ""

    @field_validator("chamber", mode="before")
    def _normalize_chamber(cls, v):
        return normalize_chamber(v)

    @field_validator("number", mode="before")
    def _coerce_number_to_int(cls, v):
        if v is None:
            return v
        try:
            return int(v)
        except (TypeError, ValueError):
            return v

    def add_full_text(self, client: CDGClient) -> str:
        """Fetch and return the full amendment text from formatted text versions."""
        if not self.text_versions or not isinstance(self.text_versions, list):
            return ""
        for text_version in self.text_versions:
            for fmt in getattr(text_version, "formats", []) or []:
                if "Formatted" in getattr(fmt, "type", ""):
                    try:
                        resp = client.session.get(
                            str(getattr(fmt, "url", "")), timeout=(10, 120)
                        )
                        return BeautifulSoup(resp.text, "html.parser").get_text()
                    except requests.RequestException as e:
                        raise FullTextDownloadError(
                            f"Network error retrieving full text for text version {self.type}: {e}"
                        ) from e
                    except (AttributeError, TypeError) as e:
                        raise RuntimeError(
                            f"Parsing error for full text in text version {self.type}: {e}"
                        ) from e
        return ""

    def build_id(self) -> str:
        """Return a canonical id for this amendment instance."""
        congress = getattr(self, "congress", None)
        a_type = getattr(self, "type", None)
        number = getattr(self, "number", None)
        if congress and number:
            return f"amendment:{congress}:{str(a_type).lower() if a_type else 'amendment'}:{number}"
        return _url_or_hash_id(self, str(number or congress or "amendment"))


class Bill(EntityBase):
    """Bill record with core metadata and optional expanded relationships."""

    actions: list[Action] | CountUrl | None = None
    amendments: list[Amendment] | CountUrl | None = None
    committees: list[CommitteeMetadata] | CountUrl | None = None
    cosponsors: list[Sponsor] | CountUrl | None = None
    related_bills: list[BillMetadata] | CountUrl | None = Field(
        default=None, alias="relatedBills"
    )
    subjects: Subjects | CountUrl | None = None
    summaries: list[Summary] | CountUrl | None = None
    text_versions: list[TextVersion] | CountUrl | None = Field(
        default=None, alias="textVersions"
    )
    titles: list[Title] | CountUrl | None = None
    full_text: str = ""
    detail_hydration: dict[BillDetailKind, DetailEvidence] = Field(default_factory=dict)
    hydration_assessment: HydrationAssessment = Field(
        default_factory=HydrationAssessment
    )
    congress: int
    constitutional_authority_statement_text: str = Field(
        default="", alias="constitutionalAuthorityStatementText"
    )
    introduced_date: datetime | None = Field(default=None, alias="introducedDate")
    latest_action: LatestAction | None = Field(default=None, alias="latestAction")
    laws: list[LawMetadata] = Field(default_factory=list, alias="laws")
    number: str
    origin_chamber: Chamber = Field(alias="originChamber")
    origin_chamber_code: ChamberCode = Field(alias="originChamberCode")
    policy_area: PolicyArea | None = Field(default=None, alias="policyArea")
    sponsors: list[Sponsor] | CountUrl | None = None
    title: str
    type: BillType
    update_date: datetime = Field(alias="updateDate")
    update_date_including_text: datetime = Field(alias="updateDateIncludingText")
    notes: list[Note] | CountUrl | None = Field(default=None, alias="notes")
    url: HttpUrl | None = Field(default=None, alias="legislationUrl")

    @model_validator(mode="before")
    def _populate_url_from_legislation_url(cls, values: dict):
        if not isinstance(values, dict):
            return values
        if values.get("legislationUrl") and not values.get("url"):
            values["url"] = values.get("legislationUrl")
        values.pop("legislationUrl", None)
        return values

    def add_full_text(self, client: CDGClient) -> str:
        """Fetch and return the full bill text from formatted text versions."""
        if not self.text_versions or not isinstance(self.text_versions, list):
            return ""
        for text_version in self.text_versions:
            for fmt in getattr(text_version, "formats", []) or []:
                if getattr(fmt, "type", "") == "Formatted Text":
                    try:
                        resp = client.session.get(
                            str(getattr(fmt, "url", "")), timeout=(10, 120)
                        )
                        resp.raise_for_status()
                        html = resp.text
                        if not html.strip():
                            raise ValueError("Formatted bill text response is empty")
                        return BeautifulSoup(html, "html.parser").get_text()
                    except requests.RequestException as e:
                        raise FullTextDownloadError(
                            f"Network error retrieving full text for text version {self.type}: {e}"
                        ) from e
                    except (AttributeError, TypeError) as e:
                        raise RuntimeError(
                            f"Parsing error for full text in text version {self.type}: {e}"
                        ) from e
        return ""

    def add_bill_details(
        self, client: CDGClient, max_pages: int = 100, *, fetch_full_text: bool = True
    ) -> None:
        """Populate the bill with related actions, summaries, and linked entities."""
        fetcher = BillDetailFetcher(client, max_pages)
        payload: JsonObject = self.model_dump(mode="json", by_alias=True)
        evidence: dict[BillDetailKind, DetailEvidence] = {}
        for kind in BillDetailKind:
            result = fetcher.fetch(
                f"bill/{self.congress}/{self.type.lower()}/{self.number}/{kind.endpoint}",
                kind,
            )
            evidence[kind] = result.evidence
            previous = payload.get(kind)
            if isinstance(result.data, list):
                if not result.evidence.complete and isinstance(previous, list):
                    previous_records = TypeAdapter(list[JsonObject]).validate_python(
                        previous
                    )
                    payload[kind] = fetcher.distinct(
                        previous_records + result.data, kind
                    )
                else:
                    payload[kind] = result.data
            elif kind is BillDetailKind.SUBJECTS and "count" not in result.data:
                if (
                    isinstance(previous, dict)
                    and "count" not in previous
                    and not result.evidence.complete
                ):
                    merged = {
                        **previous,
                        **{
                            k: v
                            for k, v in result.data.items()
                            if v is not None
                        },
                    }
                    old_subjects = previous.get("legislativeSubjects")
                    new_subjects = result.data.get("legislativeSubjects")
                    if isinstance(old_subjects, list) and isinstance(
                        new_subjects, list
                    ):
                        merged["legislativeSubjects"] = fetcher.distinct(
                            TypeAdapter(list[JsonObject]).validate_python(
                                old_subjects + new_subjects
                            ),
                            kind,
                        )
                    payload[kind] = merged
                else:
                    payload[kind] = result.data
            elif result.evidence.complete or previous is None:
                payload[kind] = result.data
        updated = Bill.model_validate(payload)
        full_text = updated.add_full_text(client) if fetch_full_text else ""
        for kind in BillDetailKind:
            setattr(self, kind.attribute, getattr(updated, kind.attribute))
        if full_text:
            self.full_text = full_text
        self.detail_hydration = evidence
        self.hydration_assessment = HydrationAssessment.assess(evidence)

    @staticmethod
    def _fetch_detail_collection(
        client: BillDetailClient, endpoint: str, key: str, max_pages: int
    ) -> list[JsonObject] | JsonObject:
        records, _ = Bill._fetch_detail_collection_with_metadata(
            client, endpoint, key, max_pages
        )
        return records

    @staticmethod
    def _fetch_detail_collection_with_metadata(
        client: BillDetailClient, endpoint: str, key: str, max_pages: int
    ) -> tuple[list[JsonObject] | JsonObject, JsonObject]:
        result = BillDetailFetcher(client, max_pages).fetch(
            endpoint, BillDetailKind(key)
        )
        metadata = result.evidence.model_dump(
            mode="json",
            include={
                "page_count",
                "expected_count",
                "fetched_count",
                "state",
                "complete",
            },
        )
        return result.data, metadata

    def build_id(self) -> str:
        """Return a canonical id for this bill instance."""
        congress = getattr(self, "congress", None)
        bill_type = getattr(self, "type", None)
        number = getattr(self, "number", None)
        if congress and bill_type and number:
            return f"bill:{congress}:{str(bill_type).lower()}:{number}"
        return _url_or_hash_id(self, str(number or congress or "bill"))


class Law(Bill):
    """Bill subtype representing an enacted law."""

    is_law: bool = True


class CommitteeReport(EntityBase):
    """Committee report metadata with citation and issuance details."""

    citation: str
    url: HttpUrl | None = None
    chamber: Chamber
    committee_name: str | None = None
    report_date: datetime | None = None
    type: str | None = None


class CommitteePrint(BaseModel):
    """Committee print metadata with title and issuance details."""

    jacket_number: int | None = Field(default=None, alias="jacketNumber")
    citation: str | None = None
    congress: int | None = None
    number: int | None = None
    title: str | None = None
    url: HttpUrl | None = None
    update_date: datetime | None = Field(default=None, alias="updateDate")
    chamber: Chamber | None = None
    committee_name: str | None = None
    print_date: datetime | None = None
    type: str | None = None
    committees: list[JsonObject] | None = None
    associated_bills: list[JsonObject] | None = Field(
        default=None, alias="associatedBills"
    )
    text: CountUrl | None = None

    model_config = ConfigDict(extra="allow", populate_by_name=True)


class CommitteeMeeting(BaseModel):
    """Committee meeting metadata with date, chamber, and committee context."""

    event_id: int | None = Field(default=None, alias="eventId")
    congress: int | None = None
    title: str | None = None
    name: str | None = None
    url: HttpUrl | None = None
    update_date: datetime | None = Field(default=None, alias="updateDate")
    chamber: Chamber | None = None
    meeting_status: str | None = Field(default=None, alias="meetingStatus")
    date: datetime | None = None
    committee_name: str | None = None
    meeting_date: datetime | None = None
    type: str | None = None
    committees: list[JsonObject] | None = None
    continuations: list[JsonObject] | None = None
    location: JsonObject | None = None
    videos: list[JsonObject] | None = None

    model_config = ConfigDict(extra="allow", populate_by_name=True)


class _BillSubResponse(BaseModel):
    """Shared pagination/request envelope for bill sub-endpoints."""

    pagination: dict | None = None
    request: dict | None = None


class BillTextResponse(_BillSubResponse):
    """Response wrapper for bill text endpoints (list of text versions)."""

    textVersions: list[TextVersion] = Field(default_factory=list)


class BillActionsResponse(_BillSubResponse):
    """Response wrapper for bill actions sub-endpoint."""

    actions: list[Action] = Field(default_factory=list)


class BillAmendmentsResponse(_BillSubResponse):
    """Response wrapper for bill amendments sub-endpoint."""

    amendments: list[AmendmentMetadata] = Field(default_factory=list)


class BillCommitteesResponse(_BillSubResponse):
    """Response wrapper for bill committees sub-endpoint."""

    committees: list[CommitteeMetadata] = Field(default_factory=list)


class BillCosponsorsResponse(_BillSubResponse):
    """Response wrapper for bill cosponsors sub-endpoint."""

    cosponsors: list[Sponsor] = Field(default_factory=list)


class BillRelatedBillsResponse(_BillSubResponse):
    """Response wrapper for related bills sub-endpoint."""

    relatedBills: list[BillMetadata] = Field(
        default_factory=list, alias="relatedBills"
    )


class BillSubjectsResponse(_BillSubResponse):
    """Response wrapper for bill subjects sub-endpoint."""

    subjects: Subjects | None = None


class BillSummariesResponse(_BillSubResponse):
    """Response wrapper for bill summaries sub-endpoint."""

    summaries: list[Summary] = Field(default_factory=list)


class BillTitlesResponse(_BillSubResponse):
    """Response wrapper for bill titles sub-endpoint."""

    titles: list[Title] = Field(default_factory=list)
