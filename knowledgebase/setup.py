"""Index setup utilities (create/delete) for the knowledgebase."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from elasticsearch import ApiError, Elasticsearch, NotFoundError

ELSER_ENDPOINT_ID = "my-elser-endpoint"
ELSER_MODEL_ID = ".elser_model_2"


@dataclass
class IndexSpec:
    """Index specification with settings and mappings."""

    name: str
    mapping: dict[str, Any]


class KnowledgebaseSetup:
    """Create and delete Elasticsearch indices used by the knowledgebase."""

    def __init__(self, client: Elasticsearch) -> None:
        self.client = client

    def create_index(self, spec: IndexSpec) -> None:
        """Create an index if it does not exist."""
        if self.client.indices.exists(index=spec.name):
            return
        self.client.indices.create(
            index=spec.name,
            settings=spec.mapping.get("settings", {}),
            mappings=spec.mapping.get("mappings", {}),
        )

    def delete_index(self, name: str) -> None:
        """Delete an index if it exists."""
        if not self.client.indices.exists(index=name):
            return
        self.client.indices.delete(index=name)

    def ensure_indices(self, specs: list[IndexSpec]) -> None:
        """Create multiple indices when missing."""
        for spec in specs:
            self.create_index(spec)

    def delete_indices(self, names: list[str]) -> None:
        """Delete multiple indices when present."""
        for name in names:
            self.delete_index(name)
