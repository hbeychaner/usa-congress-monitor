"""Set, clear, or list manual metasubject names (versioned in Elasticsearch)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cdm.config import get_config
from cdm.container import Container


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("metasubject_id", type=int, nargs="?")
    parser.add_argument("name", nargs="?", help="New name; omit with --clear")
    parser.add_argument("--clear", action="store_true", help="Remove the override")
    parser.add_argument("--history", action="store_true", help="List stored edits")
    args = parser.parse_args()
    store = Container(get_config()).metasubject_override_store
    if args.history or args.metasubject_id is None:
        for edit in store.history(args.metasubject_id):
            print(f"{edit.metasubject_id} v{edit.version} {edit.created_at:%F} {edit.name}")
        return
    if args.clear:
        print(store.clear(args.metasubject_id))
    elif args.name:
        print(store.set_name(args.metasubject_id, args.name))
    else:
        parser.error("provide a name, --clear, or --history")


if __name__ == "__main__":
    main()
