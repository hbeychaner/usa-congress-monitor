"""Spec-driven id/reference population helpers.

This module provides a small helper that applies an endpoint's
`id_strategy` (when present) to a coerced Pydantic model instance.
It is intentionally conservative: it will not raise on failures and
prefers model-level `build_id()` when available.
"""

from __future__ import annotations

from typing import Mapping, Any

from pydantic import BaseModel
from src.models.endpoint_spec import EndpointSpec

from src.data_collection.id_utils import parse_url_to_id
import logging

logger = logging.getLogger(__name__)


def _resolve_path(mapping: Mapping[str, Any] | BaseModel | None, path: str):
    """Resolve a dotted path (supports list indices) from a mapping or model."""
    if mapping is None or not path:
        return None
    if isinstance(mapping, BaseModel):
        try:
            mapping = mapping.model_dump()
        except Exception:
            try:
                mapping = vars(mapping)
            except Exception:
                mapping = {}

    parts = path.split(".")
    v = mapping
    for part in parts:
        if v is None:
            return None
        if isinstance(v, list):
            if part.isdigit():
                idx = int(part)
                if 0 <= idx < len(v):
                    v = v[idx]
                else:
                    return None
            else:
                return None
        elif isinstance(v, dict):
            v = v.get(part)
        else:
            return None
    return v


def apply_id_strategy(inst: BaseModel, original: Mapping[str, Any] | None, spec) -> BaseModel:
    """Apply `spec.id_strategy` to `inst` and return possibly-updated instance.

    - ensures `reference_id` (model field) is populated from URL when requested
    - ensures `id` is unique by appending section start/end when present

    This function never raises; failures are logged by callers instead.
    """
    strategy = getattr(spec, "id_strategy", None)
    # nothing to do
    if not strategy:
        return inst

    # allow either the typed IdStrategy model or a plain mapping
    if isinstance(strategy, BaseModel):
        strat = strategy.model_dump()
    elif isinstance(strategy, dict):
        strat = strategy
    else:
        # unknown shape
        try:
            strat = dict(strategy)
        except Exception:
            logger.exception("Failed to coerce id_strategy to dict: %s", strategy)
            return inst

    updates: dict[str, Any] = {}

    # reference id
    try:
        if strat.get("reference_from") == "url":
            # prefer explicit reference_id field if present
            if not getattr(inst, "reference_id", None):
                url = getattr(inst, "url", None)
                if url:
                    try:
                        updates["reference_id"] = parse_url_to_id(str(url))
                    except Exception as exc:
                        logger.exception("Failed to parse reference id from url: %s", exc)
    except Exception:
        logger.exception("Error applying reference_from id_strategy: %s", strat)

    # base id: try existing id or model build_id
    base_id = None
    try:
        if getattr(inst, "id", None):
            base_id = str(getattr(inst, "id"))
        else:
            builder = getattr(inst, "build_id", None)
            if callable(builder):
                try:
                    base_id = builder()
                except Exception:
                    try:
                        base_id = builder(inst)
                    except Exception:
                            logger.exception("Error calling build_id on instance with arg")
                            base_id = None
            if not base_id:
                # fallback to reference id parsed from url when available
                url = getattr(inst, "url", None)
                if url:
                    base_id = parse_url_to_id(str(url))
    except Exception:
        logger.exception("Error resolving base id for instance: %s", inst)
        base_id = None

    # section bounds
    try:
        sb_path = strat.get("section_bounds")
        if sb_path and base_id:
            # resolve startPage/endPage from original record first, then instance
            target = None
            if original:
                target = _resolve_path(original, sb_path)
            if target is None:
                target = _resolve_path(inst, sb_path)
            if isinstance(target, dict):
                sp = target.get("startPage")
                ep = target.get("endPage")
                if sp is not None and ep is not None:
                    try:
                        new_id = f"{base_id}:{int(sp)}:{int(ep)}"
                        updates["id"] = new_id
                    except Exception:
                        logger.exception("Failed to coerce section bounds to ints: %s/%s", sp, ep)
    except Exception:
        logger.exception("Error applying section bounds id_strategy: %s", strat)

    if updates:
        try:
            inst = inst.model_copy(update=updates)
        except Exception:
            logger.exception("Failed to model_copy with id updates, falling back to setattr")
            for k, v in updates.items():
                try:
                    setattr(inst, k, v)
                except Exception as exc:
                    logger.exception("Failed to setattr %s on instance: %s", k, exc)

    return inst
