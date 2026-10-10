"""Roll-call votes with per-member positions from Voteview bulk CSVs.

One document per roll call; member positions are stored as keyword id arrays so
a congress (about 2k roll calls) stays small and "who voted yea" is a term query.
"""

from __future__ import annotations

import csv
import datetime as dt
import re
from collections import Counter, defaultdict
from collections.abc import Iterator
from enum import StrEnum
from pathlib import Path
from typing import Any, ClassVar

import requests
from elasticsearch import Elasticsearch
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
    field_validator,
)

from cdm.store.opensearch import bulk_upsert

FIRST_CONGRESS = 113


class Chamber(StrEnum):
    HOUSE = "house"
    SENATE = "senate"

    @property
    def file_prefix(self) -> str:
        return self.value[0].upper()


class MemberChamber(StrEnum):
    """Chamber label on a Voteview member row, which also lists the President."""

    HOUSE = "house"
    SENATE = "senate"
    PRESIDENT = "president"


class CsvKind(StrEnum):
    MEMBERS = "members"
    ROLLCALLS = "rollcalls"
    VOTES = "votes"


class Position(StrEnum):
    YEA = "yea"
    NAY = "nay"
    PRESENT = "present"
    NOT_VOTING = "not_voting"

    @classmethod
    def from_cast_code(cls, code: int) -> Position:
        """Voteview codes: 1-3 yea (incl. paired/announced), 4-6 nay, 7-8 present."""
        if 1 <= code <= 3:
            return cls.YEA
        if 4 <= code <= 6:
            return cls.NAY
        if code in (7, 8):
            return cls.PRESENT
        return cls.NOT_VOTING


class Party(StrEnum):
    DEMOCRAT = "D"
    REPUBLICAN = "R"
    OTHER = "I"

    @classmethod
    def from_code(cls, code: int) -> Party:
        return _PARTY_BY_CODE.get(code, cls.OTHER)


_PARTY_BY_CODE: dict[int, Party] = {100: Party.DEMOCRAT, 200: Party.REPUBLICAN}
_MAJOR_PARTIES = (Party.DEMOCRAT, Party.REPUBLICAN)


def current_congress(year: int) -> int:
    return (year - 1787) // 2


class CsvRow(BaseModel):
    """Base for typed Voteview CSV rows; empty cells become None."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    @field_validator("*", mode="before")
    @classmethod
    def _blank_to_none(cls, value: object) -> object:
        return None if value == "" else value


class MemberRow(CsvRow):
    chamber: MemberChamber
    icpsr: str
    party_code: float | None = None
    bioguide_id: str | None = None

    @field_validator("chamber", mode="before")
    @classmethod
    def _lower(cls, value: object) -> object:
        return value.lower() if isinstance(value, str) else value

    @property
    def party(self) -> Party:
        return Party.from_code(int(self.party_code or 0))


class RollCallRow(CsvRow):
    congress: int
    chamber: Chamber
    roll_number: int = Field(alias="rollnumber")
    session_number: int | None = Field(default=None, alias="session")
    clerk_roll_number: int | None = Field(default=None, alias="clerk_rollnumber")
    date: dt.date | None = None
    bill_number: str | None = None
    result: str | None = Field(default=None, alias="vote_result")
    vote_desc: str | None = None
    question: str | None = Field(default=None, alias="vote_question")
    dtl_desc: str | None = None

    @field_validator("chamber", mode="before")
    @classmethod
    def _lower(cls, value: object) -> object:
        return value.lower() if isinstance(value, str) else value

    @property
    def description(self) -> str | None:
        return self.vote_desc or self.dtl_desc


class VoteRow(CsvRow):
    roll_number: int = Field(alias="rollnumber")
    icpsr: str
    cast_code: int

    @property
    def position(self) -> Position:
        return Position.from_cast_code(self.cast_code)


class Member(BaseModel):
    model_config = ConfigDict(frozen=True)

    bioguide_id: str
    party: Party


class CsvFile(BaseModel):
    """One cached Voteview CSV for a chamber and congress."""

    model_config = ConfigDict(frozen=True)

    kind: CsvKind
    chamber: Chamber
    congress: int

    @property
    def name(self) -> str:
        return f"{self.chamber.file_prefix}{self.congress}_{self.kind}.csv"


class CsvReader[RowT: CsvRow]:
    """Streams a CSV file as validated row models."""

    def __init__(self, row_type: type[RowT]) -> None:
        self.row_type = row_type

    def read(self, path: Path) -> Iterator[RowT]:
        with path.open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                yield self.row_type.model_validate(row)


class VoteviewClient:
    """Downloads Voteview CSVs into a local cache directory."""

    BASE_URL = "https://voteview.com/static/data/out"

    def __init__(
        self,
        cache_dir: Path,
        *,
        session: requests.Session | None = None,
        timeout: int = 120,
    ) -> None:
        self.cache_dir = cache_dir
        self.session = session or requests.Session()
        self.timeout = timeout

    def fetch(self, csv_file: CsvFile, *, refresh: bool = False) -> Path:
        path = self.cache_dir / csv_file.name
        if path.exists() and not refresh:
            return path
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        response = self.session.get(
            f"{self.BASE_URL}/{csv_file.kind}/{csv_file.name}",
            timeout=self.timeout,
        )
        response.raise_for_status()
        partial = path.with_suffix(".tmp")
        partial.write_bytes(response.content)
        partial.replace(path)
        return path


class RollCallDocument(BaseModel):
    """An indexed roll call; ``positions`` is serialized as per-position id lists."""

    RECORD_TYPE: ClassVar[str] = "voteview-rollcalls"
    _BILL_NUMBER: ClassVar[re.Pattern[str]] = re.compile(r"^([A-Z]+)(\d+)$")

    congress: int
    chamber: Chamber
    roll_number: int
    session_number: int | None = None
    clerk_roll_number: int | None = None
    date: dt.date | None = None
    question: str | None = None
    description: str | None = None
    result: str | None = None
    bill_number: str | None = None
    positions: dict[Position, list[str]] = Field(
        default_factory=lambda: {position: [] for position in Position},
        exclude=True,
    )
    party_positions: dict[Party, Position] = Field(default_factory=dict)
    party_split: bool = False
    defector_ids: list[str] = Field(default_factory=list)

    @computed_field
    @property
    def id(self) -> str:
        return f"rollcall:{self.congress}:{self.chamber}:{self.roll_number}"

    @computed_field
    @property
    def record_type(self) -> str:
        return self.RECORD_TYPE

    @computed_field
    @property
    def legislation_id(self) -> str | None:
        """Map a Voteview bill label such as HR5 to ``bill:{congress}:hr:5``."""
        match = self._BILL_NUMBER.match((self.bill_number or "").strip().upper())
        if not match:
            return None
        return f"bill:{self.congress}:{match.group(1).lower()}:{int(match.group(2))}"

    @computed_field
    @property
    def yea_ids(self) -> list[str]:
        return self.positions[Position.YEA]

    @computed_field
    @property
    def nay_ids(self) -> list[str]:
        return self.positions[Position.NAY]

    @computed_field
    @property
    def present_ids(self) -> list[str]:
        return self.positions[Position.PRESENT]

    @computed_field
    @property
    def not_voting_ids(self) -> list[str]:
        return self.positions[Position.NOT_VOTING]

    @computed_field
    @property
    def yea_count(self) -> int:
        return len(self.yea_ids)

    @computed_field
    @property
    def nay_count(self) -> int:
        return len(self.nay_ids)

    def apply_party_analysis(self, parties: dict[str, Party]) -> None:
        """Derive party majorities, the party-split flag and defectors."""
        tallies: dict[Party, Counter[Position]] = defaultdict(Counter)
        for position, ids in self.positions.items():
            for bioguide_id in ids:
                tallies[parties[bioguide_id]][position] += 1

        for party in _MAJOR_PARTIES:
            yea, nay = tallies[party][Position.YEA], tallies[party][Position.NAY]
            if yea != nay:
                self.party_positions[party] = Position.YEA if yea > nay else Position.NAY

        self.party_split = (
            len(self.party_positions) == len(_MAJOR_PARTIES)
            and len(set(self.party_positions.values())) > 1
        )
        if not self.party_split:
            return
        for position in (Position.YEA, Position.NAY):
            for bioguide_id in self.positions[position]:
                expected = self.party_positions.get(parties[bioguide_id])
                if expected is not None and expected != position:
                    self.defector_ids.append(bioguide_id)

    def to_index_document(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class RollCallBuilder:
    """Builds roll calls for one chamber and congress from its three CSVs."""

    def __init__(self, members: Path, rollcalls: Path, votes: Path) -> None:
        self.members_path = members
        self.rollcalls_path = rollcalls
        self.votes_path = votes

    def _load_members(self) -> dict[str, Member]:
        members: dict[str, Member] = {}
        for row in CsvReader(MemberRow).read(self.members_path):
            if row.chamber is MemberChamber.PRESIDENT or not row.bioguide_id:
                continue
            members[row.icpsr] = Member(bioguide_id=row.bioguide_id, party=row.party)
        return members

    def _load_positions(
        self, members: dict[str, Member]
    ) -> dict[int, list[tuple[str, Position]]]:
        positions: dict[int, list[tuple[str, Position]]] = defaultdict(list)
        for row in CsvReader(VoteRow).read(self.votes_path):
            member = members.get(row.icpsr)
            if member is not None:
                positions[row.roll_number].append((member.bioguide_id, row.position))
        return positions

    def build(self) -> Iterator[RollCallDocument]:
        members = self._load_members()
        positions = self._load_positions(members)
        parties = {member.bioguide_id: member.party for member in members.values()}
        for row in CsvReader(RollCallRow).read(self.rollcalls_path):
            document = RollCallDocument(
                **row.model_dump(exclude={"vote_desc", "dtl_desc"}),
                description=row.description,
            )
            for bioguide_id, position in positions.get(row.roll_number, []):
                document.positions[position].append(bioguide_id)
            document.apply_party_analysis(parties)
            yield document


class VoteIngestor:
    """Downloads, builds and bulk-replaces roll calls in the rollcall index."""

    def __init__(self, client: Elasticsearch, voteview: VoteviewClient) -> None:
        self.client = client
        self.voteview = voteview

    def ingest_congress(self, congress: int, *, refresh: bool = False) -> int:
        total = 0
        for chamber in Chamber:
            paths = {
                kind: self.voteview.fetch(
                    CsvFile(kind=kind, chamber=chamber, congress=congress),
                    refresh=refresh,
                )
                for kind in CsvKind
            }
            builder = RollCallBuilder(
                paths[CsvKind.MEMBERS], paths[CsvKind.ROLLCALLS], paths[CsvKind.VOTES]
            )
            result = bulk_upsert(
                self.client,
                "rollcall",
                (document.to_index_document() for document in builder.build()),
                replace=True,
            )
            if result.get("errors"):
                raise RuntimeError(
                    f"rollcall bulk errors: {result.get('error_details')}"
                )
            total += int(result["updated"])
        return total

    def ingest_range(
        self, congresses: range | list[int], *, refresh: bool = False
    ) -> dict[int, int]:
        current = current_congress(dt.datetime.now(dt.UTC).year)
        return {
            congress: self.ingest_congress(
                congress,
                # The current congress changes daily, so always refresh it.
                refresh=refresh or congress == current,
            )
            for congress in congresses
        }
