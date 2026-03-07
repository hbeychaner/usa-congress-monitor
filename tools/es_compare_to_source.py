import os
from dotenv import load_dotenv
from knowledgebase.config import load_config
from knowledgebase.client import build_client
from elasticsearch import AsyncElasticsearch
import asyncio
import glob
import json

# Load environment variables
load_dotenv()
config = load_config()

async def main():
    client = build_client(config.url, config.api_key)
    indices = [
        "congress-bills",
        "congress-summaries",
        "congress-house-votes",
        "congress-progress-tracking"
    ]
    for index in indices:
        try:
            count = await client.count(index=index)
            print(f"Index '{index}': {count['count']} documents")
        except Exception as e:
            print(f"Error querying index '{index}': {e}")
    # Compare to daily_output_7d source files
    print("\n--- Daily Output 7d ---")
    for endpoint in ["bill", "summaries", "house-vote"]:
        path = f"daily_output_7d/{endpoint}/list.json"
        try:
            with open(path, "r") as f:
                data = json.load(f)
            print(f"Source '{endpoint}': {len(data)} records")
        except Exception as e:
            print(f"Error reading source '{endpoint}': {e}")
    await client.close()

if __name__ == "__main__":
    asyncio.run(main())
