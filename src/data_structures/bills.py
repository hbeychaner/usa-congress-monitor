"""This module contains the data structures used in the application, including bills, amendments, congresses, and more."""

from datetime import datetime
from enum import StrEnum
from typing import List, Optional 
from pydantic import BaseModel, HttpUrl


class ResultType(StrEnum):
    JSON = "json"

class Chamber(StrEnum):
    HOUSE = "House"
    SENATE = "Senate"

class SessionType(StrEnum):
    REGULAR = "regular"
    SPECIAL = "special"

class AmendmentType(StrEnum):
    HAMDT = "hamdt"
    SAMDT = "samdt"
    SUAMDT = "suamdt"

class AmendmentList(BaseModel):
    count: int
    url: HttpUrl

class CosponsorCount(BaseModel):
    count: int
    countIncludingWithdrawnCosponsors: int
    url: HttpUrl

class Party(StrEnum):
    DEMOCRAT = "D"
    REPUBLICAN = "R"
    GREEN = "G"
    INDEPENDENT = "I"
    TEA_PARTY = "T"

class BillType(StrEnum):
    CONCURRENT_RESOLUTION = "HCONRES"
    JOINT_RESOLUTION = "HJRES"
    HOUSE_BILL = "HR"
    HOUSE_RESOLUTION = "HRES"
    SENATE_BILL = "S"
    SENATE_CONCURRENT_RESOLUTION = "SCONRES"
    SENATE_JOINT_RESOLUTION = "SJRES"
    SENATE_RESOLUTION = "SRES"

class SourceSystem(BaseModel):
    code: int
    name: str

class VoteEvent(BaseModel):
    chamber: Chamber
    congress: int
    date: datetime
    rollNumber: int
    sessionNumber: int
    url: HttpUrl

class ActionDetails(BaseModel):
    actionCode: str
    recordedVotes: Optional[VoteEvent]
    sourceSystem: SourceSystem
    actionDate: datetime

class Action(BaseModel):
    text: str
    type: str
    details: Optional[ActionDetails]
    
class BillDetails(BaseModel):
    actions: List[Action]
    amendments: List[str]
    cboCostEstimates: List[str]
    committeeReports: List[str]
    committees: List[str]
    constitutionalAuthorityStatementText: str
    cosponsors: List[str]
    introducedDate: datetime
    laws: List[str]
    policyArea: str
    relatedBills: List[str]
    sponsors: List[str]
    subjects: List[str]
    summaries: List[str]
    textVersions: List[str]
    titles: List[str]

class Bill(BaseModel):
    congress: int
    latestAction: dict
    number: int | str
    originChamber: str
    originChamberCode: str
    title: str
    type: BillType
    updateDate: datetime
    updateDateIncludingText: datetime
    url: HttpUrl