# scripts source reference

[All source areas](README.md)

Generated from declarations; see the catalogue scope in the index.

## scripts/backfill_bill_member_links.py

[Source](../../../scripts/backfill_bill_member_links.py)

- function: [`main() -> None`](../../../scripts/backfill_bill_member_links.py#L13)

## scripts/backfill_committee_activities.py

[Source](../../../scripts/backfill_committee_activities.py)

- function: [`main() -> int`](../../../scripts/backfill_committee_activities.py#L17)

## scripts/bootstrap_env.py

[Source](../../../scripts/bootstrap_env.py)

- class: [`Command(StrEnum)`](../../../scripts/bootstrap_env.py#L21)
- class: [`EnvFile()`](../../../scripts/bootstrap_env.py#L26)
- function: [`EnvFile.__init__(self, path: Path) -> None`](../../../scripts/bootstrap_env.py#L29)
- function: [`EnvFile.get(self, key: str) -> str`](../../../scripts/bootstrap_env.py#L33)
- function: [`EnvFile.set(self, key: str, value: str) -> None`](../../../scripts/bootstrap_env.py#L40)
- function: [`EnvFile.save(self) -> None`](../../../scripts/bootstrap_env.py#L47)
- class: [`EnvBootstrapper()`](../../../scripts/bootstrap_env.py#L51)
- function: [`EnvBootstrapper.init(self) -> None`](../../../scripts/bootstrap_env.py#L56)
- function: [`EnvBootstrapper.create_api_key(self) -> None`](../../../scripts/bootstrap_env.py#L68)
- function: [`main() -> int`](../../../scripts/bootstrap_env.py#L85)

## scripts/build_member_graph.py

[Source](../../../scripts/build_member_graph.py)

- function: [`main() -> None`](../../../scripts/build_member_graph.py#L11)

## scripts/build_perspectives.py

[Source](../../../scripts/build_perspectives.py)

- function: [`parse_args() -> PerspectiveRequest`](../../../scripts/build_perspectives.py#L12)
- function: [`main() -> None`](../../../scripts/build_perspectives.py#L32)

## scripts/create_indices.py

[Source](../../../scripts/create_indices.py)

- function: [`_load_env_defaults() -> dict`](../../../scripts/create_indices.py#L63)
- function: [`_make_client(url: str, user: str, password: str, api_key: str \| None=None)`](../../../scripts/create_indices.py#L73)
- function: [`_print_status(rows: list[dict]) -> None`](../../../scripts/create_indices.py#L86)
- function: [`_print_audit(audit: dict) -> None`](../../../scripts/create_indices.py#L97)
- function: [`main() -> None`](../../../scripts/create_indices.py#L115)

## scripts/export_openapi.py

[Source](../../../scripts/export_openapi.py)

- class: [`OpenAPIExporter()`](../../../scripts/export_openapi.py#L10)
- function: [`OpenAPIExporter.__init__(self, application: FastAPI) -> None`](../../../scripts/export_openapi.py#L11)
- function: [`OpenAPIExporter.render(self) -> str`](../../../scripts/export_openapi.py#L14)
- function: [`main() -> None`](../../../scripts/export_openapi.py#L18)

## scripts/health_check.py

[Source](../../../scripts/health_check.py)

- function: [`_parse_timestamp(value: str) -> datetime`](../../../scripts/health_check.py#L27)
- function: [`_failure_category(error: str \| None) -> str`](../../../scripts/health_check.py#L32)
- function: [`_job_snapshot(store: JobStore, window_minutes: int) -> dict[str, Any]`](../../../scripts/health_check.py#L61)
- function: [`_check_redis() -> dict[str, Any]`](../../../scripts/health_check.py#L100)
- function: [`_check_opensearch() -> dict[str, Any]`](../../../scripts/health_check.py#L106)
- function: [`_check_celery() -> dict[str, Any]`](../../../scripts/health_check.py#L117)
- function: [`_check_member_graph() -> dict[str, Any]`](../../../scripts/health_check.py#L129)
- function: [`collect_health(window_minutes: int=15) -> dict[str, Any]`](../../../scripts/health_check.py#L139)
- field: [`collect_health.report: dict[str, Any]`](../../../scripts/health_check.py#L141)
- function: [`main() -> int`](../../../scripts/health_check.py#L196)

## scripts/ingest_district_boundaries.py

[Source](../../../scripts/ingest_district_boundaries.py)

- function: [`main() -> None`](../../../scripts/ingest_district_boundaries.py#L36)

## scripts/ingest_votes.py

[Source](../../../scripts/ingest_votes.py)

- function: [`main() -> None`](../../../scripts/ingest_votes.py#L30)

## scripts/job_status.py

[Source](../../../scripts/job_status.py)

- function: [`main() -> None`](../../../scripts/job_status.py#L15)

## scripts/monitor_ingest_progress.py

[Source](../../../scripts/monitor_ingest_progress.py)

- class: [`IngestJob()`](../../../scripts/monitor_ingest_progress.py#L43)
- field: [`IngestJob.job_id: str`](../../../scripts/monitor_ingest_progress.py#L44)
- field: [`IngestJob.status: str`](../../../scripts/monitor_ingest_progress.py#L45)
- field: [`IngestJob.resource: str`](../../../scripts/monitor_ingest_progress.py#L46)
- field: [`IngestJob.outdir: Path`](../../../scripts/monitor_ingest_progress.py#L47)
- field: [`IngestJob.from_date: str \| None`](../../../scripts/monitor_ingest_progress.py#L48)
- field: [`IngestJob.to_date: str \| None`](../../../scripts/monitor_ingest_progress.py#L49)
- field: [`IngestJob.fetch_items: bool`](../../../scripts/monitor_ingest_progress.py#L50)
- field: [`IngestJob.hydrated: int`](../../../scripts/monitor_ingest_progress.py#L51)
- field: [`IngestJob.discovered: int`](../../../scripts/monitor_ingest_progress.py#L52)
- field: [`IngestJob.target: int`](../../../scripts/monitor_ingest_progress.py#L53)
- function: [`_connect_jobs()`](../../../scripts/monitor_ingest_progress.py#L56)
- function: [`_load_active_ingest_jobs(conn: Connection) -> list[IngestJob]`](../../../scripts/monitor_ingest_progress.py#L60)
- field: [`_load_active_ingest_jobs.jobs: list[IngestJob]`](../../../scripts/monitor_ingest_progress.py#L68)
- function: [`_count_rows(db_path: Path, statement) -> int`](../../../scripts/monitor_ingest_progress.py#L89)
- function: [`_hydrated_count(job: IngestJob) -> int`](../../../scripts/monitor_ingest_progress.py#L100)
- function: [`_cached_list_count(job: IngestJob) -> int`](../../../scripts/monitor_ingest_progress.py#L110)
- function: [`_checkpoint_next_offset(job: IngestJob) -> int \| None`](../../../scripts/monitor_ingest_progress.py#L115)
- function: [`_fetch_bill_total(job: IngestJob, cache: dict[tuple[str \| None, str \| None], int \| None]) -> int \| None`](../../../scripts/monitor_ingest_progress.py#L127)
- function: [`_bar(done: int, total: int, width: int=44) -> str`](../../../scripts/monitor_ingest_progress.py#L162)
- function: [`_format_eta(seconds: float \| None) -> str`](../../../scripts/monitor_ingest_progress.py#L170)
- function: [`_render(jobs: list[IngestJob], total_hydrated: int, total_discovered: int, total_target: int, hydration_rate: float \| None, discovery_rate: float \| None) -> str`](../../../scripts/monitor_ingest_progress.py#L179)
- function: [`main() -> None`](../../../scripts/monitor_ingest_progress.py#L226)
- field: [`main.total_cache: dict[tuple[str \| None, str \| None], int \| None]`](../../../scripts/monitor_ingest_progress.py#L232)
- field: [`main.last_time: float \| None`](../../../scripts/monitor_ingest_progress.py#L233)
- field: [`main.last_hydrated: int \| None`](../../../scripts/monitor_ingest_progress.py#L234)
- field: [`main.last_discovered: int \| None`](../../../scripts/monitor_ingest_progress.py#L235)
- field: [`main.hydration_rate: float \| None`](../../../scripts/monitor_ingest_progress.py#L267)
- field: [`main.discovery_rate: float \| None`](../../../scripts/monitor_ingest_progress.py#L268)

## scripts/preview_analytics_retirement.py

[Source](../../../scripts/preview_analytics_retirement.py)

- function: [`main() -> None`](../../../scripts/preview_analytics_retirement.py#L14)

## scripts/promote_voting_graph.py

[Source](../../../scripts/promote_voting_graph.py)

- class: [`Operation(StrEnum)`](../../../scripts/promote_voting_graph.py#L13)
- class: [`Options(BaseModel)`](../../../scripts/promote_voting_graph.py#L20)
- field: [`Options.operation: Operation`](../../../scripts/promote_voting_graph.py#L21)
- field: [`Options.bundle: Path`](../../../scripts/promote_voting_graph.py#L22)
- field: [`Options.repair_evidence: Path`](../../../scripts/promote_voting_graph.py#L23)
- field: [`Options.output: Path`](../../../scripts/promote_voting_graph.py#L24)
- field: [`Options.candidate: Path \| None`](../../../scripts/promote_voting_graph.py#L25)
- field: [`Options.browser_report: Path \| None`](../../../scripts/promote_voting_graph.py#L26)
- class: [`VotingPromotionCommand()`](../../../scripts/promote_voting_graph.py#L29)
- function: [`VotingPromotionCommand.run(self) -> None`](../../../scripts/promote_voting_graph.py#L30)

## scripts/queue_full_ingest.py

[Source](../../../scripts/queue_full_ingest.py)

- function: [`_date(value: str) -> date`](../../../scripts/queue_full_ingest.py#L25)
- function: [`parse_args() -> argparse.Namespace`](../../../scripts/queue_full_ingest.py#L29)
- function: [`_config(args: argparse.Namespace) -> FullIngestConfig`](../../../scripts/queue_full_ingest.py#L57)
- function: [`_print_job(job: FullIngestJob) -> None`](../../../scripts/queue_full_ingest.py#L71)
- function: [`main() -> None`](../../../scripts/queue_full_ingest.py#L75)

## scripts/queue_govinfo_bulk.py

[Source](../../../scripts/queue_govinfo_bulk.py)

- function: [`main() -> None`](../../../scripts/queue_govinfo_bulk.py#L19)

## scripts/reconcile_govinfo_bulk.py

[Source](../../../scripts/reconcile_govinfo_bulk.py)

- function: [`main() -> None`](../../../scripts/reconcile_govinfo_bulk.py#L14)

## scripts/relemmatize_indices.py

[Source](../../../scripts/relemmatize_indices.py)

- function: [`parse_args() -> argparse.Namespace`](../../../scripts/relemmatize_indices.py#L32)
- function: [`lemma_indices() -> list[str]`](../../../scripts/relemmatize_indices.py#L51)
- function: [`_root_fields(name: str) -> list[str]`](../../../scripts/relemmatize_indices.py#L55)
- function: [`_changed_roots(name: str, before: dict, after: dict) -> list[str]`](../../../scripts/relemmatize_indices.py#L59)
- field: [`_changed_roots.candidates: list[str]`](../../../scripts/relemmatize_indices.py#L61)
- function: [`process_index(client, name: str, *, batch_size: int, dry_run: bool, max_docs: int \| None=None) -> tuple[int, int]`](../../../scripts/relemmatize_indices.py#L67)
- field: [`process_index.actions: list[dict]`](../../../scripts/relemmatize_indices.py#L75)
- function: [`process_index.flush() -> int`](../../../scripts/relemmatize_indices.py#L77)
- function: [`main() -> int`](../../../scripts/relemmatize_indices.py#L119)

## scripts/repair_graph_sources.py

[Source](../../../scripts/repair_graph_sources.py)

- class: [`Operation(StrEnum)`](../../../scripts/repair_graph_sources.py#L13)
- class: [`Options(BaseModel)`](../../../scripts/repair_graph_sources.py#L19)
- field: [`Options.operation: Operation`](../../../scripts/repair_graph_sources.py#L20)
- field: [`Options.bundle: Path`](../../../scripts/repair_graph_sources.py#L21)
- field: [`Options.evidence: Path`](../../../scripts/repair_graph_sources.py#L22)
- field: [`Options.rehearsal: Path \| None`](../../../scripts/repair_graph_sources.py#L23)
- field: [`Options.staging_url: str \| None`](../../../scripts/repair_graph_sources.py#L24)
- class: [`SourceRepairCommand()`](../../../scripts/repair_graph_sources.py#L27)
- function: [`SourceRepairCommand.run(self) -> None`](../../../scripts/repair_graph_sources.py#L28)

## scripts/reparse_govinfo.py

[Source](../../../scripts/reparse_govinfo.py)

- function: [`parse_args() -> argparse.Namespace`](../../../scripts/reparse_govinfo.py#L27)
- function: [`_matches(payload: dict, collections: set[str], congresses: list[int] \| None) -> bool`](../../../scripts/reparse_govinfo.py#L65)
- function: [`main() -> int`](../../../scripts/reparse_govinfo.py#L71)
- field: [`main.jobs_by_package: dict[str, str]`](../../../scripts/reparse_govinfo.py#L84)

## scripts/report_govinfo_coverage.py

[Source](../../../scripts/report_govinfo_coverage.py)

- function: [`main() -> None`](../../../scripts/report_govinfo_coverage.py#L19)

## scripts/resume_queued_jobs.py

[Source](../../../scripts/resume_queued_jobs.py)

- function: [`parse_args() -> argparse.Namespace`](../../../scripts/resume_queued_jobs.py#L39)
- function: [`main() -> None`](../../../scripts/resume_queued_jobs.py#L71)

## scripts/set_metasubject_override.py

[Source](../../../scripts/set_metasubject_override.py)

- function: [`main() -> None`](../../../scripts/set_metasubject_override.py#L15)

## scripts/stage_graph_repair.py

[Source](../../../scripts/stage_graph_repair.py)

- class: [`Operation(StrEnum)`](../../../scripts/stage_graph_repair.py#L14)
- class: [`Options(BaseModel)`](../../../scripts/stage_graph_repair.py#L20)
- field: [`Options.operation: Operation`](../../../scripts/stage_graph_repair.py#L21)
- field: [`Options.bundle: Path`](../../../scripts/stage_graph_repair.py#L22)
- field: [`Options.output: Path \| None`](../../../scripts/stage_graph_repair.py#L23)
- field: [`Options.staging_url: str \| None`](../../../scripts/stage_graph_repair.py#L24)
- class: [`GraphRepairCommand()`](../../../scripts/stage_graph_repair.py#L27)
- function: [`GraphRepairCommand.run(self) -> None`](../../../scripts/stage_graph_repair.py#L28)

## scripts/submit_ingest.py

[Source](../../../scripts/submit_ingest.py)

- function: [`parse_args() -> argparse.Namespace`](../../../scripts/submit_ingest.py#L16)
- function: [`main() -> None`](../../../scripts/submit_ingest.py#L44)

## scripts/train_topic_model.py

[Source](../../../scripts/train_topic_model.py)

- function: [`parse_args(argv: Sequence[str] \| None=None) -> TopicTrainingOptions`](../../../scripts/train_topic_model.py#L22)
- function: [`main() -> None`](../../../scripts/train_topic_model.py#L48)
