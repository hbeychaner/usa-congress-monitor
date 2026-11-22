"""Legislation list models (bills, amendments, laws, treaties, House roll call votes)."""

from __future__ import annotations

import logging
from datetime import datetime
from threading import Lock

from pydantic import BaseModel, Field, HttpUrl, model_validator

from cdm.models.shared import EntityBase
from cdm.models.taxonomy import RecordTypeBase

logger = logging.getLogger(__name__)

_house_vote_metrics_lock = Lock()
_house_vote_metrics = {"candidate_style_detections": 0}


def get_house_vote_metrics() -> dict[str, int]:
    """Return counters collected while normalizing House vote payloads."""
    with _house_vote_metrics_lock:
        return dict(_house_vote_metrics)


def reset_house_vote_metrics() -> None:
    """Reset House vote normalization counters, primarily for test isolation."""
    with _house_vote_metrics_lock:
        for key in _house_vote_metrics:
            _house_vote_metrics[key] = 0


def _record_candidate_style_detection() -> None:
    with _house_vote_metrics_lock:
        _house_vote_metrics["candidate_style_detections"] += 1


class VotePartyTotal(BaseModel):
    """Totals for a vote broken down by party or overall counts."""

    yea: int | None = Field(default=None, alias="yea")
    nay: int | None = Field(default=None, alias="nay")
    present: int | None = Field(default=None, alias="present")
    not_voting: int | None = Field(default=None, alias="notVoting")


class VoteQuestion(BaseModel):
    """Structured information about the question being voted on."""

    question: str | None = Field(default=None, alias="question")
    result: str | None = Field(default=None, alias="result")
    required: str | None = Field(default=None, alias="required")


class VoteCandidateTotal(BaseModel):
    """Per-candidate totals present in some vote payloads (e.g. Speaker election)."""

    candidate: str | None = Field(default=None, alias="candidate")
    total: int | None = Field(default=None, alias="total")


class HouseRollCallVoteListItem(EntityBase, RecordTypeBase):
    """List-level roll call vote entry for the House."""

    recordType: str = "congress-house-votes"
    start_date: datetime | None = Field(default=None, alias="startDate")
    update_date: datetime | None = Field(default=None, alias="updateDate")
    identifier: int | str | None = None
    congress: int | None = None
    session_number: int | None = Field(default=None, alias="sessionNumber")
    roll_call_number: int | None = Field(default=None, alias="rollCallNumber")
    vote_type: str | None = Field(default=None, alias="voteType")
    result: str | None = None
    legislation_type: str | None = Field(default=None, alias="legislationType")
    legislation_number: int | None = Field(default=None, alias="legislationNumber")
    amendment_type: str | None = Field(default=None, alias="amendmentType")
    amendment_number: int | None = Field(default=None, alias="amendmentNumber")
    amendment_author: str | None = Field(default=None, alias="amendmentAuthor")
    vote_party_total: VotePartyTotal | None = Field(
        default=None, alias="votePartyTotal"
    )
    vote_question: VoteQuestion | None = Field(default=None, alias="voteQuestion")
    vote_candidate_total: list[VoteCandidateTotal] | None = Field(
        default=None, alias="voteCandidateTotal"
    )
    source_data_url: HttpUrl | None = Field(default=None, alias="sourceDataURL")
    url: HttpUrl | None = Field(default=None, alias="legislationUrl")
    api_url: HttpUrl | None = Field(default=None, alias="url")

    model_config = {"populate_by_name": True}

    @model_validator(mode="before")
    def _normalize_vote_fields(cls, values: dict):
        if not isinstance(values, dict):
            return values

        vq = values.get("voteQuestion") or values.get("vote_question")
        if isinstance(vq, str):
            norm_vq = {"question": vq}
            values["voteQuestion"] = norm_vq
            values["vote_question"] = norm_vq

        vpt = values.get("votePartyTotal")
        if isinstance(vpt, list):
            if any(
                isinstance(x, dict) and ("candidate" in x or "total" in x) for x in vpt
            ):
                values["voteCandidateTotal"] = vpt
                values.pop("votePartyTotal", None)
                _record_candidate_style_detection()
            else:
                totals = {"yea": 0, "nay": 0, "present": 0, "notVoting": 0}
                any_found = False
                for item in vpt:
                    if not isinstance(item, dict):
                        continue
                    for src, key in (
                        ("yeaTotal", "yea"),
                        ("yea", "yea"),
                        ("nayTotal", "nay"),
                        ("nay", "nay"),
                        ("presentTotal", "present"),
                        ("present", "present"),
                        ("notVotingTotal", "notVoting"),
                        ("notVoting", "notVoting"),
                        ("not_voting", "notVoting"),
                    ):
                        val = item.get(src)
                        if val is not None:
                            try:
                                totals[key] += int(val)
                                any_found = True
                            except Exception:
                                logger.exception(
                                    "Failed to parse vote party total value: %s", val
                                )
                if any_found:
                    values["votePartyTotal"] = totals

        if values.get("legislationUrl") and not values.get("url"):
            values["url"] = values.get("legislationUrl")
        values.pop("legislationUrl", None)

        if values.get("voteQuestion") and not values.get("vote_question"):
            vq2 = values.get("voteQuestion")
            if isinstance(vq2, str):
                values["vote_question"] = {"question": vq2}
            elif isinstance(vq2, dict):
                values["vote_question"] = vq2

        if not values.get("id"):
            congress = values.get("congress")
            sess = values.get("sessionNumber") or values.get("session_number")
            roll = values.get("rollCallNumber") or values.get("roll_call_number")
            ident = values.get("identifier")
            if congress is not None and sess is not None and roll is not None:
                try:
                    values["id"] = (
                        f"house-rollcall-vote:{int(congress)}:{int(sess)}:{int(roll)}"
                    )
                except (TypeError, ValueError):
                    values["id"] = f"house-rollcall-vote:{congress}:{sess}:{roll}"
            elif ident is not None:
                values["id"] = f"house-rollcall-vote:{ident}"

        return values


class AmendmentLatestAction(BaseModel):
    """Latest action metadata attached to an amendment list item."""

    action_date: datetime | None = Field(default=None, alias="actionDate")
    action_time: str | None = Field(default=None, alias="actionTime")
    text: str | None = None


class AmendmentListItem(EntityBase, RecordTypeBase):
    """List-level amendment entry with latest action and type."""

    recordType: str = "congress-amendments"
    congress: int | None = None
    description: str | None = None
    latest_action: AmendmentLatestAction | None = Field(
        default=None, alias="latestAction"
    )
    number: str | None = None
    purpose: str | None = None
    type: str | None = None
    update_date: datetime | None = Field(default=None, alias="updateDate")
    url: HttpUrl | None = None


class BillLatestAction(BaseModel):
    """Latest action metadata attached to a bill list item."""

    action_date: datetime | None = Field(default=None, alias="actionDate")
    text: str | None = None


class LawEntry(BaseModel):
    """Law entry used in law list items (number and type)."""

    number: str | None = None
    type: str | None = None


class _BillOrLawListItem(EntityBase, RecordTypeBase):
    """Shared list-item fields for bills and enacted laws."""

    congress: int | None = None
    latest_action: BillLatestAction | None = Field(default=None, alias="latestAction")
    number: str | None = None
    origin_chamber: str | None = Field(default=None, alias="originChamber")
    origin_chamber_code: str | None = Field(default=None, alias="originChamberCode")
    title: str | None = None
    type: str | None = None
    update_date: datetime | None = Field(default=None, alias="updateDate")
    update_date_including_text: datetime | None = Field(
        default=None, alias="updateDateIncludingText"
    )
    url: HttpUrl | None = None


class BillListItem(_BillOrLawListItem):
    """List-level bill entry with title and latest action."""

    recordType: str = "congress-bills"


class LawListItem(_BillOrLawListItem):
    """List-level law entry derived from bill data."""

    recordType: str = "congress-laws"
    laws: list[LawEntry] | None = None


class TreatyListItem(EntityBase, RecordTypeBase):
    """List-level treaty entry with congress and numbering info."""

    recordType: str = "congress-treaties"
    congress_received: int | None = Field(default=None, alias="congressReceived")
    congress_considered: int | None = Field(default=None, alias="congressConsidered")
    number: int | None = None
    parts: dict[str, object] | None = None
    suffix: str | None = None
    topic: str | None = None
    transmitted_date: datetime | None = Field(default=None, alias="transmittedDate")
    update_date: datetime | None = Field(default=None, alias="updateDate")
    url: HttpUrl | None = None


__all__ = [
    "AmendmentLatestAction",
    "AmendmentListItem",
    "BillLatestAction",
    "BillListItem",
    "HouseRollCallVoteListItem",
    "LawEntry",
    "LawListItem",
    "TreatyListItem",
    "VoteCandidateTotal",
    "VotePartyTotal",
    "VoteQuestion",
    "get_house_vote_metrics",
    "reset_house_vote_metrics",
]
