"""Connection helpers for the local or hosted OpenSearch-compatible cluster."""

from __future__ import annotations

from typing import Any

from elasticsearch import Elasticsearch

from cdm.config import ElasticConfig, get_config


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
            raise ValueError("OpenSearch URL is not configured")
        if not api_key:
            raise ValueError("OpenSearch API key is not configured")
        return Elasticsearch(url, api_key=api_key)


def get_opensearch_client(*, url: str | None = None, api_key: str | None = None) -> Any:
    """Client from the process-wide config; prefer injecting a client instead."""
    return ElasticClientFactory(get_config().elastic).create(url=url, api_key=api_key)


def check_opensearch_connection(client: Any) -> dict:
    """Return cluster info, raising if the client cannot reach the cluster."""
    return client.info()
