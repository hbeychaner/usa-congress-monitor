"""Train the discovery BERTopic model on legislation titles + summaries + CRS subjects.

Reads bills from the legislation index, fits a batch BERTopic model, saves it
under --model-dir, generates human-readable topic titles with a local Ollama
model (skipped with --no-llm-labels), and writes topics, per-document
assignments, and topics-over-time rows to the congress-analysis-topics index
(discriminated by ``kind``). Discovery output only — not canonical topic labels.

Usage:
    uv run python scripts/train_topic_model.py --max-docs 5000 --dry-run
    uv run python scripts/train_topic_model.py
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from elasticsearch.helpers import bulk, scan

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cdm.config import get_config
from cdm.container import Container
from cdm.contracts.api import TrainingState
from cdm.store.metasubject_repository import METASUBJECT_MAPPINGS
from cdm.store.opensearch import read_alias
from cdm.utils.metasubjects import QuarterlyTrendBuilder, topic_to_metasubject
from cdm.utils.retrain_cleanup import RetrainCleanup
from cdm.utils.topic_modeler import TopicModeler, build_topic_documents
from cdm.utils.topic_training import write_status

# Earlier Congresses lack CRS summaries and bill text, which makes topics title-driven.
MIN_TRAINING_CONGRESS = 113


@dataclass(frozen=True)
class ProgressSpan:
    """Share of the overall progress bar owned by one training stage."""

    start: float
    end: float

    def at(self, fraction: float) -> float:
        return self.start + (self.end - self.start) * fraction


FETCH_SPAN = ProgressSpan(0.0, 0.05)
EMBED_SPAN = ProgressSpan(0.05, 0.55)
CLUSTER_SPAN = ProgressSpan(0.55, 0.80)
OVER_TIME_SPAN = ProgressSpan(0.80, 0.85)
LABEL_SPAN = ProgressSpan(0.85, 0.92)
INDEX_SPAN = ProgressSpan(0.92, 1.0)

_ANALYSIS_MAPPINGS = {
    "properties": {
        "kind": {"type": "keyword"},
        "model_version": {"type": "keyword"},
        "trained_at": {"type": "date"},
        "topic_id": {"type": "integer"},
        "name": {"type": "keyword"},
        "label": {"type": "keyword"},
        "size": {"type": "integer"},
        "top_words": {"type": "keyword"},
        "doc_id": {"type": "keyword"},
        "probability": {"type": "float"},
        "words": {"type": "text"},
        "frequency": {"type": "integer"},
        "timestamp": {"type": "date"},
    }
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-docs", type=int, help="Cap corpus size (for test runs)")
    parser.add_argument(
        "--min-congress",
        type=int,
        default=MIN_TRAINING_CONGRESS,
        help="Only train on bills from this Congress onward (default: %(default)s)",
    )
    parser.add_argument("--min-topic-size", type=int, default=25)
    parser.add_argument("--nr-bins", type=int, default=60)
    parser.add_argument("--embedding-model", help="Defaults to the configured model")
    parser.add_argument("--model-dir", default="models/topics")
    parser.add_argument(
        "--status-file",
        type=Path,
        help="Write progress to this JSON file (used by the admin/scheduled launcher)",
    )
    parser.add_argument(
        "--no-llm-labels",
        action="store_true",
        help="Skip Ollama topic-title generation (keyword labels only)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fit and print topics without saving the model or indexing results",
    )
    return parser.parse_args()


def fetch_documents(client, max_docs: int | None, min_congress: int):
    hits = scan(
        client,
        index=read_alias("bill"),
        query={
            "query": {
                "bool": {
                    "filter": [
                        {"term": {"source_type": "bill"}},
                        {"range": {"congress": {"gte": min_congress}}},
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
    collected = []
    for hit in hits:
        collected.append(hit)
        if max_docs is not None and len(collected) >= max_docs:
            break
    return build_topic_documents(collected)


def index_results(
    client,
    index,
    *,
    model_version,
    summaries,
    assignments,
    over_time,
    metasubject_actions=(),
    metasubject_assignments=None,
):
    if not client.indices.exists(index=index):
        client.indices.create(index=index, mappings=_ANALYSIS_MAPPINGS)
    client.indices.put_mapping(
        index=index, properties=METASUBJECT_MAPPINGS["properties"]
    )
    trained_at = datetime.now(UTC).isoformat()

    def actions():
        for topic in summaries:
            yield {
                "_index": index,
                "_id": f"topic:{model_version}:{topic.topic_id}",
                "kind": "topic",
                "model_version": model_version,
                "trained_at": trained_at,
                **topic.model_dump(mode="json", exclude_none=True),
            }
        for assignment in assignments:
            grouped = (metasubject_assignments or {}).get(assignment.doc_id)
            yield {
                "_index": index,
                "_id": f"assignment:{model_version}:{assignment.doc_id}",
                "kind": "assignment",
                "model_version": model_version,
                "trained_at": trained_at,
                "doc_id": assignment.doc_id,
                "topic_id": assignment.topic_id,
                "probability": assignment.probability,
                **(
                    {
                        "metasubject_id": grouped.metasubject_id,
                        "metasubject_confidence": grouped.confidence,
                        "assigned_by": grouped.assigned_by.value,
                        "low_confidence": grouped.low_confidence,
                    }
                    if grouped
                    else {}
                ),
            }
        for row_number, row in enumerate(over_time):
            yield {
                "_index": index,
                "_id": f"over_time:{model_version}:{row_number}",
                "kind": "topic_over_time",
                "model_version": model_version,
                "trained_at": trained_at,
                **row.model_dump(mode="json"),
            }
        yield from metasubject_actions

    success, errors = bulk(client, actions(), raise_on_error=False)
    return success, list(errors) if isinstance(errors, list) else []


def main() -> None:
    args = parse_args()
    status_file = args.status_file

    def report(**fields) -> None:
        if status_file:
            write_status(status_file, **fields)

    try:
        run(args, report)
    except BaseException as exc:
        report(
            state=TrainingState.FAILED,
            finished_at=datetime.now(UTC).isoformat(),
            message=str(exc) or type(exc).__name__,
        )
        raise


def run(args: argparse.Namespace, report) -> None:
    config = get_config()
    container = Container(config)
    client = container.elastic_client
    analysis_index = config.elastic.analysis_index
    embedding_model = args.embedding_model or config.embedding.embedding_model

    report(stage="fetching documents", progress=FETCH_SPAN.start)
    print("Fetching documents...")
    documents = fetch_documents(client, args.max_docs, args.min_congress)
    print(f"Corpus: {len(documents)} documents")
    if not documents:
        raise SystemExit("no documents found; is the legislation index populated?")

    embedding_store = container.embedding_store(embedding_model)
    # A capped test run sees only part of the corpus, so it must not prune.
    live_doc_ids = None if args.max_docs else {doc.doc_id for doc in documents}
    modeler = TopicModeler(
        embedding_model=embedding_model,
        min_topic_size=args.min_topic_size,
        embedding_store=embedding_store,
    )
    total = f"{len(documents):,} documents"

    def report_embedding(fraction: float) -> None:
        report(stage=f"embedding {total}", progress=EMBED_SPAN.at(fraction))
        if fraction >= 1.0:
            report(stage=f"clustering {total}", progress=CLUSTER_SPAN.start)

    report(stage=f"embedding {total}", progress=EMBED_SPAN.start)
    assignments = modeler.fit(documents, on_embed_progress=report_embedding)
    report(stage="computing topic trends", progress=OVER_TIME_SPAN.start)
    summaries = modeler.topic_summaries()
    over_time = modeler.topics_over_time(nr_bins=args.nr_bins)

    if not args.no_llm_labels:
        report(stage="labeling topics", progress=LABEL_SPAN.start)

        print("Generating topic titles with Ollama...")
        labels = container.topic_labeler.label_topics(
            summaries, modeler.representative_docs()
        )
        for topic in summaries:
            label = labels.get(topic.topic_id)
            if label:
                topic.label = label
        print(f"Labeled {len(labels)}/{len(summaries) - 1} topics")

    report(stage="grouping metasubjects", progress=LABEL_SPAN.end)
    repository = container.metasubject_repository
    previous = repository.latest() if client.indices.exists(index=analysis_index) else []
    namer = container.metasubject_namer(use_llm=not args.no_llm_labels)
    metasubjects = container.metasubject_builder(
        namer, container.metasubject_override_store.current()
    ).build(modeler.topic_vectors(summaries), previous)
    topic_groups = topic_to_metasubject(metasubjects)
    for topic in summaries:
        topic.metasubject_id = topic_groups.get(topic.topic_id)
    assigner = container.metasubject_assigner(metasubjects)
    grouped_docs = assigner.assign(
        [a.doc_id for a in assignments],
        [a.topic_id for a in assignments],
        modeler.document_embeddings(),
    )
    metasubjects = assigner.with_sizes(grouped_docs)
    metasubject_assignments = {g.doc_id: g for g in grouped_docs}
    metasubject_over_time = QuarterlyTrendBuilder().build(
        grouped_docs, [doc.timestamp for doc in documents]
    )
    low_confidence = sum(g.low_confidence for g in grouped_docs)
    print(
        f"Metasubjects: {len(metasubjects)} ({low_confidence:,} low-confidence bills)"
    )
    for group in metasubjects:
        print(f"  {group.metasubject_id:>3}  {group.size:>6}  {group.name}")

    print(f"\nTopics found: {len(summaries) - 1} (excluding outliers)")
    for topic in summaries[:20]:
        display = topic.label or topic.name
        print(f"  {topic.topic_id:>4}  {topic.size:>6}  {display}")

    if args.dry_run:
        print("\nDry run: model not saved, results not indexed.")
        report(
            state=TrainingState.SUCCEEDED,
            finished_at=datetime.now(UTC).isoformat(),
            message="dry run",
        )
        return

    report(stage="indexing results", progress=INDEX_SPAN.start)
    model_version = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    model_path = Path(args.model_dir) / model_version
    modeler.save(model_path)
    print(f"\nModel saved to {model_path}")

    success, errors = index_results(
        client,
        analysis_index,
        model_version=model_version,
        summaries=summaries,
        assignments=assignments,
        over_time=over_time,
        metasubject_assignments=metasubject_assignments,
        metasubject_actions=repository.actions(
            model_version,
            datetime.now(UTC).isoformat(),
            metasubjects,
            metasubject_over_time,
        ),
    )
    print(f"Indexed {success} docs to {analysis_index} ({len(errors)} errors)")
    if errors:
        for error in errors[:5]:
            print(f"  {error}")
        raise RuntimeError(f"{len(errors)} documents failed to index")
    cleanup = RetrainCleanup(
        client,
        analysis_index,
        Path(args.model_dir),
        embedding_store=embedding_store,
        live_doc_ids=live_doc_ids,
    ).run()
    print(f"Cleanup: {cleanup.summary()}")
    report(
        state=TrainingState.SUCCEEDED,
        stage="done",
        progress=1.0,
        finished_at=datetime.now(UTC).isoformat(),
        model_version=model_version,
        message=(
            f"{len(summaries) - 1} topics, {len(assignments):,} bills assigned; "
            f"{cleanup.summary()}"
        ),
    )


if __name__ == "__main__":
    main()
