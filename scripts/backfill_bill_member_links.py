"""Backfill searchable member relationship keys on existing bill documents."""

from __future__ import annotations

from elasticsearch.helpers import scan, streaming_bulk

from cdm.store.client import get_opensearch_client
from cdm.store.indexer import _bioguide_ids
from cdm.store.opensearch import read_alias, write_alias


def main() -> None:
    client = get_opensearch_client()
    actions = []
    scanned = 0
    updated = 0
    errors = 0
    for hit in scan(
        client,
        index=read_alias("bill"),
        query={
            "_source": ["id", "sponsors", "cosponsors"],
            "query": {"term": {"source_type": "bill"}},
        },
        request_timeout=120,
    ):
        scanned += 1
        source = hit.get("_source", {})
        actions.append({
            "_op_type": "update",
            "_index": write_alias("bill"),
            "_id": hit["_id"],
            "doc": {
                "sponsor_bioguide_ids": _bioguide_ids(source.get("sponsors")),
                "cosponsor_bioguide_ids": _bioguide_ids(source.get("cosponsors")),
            },
        })
        if len(actions) < 500:
            continue
        for ok, _ in streaming_bulk(
            client.options(request_timeout=120), actions, raise_on_error=False
        ):
            updated += int(ok)
            errors += int(not ok)
        actions.clear()

    if actions:
        for ok, _ in streaming_bulk(
            client.options(request_timeout=120), actions, raise_on_error=False
        ):
            updated += int(ok)
            errors += int(not ok)

    client.indices.refresh(index=write_alias("bill"))
    print(f"scanned={scanned} updated={updated} errors={errors}")


if __name__ == "__main__":
    main()
