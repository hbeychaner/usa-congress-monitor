"""Elasticsearch client factory for the knowledgebase."""

from __future__ import annotations

from elasticsearch import Elasticsearch


def build_client(url: str, api_key: str) -> Elasticsearch:
    """Create an Elasticsearch client using API key auth."""
    if not url:
        raise ValueError("ELASTIC_API_URL is required.")
    if not api_key:
        raise ValueError("ELASTIC_API_KEY is required.")
    return Elasticsearch(url, api_key=api_key, request_timeout=60)
