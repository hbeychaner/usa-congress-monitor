"""Applies an endpoint's ``id_strategy`` to a coerced model instance.

Conservative by design: failures are logged and the instance is returned
unchanged rather than raised.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping

from pydantic import BaseModel

from cdm.data_collection.id_utils import UrlIdParser
from cdm.models.endpoint_spec import EndpointSpec, ReferenceSource

logger = logging.getLogger(__name__)

type Node = object


class IdStrategyApplier:
    """Populates ``reference_id`` and section-qualified ``id`` on instances."""

    def __init__(self, url_parser: type[UrlIdParser] = UrlIdParser) -> None:
        self._url_parser = url_parser

    @staticmethod
    def resolve_path(
        source: Mapping[str, object] | BaseModel | None, path: str
    ) -> Node:
        """Resolve a dotted path (with list indices) from a mapping or model."""
        if source is None or not path:
            return None
        node: Node = source.model_dump() if isinstance(source, BaseModel) else source
        for part in path.split("."):
            if isinstance(node, list):
                index = int(part) if part.isdigit() else len(node)
                if index >= len(node):
                    return None
                node = node[index]
            elif isinstance(node, Mapping):
                node = node.get(part)
            else:
                return None
        return node

    def apply[T: BaseModel](
        self, inst: T, original: Mapping[str, object] | None, spec: EndpointSpec
    ) -> T:
        """Return ``inst`` with id updates from ``spec.id_strategy`` applied."""
        strategy = spec.id_strategy
        if strategy is None:
            return inst
        updates: dict[str, str] = {}
        url = getattr(inst, "url", None)
        if (
            strategy.reference_from == ReferenceSource.URL
            and url
            and not getattr(inst, "reference_id", None)
        ):
            try:
                updates["reference_id"] = self._url_parser.parse(str(url))
            except (TypeError, ValueError):
                logger.exception("Failed to parse reference id from url")
        base_id = self._base_id(inst, url)
        if strategy.section_bounds and base_id:
            section_id = self._section_id(
                inst, original, strategy.section_bounds, base_id
            )
            if section_id:
                updates["id"] = section_id
        return inst.model_copy(update=updates) if updates else inst

    def _base_id(self, inst: BaseModel, url: object) -> str | None:
        existing = getattr(inst, "id", None)
        if existing:
            return str(existing)
        builder = getattr(inst, "build_id", None)
        if callable(builder):
            try:
                built = builder()
            except (AttributeError, TypeError, ValueError):
                logger.exception("Error calling build_id on instance")
                built = None
            if built:
                return str(built)
        return self._url_parser.parse(str(url)) if url else None

    def _section_id(
        self,
        inst: BaseModel,
        original: Mapping[str, object] | None,
        path: str,
        base_id: str,
    ) -> str | None:
        target = self.resolve_path(original, path) if original else None
        if target is None:
            target = self.resolve_path(inst, path)
        if not isinstance(target, Mapping):
            return None
        start, end = target.get("startPage"), target.get("endPage")
        if start is None or end is None:
            return None
        try:
            return f"{base_id}:{int(str(start))}:{int(str(end))}"
        except (TypeError, ValueError):
            logger.exception("Failed to coerce section bounds: %s/%s", start, end)
            return None
