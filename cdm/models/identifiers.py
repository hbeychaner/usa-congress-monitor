"""Identifier and enum models used in endpoint parameters."""

from __future__ import annotations

import re
from enum import StrEnum

from pydantic import BaseModel, Field


class CommitteeCode(str):
    """Validation wrapper for 4-alpha + 2-digit committee system codes (e.g., 'hspw00')."""

    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v: object) -> str:
        if not isinstance(v, str):
            raise TypeError("CommitteeCode must be a string")
        if not re.fullmatch(r"[a-zA-Z]{4}\d{2}", v):
            raise ValueError(
                f"CommitteeCode '{v}' must match pattern: 4 alpha + 2 digits (e.g., 'hspw00')"
            )
        return v.lower()


class ReportType(StrEnum):
    """Enumeration of committee report types used in endpoints."""

    HRPT = "hrpt"
    SRPT = "srpt"
    ERPT = "erpt"


class CommunicationType(StrEnum):
    """Enumeration of communication types used in endpoints."""

    EC = "ec"
    PM = "pm"
    PT = "pt"
    ML = "ml"
    POM = "pom"


class StateCode(StrEnum):
    """Two-letter postal code abbreviation for U.S. states."""

    AL = "AL"
    AK = "AK"
    AZ = "AZ"
    AR = "AR"
    CA = "CA"
    CO = "CO"
    CT = "CT"
    DE = "DE"
    FL = "FL"
    GA = "GA"
    HI = "HI"
    ID = "ID"
    IL = "IL"
    IN = "IN"
    IA = "IA"
    KS = "KS"
    KY = "KY"
    LA = "LA"
    ME = "ME"
    MD = "MD"
    MA = "MA"
    MI = "MI"
    MN = "MN"
    MS = "MS"
    MO = "MO"
    MT = "MT"
    NE = "NE"
    NV = "NV"
    NH = "NH"
    NJ = "NJ"
    NM = "NM"
    NY = "NY"
    NC = "NC"
    ND = "ND"
    OH = "OH"
    OK = "OK"
    OR = "OR"
    PA = "PA"
    RI = "RI"
    SC = "SC"
    SD = "SD"
    TN = "TN"
    TX = "TX"
    UT = "UT"
    VT = "VT"
    VA = "VA"
    WA = "WA"
    WV = "WV"
    WI = "WI"
    WY = "WY"


class EventId(BaseModel):
    """Wrapper for event identifiers used in hearings or meetings."""

    event_id: str = Field(description="What the event identifier is.")


class JacketNumber(BaseModel):
    """Wrapper for jacket numbers assigned to hearings or reports."""

    jacket_number: int = Field(description="What the jacket number is.")


class VolumeNumber(BaseModel):
    """Wrapper for volume numbers of the Congressional Record."""

    volume_number: int = Field(description="What the volume number is.")


class IssueNumber(BaseModel):
    """Wrapper for issue numbers of the Congressional Record."""

    issue_number: int = Field(description="What the issue number is.")


class District(BaseModel):
    """Wrapper for congressional district numbers."""

    district: int = Field(description="What the district number is.")


class RequirementNumber(BaseModel):
    """Wrapper for House requirement identifiers."""

    requirement_number: int = Field(description="What the requirement number is.")


class Ordinal(BaseModel):
    """Wrapper for ordinal values used in ordered lists."""

    ordinal: int = Field(description="What the ordinal position is.")


class TreatySuffix(BaseModel):
    """Wrapper for treaty suffix designators."""

    treaty_suffix: str = Field(description="What the treaty suffix is.")


class ReportNumber(BaseModel):
    """Wrapper for committee report numbers."""

    report_number: int = Field(description="What the report number is.")


class BillNumber(BaseModel):
    """Wrapper for bill numbers in endpoint parameters."""

    bill_number: int = Field(description="What the bill number is.")


class LawNumber(BaseModel):
    """Wrapper for law numbers assigned by NARA."""

    law_number: int = Field(description="What the law number is.")


class AmendmentNumber(BaseModel):
    """Wrapper for amendment numbers in endpoint parameters."""

    amendment_number: int = Field(description="What the amendment number is.")


class CommunicationNumber(BaseModel):
    """Wrapper for communication numbers in endpoint parameters."""

    communication_number: int = Field(description="What the communication number is.")


class NominationNumber(BaseModel):
    """Wrapper for nomination numbers in endpoint parameters."""

    nomination_number: int = Field(description="What the nomination number is.")


class TreatyNumber(BaseModel):
    """Wrapper for treaty numbers in endpoint parameters."""

    treaty_number: int = Field(description="What the treaty number is.")


__all__ = [
    "AmendmentNumber",
    "BillNumber",
    "CommitteeCode",
    "CommunicationNumber",
    "CommunicationType",
    "District",
    "EventId",
    "IssueNumber",
    "JacketNumber",
    "LawNumber",
    "NominationNumber",
    "Ordinal",
    "ReportNumber",
    "ReportType",
    "RequirementNumber",
    "StateCode",
    "TreatyNumber",
    "TreatySuffix",
    "VolumeNumber",
]
