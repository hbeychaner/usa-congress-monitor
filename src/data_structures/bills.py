from datetime import datetime
from enum import StrEnum
from typing import List, Optional
from pydantic import BaseModel, HttpUrl

class Summary(BaseModel):
    actionDate: datetime
    actionDesc: str
    text: str
    updateDate: datetime
    versionCode: str

class Chamber(StrEnum):
    HOUSE = "House"
    SENATE = "Senate"

class CommitteeType(StrEnum):
    STANDING = "Standing"
    SELECT = "Select"
    SPECIAL = "Special"
    JOINT = "Joint"
    TASK_FORCE = "Task Force"
    OTHER = "Other"
    SUBCOMMITTEE = "Subcommittee"
    COMMISSION_OR_CAUCUS = "Commission or Caucus"

#Possible values are "Referred to", "Re-Referred to", "Hearings by", "Markup by", "Reported by", "Reported original measure", "Committed to", "Re-Committed to", and "Legislative Interest".
class ActivityType(StrEnum):
    REFERRED_TO = "Referred to"
    RE_REFERRED_TO = "Re-Referred to"
    HEARINGS_BY = "Hearings by"
    MARKUP_BY = "Markup by"
    REPORTED_BY = "Reported by"
    REPORTED_ORIGINAL_MEASURE = "Reported original measure"
    COMMITTED_TO = "Committed to"
    RE_COMMITTED_TO = "Re-Committed to"
    LEGISLATIVE_INTEREST = "Legislative Interest"

class Activity(BaseModel):
    name: ActivityType
    date: datetime

class Committee(BaseModel):
    name: str
    systemCode: str
    url: HttpUrl
    chamber: Optional[Chamber] = None
    type: Optional[CommitteeType] = None
    subcommittees: str
    activities: Optional[List[Activity]] = None

    
class SourceSystem(BaseModel):
    name: str

class Action(BaseModel):
    actionDate: Optional[datetime] = None
    committees: Optional[List[Committee]] = None
    sourceSystem: SourceSystem
    text: str
    type: str
    actionCode: Optional[str] = None
    actionTime: Optional[datetime] = None

class Activity(BaseModel):
    date: datetime
    name: str

class Committee(BaseModel):
    activities: List[Activity]
    chamber: Chamber
    name: str
    systemCode: str
    type: str
    url: HttpUrl

class LatestAction(BaseModel):
    actionDate: datetime
    text: str

class Amendment(BaseModel):
    congress: int
    latestAction: LatestAction
    number: str
    purpose: str
    type: str
    updateDate: datetime
    url: HttpUrl

class RelationshipDetail(BaseModel):
    identifiedBy: str
    type: str

class BillMetadata(BaseModel):
    congress: int
    latestAction: LatestAction
    number: int
    relationshipDetails: Optional[List[RelationshipDetail]] = []
    title: str
    type: str
    url: HttpUrl

class Title(BaseModel):
    title: str
    titleType: str
    titleTypeCode: int
    updateDate: datetime
    billTextVersionCode: Optional[str] = None
    billTextVersionName: Optional[str] = None
    
class Format(BaseModel):
    type: str
    url: HttpUrl

class TextVersion(BaseModel):
    date: datetime
    formats: List[Format]
    type: str

class PolicyArea(BaseModel):
    name: str
    updateDate: Optional[datetime] = None

class LegislativeSubject(BaseModel):
    name: str
    updateDate: datetime

class Subjects(BaseModel):
    legislativeSubjects: List[LegislativeSubject]
    policyArea: PolicyArea

class CountUrl(BaseModel):
    count: int
    url: HttpUrl

class LatestAction(BaseModel):
    actionDate: datetime
    text: str
    actionTime: Optional[datetime] = None

class cboCostEstimate(BaseModel):
    pubDate: datetime
    title: str
    url: HttpUrl
    description: Optional[str] = None

class Member(BaseModel):
    bioguideId: str
    firstName: str
    fullName: str
    lastName: str
    party: str
    state: str
    url: HttpUrl
    middleName: Optional[str]
    district: Optional[int]
    isOriginalCosponsor: Optional[bool] = None
    cboCostEstimates: Optional[List[cboCostEstimate]]
    isByRequest: Optional[str]

class ChamberCode(StrEnum):
    house = "H"
    senate = "S"
    
class Bill(BaseModel):
    congress: int
    constitutionalAuthorityStatementText: str
    introducedDate: datetime
    latestAction: LatestAction
    number: str
    originChamber: Chamber
    originChamberCode: ChamberCode
    policyArea: PolicyArea
    sponsors: List[Member]
    title: str
    type: str
    updateDate: datetime
    updateDateIncludingText: datetime

