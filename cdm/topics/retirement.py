"""Read-only lineage inventory, not a deletion plan or authorization."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal

from elasticsearch.helpers import scan
from pydantic import AwareDatetime, BaseModel, Field

from cdm.config.topic_analysis import PerspectiveKind, TopicKind
from cdm.graph.models import Signal
from cdm.graph.store import GraphStore
from cdm.store.perspective_repository import PerspectivePublication
from cdm.store.topic_publication import CompletedTopicRun, TopicPublicationStore


class ReferenceState(StrEnum):
    REFERENCED = "referenced"
    UNREFERENCED = "unreferenced"
    UNKNOWN = "unknown"


class ReferenceKind(StrEnum):
    TOPICS = "published_topics"
    GRAPH = "published_topic_graph"
    PERSPECTIVES = "perspective_snapshot"
    LEGACY_PERSPECTIVES = "unsuperseded_legacy_perspectives"


class PublishedReference(BaseModel):
    kind: ReferenceKind
    model_version: str | None = Field(default=None, min_length=1)
    congress: int | None = Field(default=None, gt=0)


class _PerspectiveLineage(BaseModel):
    kind: PerspectiveKind
    congress: int = Field(gt=0)
    model_version: str | None = Field(default=None, min_length=1)


class TopicRunReview(BaseModel):
    run: CompletedTopicRun
    state: ReferenceState
    cache_state: ReferenceState
    cache_shared_with: list[str]


class RetirementReport(BaseModel):
    generated_at: AwareDatetime
    deletion_authorized: Literal[False] = False
    current_run: CompletedTopicRun | None
    runs: list[TopicRunReview]
    references: list[PublishedReference]
    legacy_embedding_index: str
    unknown_cache_versions: list[str]
    warnings: list[str]
    limitations: tuple[str, ...] = (
        "Unreferenced does not mean safe to delete; replacements are not verified.",
        "Reads span indexes and are not an atomic snapshot; references can change.",
        (
            "Only validated topic manifests are inventoried, not failed/unmanifested "
            "artifacts, graph history, cache contents, or congressional source records."
        ),
        "Recorded model paths are not inspected or validated for deletion.",
    )


class RetirementReporter:
    def __init__(
        self,
        publications: TopicPublicationStore,
        graphs: GraphStore,
        legacy_embedding_index: str,
    ) -> None:
        self._publications = publications
        self._graphs = graphs
        self._legacy_embedding_index = legacy_embedding_index

    def _inventory(
        self,
    ) -> tuple[list[CompletedTopicRun], list[_PerspectiveLineage]]:
        runs: list[CompletedTopicRun] = []
        perspectives: list[_PerspectiveLineage] = []
        if not self._publications.client.indices.exists(index=self._publications.index):
            return runs, perspectives
        for hit in scan(
            self._publications.client,
            index=self._publications.index,
            allow_partial_search_results=False,
            query={
                "query": {
                    "terms": {
                        "kind": [TopicKind.RUN, *PerspectiveKind],
                    }
                },
                "_source": sorted(set(CompletedTopicRun.model_fields) | {"congress"}),
            },
        ):
            source = hit["_source"]
            if source["kind"] == TopicKind.RUN:
                run = CompletedTopicRun.model_validate(source)
                if hit["_id"] != run.id:
                    raise ValueError("Topic manifest identity does not match version")
                runs.append(run)
            else:
                lineage = _PerspectiveLineage.model_validate(source)
                if lineage.kind == PerspectiveKind.PUBLICATION and hit[
                    "_id"
                ] != PerspectivePublication.document_id(lineage.congress):
                    raise ValueError(
                        "Perspective snapshot identity does not match Congress"
                    )
                perspectives.append(lineage)
        return runs, perspectives

    def report(self) -> RetirementReport:
        current = self._publications.current()
        runs, perspectives = self._inventory()
        references: list[PublishedReference] = []
        warnings: list[str] = []
        if current:
            references.append(
                PublishedReference(
                    kind=ReferenceKind.TOPICS, model_version=current.model_version
                )
            )
        else:
            warnings.append(
                "No published topic run; no validated replacement is established."
            )
        if pointer := self._graphs.active_pointer(Signal.TOPIC):
            if pointer.signal != Signal.TOPIC:
                raise ValueError("Topic graph pointer identity does not match signal")
            references.append(
                PublishedReference(
                    kind=ReferenceKind.GRAPH,
                    model_version=pointer.source_model_version,
                )
            )
        snapshots = {
            entry.congress
            for entry in perspectives
            if entry.kind == PerspectiveKind.PUBLICATION
        }
        for entry in perspectives:
            if (
                entry.kind == PerspectiveKind.PUBLICATION
                or entry.congress not in snapshots
            ):
                reference = PublishedReference(
                    kind=ReferenceKind.PERSPECTIVES
                    if entry.kind == PerspectiveKind.PUBLICATION
                    else ReferenceKind.LEGACY_PERSPECTIVES,
                    model_version=entry.model_version,
                    congress=entry.congress,
                )
                if reference not in references:
                    references.append(reference)
        if any(reference.model_version is None for reference in references):
            warnings.append("Published consumers have unknown topic lineage.")
        known = {run.model_version for run in runs}
        missing = sorted(
            {ref.model_version for ref in references if ref.model_version} - known
        )
        if missing:
            warnings.append(
                f"Referenced versions without validated manifests: {', '.join(missing)}"
            )
        cache_runs = [*runs, current] if current else runs
        known_caches = {run.model_version for run in cache_runs if run.embedding_cache}
        unknown_caches = sorted(
            (known | {ref.model_version for ref in references if ref.model_version})
            - known_caches
        )
        if unknown_caches:
            warnings.append(
                "Some versions lack cache identity; cache ownership is unknown."
            )
        reviews: list[TopicRunReview] = []
        uncertain = current is None or any(
            ref.model_version is None for ref in references
        )
        for run in sorted(runs, key=lambda run: run.model_version):
            referenced = any(
                ref.model_version == run.model_version for ref in references
            )
            cache_owners = sorted(
                {
                    other.model_version
                    for other in cache_runs
                    if run.embedding_cache
                    and other.embedding_cache
                    and other.embedding_cache.index == run.embedding_cache.index
                }
            )
            cache_state = ReferenceState.UNKNOWN
            if run.embedding_cache and not uncertain and not unknown_caches:
                cache_state = ReferenceState.UNREFERENCED
            if any(ref.model_version in cache_owners for ref in references):
                cache_state = ReferenceState.REFERENCED
            reviews.append(
                TopicRunReview(
                    run=run,
                    state=ReferenceState.REFERENCED
                    if referenced
                    else ReferenceState.UNKNOWN
                    if uncertain
                    else ReferenceState.UNREFERENCED,
                    cache_state=cache_state,
                    cache_shared_with=[
                        owner for owner in cache_owners if owner != run.model_version
                    ],
                )
            )
        return RetirementReport(
            generated_at=datetime.now(UTC),
            current_run=current,
            runs=reviews,
            references=sorted(
                references,
                key=lambda ref: (ref.kind, ref.congress or 0, ref.model_version or ""),
            ),
            legacy_embedding_index=self._legacy_embedding_index,
            unknown_cache_versions=unknown_caches,
            warnings=warnings,
        )
