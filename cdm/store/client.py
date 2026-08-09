"""Connection helpers for the local or hosted OpenSearch-compatible cluster."""

from __future__ import annotations

from typing import Any


def get_opensearch_client(*, url: str | None = None, api_key: str | None = None) -> Any:
    """Create an Elasticsearch-compatible client from explicit or project config."""
    from elasticsearch import Elasticsearch

    if url is None or api_key is None:
        from settings import ES_LOCAL_API_KEY, ES_LOCAL_URL

        url = url or ES_LOCAL_URL
        api_key = api_key or ES_LOCAL_API_KEY

    if not url:
        raise ValueError("OpenSearch URL is not configured")
    if not api_key:
        raise ValueError("OpenSearch API key is not configured")

    return Elasticsearch(url, api_key=api_key)


def check_opensearch_connection(client: Any) -> dict:
    """Return cluster info, raising if the client cannot reach the cluster."""
    return client.info()
