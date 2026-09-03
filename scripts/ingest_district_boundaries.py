"""Import 119th-Congress district boundaries into OpenSearch once."""

from __future__ import annotations

import sys
from pathlib import Path

import requests
from elasticsearch.helpers import streaming_bulk

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cdm.store.client import get_opensearch_client
from cdm.store.opensearch import write_alias

SOURCE_URL = (
    "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/Legislative/"
    "MapServer/0/query"
)
STATE_FIPS = {
    "AL": "01", "AK": "02", "AZ": "04", "AR": "05", "CA": "06", "CO": "08",
    "CT": "09", "DE": "10", "FL": "12", "GA": "13", "HI": "15", "ID": "16",
    "IL": "17", "IN": "18", "IA": "19", "KS": "20", "KY": "21", "LA": "22",
    "ME": "23", "MD": "24", "MA": "25", "MI": "26", "MN": "27", "MS": "28",
    "MO": "29", "MT": "30", "NE": "31", "NV": "32", "NH": "33", "NJ": "34",
    "NM": "35", "NY": "36", "NC": "37", "ND": "38", "OH": "39", "OK": "40",
    "OR": "41", "PA": "42", "RI": "44", "SC": "45", "SD": "46", "TN": "47",
    "TX": "48", "UT": "49", "VT": "50", "VA": "51", "WA": "53", "WV": "54",
    "WI": "55", "WY": "56", "DC": "11",
}


def main() -> None:
    actions = []
    for state_code, fips in STATE_FIPS.items():
        response = requests.get(
            SOURCE_URL,
            params={"where": f"STATE='{fips}'", "outFields": "*", "f": "geojson"},
            timeout=60,
        )
        response.raise_for_status()
        for feature in response.json()["features"]:
            district_value = str(feature["properties"].get("CD119", ""))
            if not district_value.isdigit():
                continue
            district = int(district_value)
            document = {
                "id": f"district:119:{state_code}:{district}",
                "state_code": state_code,
                "district": district,
                "geometry": feature["geometry"],
            }
            actions.append({"_op_type": "index", "_index": write_alias("district"), "_id": document["id"], "_source": document})
    client = get_opensearch_client()
    indexed = 0
    errors = 0
    for ok, _ in streaming_bulk(
        client.options(request_timeout=120),
        actions,
        chunk_size=1,
        max_chunk_bytes=10_000_000,
        refresh=False,
    ):
        indexed += int(ok)
        errors += int(not ok)
    client.indices.refresh(index=write_alias("district"))
    print(f"indexed={indexed} errors={errors}")


if __name__ == "__main__":
    main()