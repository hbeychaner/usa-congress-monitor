from datetime import UTC, datetime
from functools import lru_cache

from cdm.contracts.api import (
    ChamberTimeline,
    CongressGroup,
    StateSummary,
    StateTimelineResponse,
    TimelineMember,
)
from cdm.store.client import get_opensearch_client
from cdm.store.opensearch import read_alias

_STATE_CODES = {
    "Alabama": "AL",
    "Alaska": "AK",
    "Arizona": "AZ",
    "Arkansas": "AR",
    "California": "CA",
    "Colorado": "CO",
    "Connecticut": "CT",
    "Delaware": "DE",
    "Florida": "FL",
    "Georgia": "GA",
    "Hawaii": "HI",
    "Idaho": "ID",
    "Illinois": "IL",
    "Indiana": "IN",
    "Iowa": "IA",
    "Kansas": "KS",
    "Kentucky": "KY",
    "Louisiana": "LA",
    "Maine": "ME",
    "Maryland": "MD",
    "Massachusetts": "MA",
    "Michigan": "MI",
    "Minnesota": "MN",
    "Mississippi": "MS",
    "Missouri": "MO",
    "Montana": "MT",
    "Nebraska": "NE",
    "Nevada": "NV",
    "New Hampshire": "NH",
    "New Jersey": "NJ",
    "New Mexico": "NM",
    "New York": "NY",
    "North Carolina": "NC",
    "North Dakota": "ND",
    "Ohio": "OH",
    "Oklahoma": "OK",
    "Oregon": "OR",
    "Pennsylvania": "PA",
    "Rhode Island": "RI",
    "South Carolina": "SC",
    "South Dakota": "SD",
    "Tennessee": "TN",
    "Texas": "TX",
    "Utah": "UT",
    "Vermont": "VT",
    "Virginia": "VA",
    "Washington": "WA",
    "West Virginia": "WV",
    "Wisconsin": "WI",
    "Wyoming": "WY",
    "District of Columbia": "DC",
}


def _member_records() -> list[dict]:
    response = get_opensearch_client().search(
        index=read_alias("member"),
        body={"size": 10000, "query": {"match_all": {}}},
    )
    return [hit["_source"] for hit in response["hits"]["hits"]]


def _congress_for_year(year: int) -> int:
    return ((year - 1789) // 2) + 1


def list_states() -> list[StateSummary]:
    names = {str(record.get("state", "")) for record in _member_records()}
    return [
        StateSummary(code=_STATE_CODES[name], name=name)
        for name in sorted(names)
        if name in _STATE_CODES
    ]


@lru_cache(maxsize=64)
def get_state_districts(state_code: str) -> dict:
    response = get_opensearch_client().search(
        index=read_alias("district"),
        body={
            "size": 100,
            "query": {"term": {"state_code": state_code.upper()}},
            "sort": [{"district": "asc"}],
        },
    )
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "id": hit["_source"]["id"],
                "properties": {
                    "state": hit["_source"]["state_code"],
                    "district": hit["_source"]["district"],
                },
                "geometry": hit["_source"]["geometry"],
            }
            for hit in response["hits"]["hits"]
        ],
    }


def get_state_timeline(
    state_code: str, from_congress: int | None, to_congress: int | None
) -> StateTimelineResponse:
    code = state_code.upper()
    selected = next(
        (s for s in list_states() if s.code == code), StateSummary(code=code, name=code)
    )
    house_members: list[TimelineMember] = []
    senate_members: list[TimelineMember] = []
    seen_terms: set[tuple[str, str, int, int]] = set()
    for record in _member_records():
        state = str(record.get("state") or record.get("state_name") or "")
        if _STATE_CODES.get(state) != code:
            continue
        raw_terms = record.get("terms") or {}
        terms = (
            raw_terms if isinstance(raw_terms, list) else raw_terms.get("item") or []
        )
        for term in terms:
            start_year = term.get("start_year")
            end_year = term.get("end_year") or datetime.now(UTC).year
            if not isinstance(start_year, int) or not isinstance(end_year, int):
                continue
            member = TimelineMember(
                bioguide_id=str(record["bioguide_id"]).upper(),
                name=str(
                    record.get("name")
                    or record.get("full_name")
                    or record.get("direct_order_name")
                    or record["bioguide_id"]
                ),
                party=str(record.get("party_name") or record.get("party") or "Unknown"),
                congress_start=_congress_for_year(start_year),
                congress_end=_congress_for_year(end_year),
            )
            chamber_name = str(term.get("chamber", "")).lower()
            chamber_key = "house" if "house" in chamber_name else "senate"
            term_key = (member.bioguide_id, chamber_key, member.congress_start, 0)
            if term_key in seen_terms:
                continue
            seen_terms.add(term_key)
            if "house" in str(term.get("chamber", "")).lower():
                house_members.append(member)
            elif "senate" in str(term.get("chamber", "")).lower():
                senate_members.append(member)

    # Keep filters in place for API contract shape; implementation will become DB-backed.
    if from_congress is not None:
        house_members = [m for m in house_members if m.congress_end >= from_congress]
        senate_members = [m for m in senate_members if m.congress_end >= from_congress]
    if to_congress is not None:
        house_members = [m for m in house_members if m.congress_start <= to_congress]
        senate_members = [m for m in senate_members if m.congress_start <= to_congress]

    def group_members(members: list[TimelineMember]) -> list[CongressGroup]:
        groups: dict[int, dict[str, TimelineMember]] = {}
        for member in members:
            start = max(member.congress_start, from_congress or member.congress_start)
            end = min(member.congress_end, to_congress or member.congress_end)
            for congress in range(start, end + 1):
                groups.setdefault(congress, {}).setdefault(member.bioguide_id, member)
        return [
            CongressGroup(congress=congress, members=list(groups[congress].values()))
            for congress in sorted(groups, reverse=True)
        ]

    return StateTimelineResponse(
        state_code=selected.code,
        state_name=selected.name,
        house=ChamberTimeline(
            chamber="house", members=house_members, groups=group_members(house_members)
        ),
        senate=ChamberTimeline(
            chamber="senate",
            members=senate_members,
            groups=group_members(senate_members),
        ),
    )
