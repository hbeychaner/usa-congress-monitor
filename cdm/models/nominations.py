"""Nomination-related models and list items."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, HttpUrl, model_validator

from cdm.models.shared import CountUrl, EntityBase
from cdm.models.taxonomy import RecordTypeBase, Subject


class NomineePosition(BaseModel):
    """Position-level nominee entry for a nomination (nominees list)."""

    ordinal: int | None = None
    nominee_count: int | None = Field(default=None, alias="nomineeCount")
    organization: str | None = None
    position_title: str | None = Field(default=None, alias="positionTitle")
    intro_text: str | None = Field(default=None, alias="introText")
    url: HttpUrl | None = None


class NominationLatestAction(BaseModel):
    """Latest action metadata attached to a nomination list item."""

    action_date: datetime | None = Field(default=None, alias="actionDate")
    text: str | None = None


class NominationTypeInfo(BaseModel):
    """Nomination type flags indicating military or civilian status."""

    is_military: bool | None = Field(default=None, alias="isMilitary")
    is_civilian: bool | None = Field(default=None, alias="isCivilian")


class Nomination(EntityBase):
    """Nomination record with nominee, position, and status information."""

    congress: int
    number: int
    part_number: int | str | None = Field(default=None, alias="partNumber")
    citation: str | None = None
    description: str | None = None
    authority_date: datetime | None = Field(default=None, alias="authorityDate")
    received_date: datetime | None = Field(default=None, alias="receivedDate")
    update_date: datetime | None = Field(default=None, alias="updateDate")
    nomination_type: NominationTypeInfo | None = Field(
        default=None, alias="nominationType"
    )
    latest_action: NominationLatestAction | None = Field(
        default=None, alias="latestAction"
    )
    nominees: list[NomineePosition] | None = None
    actions: CountUrl | None = None
    hearings: CountUrl | None = None
    committees: CountUrl | None = None
    nominee: str | None = None
    position: str | None = None
    date: datetime | None = None
    status: str | None = None
    url: HttpUrl | None = None
    subjects: list[Subject] | None = None

    @model_validator(mode="before")
    def _populate_common_fields(cls, values: dict):
        for camel, snake in (
            ("authorityDate", "authority_date"),
            ("receivedDate", "received_date"),
            ("updateDate", "update_date"),
            ("nominationType", "nomination_type"),
            ("latestAction", "latest_action"),
            ("partNumber", "part_number"),
        ):
            if values.get(camel) and not values.get(snake):
                values[snake] = values.get(camel)

        if not values.get("date"):
            for key in (
                "authorityDate",
                "authority_date",
                "receivedDate",
                "received_date",
            ):
                if values.get(key):
                    values["date"] = values.get(key)
                    break

        nominees = values.get("nominees")
        if isinstance(nominees, list) and nominees:
            first = nominees[0]
            if not values.get("position"):
                values["position"] = (
                    first.get("positionTitle") or first.get("position_title")
                    if isinstance(first, dict)
                    else getattr(first, "position_title", None)
                )
            if not values.get("nominee"):
                values["nominee"] = (
                    first.get("organization") or first.get("introText")
                    if isinstance(first, dict)
                    else getattr(first, "organization", None)
                    or getattr(first, "intro_text", None)
                )

        return values

    def build_id(self) -> str:
        """Build a stable nomination id, including a partition when present."""
        if self.id:
            return self.id
        identifier = f"nomination:{self.congress}:{self.number}"
        if self.part_number is not None:
            identifier += f":part{self.part_number}"
        return identifier


class NominationListItem(EntityBase, RecordTypeBase):
    """List-level nomination entry with citation and action data."""

    recordType: str = "congress-nominations"
    congress: int
    number: int
    part_number: int | str | None = Field(default=None, alias="partNumber")
    citation: str | None = None
    description: str | None = None
    received_date: datetime | None = Field(default=None, alias="receivedDate")
    latest_action: NominationLatestAction | None = Field(
        default=None, alias="latestAction"
    )
    nomination_type: NominationTypeInfo | None = Field(
        default=None, alias="nominationType"
    )
    update_date: datetime | None = Field(default=None, alias="updateDate")
    url: HttpUrl | None = None
    organization: str | None = None


__all__ = [
    "Nomination",
    "NominationLatestAction",
    "NominationListItem",
    "NominationTypeInfo",
    "NomineePosition",
]
