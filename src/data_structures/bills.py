from datetime import datetime
from enum import StrEnum
from pydantic import BaseModel, HttpUrl, Field, field_validator
from typing import List, Annotated, Optional

class Format(BaseModel):
    type: str
    url: HttpUrl
    full_text: str = "" # This needs to be retrieved from the url

class BehalfType(StrEnum):
    #This can be "Submitted on behalf of" the sponsor and/or "Proposed on behalf of" the sponsor. Assign value based on first word of input
    SUBMITTED = "Submitted"
    PROPOSED = "Proposed"

    def __init__(self, value):
        self._value_ = value
        self.type_url = value.split()[0]

class AmendmentType(StrEnum):
    SAMDT = "SAMDT" # Senate Amendment
    HAMDT = "HAMDT" # House Amendment
    SUAMDT = "SUAMDT" # Senate Unnumbered Amendment

    def __init__(self, value):
        self._value_ = value
        self.type_url = value.lower()

class TextVersion(BaseModel):
    date: datetime
    formats: List[Format]
    type: str

class PolicyArea(BaseModel):
    name: str
    update_date: Annotated[datetime, Field(alias='updateDate')] = None

class LegislativeSubject(BaseModel):
    name: str
    update_date: Annotated[datetime, Field(alias='updateDate')] = None

class Chamber(StrEnum):
    HOUSE = "House"
    SENATE = "Senate"

class LawType(StrEnum):
    PUBLIC = "Public Law"
    PRIVATE = "Private Law"

    def __init__(self, value):
        self._value_ = value
        if value == "Public Law":
            self.type_url = "pub"
        elif value == "Private Law":
            self.type_url = "priv"

class LatestAction(BaseModel):
    action_date: Annotated[datetime, Field(alias="actionDate")] = None
    text: str

class Note(BaseModel):
    texts: Annotated[List[str], Field(alias='text')]
    text: str = ""
    def __init__(self, text: str):
        self.text = ["\n".join(x["text"]) for x in text]

class Summary(BaseModel):
    action_date: Annotated[datetime, Field(alias='actionDate')]
    action_desc: Annotated[str, Field(alias='actionDesc')]
    text: str
    updateDate: Annotated[datetime, Field(alias='updateDate')]
    version_code: Annotated[str, Field(alias='versionCode')]

class CommitteeMetadata(BaseModel):
    name: str
    system_code: Annotated[str, Field(alias='systemCode')]
    url: HttpUrl
    
class SourceSystem(BaseModel):
    name: str
    code: int = -1

class ActionSourceSystem(StrEnum):
    SENATE = "0"
    LIBRARY_OF_CONGRESS = "9"
    HOUSE1 = "1"
    HOUSE2 = "2"

class Activity(BaseModel):
    date: datetime
    name: str

class IdentifyingEntity(StrEnum):
    HOUSE = "House"
    SENATE = "Senate"
    CRS = "CRS" # Congressional Research Service

class RelationshipDetail(BaseModel):
    identified_by: Annotated[IdentifyingEntity, Field(alias='identifiedBy')] = None
    type: str

class CountUrl(BaseModel):
    count: int
    url: HttpUrl

class Title(BaseModel):
    title: str
    title_type: Annotated[str, Field(alias='titleType')]
    title_type_code: Annotated[int, Field(alias='titleTypeCode')]
    update_date: Annotated[datetime, Field(alias='updateDate')]
    bill_text_version_code: Annotated[str, Field(alias='billTextVersionCode')] = ""
    bill_text_version_name: Annotated[str, Field(alias='billTextVersionName')] = ""

class ChamberCode(StrEnum):
    house = "H"
    senate = "S"

class BillType(StrEnum):
    def __init__(self, value):
        self._value_ = value
        self.type_url = value.lower()
    
    HR = "HR" # Bill introduced in House
    S = "S" # Bill introduced in Senate
    HJRES = "HJRES" # Joint resolution introduced in House
    SJRES = "SJRES" # Joint resolution introduced in Senate
    HCONRES = "HCONRES" # Concurrent resolution introduced in House
    SCONRES = "SCONRES" # Concurrent resolution introduced in Senate
    HRES = "HRES" # Simple resolution introduced in House
    SRES = "SRES" # Simple resolution introduced in Senate

class Member(BaseModel):
    bioguide_id: Annotated[str, Field(alias='bioguideId')]
    firstName: str
    first_name: Annotated[str, Field(alias='firstName')]
    full_name: Annotated[str, Field(alias='fullName')]
    last_name: Annotated[str, Field(alias='lastName')]
    party: str
    state: str
    url: HttpUrl
    middle_name: Annotated[str, Field(alias='middleName')] = ""
    district: Optional[int] = None
    is_original_cosponsor: Annotated[bool, Field(alias='isOriginalCosponsor')] = False
    is_by_request: Annotated[str, Field(alias='isByRequest')] = ""

class Sponsor(Member):
    sponsorship_date: Annotated[datetime, Field(alias='sponsorshipDate')]
    is_original_cosponsor: Annotated[bool, Field(alias='isOriginalCosponsor')] = False
    sponsorship_withrawn_date: Annotated[datetime, Field(alias='sponsorshipWithdrawnDate')] = None


class LawMetadata(BaseModel):
    number: str
    law_type: Annotated[LawType, Field(alias="type")]

    @field_validator('law_type', mode='before')
    def convert_law_type(cls, value):
        if value == "Public Law":
            return LawType.PUBLIC
        elif value == "Private Law":
            return LawType.PRIVATE
        raise ValueError("Invalid law type")

class Law(BaseModel):
    congress: int
    latest_action: Annotated[LatestAction, Field(alias="latestAction")]
    laws: List[LawMetadata]
    number: str
    origin_chamber: Annotated[Chamber, Field(alias="originChamber")]
    origin_chamber_code: Annotated[ChamberCode, Field(alias="originChamberCode")]
    title: str
    bill_type: Annotated[BillType, Field(alias="type")]
    update_date: Annotated[datetime, Field(alias="updateDate")]
    update_date_including_text: Annotated[datetime, Field(alias="updateDateIncludingText")]
    url: HttpUrl

class Committee(BaseModel):
    activities: List[Activity]
    chamber: str
    name: str
    system_code: Annotated[str, Field(alias='systemCode')]
    type: str
    url: HttpUrl

class RecordedVote(BaseModel):
    roll_number: Annotated[int, Field(alias='rollNumber')]
    url: HttpUrl
    chamber: Annotated[Chamber, Field(alias='chamber')]
    congress: int
    date: datetime
    session_number: Annotated[int, Field(alias='sessionNumber')]

class Action(BaseModel):
    action_date: Annotated[datetime, Field(alias='actionDate')]
    committees: Optional[List[CommitteeMetadata]] = []
    source_system: Annotated[SourceSystem, Field(alias='sourceSystem')] = None
    text: str
    type: str
    action_code: Annotated[str, Field(alias='actionCode')] = ""
    action_time: Annotated[datetime, Field(alias='actionTime')] = None
    recorded_votes: Annotated[List[RecordedVote], Field(alias='recordedVotes')] = []

class AmendmentMetadata(BaseModel):
    congress: int
    latest_action: Annotated[LatestAction, Field(alias='latestAction')] = None
    number: str
    purpose: str = ""
    type: str
    update_date: Annotated[datetime, Field(alias='updateDate')]
    url: HttpUrl

class Treaty(BaseModel):
    congress: int
    treaty_number: Annotated[str, Field(alias='treatyNumber')]
    url: HttpUrl

class Amendment(BaseModel):
    congress: int
    description: str
    purpose: str = ""
    latest_action: Annotated[LatestAction, Field(alias='latestAction')] = None
    number: str
    type: str
    update_date: Annotated[datetime, Field(alias='updateDate')]
    url: HttpUrl
    sponsors: List[Member] = []
    cosponsors: List[Member] = [] # Note that this needs to be populated in a separate step
    on_behalf_of_sponsor: Annotated[Member, Field(alias='onBehalfOfSponsor')] = None
    behalf_type: Annotated[BehalfType, Field(alias='behalfType')] = None
    proposed_date: Annotated[datetime, Field(alias='proposedDate')] = None
    submitted_date: Annotated[datetime, Field(alias='submittedDate')] = None
    chamber: Annotated[Chamber, Field(alias='chamber')] = None
    amended_treaty: Annotated[Treaty, Field(alias='amendedTreaty')] = None
    actions: List[Action] = [] # This needs to be populated in a separate step

class BillMetadata(BaseModel):
    congress: int
    latest_action: Annotated[LatestAction, Field(alias="latestAction")]
    number: int
    relationship_details: Annotated[List[RelationshipDetail], Field(alias="relationshipDetails")] = []
    title: str
    type: str
    url: HttpUrl

class Subjects(BaseModel):
    legislative_subjects: Annotated[List[LegislativeSubject], Field(alias='legislativeSubjects')] = []
    policy_area: Annotated[PolicyArea, Field(alias='policyArea')]

class Bill(BaseModel):
    congress: int
    constitutional_authority_statement_text: Annotated[str, Field(alias="constitutionalAuthorityStatement")] = ""
    introduced_date: Annotated[datetime, Field(alias="introducedDate")] = None
    latest_action: Annotated[LatestAction, Field(alias="latestAction")]
    laws: Annotated[List[LawMetadata], Field(alias="laws")] = []
    number: str
    origin_chamber: Annotated[Chamber, Field(alias="originChamber")]
    origin_chamber_code: Annotated[ChamberCode, Field(alias="originChamberCode")]
    policy_area: Annotated[PolicyArea, Field(alias="policyArea")] = None
    sponsors: List[Member] = []
    title: str
    type: str
    update_date: Annotated[datetime, Field(alias="updateDate")]
    update_date_including_text: Annotated[datetime, Field(alias="updateDateIncludingText")]
    notes: Annotated[Note, Field(alias="notes")] = None
