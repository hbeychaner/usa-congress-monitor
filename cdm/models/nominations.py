"""Nomination-related models and list items."""

from __future__ import annotations

import logging
from datetime import datetime

from pydantic import BaseModel, Field, HttpUrl, model_validator

from cdm.models.shared import CountUrl, EntityBase
from cdm.models.taxonomy import RecordTypeBase, Subject

logger = logging.getLogger(__name__)


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

    action_date: datetime | None = Field(
        default=None,
        alias="actionDate",
        description="When the latest action occurred.",
    )
    text: str | None = Field(
        default=None, description="What the latest action text says."
    )


class NominationTypeInfo(BaseModel):
    """Nomination type flags indicating military or civilian status."""

    is_military: bool | None = Field(
        default=None,
        alias="isMilitary",
        description="Whether the nomination is military.",
    )
    is_civilian: bool | None = Field(
        default=None,
        alias="isCivilian",
        description="Whether the nomination is civilian.",
    )


class Nomination(EntityBase):
    """Nomination record with nominee, position, and status information."""

    congress: int = Field(description="Which Congress the nomination belongs to.")
    number: int = Field(description="What the nomination number is.")
    part_number: int | str | None = Field(
        default=None,
        alias="partNumber",
        description="What the nomination part number is.",
    )
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
    nominee: str | None = Field(default=None, description="Who the nominee is.")
    position: str | None = Field(
        default=None, description="Which position the nominee is for."
    )
    date: datetime | None = Field(
        default=None,
        description="When the nomination was submitted or received.",
    )
    status: str | None = Field(
        default=None,
        description="What the current status of the nomination is.",
    )
    url: HttpUrl | None = Field(
        default=None,
        description="Where to retrieve the nomination record in the API.",
    )
    subjects: list[Subject] | None = Field(
        default=None,
        description="What subjects are tagged to the nomination.",
    )

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
                if isinstance(first, dict):
                    values["position"] = first.get("positionTitle") or first.get(
                        "position_title"
                    )
                else:
                    values["position"] = getattr(first, "position_title", None)
            if not values.get("nominee"):
                if isinstance(first, dict):
                    values["nominee"] = first.get("organization") or first.get(
                        "introText"
                    )
                else:
                    values["nominee"] = getattr(first, "organization", None) or getattr(
                        first, "intro_text", None
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

    recordType: str = Field(
        default="congress-nominations",
        description="Which knowledgebase index this record belongs to.",
    )
    congress: int = Field(description="Which Congress the nomination belongs to.")
    number: int = Field(description="What the nomination number is.")
    part_number: int | str | None = Field(
        default=None,
        alias="partNumber",
        description="What part number the nomination has.",
    )
    citation: str | None = Field(
        default=None, description="What the official nomination citation is."
    )
    description: str | None = Field(
        default=None, description="What the nomination describes."
    )
    received_date: datetime | None = Field(
        default=None,
        alias="receivedDate",
        description="When the nomination was received.",
    )
    latest_action: NominationLatestAction | None = Field(
        default=None, alias="latestAction", description="What the latest action is."
    )
    nomination_type: NominationTypeInfo | None = Field(
        default=None,
        alias="nominationType",
        description="What type of nomination this is.",
    )
    update_date: datetime | None = Field(
        default=None,
        alias="updateDate",
        description="When the nomination was last updated.",
    )
    url: HttpUrl | None = Field(
        default=None,
        description="Where to retrieve the nomination record in the API.",
    )
    organization: str | None = Field(
        default=None, description="Which organization the nomination is for."
    )


__all__ = [
    "Nomination",
    "NominationLatestAction",
    "NominationListItem",
    "NominationTypeInfo",
    "NomineePosition",
]
