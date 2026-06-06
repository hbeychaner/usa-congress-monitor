"""Search helpers and query builder for congress data in OpenSearch."""

from __future__ import annotations

from typing import Any, Optional


def search(
    client: Any,
    resource: str,
    query: Optional[dict] = None,
    size: int = 20,
    from_: int = 0,
) -> dict:
    """Execute a simple match query against the *resource* index.

    Returns the raw Elasticsearch response dict.
    """
    from cdm.store.opensearch import read_alias

    body: dict = {
        "query": query or {"match_all": {}},
        "size": size,
        "from": from_,
    }
    return client.search(index=read_alias(resource), body=body)
