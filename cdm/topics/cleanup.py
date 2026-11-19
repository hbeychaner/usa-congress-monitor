"""Verified, generation-scoped cleanup; source records and base models are untouched."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import ClassVar, NewType

import requests
from elasticsearch import Elasticsearch
from pydantic import BaseModel, Field

from cdm.config.app_config import AnalyticsRetentionConfig
from cdm.config.topic_analysis import PerspectiveKind, TopicKind
from cdm.contracts.api import NeighborhoodResponse, PartiesResponse, TopicsResponse
from cdm.graph.models import DocumentKind, GraphPointerSnapshot, Signal
from cdm.graph.store import GraphStore
from cdm.jobs.store import JobKind, JobStatus, JobStore
from cdm.store.client import SearchCompletion
from cdm.store.perspective_repository import PerspectiveRepository, PerspectiveSnapshot
from cdm.store.topic_publication import TopicPublicationSnapshot, TopicPublicationStore
from cdm.topics.retirement import RetirementReporter
from cdm.utils.json_types import JsonObject
from cdm.workers.results import JobResult, SkippedClaim

ModelVersion = NewType("ModelVersion", str)
CacheIndex = NewType("CacheIndex", str)


class CleanupRequest(BaseModel):
    request_id: str = Field(min_length=1)
    parent_job_id: str | None = None


class CleanupPolicy:
    version_pattern: ClassVar[str] = r"\d{8}T\d{6}Z(?:-[a-f0-9]{32})?"
    artifact_files: ClassVar[frozenset[str]] = frozenset(
        {
            "config.json",
            "ctfidf_config.json",
            "topic_embeddings.safetensors",
            "ctfidf.safetensors",
            "topics.json",
        }
    )
    topic_kinds: ClassVar[tuple[TopicKind, ...]] = tuple(
        kind for kind in TopicKind if kind != TopicKind.POINTER
    )

    @classmethod
    def version(cls, value: str) -> ModelVersion:
        if not re.fullmatch(cls.version_pattern, value):
            raise ValueError(f"Unrecognized analytics generation: {value}")
        datetime.strptime(value.split("-")[0], "%Y%m%dT%H%M%SZ")
        return ModelVersion(value)

    @staticmethod
    def keep(
        current: str, previous: str | None, versions: set[ModelVersion]
    ) -> set[ModelVersion]:
        retained = {CleanupPolicy.version(current)}
        if previous is not None:
            retained.add(CleanupPolicy.version(previous))
        elif older := sorted(version for version in versions if version < current):
            retained.add(older[-1])
        return retained


class CleanupState(BaseModel):
    topics: TopicPublicationSnapshot
    graphs: dict[Signal, GraphPointerSnapshot]
    perspectives: dict[int, PerspectiveSnapshot]


class GenerationDeletion(BaseModel):
    index: str
    version: ModelVersion
    kinds: list[str]
    version_field: str = "model_version"
    signal: Signal | None = None
    congress: int | None = None
    documents: int = Field(ge=0)

    def query(self) -> JsonObject:
        filters: list[JsonObject] = [
            {"terms": {"kind": self.kinds}},
            {"term": {self.version_field: self.version}},
        ]
        if self.signal is not None:
            filters.append({"term": {"signal": self.signal}})
        if self.congress is not None:
            filters.append({"term": {"congress": self.congress}})
        return {"bool": {"filter": filters}}


class CleanupPlan(BaseModel):
    state: CleanupState = Field(exclude=True)
    retained_models: set[ModelVersion]
    generations: list[GenerationDeletion] = Field(default_factory=list)
    directories: list[Path] = Field(default_factory=list)
    caches: dict[CacheIndex, str] = Field(default_factory=dict)


class CleanupResult(BaseModel):
    documents_deleted: int = 0
    model_bytes_freed: int = 0
    directories_deleted: int = 0
    caches_deleted: list[str] = Field(default_factory=list)


class AnalyticsCleanup:
    def __init__(
        self,
        client: Elasticsearch,
        publications: TopicPublicationStore,
        graphs: GraphStore,
        perspectives: PerspectiveRepository,
        reporter: RetirementReporter,
        store: JobStore,
        http: requests.Session,
        settings: AnalyticsRetentionConfig,
        embedding_index: str,
    ) -> None:
        self._client = client
        self._topics = publications
        self._graphs = graphs
        self._perspectives = perspectives
        self._reporter = reporter
        self._store = store
        self._http = http
        self._settings = settings
        self._embedding_index = embedding_index

    def _state(self) -> CleanupState:
        topics = self._topics.snapshot()
        if topics is None:
            raise ValueError("Cleanup requires a published, validated topic model")
        return CleanupState(
            topics=topics,
            graphs={signal: self._graphs.pointer_snapshot(signal) for signal in Signal},
            perspectives={
                congress: self._perspectives.snapshot(congress)
                for congress in sorted(self._perspectives.congresses())
            },
        )

    def _versions(
        self,
        index: str,
        kinds: list[str],
        *,
        signal: Signal | None = None,
        congress: int | None = None,
    ) -> dict[ModelVersion, int]:
        field = "graph_version" if signal is not None else "model_version"
        conditions: list[JsonObject] = [{"terms": {"kind": kinds}}]
        if signal is not None:
            conditions.append({"term": {"signal": signal}})
        if congress is not None:
            conditions.append({"term": {"congress": congress}})
        response = self._client.search(
            index=index,
            size=0,
            allow_partial_search_results=False,
            query={"bool": {"filter": conditions}},
            aggs={
                "versions": {
                    "terms": {
                        "field": field,
                        "size": self._settings.analytics_generation_limit,
                        "show_term_doc_count_error": True,
                    }
                }
            },
        )
        SearchCompletion.model_validate(response.body).require_complete()
        aggregation = response["aggregations"]["versions"]
        if (
            aggregation["sum_other_doc_count"]
            or aggregation["doc_count_error_upper_bound"]
        ):
            raise ValueError("Generation inventory is truncated or approximate")
        return {
            CleanupPolicy.version(bucket["key"]): int(bucket["doc_count"])
            for bucket in aggregation["buckets"]
        }

    def _files(self, directory: Path) -> list[Path]:
        root = self._settings.analytics_model_root.absolute()
        if root.resolve(strict=True) != root or root.is_symlink():
            raise ValueError(f"Model root must be a real, local directory: {root}")
        if directory.parent != root or directory.is_symlink() or not directory.is_dir():
            raise ValueError(f"Unsafe model artifact directory: {directory}")
        files = list(directory.iterdir())
        if {path.name for path in files} != CleanupPolicy.artifact_files or any(
            path.is_symlink() or not path.is_file() for path in files
        ):
            raise ValueError(
                f"Unrecognized files in model artifact directory: {directory}"
            )
        return files

    def plan(self) -> CleanupPlan:
        state = self._state()
        report = self._reporter.report()
        if report.warnings or any(
            ref.model_version is None for ref in report.references
        ):
            raise ValueError(f"Unknown live analytics lineage: {report.warnings}")
        pointer = state.topics.pointer
        topic_versions = self._versions(
            self._topics.index, list(CleanupPolicy.topic_kinds)
        )
        retained = CleanupPolicy.keep(
            pointer.run.model_version,
            pointer.previous.model_version if pointer.previous else None,
            set(topic_versions),
        )
        cutoff = min(retained)
        plan = CleanupPlan(state=state, retained_models=retained)
        for reference in report.references:
            if reference.model_version:
                retained.add(CleanupPolicy.version(reference.model_version))
        for signal, snapshot in state.graphs.items():
            current = snapshot.pointer
            versions = self._versions(
                self._graphs.index,
                [DocumentKind.EDGE],
                signal=signal,
            )
            if current is None:
                if versions:
                    raise ValueError(
                        f"Graph generations have no live pointer: {signal}"
                    )
                continue
            keep = CleanupPolicy.keep(
                current.graph_version,
                current.previous.graph_version if current.previous else None,
                set(versions),
            )
            for graph in (current, current.previous):
                if graph and graph.source_model_version:
                    retained.add(CleanupPolicy.version(graph.source_model_version))
            plan.generations.extend(
                GenerationDeletion(
                    index=self._graphs.index,
                    version=version,
                    kinds=[DocumentKind.EDGE],
                    version_field="graph_version",
                    signal=signal,
                    documents=count,
                )
                for version, count in versions.items()
                if version not in keep and version < min(keep)
            )
        for congress, snapshot in state.perspectives.items():
            current = snapshot.publication
            if current is None:
                raise ValueError(
                    f"Cleanup requires a published perspective snapshot: {congress}"
                )
            versions = self._versions(
                self._topics.index,
                [PerspectiveKind.PARTY_TOPIC],
                congress=congress,
            )
            keep = CleanupPolicy.keep(
                current.model_version,
                current.previous.model_version if current.previous else None,
                set(versions),
            )
            if current.previous is not None:
                retained.add(CleanupPolicy.version(current.previous.model_version))
            plan.generations.extend(
                GenerationDeletion(
                    index=self._topics.index,
                    version=version,
                    kinds=[PerspectiveKind.PARTY_TOPIC],
                    congress=congress,
                    documents=count,
                )
                for version, count in versions.items()
                if version not in keep and version < min(keep)
            )
        plan.retained_models = retained
        plan.generations.extend(
            GenerationDeletion(
                index=self._topics.index,
                version=version,
                kinds=list(CleanupPolicy.topic_kinds),
                documents=count,
            )
            for version, count in topic_versions.items()
            if version not in retained and version < cutoff
        )
        root = self._settings.analytics_model_root.absolute()
        for directory in sorted(root.iterdir()):
            version = CleanupPolicy.version(directory.name)
            if version not in retained and version < cutoff:
                self._files(directory)
                plan.directories.append(directory)
        runs = {
            CleanupPolicy.version(review.run.model_version): review.run
            for review in report.runs
        }
        if any(version not in runs for version in retained):
            raise ValueError(
                "Retained model dependencies lack validated manifests; caches are not safe to prune"
            )
        if retained.intersection(report.unknown_cache_versions):
            raise ValueError("Retained model embedding cache ownership is unknown")
        caches = set()
        for version in retained:
            run = runs[version]
            if run.embedding_cache is None:
                caches.add(self._embedding_index)
            else:
                caches.add(run.embedding_cache.index)
            path = Path(run.model_path).absolute()
            if path.parent != root or path.name != version:
                raise ValueError(
                    f"Retained model lies outside the configured model root: {path}"
                )
            self._files(path)
        definitions = self._client.indices.get(index=f"{self._embedding_index}*")
        if caches.difference(definitions):
            raise ValueError("A retained model's embedding cache is missing")
        for index, definition in definitions.items():
            if index in caches:
                continue
            if index != self._embedding_index and not re.fullmatch(
                re.escape(self._embedding_index) + r"-[a-f0-9]{64}",
                index,
            ):
                raise ValueError(f"Unknown embedding cache ownership: {index}")
            if definition["aliases"]:
                raise ValueError(f"Unused cache still has an alias: {index}")
            plan.caches[CacheIndex(index)] = definition["settings"]["index"]["uuid"]
        if self._state() != state:
            raise ValueError("Analytics publications changed during cleanup planning")
        return plan

    def _get(self, path: str, **params: str | int) -> object:
        response = self._http.get(
            f"{self._settings.analytics_live_api_url.rstrip('/')}/{path}",
            params=params,
            timeout=self._settings.analytics_cleanup_timeout,
        )
        response.raise_for_status()
        return response.json()

    def verify_live(self, state: CleanupState) -> None:
        topics = TopicsResponse.model_validate(self._get("topics"))
        version = state.topics.pointer.run.model_version
        if (
            topics.model_version != version
            or topics.analysis.source_model_version != version
            or not topics.topics
        ):
            raise ValueError("Live topics API does not serve the published generation")
        for congress, snapshot in state.perspectives.items():
            parties = PartiesResponse.model_validate(
                self._get("parties", congress=congress)
            )
            if (
                snapshot.publication is None
                or parties.model_version != snapshot.publication.model_version
            ):
                raise ValueError(
                    f"Live perspectives API generation mismatch: {congress}"
                )
        pointers = {
            signal: snapshot.pointer.graph_version
            for signal, snapshot in state.graphs.items()
            if snapshot.pointer
        }
        if pointers:
            edge = self._client.search(
                index=self._graphs.index,
                size=1,
                allow_partial_search_results=False,
                query={"term": {"kind": DocumentKind.EDGE}},
                source_includes=["member"],
            )
            SearchCompletion.model_validate(edge.body).require_complete()
            if not edge["hits"]["hits"]:
                raise ValueError(
                    "Published graph has no member available for live verification"
                )
            graph = NeighborhoodResponse.model_validate(
                self._get(
                    "graph/neighborhood",
                    member=edge["hits"]["hits"][0]["_source"]["member"],
                    limit=1,
                )
            )
            if graph.versions != pointers:
                raise ValueError(
                    "Live graph API does not serve the published generations"
                )

    def apply(self, plan: CleanupPlan) -> CleanupResult:
        self.verify_live(plan.state)
        result = CleanupResult()
        for generation in plan.generations:
            if self._state() != plan.state:
                raise ValueError("Publications changed; cleanup stopped")
            response = self._client.options(
                request_timeout=self._settings.analytics_cleanup_timeout,
            ).delete_by_query(
                index=generation.index,
                query=generation.query(),
                conflicts="abort",
                scroll_size=self._settings.analytics_cleanup_batch,
                refresh=True,
                requests_per_second=5000,
            )
            if (
                response["timed_out"]
                or response["failures"]
                or response["version_conflicts"]
            ):
                raise RuntimeError(f"Incomplete generation deletion: {response.body}")
            if response["deleted"] != generation.documents:
                raise RuntimeError(
                    "Generation changed during deletion; cleanup stopped"
                )
            result.documents_deleted += response["deleted"]
        for directory in plan.directories:
            if self._state() != plan.state:
                raise ValueError("Publications changed; artifact cleanup stopped")
            for path in self._files(directory):
                size = path.stat().st_size
                path.unlink()
                result.model_bytes_freed += size
            directory.rmdir()
            result.directories_deleted += 1
        for index, uuid in plan.caches.items():
            if self._state() != plan.state:
                raise ValueError("Publications changed; cache cleanup stopped")
            observed = self._client.indices.get(index=index)
            if (
                set(observed) != {index}
                or observed[index]["aliases"]
                or observed[index]["settings"]["index"]["uuid"] != uuid
            ):
                raise ValueError(f"Embedding cache identity changed: {index}")
            if not self._client.indices.delete(index=index)["acknowledged"]:
                raise RuntimeError(
                    f"Embedding cache deletion was not acknowledged: {index}"
                )
            result.caches_deleted.append(index)
        self.verify_live(plan.state)
        return result

    def run(self, job_id: str) -> JobResult:
        row = self._store.mark_running(
            job_id,
            update_windows=False,
            max_active=1,
            exclusive_kinds=JobKind.analytics(),
        )
        if row is None:
            return SkippedClaim(self._store).result(job_id)
        request = CleanupRequest.model_validate(row["payload"])
        if row["kind"] != JobKind.ANALYTICS_CLEANUP:
            raise ValueError("Cleanup job kind does not match its payload")
        if request.parent_job_id is not None:
            parent = self._store.get(request.parent_job_id)
            if (
                parent["status"] != JobStatus.SUCCEEDED
                or parent["kind"] not in JobKind.analytics()[:-1]
            ):
                raise ValueError("Cleanup requires a successful analytics parent job")
        result = self.apply(self.plan())
        self._store.report_progress(job_id, result.model_dump(mode="json"))
        completed = self._store.mark_succeeded(job_id)
        return JobResult(job_id=job_id, status=completed["status"])
