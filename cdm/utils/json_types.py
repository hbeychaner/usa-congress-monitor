"""Recursive JSON value types for payloads that are genuinely schemaless."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

# Covariant containers let typed lists and dicts be used wherever JSON is expected.
type JsonValue = (
    str | int | float | bool | None | Sequence[JsonValue] | Mapping[str, JsonValue]
)
type JsonObject = dict[str, JsonValue]
