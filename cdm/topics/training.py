"""Build a complete topic generation without exposing intermediate results."""

from collections import Counter
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from typing import Self
from uuid import uuid4

from elasticsearch import Elasticsearch
from elasticsearch.helpers import scan
from pydantic import BaseModel, model_validator

from cdm.config.topic_analysis import (
    EmbeddingCache,
    TopicId,
    TopicKind,
    TopicTrainingOptions,
    TrainingProgressConfig,
)
from cdm.contracts.labels import LabelFallbackReason, LabelSource
from cdm.jobs.analytics import AnalysisProgress as TrainingProgress
from cdm.store.metasubject_repository import MetasubjectRepository
from cdm.store.opensearch import read_alias
from cdm.store.topic_publication import (
    CompletedTopicRun,
    TopicPublicationStore,
    TopicRunCounts,
    TopicRunSpecification,
)
from cdm.utils.json_types import JsonObject
from cdm.utils.metasubjects import (
    Metasubject,
    MetasubjectAssigner,
    MetasubjectAssignment,
    MetasubjectBuilder,
    MetasubjectOverTimeRow,
    QuarterlyTrendBuilder,
    topic_to_metasubject,
)
from cdm.utils.topic_labeler import TopicLabeler
from cdm.utils.topic_modeler import (
    TopicAssignment,
    TopicDocument,
    TopicModeler,
    build_topic_documents,
)
from cdm.utils.topic_records import TopicSummaryRow, TopicTimeBin


class TopicTrainingOutput(BaseModel):
    documents: list[TopicDocument]
    topics: list[TopicSummaryRow]
    assignments: list[TopicAssignment]
    over_time: list[TopicTimeBin]
    metasubjects: list[Metasubject]
    grouped_assignments: list[MetasubjectAssignment]
    metasubject_over_time: list[MetasubjectOverTimeRow]

    @model_validator(mode="after")
    def validate_coverage(self) -> Self:
        documents = {doc.doc_id: doc for doc in self.documents}
        assignments = {row.doc_id: row for row in self.assignments}
        grouped = {row.doc_id: row for row in self.grouped_assignments}
        if (
            not documents
            or len(documents) != len(self.documents)
            or len(assignments) != len(self.assignments)
            or len(grouped) != len(self.grouped_assignments)
            or documents.keys() != assignments.keys()
            or documents.keys() != grouped.keys()
        ):
            raise ValueError(
                "Every unique corpus document needs exactly one assignment of each kind"
            )
        topics = {topic.topic_id: topic for topic in self.topics}
        groups = {group.metasubject_id: group for group in self.metasubjects}
        if len(topics) != len(self.topics) or len(groups) != len(self.metasubjects):
            raise ValueError("Duplicate topic or metasubject identifiers")
        if not (topics.keys() - {TopicId.OUTLIER}) or not groups:
            raise ValueError(
                "A published model needs non-outlier topics and metasubjects"
            )
        topic_sizes = Counter(row.topic_id for row in self.assignments)
        group_sizes = Counter(row.metasubject_id for row in self.grouped_assignments)
        if (
            not topic_sizes.keys() <= topics.keys()
            or not group_sizes.keys() <= groups.keys()
        ):
            raise ValueError("Assignments reference unknown topics or metasubjects")
        if any(topic.size != topic_sizes[topic.topic_id] for topic in self.topics):
            raise ValueError("Topic sizes do not cover the corpus")
        if any(
            group.size != group_sizes[group.metasubject_id]
            for group in self.metasubjects
        ):
            raise ValueError("Metasubject sizes do not cover the corpus")
        grouped_topics = [
            topic_id for group in self.metasubjects for topic_id in group.topic_ids
        ]
        if len(grouped_topics) != len(set(grouped_topics)) or set(
            grouped_topics
        ) != topics.keys() - {TopicId.OUTLIER}:
            raise ValueError("Every non-outlier topic needs exactly one metasubject")
        topic_groups = topic_to_metasubject(self.metasubjects)
        if any(
            topic.metasubject_id != topic_groups[topic.topic_id]
            for topic in self.topics
            if topic.topic_id != TopicId.OUTLIER
        ) or any(
            grouped[row.doc_id].metasubject_id != topic_groups[row.topic_id]
            for row in self.assignments
            if row.topic_id != TopicId.OUTLIER
        ):
            raise ValueError("Topic and document metasubject assignments disagree")
        dated_topics = Counter(
            row.topic_id
            for row in self.assignments
            if documents[row.doc_id].timestamp is not None
        )
        dated_groups = Counter(
            row.metasubject_id
            for row in self.grouped_assignments
            if documents[row.doc_id].timestamp is not None
        )
        topic_totals: Counter[int] = Counter()
        group_totals: Counter[int] = Counter()
        for row in self.over_time:
            if row.topic_id not in topics:
                raise ValueError("Topic trend references an unknown topic")
            if row.frequency < 0:
                raise ValueError("Negative topic trend frequency")
            topic_totals[row.topic_id] += row.frequency
        for row in self.metasubject_over_time:
            if row.metasubject_id not in groups:
                raise ValueError("Metasubject trend references an unknown metasubject")
            if row.frequency < 0:
                raise ValueError("Negative metasubject trend frequency")
            group_totals[row.metasubject_id] += row.frequency
        if topic_totals != dated_topics or group_totals != dated_groups:
            raise ValueError("Trend frequencies do not cover the dated corpus")
        return self

    def counts(self) -> TopicRunCounts:
        return TopicRunCounts(
            topics=len(self.topics),
            assignments=len(self.assignments),
            over_time=len(self.over_time),
            metasubjects=len(self.metasubjects),
            metasubject_over_time=len(self.metasubject_over_time),
        )


class TopicTrainingJob:
    def __init__(
        self,
        client: Elasticsearch,
        publications: TopicPublicationStore,
        repository: MetasubjectRepository,
        modeler: TopicModeler,
        builder: MetasubjectBuilder,
        assigner_factory: Callable[[list[Metasubject]], MetasubjectAssigner],
        options: TopicTrainingOptions,
        report: Callable[[TrainingProgress], None],
        labeler: TopicLabeler | None = None,
        progress: TrainingProgressConfig | None = None,
    ) -> None:
        self._client = client
        self._publications = publications
        self._repository = repository
        self._modeler = modeler
        self._builder = builder
        self._assigner_factory = assigner_factory
        self._options = options
        self._embedding_model = modeler.embedding_model_name
        self._report = report
        self._labeler = labeler
        self._progress = progress or TrainingProgressConfig()

    def _stage(self, stage: str, progress: float) -> None:
        self._report(TrainingProgress(stage=stage, progress=progress))

    def _fetch(self) -> list[TopicDocument]:
        hits = scan(
            self._client,
            index=read_alias("bill"),
            allow_partial_search_results=False,
            query={
                "query": {
                    "bool": {
                        "filter": [
                            {"term": {"source_type": "bill"}},
                            {
                                "range": {
                                    "congress": {"gte": self._options.min_congress}
                                }
                            },
                        ]
                    }
                },
                "_source": [
                    "title",
                    "title_lemma",
                    "summaries",
                    "introduced_date",
                    "latest_action",
                    "policy_area",
                    "subjects.legislative_subjects",
                ],
            },
        )
        collected: list[JsonObject] = []
        for hit in hits:
            collected.append(hit)
            if (
                self._options.max_docs is not None
                and len(collected) >= self._options.max_docs
            ):
                break
        return build_topic_documents(collected)

    def _embedding_progress(self, fraction: float) -> None:
        steps = self._progress
        self._stage(
            "embedding documents",
            steps.embed + (steps.cluster - steps.embed) * fraction,
        )
        if fraction >= 1.0:
            self._stage("clustering documents", steps.cluster)

    def _fit(self, documents: list[TopicDocument]) -> TopicTrainingOutput:
        self._stage("embedding documents", self._progress.embed)
        assignments = self._modeler.fit(
            documents, on_embed_progress=self._embedding_progress
        )
        topics = self._modeler.topic_summaries()
        for topic in topics:
            topic.label_source = (
                LabelSource.DETERMINISTIC
                if topic.topic_id == TopicId.OUTLIER
                else LabelSource.KEYWORDS
            )
            topic.fallback_reason = (
                None
                if topic.topic_id == TopicId.OUTLIER
                else LabelFallbackReason.DISABLED
            )
        self._stage("computing topic trends", self._progress.trends)
        over_time = (
            self._modeler.topics_over_time(nr_bins=self._options.nr_bins)
            if any(doc.timestamp is not None for doc in documents)
            else []
        )
        if self._labeler is not None and not self._options.preview:
            self._stage("labeling topics", self._progress.labels)
            labels = self._labeler.label_topics(
                topics, self._modeler.representative_docs()
            )
            if labels.keys() != {
                topic.topic_id for topic in topics if topic.topic_id != TopicId.OUTLIER
            }:
                raise ValueError("Topic label results do not cover the fitted topics")
            for topic in topics:
                if topic.topic_id != TopicId.OUTLIER:
                    label = labels[topic.topic_id]
                    topic.label = label.label
                    topic.label_source = label.label_source
                    topic.fallback_reason = label.fallback_reason
        self._stage("grouping metasubjects", self._progress.groups)
        vectors = self._modeler.topic_vectors(topics)
        for topic, vector in zip(topics, vectors, strict=True):
            topic.centroid = vector.vector.tolist()
        groups = self._builder.build(vectors, self._repository.latest())
        topic_groups = topic_to_metasubject(groups)
        for topic in topics:
            topic.metasubject_id = topic_groups.get(topic.topic_id)
        assigner = self._assigner_factory(groups)
        grouped = assigner.assign(
            [row.doc_id for row in assignments],
            [row.topic_id for row in assignments],
            self._modeler.document_embeddings(),
        )
        return TopicTrainingOutput(
            documents=documents,
            topics=topics,
            assignments=assignments,
            over_time=over_time,
            metasubjects=assigner.with_sizes(grouped),
            grouped_assignments=grouped,
            metasubject_over_time=QuarterlyTrendBuilder().build(
                grouped, [doc.timestamp for doc in documents]
            ),
        )

    def _actions(
        self, output: TopicTrainingOutput, run: TopicRunSpecification
    ) -> Iterator[JsonObject]:
        common = {
            "_index": self._publications.index,
            "model_version": run.model_version,
            "trained_at": run.trained_at.isoformat(),
        }
        for kind, records in (
            (TopicKind.TOPIC, ((str(row.topic_id), row) for row in output.topics)),
            (
                TopicKind.OVER_TIME,
                ((str(number), row) for number, row in enumerate(output.over_time)),
            ),
            (
                TopicKind.METASUBJECT,
                ((str(row.metasubject_id), row) for row in output.metasubjects),
            ),
            (
                TopicKind.METASUBJECT_OVER_TIME,
                (
                    (str(number), row)
                    for number, row in enumerate(output.metasubject_over_time)
                ),
            ),
        ):
            prefix = "over_time" if kind == TopicKind.OVER_TIME else kind
            for identifier, record in records:
                yield {
                    **common,
                    "_id": f"{prefix}:{run.model_version}:{identifier}",
                    "kind": kind,
                    **record.model_dump(mode="json", exclude_none=True),
                }
        grouped = {row.doc_id: row for row in output.grouped_assignments}
        for row in output.assignments:
            group = grouped[row.doc_id]
            yield {
                **common,
                "_id": f"{TopicKind.ASSIGNMENT}:{run.model_version}:{row.doc_id}",
                "kind": TopicKind.ASSIGNMENT,
                "doc_id": row.doc_id,
                "topic_id": row.topic_id,
                "probability": row.probability,
                "metasubject_id": group.metasubject_id,
                "metasubject_confidence": group.confidence,
                "assigned_by": group.assigned_by,
                "low_confidence": group.low_confidence,
            }

    def execute(self) -> CompletedTopicRun | None:
        baseline = self._publications.snapshot()
        if self._options.publish_version:
            self._stage("publishing completed run", self._progress.index)
            completed = self._publications.publish(
                self._options.publish_version, baseline
            )
            self._report(
                TrainingProgress(
                    stage="published",
                    progress=1.0,
                    model_version=completed.model_version,
                )
            )
            return completed
        if self._options.preview and self._modeler.embedding_store is not None:
            raise ValueError("Preview training must not use a writable embedding cache")
        cache = self._modeler.embedding_store
        if not self._options.preview and (
            cache is None or cache.model != self._embedding_model
        ):
            raise ValueError("Full training requires a cache for its embedding model")
        self._stage("fetching documents", self._progress.fetch)
        documents = self._fetch()
        if not documents:
            raise ValueError("No usable documents found in the legislation corpus")
        output = self._fit(documents)
        for topic in output.topics[:20]:
            print(f"{topic.topic_id:>4} {topic.size:>6} {topic.label or topic.name}")
        if self._options.preview:
            message = "Read-only preview: no model, analysis or embedding-cache writes; no LLM calls"
            print(message)
            self._report(
                TrainingProgress(
                    stage="preview complete",
                    progress=1.0,
                    message=message,
                    model_version=None,
                )
            )
            return None
        trained_at = datetime.now(UTC)
        version = f"{trained_at:%Y%m%dT%H%M%SZ}-{uuid4().hex}"
        model_path = self._options.model_dir / version
        self._modeler.save(model_path)
        run = TopicRunSpecification(
            model_version=version,
            trained_at=trained_at,
            embedding_model=self._embedding_model,
            embedding_cache=EmbeddingCache(
                index=cache.index,
                model=cache.model,
                dimensions=self._modeler.document_embeddings().shape[1],
            )
            if cache
            else None,
            min_congress=self._options.min_congress,
            corpus_size=len(documents),
            dated_documents=sum(doc.timestamp is not None for doc in documents),
            model_path=str(model_path),
            counts=output.counts(),
        )
        self._stage("validating and publishing results", self._progress.index)
        self._publications.write(run, self._actions(output, run))
        completed = self._publications.publish(version, baseline)
        self._report(
            TrainingProgress(
                stage="done",
                progress=self._progress.done,
                model_version=version,
                message=f"Published {len(output.topics)} topics and {len(documents):,} assignments",
            )
        )
        return completed
