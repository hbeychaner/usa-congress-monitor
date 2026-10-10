"""Deterministic canonical record identifiers derived from records and URLs."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from enum import StrEnum
from urllib.parse import urlparse

from pydantic import BaseModel

logger = logging.getLogger(__name__)

type Json = Mapping[str, object] | str | int | float | bool | None


class IdPrefix(StrEnum):
    URL = "url"
    PERSON = "person"
    ID = "id"
    BILL = "bill"
    AMENDMENT = "amendment"
    RECORD = "record"


class UrlIdParser:
    """Turns Congress.gov API URLs into stable ids like ``bill:110:hconres:10``."""

    @staticmethod
    def normalize_segment(segment: str) -> str:
        """Numeric segments are kept; others are stripped and lowercased."""
        if segment.isdigit():
            return segment
        return segment.strip().lower()

    @classmethod
    def parse(cls, url: str) -> str:
        """Strip scheme, query and API version token; join normalized segments."""
        if not url:
            return f"{IdPrefix.URL}:"
        parsed = urlparse(url)
        parts = [seg for seg in (parsed.path or "").split("/") if seg]
        if parts and parts[0].lower().startswith("v") and parts[0][1:].isdigit():
            parts = parts[1:]
        if not parts:
            return f"{IdPrefix.URL}:{parsed.netloc}"
        resource = parts[0].lower()
        rest = [cls.normalize_segment(seg) for seg in parts[1:]]
        if rest:
            return f"{resource}:{':'.join(rest)}"
        return resource


class CanonicalIdBuilder:
    """Derives a canonical id from a model, mapping or arbitrary object."""

    BIOGUIDE_KEYS = ("bioguide_id", "bioguide")
    PLAIN_ID_KEYS = ("id", "identifier", "guid")

    def __init__(self, url_parser: type[UrlIdParser] = UrlIdParser) -> None:
        self._url_parser = url_parser

    def build(self, record: BaseModel | Mapping[str, Json] | object) -> str:
        """Prefer ``build_id()``, then id fields, bill/amendment keys, URL, hash."""
        built = self._from_builder(record)
        if built:
            return built
        mapping = self._as_mapping(record)
        for key in (*self.BIOGUIDE_KEYS, *self.PLAIN_ID_KEYS):
            value = mapping.get(key)
            if value:
                prefix = IdPrefix.PERSON if key in self.BIOGUIDE_KEYS else IdPrefix.ID
                return f"{prefix}:{value}"
        if mapping.get("congress") and mapping.get("number"):
            congress, number = str(mapping["congress"]), str(mapping["number"])
            if mapping.get("type"):
                return f"{IdPrefix.BILL}:{congress}:{str(mapping['type']).lower()}:{number}"
            if mapping.get("purpose"):
                return f"{IdPrefix.AMENDMENT}:{congress}:amendment:{number}"
        url = mapping.get("url")
        if url:
            try:
                return self._url_parser.parse(str(url))
            except Exception:
                logger.exception("Failed to parse URL to id fallback: %s", url)
        return f"{IdPrefix.RECORD}:{abs(hash(str(mapping))) % (10**12)}"

    @staticmethod
    def _from_builder(record: object) -> str | None:
        builder = getattr(record, "build_id", None)
        if not callable(builder):
            return None
        try:
            try:
                built = builder()
            except TypeError:
                built = builder(record)
        except (AttributeError, TypeError, ValueError):
            logger.exception("Error calling build_id")
            return None
        return str(built) if built else None

    @staticmethod
    def _as_mapping(record: object) -> Mapping[str, object]:
        if isinstance(record, BaseModel):
            return record.model_dump()
        if isinstance(record, Mapping):
            return record
        try:
            return vars(record)
        except TypeError:
            logger.exception("Failed to convert record to vars()")
            return {}
