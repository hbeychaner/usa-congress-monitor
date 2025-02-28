from datetime import datetime
from enum import StrEnum
from pydantic import BaseModel, HttpUrl, Field, field_validator
from typing import List, Annotated, Optional

class Format(BaseModel):
    type: str
    url: HttpUrl

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
    action_date: Annotated[datetime, Field(alias="actionDate")]
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

class Action(BaseModel):
    action_date: Annotated[datetime, Field(alias='actionDate')] = None
    committees: Optional[List[CommitteeMetadata]] = []
    source_system: Annotated[SourceSystem, Field(alias='sourceSystem')]
    text: str
    type: str
    action_code: Annotated[str, Field(alias='actionCode')] = ""
    action_time: Annotated[datetime, Field(alias='actionTime')] = None

class Amendment(BaseModel):
    congress: int
    latest_action: Annotated[LatestAction, Field(alias='latestAction')]
    number: str
    purpose: str
    type: str
    update_date: Annotated[datetime, Field(alias='updateDate')]
    url: HttpUrl

class BillMetadata(BaseModel):
    congress: int
    latest_action: Annotated[LatestAction, Field(alias="latestAction")]
    number: int
    relationship_details: Annotated[List[RelationshipDetail], Field(alias="relationshipDetails")] = []
    title: str
    type: str
    url: HttpUrl

class Subjects(BaseModel):
    legislative_subjects: Optional[List[LegislativeSubject]] = []
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
