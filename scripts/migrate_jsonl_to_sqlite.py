"""Migrate legacy ingest JSONL archives to compact SQLite archives."""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from tqdm import tqdm

from cdm.ingest.archive import SQLiteListCache, SQLiteRecordArchive


def _iter_json_array(path: Path) -> Iterator[dict[str, Any]]:
    decoder = json.JSONDecoder()
    with path.open(encoding="utf-8") as handle:
        buffer = ""
        position = 0
        first = True
        while True:
            chunk = handle.read(1024 * 1024)
            if chunk:
                buffer += chunk
            elif position >= len(buffer):
                break
            while True:
                while position < len(buffer) and buffer[position].isspace():
                    position += 1
                if first:
                    if position >= len(buffer):
                        break
                    if buffer[position] != "[":
                        raise ValueError(f"Expected JSON array in {path}")
                    position += 1
                    first = False
                while position < len(buffer) and buffer[position].isspace():
                    position += 1
                if position < len(buffer) and buffer[position] == "]":
                    return
                if position < len(buffer) and buffer[position] == ",":
                    position += 1
                    continue
                try:
                    value, end = decoder.raw_decode(buffer, position)
                except json.JSONDecodeError:
                    if chunk:
                        break
                    raise ValueError(f"Invalid JSON array in {path}")
                if not isinstance(value, dict):
                    raise TypeError(f"Expected object in {path}")
                yield value
                position = end
                while position < len(buffer) and buffer[position].isspace():
                    position += 1
                if position < len(buffer) and buffer[position] == ",":
                    position += 1
                    continue
                if position < len(buffer) and buffer[position] == "]":
                    return
                if position >= len(buffer):
                    break
                raise ValueError(f"Invalid JSON array in {path}")
            if position:
                buffer = buffer[position:]
                position = 0


def migrate(
    root: Path, delete_source: bool = False, pause_seconds: float = 0.25
) -> tuple[int, int]:
    if pause_seconds < 0:
        raise ValueError("pause_seconds must be non-negative")
    item_files = list(root.rglob("records-attempt-*.jsonl"))
    item_files.extend(root.rglob("items.jsonl"))
    list_files = list(root.rglob("list_records.jsonl"))
    array_files = []
    for pattern in ("items.json", "list.json", "raw_list.json"):
        array_files.extend(root.rglob(pattern))
    migrated_items = 0
    migrated_lists = 0
    sources = item_files + list_files + array_files
    total_bytes = sum(source.stat().st_size for source in sources)
    progress = tqdm(
        total=total_bytes,
        desc="Migrating source files",
        unit="B",
        unit_scale=True,
        unit_divisor=1024,
        disable=not sys.stderr.isatty(),
    )
    completed = 0

    try:
        for source in item_files:
            source_size = source.stat().st_size
            archive = SQLiteRecordArchive(source.parent, attempt=0)
            resource = source.parent.name
            item_batch: list[dict[str, Any]] = []
            with source.open(encoding="utf-8") as handle:
                for line_number, line in enumerate(handle, 1):
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError as exc:
                        raise ValueError(
                            f"Invalid JSON in {source}:{line_number}"
                        ) from exc
                    if not isinstance(record, dict):
                        raise TypeError(f"Expected object in {source}:{line_number}")
                    item_batch.append(record)
                    if len(item_batch) >= 500:
                        archive.write_many(resource, item_batch)
                        migrated_items += len(item_batch)
                        item_batch = []
                        time.sleep(pause_seconds)
            if item_batch:
                archive.write_many(resource, item_batch)
                migrated_items += len(item_batch)
            if delete_source:
                source.unlink()
            completed += 1
            progress.update(source_size)
            progress.set_postfix(files=f"{completed}/{len(sources)}")

        for source in list_files:
            source_size = source.stat().st_size
            target = source.with_name("list_records.sqlite3")
            cache = SQLiteListCache(target)
            list_batch: list[tuple[int, dict[str, Any]]] = []
            with source.open(encoding="utf-8") as handle:
                for line_number, line in enumerate(handle, 1):
                    try:
                        entry = json.loads(line)
                        offset = int(entry["offset"])
                        record = entry["record"]
                    except (
                        KeyError,
                        TypeError,
                        ValueError,
                        json.JSONDecodeError,
                    ) as exc:
                        raise ValueError(
                            f"Invalid list cache in {source}:{line_number}"
                        ) from exc
                    if not isinstance(record, dict):
                        raise TypeError(
                            f"Expected record object in {source}:{line_number}"
                        )
                    list_batch.append((offset, record))
                    if len(list_batch) >= 500:
                        cache.write_many(list_batch)
                        migrated_lists += len(list_batch)
                        list_batch = []
                        time.sleep(pause_seconds)
            if list_batch:
                cache.write_many(list_batch)
                migrated_lists += len(list_batch)
            if delete_source:
                source.unlink()
            completed += 1
            progress.update(source_size)
            progress.set_postfix(files=f"{completed}/{len(sources)}")

        for source in array_files:
            source_size = source.stat().st_size
            archive = SQLiteRecordArchive(source.parent, attempt=0)
            resource = source.parent.name
            batch: list[dict[str, Any]] = []
            count = 0
            for record in _iter_json_array(source):
                batch.append(record)
                count += 1
                if len(batch) >= 500:
                    archive.write_many(resource, batch)
                    batch = []
                    time.sleep(pause_seconds)
            if batch:
                archive.write_many(resource, batch)
            if delete_source:
                source.unlink()
            migrated_items += count
            completed += 1
            progress.update(source_size)
            progress.set_postfix(files=f"{completed}/{len(sources)}")
    finally:
        progress.close()

    return migrated_items, migrated_lists


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path, help="Data directory to migrate")
    parser.add_argument("--delete-source", action="store_true")
    parser.add_argument(
        "--pause-seconds",
        type=float,
        default=0.25,
        help="Pause after each 500-record write (default: 0.25)",
    )
    args = parser.parse_args()
    items, lists = migrate(args.root, args.delete_source, args.pause_seconds)
    print(f"migrated item rows: {items}; list-cache rows: {lists}")


if __name__ == "__main__":
    main()
