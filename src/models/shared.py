"""Shared small model fragments used across model modules."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Optional

from pydantic import BaseModel, Field, HttpUrl


class Format(BaseModel):
    """Format metadata for a text version (e.g., PDF, HTML)."""

    type: str = Field(description="What format type the text version is.")
    url: HttpUrl = Field(description="Where to retrieve the formatted content.")


class Activity(BaseModel):
    """Committee activity entry with name and date."""

    date: datetime = Field(description="When the committee activity occurred")
    name: str = Field(description="What the committee activity name is.")


class CountUrl(BaseModel):
    """Count and URL pair used by list endpoints."""

    count: int = Field(description="How many items are available.")
    url: HttpUrl = Field(description="Where to retrieve the related list in the API.")
    count_including_withdrawn_cosponsors: Annotated[
        Optional[int], Field(alias="countIncludingWithdrawnCosponsors", default=None)
    ] = None


class Title(BaseModel):
    """Title entry with type, update date, and text version metadata."""

    title: str = Field(description="What the title text is.")
    title_type: str = Field(
        alias="titleType", description="What type of title this is."
    )
    title_type_code: int = Field(
        alias="titleTypeCode", description="What the title type code is."
    )
    update_date: datetime = Field(
        alias="updateDate", description="When the title was last updated."
    )
    bill_text_version_code: str = Field(
        alias="billTextVersionCode",
        default="",
        description="Which bill text version code is referenced.",
    )
    bill_text_version_name: str = Field(
        alias="billTextVersionName",
        default="",
        description="What the bill text version name is.",
    )


class SourceSystem(BaseModel):
    """System metadata indicating the source of an action or record."""

    name: str = Field(description="What the source system name is.")
    code: int = Field(description="What the source system code is.", default=-1)


class Note(BaseModel):
    """Notes container for bill metadata entries."""

    text: str = Field(description="What the note text is.")


class EntityBase(BaseModel):
    """Base class for item models that may provide common identifier fields.

    Concrete models can inherit from this to indicate they represent a single
    entity and may implement or rely on `build_id()` for canonical id logic.
    """

    id: str | None = Field(default=None, description="Canonical identifier")

    def build_id(self) -> str:
        """Return a deterministic identifier for this entity.

        Default heuristics (in order):
        - return the existing ``id`` if present
        - use ``bioguide_id`` (members)
        - compose from ``congress`` + ``type`` + ``number`` (bills/laws)
        - extract the id from a ``url`` using shared validators

        Subclasses may override this to implement domain-specific logic.
        If no heuristic can produce an id, a ``ValueError`` is raised.
        """
        # prefer explicit id when available
        val = getattr(self, "id", None)
        if val:
            return str(val)

        # member-style identifier
        bioguide = getattr(self, "bioguide_id", None) or getattr(
            self, "bioguideId", None
        )
        if bioguide:
            return f"member:{bioguide}"

        # bill/law style identifiers: only compose this form when an
        # explicit `type` is present (bills/laws include a `type` like
        # 'hr'/'s' or 'pub'/'priv'). Avoid assuming 'bill' for arbitrary
        # congress/number pairs which represent other resources.
        congress = getattr(self, "congress", None)
        number = getattr(self, "number", None)
        typ = getattr(self, "type", None)
        if congress is not None and number is not None and typ is not None:
            try:
                t = str(typ).lower()
            except Exception:
                t = "bill"
            return f"bill:{congress}:{t}:{number}"

        # Generic congress/number fallback for non-bill resources. Many
        # list item types (communications, requirements, nominations) have
        # a congress + number but no `type` field; create a deterministic
        # id using the model class name and optional chamber when present.
        if congress is not None and number is not None:
            chamber = getattr(self, "chamber", None)
            # derive a short resource name from recordType when available,
            # otherwise fall back to the model class name.
            record_type = getattr(self, "recordType", None)
            if isinstance(record_type, str) and record_type:
                resource = record_type.replace("congress-", "").replace("-", "_")
            else:
                resource = self.__class__.__name__.lower()
            if chamber:
                return f"{resource}:{congress}:{chamber}:{number}"
            return f"{resource}:{congress}:{number}"

        # try extracting from a URL using the canonical URL parser
        url = getattr(self, "url", None)
        if url:
            from src.data_collection.id_utils import parse_url_to_id

            return parse_url_to_id(str(url))

        raise ValueError(
            f"Could not build canonical id for {self.__class__.__name__}: no id-bioguide-congress/number-or-url present"
        )


class ListMetadataBase(BaseModel):
    """Base class for list response wrappers that include pagination metadata."""

    pagination: dict | None = Field(default=None, description="Pagination info")
