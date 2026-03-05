"""Script to reset all chunk statuses in congress-progress-tracking to 'pending'."""

import asyncio
from knowledgebase.client import build_client
from knowledgebase.progress import TRACKING_INDEX
from settings import ELASTIC_API_URL, ELASTIC_API_KEY


async def reset_all_pending():
    from elasticsearch import AsyncElasticsearch

    es = build_client(ELASTIC_API_URL, ELASTIC_API_KEY)
    # Get all chunk docs
    resp = await es.search(index=TRACKING_INDEX, query={"match_all": {}}, size=10000)
    for hit in resp["hits"]["hits"]:
        doc = hit["_source"]
        doc_id = hit["_id"]
        # Only reset if not already pending
        if doc.get("status") != "pending":
            doc["status"] = "pending"
            await es.index(index=TRACKING_INDEX, id=doc_id, document=doc)
    await es.close()
    print("All chunk statuses reset to 'pending'.")


if __name__ == "__main__":
    asyncio.run(reset_all_pending())
