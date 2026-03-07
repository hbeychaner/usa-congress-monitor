"""Small models used by the consumer core for structured returns.

These are intentionally lightweight and meant to live alongside the existing
endpoint-specific models in `src/models`.
"""
from __future__ import annotations

from pydantic import BaseModel
from typing import Any, List, Dict


class ParsedResponse(BaseModel):
    raw: Dict[str, Any]
    records: List[Dict[str, Any]]
