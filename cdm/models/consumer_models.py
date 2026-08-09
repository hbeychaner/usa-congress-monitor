"""Small models used by the consumer core for structured returns.

These are intentionally lightweight and meant to live alongside the existing
endpoint-specific models in `cdm/models`.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class ParsedResponse(BaseModel):
    """Canonical wrapper for parsed API responses used by consumers.

    Attributes:
        raw: The original JSON mapping returned by the API.
        records: The extracted list of record mappings for downstream processing.
    """

    raw: dict[str, Any]
    records: list[dict[str, Any]]
