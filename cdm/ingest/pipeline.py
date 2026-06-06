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
        save_raw_items=True,
    )
    pipeline = Pipeline(cfg)
    pipeline.run_all()                          # all 20 resources
    pipeline.run([Resource.BILL, Resource.AMENDMENT])  # specific subset
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Sequence

from cdm.ingest.resource_config import (
    RESOURCE_CONFIGS,
    ResourceConfig,
    date_windowed,
    congress_scoped,
    static_resources,
)
from cdm.ingest.runner import IngestRunner, Resource

logger = logging.getLogger(__name__)


@dataclass
class PipelineConfig:
    outdir: Path
    # Date window (applied to all date-windowed resources)
    from_date: Optional[str] = None
    to_date: Optional[str] = None
    # Congress number (applied to congress-scoped resources)
    congress: Optional[int] = None
    # Item fetching
    fetch_items: bool = False   # override per-resource default when True
    save_raw_items: bool = True
    # Limits (useful for sampling / smoke-tests)
    max_pages: Optional[int] = None
    max_items: Optional[int] = None
    # Concurrency: parallel item-fetch workers
    concurrency: int = 1
    # Shared rate limiter (TokenBucket); None = no rate limiting
    rate_limiter: Optional[object] = None
    # API auth
    api_key: Optional[str] = None
    # Whether to continue past errors in individual resources
    skip_errors: bool = True


@dataclass
class ResourceResult:
    resource: Resource
    success: bool
    list_count: int = 0
    item_count: int = 0
    error: Optional[str] = None
    outdir: Optional[Path] = None


class Pipeline:
    """Orchestrates IngestRunner across multiple resources."""

    def __init__(self, config: PipelineConfig) -> None:
        self.config = config

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run_all(self) -> List[ResourceResult]:
        """Run all 20 resources grouped by scope type."""
        resources = list(Resource)
        return self.run(resources)

    def run_date_windowed(self) -> List[ResourceResult]:
        """Run only date-windowed resources (require --from-date / --to-date)."""
        return self.run([c.resource for c in date_windowed()])

    def run_congress_scoped(self) -> List[ResourceResult]:
        """Run only congress-scoped resources (require --congress)."""
        return self.run([c.resource for c in congress_scoped()])

    def run_static(self) -> List[ResourceResult]:
        """Run only static resources (no date or congress filter)."""
        return self.run([c.resource for c in static_resources()])

    def run(self, resources: Sequence[Resource]) -> List[ResourceResult]:
        """Run IngestRunner for each resource in *resources*."""
        results: List[ResourceResult] = []
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
            result.error = f"congress number required for {resource.value}; pass --congress"
            logger.warning(result.error)
            return result

        # Determine whether to fetch items for this resource.
        # config.fetch_items (set by --items flag) explicitly enables item fetch.
        # cfg.list_only always disables it regardless.
        # cfg.fetch_items_default=False marks very large resources (e.g. bills)
        # that should remain list-only even when --items is set globally;
        # target them explicitly with --resources bill --items to override.
        fetch_items = (
            self.config.fetch_items
            and cfg.fetch_items_default
            and not cfg.list_only
        )

        # Apply date params only when the resource supports them
        from_date = (
            self.config.from_date if cfg.from_date_param else None
        )
        to_date = (
            self.config.to_date if cfg.to_date_param else None
        )

        try:
            runner = IngestRunner(
                outdir=outdir,
                resource=resource,
                api_key=self.config.api_key,
                fetch_items=fetch_items,
                save_raw_items=self.config.save_raw_items,
                max_pages=self.config.max_pages,
                max_items=self.config.max_items,
                congress=self.config.congress,
                from_date=from_date,
                to_date=to_date,
                concurrency=self.config.concurrency,
                rate_limiter=self.config.rate_limiter,
            )
            runner.run()

            # Measure outputs
            list_file = outdir / "list.json"
            items_file = outdir / "items.json"
            result.list_count = (
                len(json.loads(list_file.read_text()))
                if list_file.exists()
                else 0
            )
            result.item_count = (
                len(json.loads(items_file.read_text()))
                if items_file.exists()
                else 0
            )

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
                "run_at": datetime.now(timezone.utc).isoformat(),
            }
            (outdir / "meta.json").write_text(
                json.dumps(meta, indent=2), encoding="utf-8"
            )

            result.success = True
        except Exception as exc:
            result.error = str(exc)
            logger.exception("Resource %s failed: %s", resource.value, exc)
            if not self.config.skip_errors:
                raise

        return result

    def _write_run_summary(self, results: List[ResourceResult]) -> None:
        summary = {
            "run_at": datetime.now(timezone.utc).isoformat(),
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
