import json

from congress_sdk.data_collection.id_utils import canonical_id

with open("data/bills_ingest2/items.json") as f:
    items = json.load(f)

for i, rec in enumerate(items[:10], 1):
    print(i, canonical_id(rec))
