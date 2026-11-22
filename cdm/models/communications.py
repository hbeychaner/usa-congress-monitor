"""Communication-related models (House/Senate communications and requirements)."""

from __future__ import annotations

import logging
from datetime import datetime

from pydantic import BaseModel, Field, HttpUrl, model_validator

from cdm.models.shared import EntityBase
from cdm.models.taxonomy import RecordTypeBase, Subject

logger = logging.getLogger(__name__)


class CommunicationTypeInfo(BaseModel):
    """Communication type code and display name."""

    code: str
    name: str


class HouseCommunication(EntityBase):
    """House communication record with sender, recipient, and subject."""

    congress: int | None = None
    number: int | None = None
    chamber: str | None = None
    type: str | None = None
    abstract: str | None = Field(default=None, alias="abstract")
    committees: list[dict] | None = Field(default=None, alias="committees")
    communicationType: CommunicationTypeInfo | None = Field(
        default=None, alias="communicationType"
    )
    congressional_record_date: datetime | None = Field(
        default=None, alias="congressionalRecordDate"
    )
    is_rulemaking: bool | None = Field(default=None, alias="isRulemaking")
    report_nature: str | None = Field(default=None, alias="reportNature")
    session_number: int | None = Field(default=None, alias="sessionNumber")
    date: datetime | None = None
    url: HttpUrl | None = None
    subject: Subject | None = None
    sender: str | None = None
    recipient: str | None = None

    @model_validator(mode="before")
    def _populate_type_from_comm_type(cls, values: dict):
        ct = values.get("communicationType")
        if (not values.get("type")) and isinstance(ct, dict):
            values["type"] = ct.get("name") or ct.get("code")
        return values

    @model_validator(mode="before")
    def _normalize_house_communication(cls, values: dict):
        abstract = values.get("abstract")
        if abstract and not values.get("subject"):
            subj = {"name": abstract}
            if values.get("congressionalRecordDate"):
                subj["update_date"] = values.get("congressionalRecordDate")
            values["subject"] = subj

        if not values.get("date"):
            values["date"] = values.get("updateDate") or values.get(
                "congressionalRecordDate"
            )

        if values.get("congressionalRecordDate") and not values.get(
            "congressional_record_date"
        ):
            values["congressional_record_date"] = values.get("congressionalRecordDate")

        if not values.get("sender"):
            so = values.get("submittingOfficial") or values.get("submittingAgency")
            if so:
                values["sender"] = so

        if not values.get("recipient"):
            comms = values.get("committees")
            if isinstance(comms, list) and comms and isinstance(comms[0], dict):
                if comms[0].get("name"):
                    values["recipient"] = comms[0].get("name")

        if isinstance(values.get("committees"), list):
            for c in values["committees"]:
                if isinstance(c, dict):
                    if c.get("systemCode") and not c.get("system_code"):
                        c["system_code"] = c["systemCode"]
                    if c.get("system_code") and not c.get("systemCode"):
                        c["systemCode"] = c["system_code"]

        if not values.get("id"):
            congress = values.get("congress")
            number = values.get("number")
            chamber = values.get("chamber")
            if congress is not None and number is not None:
                values["id"] = (
                    f"house_communications:{congress}:{chamber}:{number}"
                    if chamber
                    else f"house_communications:{congress}:{number}"
                )

        if not values.get("url"):
            congress = values.get("congress")
            number = values.get("number")
            ct = values.get("communicationType")
            comm_type = (ct.get("code") or ct.get("name")) if isinstance(ct, dict) else None
            if congress is not None and number is not None and comm_type:
                values["url"] = (
                    f"https://api.congress.gov/v3/house-communication/{congress}/{str(comm_type).lower()}/{number}?format=json"
                )

        for camel, snake in (
            ("updateDate", "update_date"),
            ("sessionNumber", "session_number"),
            ("reportNature", "report_nature"),
        ):
            if values.get(camel) and not values.get(snake):
                values[snake] = values.get(camel)

        ir = values.get("isRulemaking")
        if ir is not None and values.get("is_rulemaking") is None:
            if isinstance(ir, bool):
                values["is_rulemaking"] = ir
            elif isinstance(ir, str):
                values["is_rulemaking"] = ir.lower() in ("true", "1", "yes")

        return values


class HouseRequirement(EntityBase):
    """House requirement record describing a required submission or report."""

    type: str
    description: str | None = None
    date: datetime | None = None
    url: HttpUrl | None = None


class SenateCommunication(EntityBase):
    """Senate communication record with sender, recipient, and subject."""

    type: str | None = None
    date: datetime | None = None
    url: HttpUrl | None = None
    subject: Subject | None = None
    sender: str | None = None
    recipient: str | None = None

    @model_validator(mode="before")
    def _populate_type_from_comm_type(cls, values: dict):
        ct = values.get("communicationType")
        if (not values.get("type")) and isinstance(ct, dict):
            values["type"] = ct.get("name") or ct.get("code")
        return values


class _ChamberCommunicationListItem(EntityBase, RecordTypeBase):
    """Shared list-level communication fields for House and Senate."""

    chamber: str
    number: int
    communication_type: CommunicationTypeInfo | None = Field(
        default=None, alias="communicationType"
    )
    congress: int | None = None
    url: HttpUrl | None = None
    update_date: datetime | None = Field(default=None, alias="updateDate")


class HouseCommunicationListItem(_ChamberCommunicationListItem):
    """List-level House communication entry."""

    recordType: str = "congress-house-communications"


class SenateCommunicationListItem(_ChamberCommunicationListItem):
    """List-level Senate communication entry."""

    recordType: str = "congress-senate-communications"


class HouseRequirementListItem(EntityBase, RecordTypeBase):
    """List-level House requirement entry."""

    recordType: str = "congress-house-requirements"
    number: int
    update_date: datetime | None = Field(default=None, alias="updateDate")
    url: HttpUrl | None = None


__all__ = [
    "CommunicationTypeInfo",
    "HouseCommunication",
    "HouseCommunicationListItem",
    "HouseRequirement",
    "HouseRequirementListItem",
    "SenateCommunication",
    "SenateCommunicationListItem",
]
