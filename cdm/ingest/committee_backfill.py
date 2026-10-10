"""Backfill committee activities onto indexed bills from archived BILLSTATUS XML."""

from __future__ import annotations

import os
import re
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from elasticsearch import Elasticsearch
from elasticsearch.helpers import streaming_bulk
from pydantic import BaseModel

from cdm.config import GovInfoConfig
from cdm.ingest.govinfo import (
    GovInfoBillStatusParser,
    GovInfoPackage,
    GovInfoParseError,
)
from cdm.store.opensearch import write_alias
from cdm.utils.json_types import JsonObject

_FILE_NAME = re.compile(r"^BILLSTATUS-(?P<congress>\d+)(?P<type>[A-Za-z]+)\d+$")
_REPLACE_COMMITTEES = "ctx._source.committees = params.committees"


class BackfillReport(BaseModel):
    """Counters for one backfill run."""

    files: int = 0
    skipped_unparsable: int = 0
    skipped_no_committees: int = 0
    updated: int = 0
    missing_in_index: int = 0
    errors: int = 0


@dataclass(frozen=True)
class CommitteeUpdate:
    """The replacement committees list for one bill document."""

    bill_id: str
    committees: list[JsonObject]


class BillStatusFiles:
    """Lazily walk package directories for BILLSTATUS XML files."""

    def __init__(self, config: GovInfoConfig) -> None:
        self.config = config

    def __iter__(self) -> Iterator[Path]:
        root = self.config.govinfo_archive_root
        with os.scandir(root) as packages:
            for package in packages:
                directory = Path(package.path) / self.config.govinfo_billstatus_dir
                if not package.is_dir() or not directory.is_dir():
                    continue
                with os.scandir(directory) as entries:
                    for entry in entries:
                        if entry.name.endswith(self.config.govinfo_billstatus_suffix):
                            yield Path(entry.path)


class CommitteeActivityBackfill:
    """Replace each indexed bill's committees with the freshly parsed XML version."""

    def __init__(
        self, client: Elasticsearch, parser: GovInfoBillStatusParser, config: GovInfoConfig
    ) -> None:
        self.client = client
        self.parser = parser
        self.config = config

    def run(self, files: Iterator[Path], limit: int | None = None) -> BackfillReport:
        report = BackfillReport()
        pending: list[JsonObject] = []
        for path in files:
            if limit is not None and report.files >= limit:
                break
            report.files += 1
            update = self._parse(path, report)
            if update is None:
                continue
            pending.append(self._action(update))
            if len(pending) >= self.config.committee_backfill_batch_size:
                self._flush(pending, report)
        self._flush(pending, report)
        return report

    def _parse(self, path: Path, report: BackfillReport) -> CommitteeUpdate | None:
        match = _FILE_NAME.match(path.stem)
        if match is None:
            report.skipped_unparsable += 1
            return None
        package = GovInfoPackage(
            package_id=path.stem,
            collection="BILLSTATUS",
            congress=int(match["congress"]),
            measure_type=match["type"].lower(),
            url="",
        )
        try:
            record = self.parser.parse(path.read_bytes(), package)
        except GovInfoParseError:
            report.skipped_unparsable += 1
            return None
        committees = record.get("committees") or []
        if not committees:
            report.skipped_no_committees += 1
            return None
        return CommitteeUpdate(bill_id=record["id"], committees=committees)

    def _action(self, update: CommitteeUpdate) -> JsonObject:
        return {
            "_op_type": "update",
            "_index": write_alias("bill"),
            "_id": update.bill_id,
            "script": {
                "lang": "painless",
                "source": _REPLACE_COMMITTEES,
                "params": {"committees": update.committees},
            },
        }

    def _flush(self, pending: list[JsonObject], report: BackfillReport) -> None:
        if not pending:
            return
        client = self.client.options(
            request_timeout=self.config.committee_backfill_request_timeout
        )
        for ok, result in streaming_bulk(client, pending, raise_on_error=False):
            if ok:
                report.updated += 1
            elif result.get("update", {}).get("status") == 404:
                report.missing_in_index += 1
            else:
                report.errors += 1
        pending.clear()
