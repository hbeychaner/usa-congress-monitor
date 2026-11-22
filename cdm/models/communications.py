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

    code: str = Field(description="What the communication type code is.")
    name: str = Field(description="What the communication type name is.")


class HouseCommunication(EntityBase):
    """House communication record with sender, recipient, and subject."""

    congress: int | None = Field(
        default=None, description="Which Congress the communication belongs to."
    )
    number: int | None = Field(
        default=None, description="What the communication number is."
    )
    chamber: str | None = Field(
        default=None, description="Which chamber sent the communication."
    )
    type: str | None = Field(
        default=None, description="What type of communication this is."
    )
    abstract: str | None = Field(
        default=None, alias="abstract", description="Raw abstract text from the API"
    )
    committees: list[dict] | None = Field(
        default=None, alias="committees", description="Raw committee objects from the API"
    )
    communicationType: CommunicationTypeInfo | None = Field(
        default=None, alias="communicationType", description="Raw communicationType envelope"
    )
    congressional_record_date: datetime | None = Field(
        default=None,
        alias="congressionalRecordDate",
        description="Congressional Record date associated with this communication",
    )
    is_rulemaking: bool | None = Field(
        default=None,
        alias="isRulemaking",
        description="Whether the item is rulemaking; API may return string or bool.",
    )
    report_nature: str | None = Field(
        default=None,
        alias="reportNature",
        description="Human-readable description of the report nature when present.",
    )
    session_number: int | None = Field(
        default=None,
        alias="sessionNumber",
        description="Which session number the record belongs to.",
    )
    date: datetime | None = Field(
        default=None, description="When the communication was submitted."
    )
    url: HttpUrl | None = Field(
        default=None,
        description="Where to retrieve the communication record in the API.",
    )
    subject: Subject | None = Field(
        default=None, description="What subject the communication concerns."
    )
    sender: str | None = Field(
        default=None, description="Who sent the communication."
    )
    recipient: str | None = Field(
        default=None, description="Who received the communication."
    )

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
            if values.get("updateDate"):
                values["date"] = values.get("updateDate")
            elif values.get("congressionalRecordDate"):
                values["date"] = values.get("congressionalRecordDate")

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
            if isinstance(comms, list) and comms:
                first = comms[0]
                if isinstance(first, dict) and first.get("name"):
                    values["recipient"] = first.get("name")

        if isinstance(values.get("committees"), list):
            normalized = []
            for c in values.get("committees", []):
                if isinstance(c, dict):
                    if c.get("systemCode") and not c.get("system_code"):
                        c["system_code"] = c.get("systemCode")
                    if c.get("system_code") and not c.get("systemCode"):
                        c["systemCode"] = c.get("system_code")
                normalized.append(c)
            values["committees"] = normalized

        if not values.get("id"):
            congress = values.get("congress")
            number = values.get("number")
            chamber = values.get("chamber")
            if congress is not None and number is not None:
                resource = "house_communications"
                if chamber:
                    values["id"] = f"{resource}:{congress}:{chamber}:{number}"
                else:
                    values["id"] = f"{resource}:{congress}:{number}"

        if not values.get("url"):
            congress = values.get("congress")
            number = values.get("number")
            comm_type = None
            ct = values.get("communicationType")
            if isinstance(ct, dict):
                comm_type = ct.get("code") or ct.get("name")
            if congress is not None and number is not None and comm_type:
                try:
                    code = str(comm_type).lower()
                    values["url"] = (
                        f"https://api.congress.gov/v3/house-communication/{congress}/{code}/{number}?format=json"
                    )
                except (TypeError, ValueError):
                    logger.exception("Failed to construct house communication URL")

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

    type: str = Field(description="What type of requirement this is.")
    description: str | None = Field(
        default=None, description="What the requirement describes."
    )
    date: datetime | None = Field(
        default=None, description="When the requirement was recorded."
    )
    url: HttpUrl | None = Field(
        default=None,
        description="Where to retrieve the requirement record in the API.",
    )


class SenateCommunication(EntityBase):
    """Senate communication record with sender, recipient, and subject."""

    type: str | None = Field(
        default=None, description="What type of communication this is."
    )
    date: datetime | None = Field(
        default=None, description="When the communication was submitted."
    )
    url: HttpUrl | None = Field(
        default=None,
        description="Where to retrieve the communication record in the API.",
    )
    subject: Subject | None = Field(
        default=None, description="What subject the communication concerns."
    )
    sender: str | None = Field(
        default=None, description="Who sent the communication."
    )
    recipient: str | None = Field(
        default=None, description="Who received the communication."
    )

    @model_validator(mode="before")
    def _populate_type_from_comm_type(cls, values: dict):
        ct = values.get("communicationType")
        if (not values.get("type")) and isinstance(ct, dict):
            values["type"] = ct.get("name") or ct.get("code")
        return values


class _ChamberCommunicationListItem(EntityBase, RecordTypeBase):
    """Shared list-level communication fields for House and Senate."""

    chamber: str = Field(description="Which chamber sent the communication.")
    number: int = Field(description="What the communication number is.")
    communication_type: CommunicationTypeInfo | None = Field(
        default=None,
        alias="communicationType",
        description="What communication type this is.",
    )
    congress: int | None = Field(
        default=None, description="Which Congress the communication belongs to."
    )
    url: HttpUrl | None = Field(
        default=None,
        description="Where to retrieve the communication record in the API.",
    )
    update_date: datetime | None = Field(
        default=None,
        alias="updateDate",
        description="When the communication was last updated.",
    )


class HouseCommunicationListItem(_ChamberCommunicationListItem):
    """List-level House communication entry."""

    recordType: str = Field(
        default="congress-house-communications",
        description="Which knowledgebase index this record belongs to.",
    )


class SenateCommunicationListItem(_ChamberCommunicationListItem):
    """List-level Senate communication entry."""

    recordType: str = Field(
        default="congress-senate-communications",
        description="Which knowledgebase index this record belongs to.",
    )


class HouseRequirementListItem(EntityBase, RecordTypeBase):
    """List-level House requirement entry."""

    recordType: str = Field(
        default="congress-house-requirements",
        description="Which knowledgebase index this record belongs to.",
    )
    number: int = Field(description="What the requirement number is.")
    update_date: datetime | None = Field(
        default=None,
        alias="updateDate",
        description="When the requirement was last updated.",
    )
    url: HttpUrl | None = Field(
        default=None,
        description="Where to retrieve the requirement record in the API.",
    )


__all__ = [
    "CommunicationTypeInfo",
    "HouseCommunication",
    "HouseCommunicationListItem",
    "HouseRequirement",
    "HouseRequirementListItem",
    "SenateCommunication",
    "SenateCommunicationListItem",
]
