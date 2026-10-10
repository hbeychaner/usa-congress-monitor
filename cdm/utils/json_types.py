"""Recursive JSON value types for payloads that are genuinely schemaless."""

from __future__ import annotations

type JsonValue = str | int | float | bool | None | list[JsonValue] | dict[str, JsonValue]
type JsonObject = dict[str, JsonValue]
