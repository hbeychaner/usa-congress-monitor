"""Multi-resource ingest pipeline.

Orchestrates IngestRunner across a set of resources, applying shared date
window / congress parameters and writing results under a common output root.

Usage::

    from cdm.ingest.pipeline import Pipeline, PipelineConfig
    from cdm.ingest.runner import Resource

    cfg = PipelineConfig(
        outdir=Path("data/local"),
        from_date="2025-01-01",
        to_date="2025-01-31",
        fetch_items=True,
    )
    pipeline = Pipeline(cfg)
    pipeline.run_all()                          # all 20 resources
    pipeline.run([Resource.BILL, Resource.AMENDMENT])  # specific subset
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from cdm.ingest.rate_limiter import TokenBucket
from cdm.ingest.resource_config import (
    RESOURCE_CONFIGS,
    ResourceConfig,
    congress_scoped,
    date_windowed,
    static_resources,
)
from cdm.ingest.runner import FatalIngestError, IngestRunner, Resource

logger = logging.getLogger(__name__)


@dataclass
class PipelineConfig:
    outdir: Path
    # Date window (applied to all date-windowed resources)
    from_date: str | None = None
    to_date: str | None = None
    # Congress number (applied to congress-scoped resources)
    congress: int | None = None
    # Item fetching
    fetch_items: bool = False  # override per-resource default when True
    force_item_fetch: bool = (
        False  # smoke-test override for every available item endpoint
    )
    # Limits (useful for sampling / smoke-tests)
    max_pages: int | None = None
    max_items: int | None = None
    # Concurrency: parallel item-fetch workers
    concurrency: int = 1
    # Shared rate limiter (TokenBucket); None = no rate limiting
    rate_limiter: TokenBucket | None = None
    record_sink: Callable[[str, dict], None] | None = None
    record_archive_sink: Callable[[str, dict], None] | None = None
    # API auth
    api_key: str | None = None
    # Whether to continue past errors in individual resources
    skip_errors: bool = True


@dataclass
class ResourceResult:
    resource: Resource
    success: bool
    list_count: int = 0
    item_count: int = 0
    error: str | None = None
    outdir: Path | None = None


class Pipeline:
    """Orchestrates IngestRunner across multiple resources."""

    def __init__(self, config: PipelineConfig) -> None:
        self.config = config

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run_all(self) -> list[ResourceResult]:
        """Run all 20 resources grouped by scope type."""
        resources = list(Resource)
        return self.run(resources)

    def run_date_windowed(self) -> list[ResourceResult]:
        """Run only date-windowed resources (require --from-date / --to-date)."""
        return self.run([c.resource for c in date_windowed()])

    def run_congress_scoped(self) -> list[ResourceResult]:
        """Run only congress-scoped resources (require --congress)."""
        return self.run([c.resource for c in congress_scoped()])

    def run_static(self) -> list[ResourceResult]:
        """Run only static resources (no date or congress filter)."""
        return self.run([c.resource for c in static_resources()])

    def run(self, resources: Sequence[Resource]) -> list[ResourceResult]:
        """Run IngestRunner for each resource in *resources*."""
        results: list[ResourceResult] = []
        total = len(resources)
        for i, resource in enumerate(resources, 1):
            cfg = RESOURCE_CONFIGS[resource]
            logger.info(
                "[%d/%d] Starting %s (scope=%s)",
                i,
                total,
                resource.value,
                cfg.scope,
            )
            result = self._run_one(resource, cfg)
            results.append(result)
            status = "✓" if result.success else "✗"
            logger.info(
                "[%d/%d] %s %s  list=%d items=%d%s",
                i,
                total,
                status,
                resource.value,
                result.list_count,
                result.item_count,
                f"  error={result.error}" if result.error else "",
            )
        self._write_run_summary(results)
        return results

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _run_one(self, resource: Resource, cfg: ResourceConfig) -> ResourceResult:
        outdir = self.config.outdir / resource.value
        result = ResourceResult(resource=resource, success=False, outdir=outdir)

        # Validate prerequisites
        if cfg.requires_congress and self.config.congress is None:
            result.error = (
                f"congress number required for {resource.value}; pass --congress"
            )
            logger.warning(result.error)
            return result

        # Determine whether to fetch items for this resource.
        # config.fetch_items (set by --items flag) explicitly enables item fetch.
        # cfg.list_only always disables it regardless.
        # cfg.fetch_items_default=False marks very large resources (e.g. bills)
        # that should remain list-only even when --items is set globally;
        # target them explicitly with --resources bill --items to override.
        fetch_items = self.config.fetch_items and (
            self.config.force_item_fetch
            or (cfg.fetch_items_default and not cfg.list_only)
        )

        # Apply date params only when the resource supports them
        from_date = self.config.from_date if cfg.from_date_param else None
        to_date = self.config.to_date if cfg.to_date_param else None

        try:
            runner = IngestRunner(
                outdir=outdir,
                resource=resource,
                api_key=self.config.api_key,
                fetch_items=fetch_items,
                force_item_fetch=self.config.force_item_fetch,
                max_pages=self.config.max_pages,
                max_items=self.config.max_items,
                congress=self.config.congress,
                from_date=from_date,
                to_date=to_date,
                from_date_param=cfg.from_date_param or "fromDateTime",
                to_date_param=cfg.to_date_param or "toDateTime",
                concurrency=self.config.concurrency,
                rate_limiter=self.config.rate_limiter,
                record_sink=self.config.record_sink,
                record_archive_sink=self.config.record_archive_sink,
            )
            counts = runner.run()
            result.list_count = int(counts["list_count"])
            result.item_count = int(counts["item_count"])

            # Write per-resource metadata
            meta = {
                "resource": resource.value,
                "scope": cfg.scope,
                "from_date": from_date,
                "to_date": to_date,
                "congress": self.config.congress,
                "fetch_items": fetch_items,
                "list_count": result.list_count,
                "item_count": result.item_count,
                "run_at": datetime.now(UTC).isoformat(),
            }
            (outdir / "meta.json").write_text(
                json.dumps(meta, indent=2), encoding="utf-8"
            )

            result.success = True
        except FatalIngestError:
            # Always propagate fatal errors — they require a code fix.
            raise
        except Exception as exc:
            result.error = str(exc)
            logger.exception("Resource %s failed", resource.value)
            if not self.config.skip_errors:
                raise

        return result

    def _write_run_summary(self, results: list[ResourceResult]) -> None:
        summary = {
            "run_at": datetime.now(UTC).isoformat(),
            "from_date": self.config.from_date,
            "to_date": self.config.to_date,
            "congress": self.config.congress,
            "resources": [
                {
                    "resource": r.resource.value,
                    "success": r.success,
                    "list_count": r.list_count,
                    "item_count": r.item_count,
                    "error": r.error,
                }
                for r in results
            ],
            "totals": {
                "attempted": len(results),
                "succeeded": sum(1 for r in results if r.success),
                "failed": sum(1 for r in results if not r.success),
            },
        }
        self.config.outdir.mkdir(parents=True, exist_ok=True)
        summary_path = self.config.outdir / "run_summary.json"
        summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        logger.info("Run summary written to %s", summary_path)
