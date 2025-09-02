from datetime import datetime
from enum import StrEnum
from pydantic import AliasChoices, BaseModel, HttpUrl, Field
from typing import List, Annotated, Optional

class Chamber(StrEnum):
    HOUSE = "House"
    SENATE = "Senate"

class Session(BaseModel):
    chamber: str
    end_date: Annotated[datetime, Field(alias='endDate', default=None)]
    number: Annotated[int | None, Field(alias='number', default=0)]
    start_date: Annotated[datetime, Field(alias='startDate')]
    type: str

class Congress(BaseModel):
    number: int
    url: HttpUrl
    update_date: Annotated[datetime, Field(alias='updateDate')]
    start_year: Annotated[int, Field(alias='startYear')]
    end_year: Annotated[int, Field(alias='endYear')]
    name: str
    sessions: List[Session]

class CongressMetadata(BaseModel):
    number: int

class Depiction(BaseModel): 
    attribution: str
    image_url: Annotated[HttpUrl, Field(alias='imageUrl')]

    @staticmethod
    def empty() -> "Depiction":
        return Depiction(attribution="", image_url=HttpUrl(""))

class Term(BaseModel):
    chamber: Chamber
    end_year: Annotated[int, Field(alias='endYear', default=None)]
    start_year: Annotated[int, Field(alias='startYear', default=None)]

class Member(BaseModel):
    bioguide_id: Annotated[str, Field(alias='bioguideId')]
    first_name: Annotated[str, Field(alias='firstName')]
    full_name: Annotated[str, Field(validation_alias=AliasChoices('fullName', 'name'))]
    last_name: Annotated[str, Field(alias='lastName')]
    party: Annotated[str, Field(validation_alias=AliasChoices('party', 'partyName'))]
    state: str
    url: HttpUrl
    middle_name: Annotated[str, Field(alias='middleName')] = ""
    district: Optional[int] = None
    is_original_cosponsor: Annotated[bool, Field(alias='isOriginalCosponsor')] = False
    is_by_request: Annotated[str, Field(alias='isByRequest')] = ""
    depiction: Annotated[Depiction, Field(alias='depiction')] = Depiction.empty()

class Sponsor(Member):
    sponsorship_date: Annotated[datetime, Field(alias='sponsorshipDate')]
    is_original_cosponsor: Annotated[bool, Field(alias='isOriginalCosponsor')] = False
    sponsorship_withrawn_date: Annotated[Optional[datetime], Field(alias='sponsorshipWithdrawnDate')] = None
