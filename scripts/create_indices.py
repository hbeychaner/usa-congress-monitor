#!/usr/bin/env python3
"""CLI: create or update OpenSearch indices from opensearch_mappings.yaml.

Usage
─────
    # Create all 17 indices (skip already-existing)
    uv run scripts/create_indices.py

    # Create a single index
    uv run scripts/create_indices.py --index legislation

    # Update mappings on an existing index (adds new fields; safe)
    uv run scripts/create_indices.py --update

    # Update a single index
    uv run scripts/create_indices.py --update --index sponsorship

    # Show status of all indices without touching anything
    uv run scripts/create_indices.py --status

    # Dry run (print what would happen)
    uv run scripts/create_indices.py --dry-run

Options
───────
    --index NAME   Target a single logical index name (default: all)
    --update       Push updated mappings onto existing indices
    --status       Print index status table and exit
    --dry-run      Print actions without executing them
    --url URL      OpenSearch base URL (default: http://localhost:9200)
    --user USER    Basic-auth username (default: admin)
    --password PW  Basic-auth password (default: from OPENSEARCH_PASSWORD env)
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# ── ensure repo root is on sys.path ──────────────────────────────────────────
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def _load_env_defaults() -> dict:
    """Load OpenSearch connection defaults from .env / settings."""
    try:
        import settings as _s  # root settings.py loads .env

        return {
            "api_key": getattr(_s, "ELASTIC_API_KEY", None)
            or os.environ.get("ELASTIC_API_KEY"),
            "url": getattr(_s, "ELASTIC_API_URL", None)
            or os.environ.get("ELASTIC_API_URL", "http://localhost:9200"),
            "password": os.environ.get("ES_LOCAL_PASSWORD", "admin"),
        }
    except ImportError:
        return {
            "api_key": os.environ.get("ELASTIC_API_KEY"),
            "url": os.environ.get("ELASTIC_API_URL", "http://localhost:9200"),
            "password": os.environ.get("ES_LOCAL_PASSWORD", "admin"),
        }


def _make_client(url: str, user: str, password: str, api_key: str | None = None):
    from elasticsearch import Elasticsearch

    if api_key:
        return Elasticsearch(
            url, api_key=api_key, verify_certs=False, ssl_show_warn=False
        )
    return Elasticsearch(
        url,
        basic_auth=(user, password),
        verify_certs=False,
        ssl_show_warn=False,
    )


def _print_status(rows: list[dict]) -> None:
    name_w = max(len(r["full_name"]) for r in rows) + 2
    print(f"\n{'Index':<{name_w}} {'Exists':>6}  {'Docs':>10}")
    print("-" * (name_w + 20))
    for r in rows:
        marker = "✓" if r["exists"] else "✗"
        docs = f"{r['doc_count']:,}" if r["exists"] else "—"
        print(f"{r['full_name']:<{name_w}} {marker:>6}  {docs:>10}")
    print()


def main() -> None:
    _env = _load_env_defaults()

    parser = argparse.ArgumentParser(
        description="Create or update OpenSearch indices from opensearch_mappings.yaml."
    )
    parser.add_argument(
        "--index", metavar="NAME", help="Target a single index (default: all)"
    )
    parser.add_argument(
        "--update", action="store_true", help="Push updated mappings (don't create)"
    )
    parser.add_argument(
        "--status", action="store_true", help="Print status table and exit"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Print actions, don't execute"
    )
    parser.add_argument("--url", default=_env["url"], help="OpenSearch base URL")
    parser.add_argument("--user", default="elastic", help="Basic-auth username")
    parser.add_argument(
        "--password",
        default=_env["password"],
        help="Basic-auth password (default: $ES_LOCAL_PASSWORD)",
    )
    parser.add_argument(
        "--api-key",
        default=_env["api_key"],
        help="API key (overrides user/password if set; default: $ELASTIC_API_KEY)",
    )
    args = parser.parse_args()

    client = _make_client(args.url, args.user, args.password, api_key=args.api_key)

    from cdm.store.index_manager import IndexManager

    mgr = IndexManager(client, dry_run=args.dry_run)

    # ── validate --index ──────────────────────────────────────────────────
    if args.index and args.index not in mgr.index_names():
        valid = ", ".join(mgr.index_names())
        print(
            f"Error: unknown index {args.index!r}. Valid names:\n  {valid}",
            file=sys.stderr,
        )
        sys.exit(1)

    # ── status ────────────────────────────────────────────────────────────
    if args.status:
        _print_status(mgr.status())
        return

    # ── update ────────────────────────────────────────────────────────────
    if args.update:
        if args.index:
            print(f"Updating mappings on {args.index!r}…")
            mgr.update(args.index)
        else:
            print("Updating mappings on all indices…")
            mgr.update_all()
        return

    # ── create ────────────────────────────────────────────────────────────
    if args.index:
        print(f"Creating index {args.index!r}…")
        mgr.create(args.index)
    else:
        print("Creating all indices…")
        mgr.create_all()

    print("Done.")


if __name__ == "__main__":
    main()
