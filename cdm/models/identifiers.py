"""Identifier and enum models used in endpoint parameters."""

from __future__ import annotations

import re
from enum import StrEnum


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


__all__ = [
    "CommitteeCode",
    "CommunicationType",
    "ReportType",
    "StateCode",
]
