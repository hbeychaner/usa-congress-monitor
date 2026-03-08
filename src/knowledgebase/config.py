"""Configuration helpers for the knowledgebase."""

from __future__ import annotations

from dataclasses import dataclass

from settings import ELASTIC_API_KEY, ELASTIC_API_URL


@dataclass
class ElasticConfig:
    """Configuration for Elasticsearch connectivity."""

    url: str
    api_key: str


def load_config() -> ElasticConfig:
    """Load Elasticsearch config from environment variables."""
    return ElasticConfig(url=ELASTIC_API_URL, api_key=ELASTIC_API_KEY)
