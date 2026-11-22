# scripts source reference

[All source areas](README.md)

Generated from declarations; see the catalogue scope in the index.

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

## scripts/check_stack_capacity.py

[Source](../../../scripts/check_stack_capacity.py)

- function: [`main() -> int`](../../../scripts/check_stack_capacity.py#L18)

## scripts/create_indices.py

[Source](../../../scripts/create_indices.py)

- function: [`_load_env_defaults() -> dict`](../../../scripts/create_indices.py#L63)
- function: [`_make_client(url: str, user: str, password: str, api_key: str \| None=None)`](../../../scripts/create_indices.py#L73)
- function: [`_print_status(rows: list[dict]) -> None`](../../../scripts/create_indices.py#L86)
- function: [`_print_audit(audit: dict) -> None`](../../../scripts/create_indices.py#L97)
- function: [`main() -> None`](../../../scripts/create_indices.py#L115)

## scripts/ensure_ollama.py

[Source](../../../scripts/ensure_ollama.py)

- class: [`OllamaCommand()`](../../../scripts/ensure_ollama.py#L18)
- function: [`OllamaCommand.run(self) -> None`](../../../scripts/ensure_ollama.py#L19)

## scripts/export_openapi.py

[Source](../../../scripts/export_openapi.py)

- class: [`OpenAPIExporter()`](../../../scripts/export_openapi.py#L10)
- function: [`OpenAPIExporter.__init__(self, application: FastAPI) -> None`](../../../scripts/export_openapi.py#L11)
- function: [`OpenAPIExporter.render(self) -> str`](../../../scripts/export_openapi.py#L14)
- function: [`main() -> None`](../../../scripts/export_openapi.py#L18)

## scripts/ingest_district_boundaries.py

[Source](../../../scripts/ingest_district_boundaries.py)

- function: [`main() -> None`](../../../scripts/ingest_district_boundaries.py#L36)

## scripts/ingest_votes.py

[Source](../../../scripts/ingest_votes.py)

- function: [`main() -> None`](../../../scripts/ingest_votes.py#L30)

## scripts/preview_analytics_retirement.py

[Source](../../../scripts/preview_analytics_retirement.py)

- function: [`main() -> None`](../../../scripts/preview_analytics_retirement.py#L19)

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
- function: [`_config(args: argparse.Namespace) -> FullIngestConfig`](../../../scripts/queue_full_ingest.py#L62)
- function: [`_print_job(job: FullIngestJob) -> None`](../../../scripts/queue_full_ingest.py#L77)
- function: [`main() -> None`](../../../scripts/queue_full_ingest.py#L81)

## scripts/queue_govinfo_bulk.py

[Source](../../../scripts/queue_govinfo_bulk.py)

- function: [`main() -> None`](../../../scripts/queue_govinfo_bulk.py#L19)

## scripts/reconcile_govinfo_bulk.py

[Source](../../../scripts/reconcile_govinfo_bulk.py)

- function: [`main() -> None`](../../../scripts/reconcile_govinfo_bulk.py#L14)

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

## scripts/report_govinfo_coverage.py

[Source](../../../scripts/report_govinfo_coverage.py)

- function: [`main() -> None`](../../../scripts/report_govinfo_coverage.py#L19)

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
