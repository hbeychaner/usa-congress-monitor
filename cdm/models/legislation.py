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

    yea: int | None = Field(
        default=None, alias="yea", description="Number of yea votes."
    )
    nay: int | None = Field(
        default=None, alias="nay", description="Number of nay votes."
    )
    present: int | None = Field(
        default=None, alias="present", description="Number of present votes."
    )
    not_voting: int | None = Field(
        default=None, alias="notVoting", description="Number of not voting."
    )


class VoteQuestion(BaseModel):
    """Structured information about the question being voted on."""

    question: str | None = Field(
        default=None, alias="question", description="Human-readable question text."
    )
    result: str | None = Field(
        default=None, alias="result", description="Result for this question."
    )
    required: str | None = Field(
        default=None,
        alias="required",
        description="What threshold was required for passage (e.g., 'majority').",
    )


class VoteCandidateTotal(BaseModel):
    """Per-candidate totals present in some vote payloads (e.g. Speaker election)."""

    candidate: str | None = Field(
        default=None, alias="candidate", description="Candidate name."
    )
    total: int | None = Field(
        default=None, alias="total", description="Total votes for candidate."
    )


class HouseRollCallVoteListItem(EntityBase, RecordTypeBase):
    """List-level roll call vote entry for the House."""

    recordType: str = Field(
        default="congress-house-votes",
        description="Which knowledgebase index this record belongs to.",
    )
    start_date: datetime | None = Field(
        default=None, alias="startDate", description="When the vote started."
    )
    update_date: datetime | None = Field(
        default=None,
        alias="updateDate",
        description="When the vote record was last updated.",
    )
    identifier: int | str | None = Field(
        default=None, description="What the roll call vote identifier is."
    )
    congress: int | None = Field(
        default=None, description="Which Congress the vote belongs to."
    )
    session_number: int | None = Field(
        default=None,
        alias="sessionNumber",
        description="Which session the vote occurred in.",
    )
    roll_call_number: int | None = Field(
        default=None,
        alias="rollCallNumber",
        description="What the roll call number is.",
    )
    vote_type: str | None = Field(
        default=None, alias="voteType", description="What type of vote this was."
    )
    result: str | None = Field(
        default=None, description="What the vote result was."
    )
    legislation_type: str | None = Field(
        default=None,
        alias="legislationType",
        description="What type of legislation the vote was on.",
    )
    legislation_number: int | None = Field(
        default=None,
        alias="legislationNumber",
        description="What the legislation number was.",
    )
    amendment_type: str | None = Field(
        default=None,
        alias="amendmentType",
        description="What type of amendment was voted on.",
    )
    amendment_number: int | None = Field(
        default=None,
        alias="amendmentNumber",
        description="What the amendment number was.",
    )
    amendment_author: str | None = Field(
        default=None,
        alias="amendmentAuthor",
        description="Who authored the amendment.",
    )
    vote_party_total: VotePartyTotal | None = Field(
        default=None,
        alias="votePartyTotal",
        description="Totals for the vote broken down by party or category.",
    )
    vote_question: VoteQuestion | None = Field(
        default=None,
        alias="voteQuestion",
        description="Structured details about the question being voted on.",
    )
    vote_candidate_total: list[VoteCandidateTotal] | None = Field(
        default=None,
        alias="voteCandidateTotal",
        description="Per-candidate totals when present (preserved).",
    )
    source_data_url: HttpUrl | None = Field(
        default=None,
        alias="sourceDataURL",
        description="Where to retrieve the source vote data.",
    )
    url: HttpUrl | None = Field(
        default=None,
        alias="legislationUrl",
        description="Where to retrieve the vote record in the API.",
    )
    api_url: HttpUrl | None = Field(
        default=None,
        alias="url",
        description="Where to retrieve the vote in the API.",
    )

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
            is_candidate_style = any(
                isinstance(x, dict) and ("candidate" in x or "total" in x) for x in vpt
            )
            if is_candidate_style:
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

    action_date: datetime | None = Field(
        default=None,
        alias="actionDate",
        description="When the latest action occurred.",
    )
    action_time: str | None = Field(
        default=None,
        alias="actionTime",
        description="What time the latest action occurred.",
    )
    text: str | None = Field(
        default=None, description="What the latest action text says."
    )


class AmendmentListItem(EntityBase, RecordTypeBase):
    """List-level amendment entry with latest action and type."""

    recordType: str = Field(
        default="congress-amendments",
        description="Which knowledgebase index this record belongs to.",
    )
    congress: int | None = Field(
        default=None, description="Which Congress the amendment belongs to."
    )
    description: str | None = Field(
        default=None, description="What the amendment description says."
    )
    latest_action: AmendmentLatestAction | None = Field(
        default=None, alias="latestAction", description="What the latest action is."
    )
    number: str | None = Field(
        default=None, description="What the amendment number is."
    )
    purpose: str | None = Field(
        default=None, description="What purpose the amendment states."
    )
    type: str | None = Field(
        default=None, description="What type of amendment this is."
    )
    update_date: datetime | None = Field(
        default=None,
        alias="updateDate",
        description="When the amendment was last updated.",
    )
    url: HttpUrl | None = Field(
        default=None, description="Where to retrieve the amendment in the API."
    )


class BillLatestAction(BaseModel):
    """Latest action metadata attached to a bill list item."""

    action_date: datetime | None = Field(
        default=None,
        alias="actionDate",
        description="When the latest action occurred.",
    )
    text: str | None = Field(
        default=None, description="What the latest action text says."
    )


class LawEntry(BaseModel):
    """Law entry used in law list items (number and type)."""

    number: str | None = Field(
        default=None, description="What the law number is."
    )
    type: str | None = Field(
        default=None, description="What type of law this is (public/private)."
    )


class _BillOrLawListItem(EntityBase, RecordTypeBase):
    """Shared list-item fields for bills and enacted laws."""

    congress: int | None = Field(
        default=None, description="Which Congress the bill belongs to."
    )
    latest_action: BillLatestAction | None = Field(
        default=None, alias="latestAction", description="What the latest action is."
    )
    number: str | None = Field(
        default=None, description="What the bill number is."
    )
    origin_chamber: str | None = Field(
        default=None,
        alias="originChamber",
        description="Which chamber introduced the bill.",
    )
    origin_chamber_code: str | None = Field(
        default=None,
        alias="originChamberCode",
        description="What the origin chamber code is.",
    )
    title: str | None = Field(
        default=None, description="What the bill title is."
    )
    type: str | None = Field(
        default=None, description="What type of bill this is."
    )
    update_date: datetime | None = Field(
        default=None,
        alias="updateDate",
        description="When the bill was last updated.",
    )
    update_date_including_text: datetime | None = Field(
        default=None,
        alias="updateDateIncludingText",
        description="When the bill or its text was last updated.",
    )
    url: HttpUrl | None = Field(
        default=None, description="Where to retrieve the bill in the API."
    )


class BillListItem(_BillOrLawListItem):
    """List-level bill entry with title and latest action."""

    recordType: str = Field(
        default="congress-bills",
        description="Which knowledgebase index this record belongs to.",
    )


class LawListItem(_BillOrLawListItem):
    """List-level law entry derived from bill data."""

    recordType: str = Field(
        default="congress-laws",
        description="Which knowledgebase index this record belongs to.",
    )
    laws: list[LawEntry] | None = Field(
        default=None,
        description="Which law entries are associated with the bill.",
    )


class TreatyListItem(EntityBase, RecordTypeBase):
    """List-level treaty entry with congress and numbering info."""

    recordType: str = Field(
        default="congress-treaties",
        description="Which knowledgebase index this record belongs to.",
    )
    congress_received: int | None = Field(
        default=None,
        alias="congressReceived",
        description="Which Congress received the treaty.",
    )
    congress_considered: int | None = Field(
        default=None,
        alias="congressConsidered",
        description="Which Congress considered the treaty.",
    )
    number: int | None = Field(
        default=None, description="What the treaty number is."
    )
    parts: dict[str, object] | None = Field(
        default=None, description="What parts the treaty is divided into."
    )
    suffix: str | None = Field(
        default=None, description="What suffix the treaty carries."
    )
    topic: str | None = Field(
        default=None, description="What topic the treaty concerns."
    )
    transmitted_date: datetime | None = Field(
        default=None,
        alias="transmittedDate",
        description="When the treaty was transmitted.",
    )
    update_date: datetime | None = Field(
        default=None,
        alias="updateDate",
        description="When the treaty was last updated.",
    )
    url: HttpUrl | None = Field(
        default=None, description="Where to retrieve the treaty in the API."
    )


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
