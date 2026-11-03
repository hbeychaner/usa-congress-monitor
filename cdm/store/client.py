"""Connection helpers for the local or hosted OpenSearch-compatible cluster."""

from __future__ import annotations

from elasticsearch import Elasticsearch
from pydantic import AliasPath, BaseModel, Field

from cdm.config import ElasticConfig, get_config
from cdm.utils.json_types import JsonObject


class SearchConfigurationError(ValueError):
    pass


class IncompleteSearchError(RuntimeError):
    pass


class SearchCompletion(BaseModel):
    timed_out: bool
    failed_shards: int = Field(ge=0, validation_alias=AliasPath("_shards", "failed"))

    def require_complete(self) -> None:
        if self.timed_out or self.failed_shards:
            raise IncompleteSearchError("Search returned incomplete results")


class ElasticClientFactory:
    """Builds Elasticsearch clients from injected connection settings."""

    def __init__(self, config: ElasticConfig) -> None:
        self.config = config

    def create(
        self, *, url: str | None = None, api_key: str | None = None
    ) -> Elasticsearch:
        url = url or self.config.es_local_url
        api_key = api_key or self.config.es_local_api_key
        if not url:
            raise SearchConfigurationError("OpenSearch URL is not configured")
        if not api_key:
            raise SearchConfigurationError("OpenSearch API key is not configured")
        try:
            return Elasticsearch(url, api_key=api_key)
        except ValueError as exc:
            raise SearchConfigurationError(
                "Search client configuration is invalid"
            ) from exc


def get_opensearch_client(
    *, url: str | None = None, api_key: str | None = None
) -> Elasticsearch:
    """Client from the process-wide config; prefer injecting a client instead."""
    return ElasticClientFactory(get_config().elastic).create(url=url, api_key=api_key)


def check_opensearch_connection(client: Elasticsearch) -> JsonObject:
    """Return cluster info, raising if the client cannot reach the cluster."""
    return client.info().body
