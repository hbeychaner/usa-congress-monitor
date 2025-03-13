from datetime import datetime
from enum import StrEnum
from pydantic import AliasChoices, BaseModel, HttpUrl, Field, field_validator
from typing import List, Annotated, Optional
from bs4 import BeautifulSoup


class Format(BaseModel):
    type: str
    url: HttpUrl

class Session(BaseModel):
    chamber: str
    end_date: Annotated[datetime, Field(alias='endDate')]
    number: int
    start_date: Annotated[datetime, Field(alias='startDate')]
    type: str

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
    texts: Annotated[List[str], Field(alias='text')] = []
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
    action_date: Annotated[datetime, Field(alias='actionDate')] = None
    action_code: Annotated[str, Field(alias='actionCode')] = ""
    source_system: Annotated[SourceSystem, Field(alias='sourceSystem')] = None
    text: str
    type: str | None = ""
    committees: Optional[List[CommitteeMetadata]] = []
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

class Subjects(BaseModel):
    legislative_subjects: Annotated[List[LegislativeSubject], Field(alias='legislativeSubjects')] = []
    policy_area: Annotated[PolicyArea, Field(alias='policyArea')]

class BillMetadata(BaseModel):
    congress: int
    latest_action: Annotated[LatestAction, Field(alias="latestAction")]
    number: int
    relationship_details: Annotated[List[RelationshipDetail], Field(alias="relationshipDetails")] = []
    title: str
    type: str
    url: HttpUrl

class Amendment(BaseModel):
    # Fields added by collecting additional data with client object
    actions: List[Action] = []
    cosponsors: List[Member] = []
    text_versions: List[TextVersion] = []
    # Normal fields
    congress: int
    description: str
    purpose: str = ""
    latest_action: Annotated[LatestAction, Field(alias='latestAction')] = None
    number: str
    type: str
    update_date: Annotated[datetime, Field(alias='updateDate')]
    url: HttpUrl
    sponsors: List[Member] = []
    on_behalf_of_sponsor: Annotated[Member, Field(alias='onBehalfOfSponsor')] = None
    behalf_type: Annotated[BehalfType, Field(alias='behalfType')] = None
    proposed_date: Annotated[datetime, Field(alias='proposedDate')] = None
    submitted_date: Annotated[datetime, Field(alias='submittedDate')] = None
    chamber: Annotated[Chamber, Field(alias='chamber')] = None
    amended_treaty: Annotated[Treaty, Field(alias='amendedTreaty')] = None
    full_text: str = ""


    def add_full_text(self, client):
        for text_version in self.text_versions:
            for format in text_version.formats:
                # Check if the format type is "Formatted Text"
                if "Formatted" in format.type:
                    try:
                        # Retrieve HTML content from the URL
                        html = client.get(format.url)
                        # Parse the HTML content
                        soup = BeautifulSoup(html, "html.parser")
                        full_text = soup.get_text()
                    except Exception as e:
                        raise Exception(f"Failed to retrieve full text for text version {self.type}") from e
                    return full_text
                
    def get_amendment_details(self, client):
        """
        Retrieve additional data for an amendment.

        Args:
            client (CDGClient): The client object.
            amendment_metadata (AmendmentMetadata): The amendment metadata.

        Returns:
            Amendment: The amendment object.
        """
        amendment_data = {}
        congress = self.congress
        amendment_type = self.type
        amendment_number = self.number
        additional_amendment_data = {
            'actions': 'actions',
            'cosponsors': 'cosponsors', 
            'textVersions': 'text',
            'amendments': 'amendments'
        }

        for key, endpoint in additional_amendment_data.items():
            data = client.get(f"amendment/{congress}/{amendment_type.lower()}/{amendment_number}/{endpoint}", params={"format":None})
            amendment_data[key] = data[key]

        print(amendment_data)

        self.actions = [Action(**x) for x in amendment_data["actions"]]
        self.cosponsors = [Member(**x) for x in amendment_data["cosponsors"]]
        self.text_versions = [TextVersion(**x) for x in amendment_data["textVersions"]]
        self.full_text = self.add_full_text(client)

class Bill(BaseModel):
    # Fields added by collecting additional data with client object
    actions: List[Action] = []
    amendments: List[Amendment] = []
    committees: List[Committee] = []
    cosponsors: List[Sponsor] = []
    related_bills: List[BillMetadata] = []
    subjects: Subjects
    summaries: List[Summary] = []
    text_versions: List[TextVersion] = []
    titles: List[Title] = []
    full_text: str = ""

    # Fields from original data
    congress: int
    constitutional_authority_statement_text: Annotated[str, Field(alias="constitutionalAuthorityStatementText")] = ""
    introduced_date: Annotated[datetime, Field(alias="introducedDate")] = None
    latest_action: Annotated[LatestAction, Field(alias="latestAction")]
    laws: Annotated[List[LawMetadata], Field(alias="laws")] = []
    number: str
    origin_chamber: Annotated[Chamber, Field(alias="originChamber")]
    origin_chamber_code: Annotated[ChamberCode, Field(alias="originChamberCode")]
    policy_area: Annotated[PolicyArea, Field(alias="policyArea")] = None
    sponsors: List[Sponsor] = []
    title: str
    type: BillType
    update_date: Annotated[datetime, Field(alias="updateDate")]
    update_date_including_text: Annotated[datetime, Field(alias="updateDateIncludingText")]
    notes: Annotated[Note, Field(alias="notes")] = None

    def add_full_text(self, client):
        for text_version in self.text_versions:
            for format in text_version.formats:
                # Check if the format type is "Formatted Text"
                if format.type == "Formatted Text":
                    try:
                        # Retrieve HTML content from the URL
                        html = client.get(format.url)
                        # Parse the HTML content
                        soup = BeautifulSoup(html, "html.parser")
                        full_text = soup.get_text()
                    except Exception as e:
                        raise Exception(f"Failed to retrieve full text for text version {self.type}") from e
                    return full_text

    def add_bill_details(self, client):
        """
        Retrieve additional data for a bill.

        Args:
            client: A CGDClient object.
        """
        bill_data = {}
        # Currently available endpoints for additional data on bills
        additional_bill_data = {
            'actions': 'actions',
            'amendments': 'amendments',
            'committees': 'committees',
            'cosponsors': 'cosponsors',
            'relatedBills': 'relatedbills',
            'subjects': 'subjects',
            'summaries': 'summaries',
            'textVersions': 'text',
            'titles': 'titles'
        }
        congress = self.congress
        bill_type = self.type.lower()
        bill_number = self.number
        for key, endpoint in additional_bill_data.items():
            data = client.get(f"bill/{congress}/{bill_type}/{bill_number}/{endpoint}")
            bill_data[key] = data[key]
        
        self.actions = [Action(**x) for x in bill_data["actions"]]
        self.amendments = [AmendmentMetadata(**x) for x in bill_data["amendments"]]
        self.cosponsors = [Sponsor(**x) for x in bill_data["cosponsors"]]
        self.related_bills = [BillMetadata(**x) for x in bill_data["relatedBills"]]
        self.subjects = Subjects(**bill_data["subjects"])
        self.summaries = [Summary(**x) for x in bill_data["summaries"]]
        self.text_versions = [TextVersion(**x) for x in bill_data["textVersions"]]
        self.titles = [Title(**x) for x in bill_data["titles"]]
        self.full_text = self.add_full_text(client)

class Law(Bill): # This class is a subclass of Bill
    is_law: bool = True
