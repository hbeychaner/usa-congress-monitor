"""Train the discovery BERTopic model on legislation titles + summaries.

Reads bills from the legislation index, fits a batch BERTopic model, saves it
under --model-dir, and writes topics, per-document assignments, and
topics-over-time rows to the congress-analysis-topics index (discriminated by
``kind``). Discovery output only — not canonical topic labels.

Usage:
    uv run python scripts/train_topic_model.py --max-docs 5000 --dry-run
    uv run python scripts/train_topic_model.py
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cdm.store.client import get_opensearch_client
from cdm.store.opensearch import read_alias
from cdm.utils.topic_modeler import TopicModeler, build_topic_documents

ANALYSIS_INDEX = "congress-analysis-topics"

_ANALYSIS_MAPPINGS = {
    "properties": {
        "kind": {"type": "keyword"},
        "model_version": {"type": "keyword"},
        "trained_at": {"type": "date"},
        "topic_id": {"type": "integer"},
        "name": {"type": "keyword"},
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
    parser.add_argument("--min-topic-size", type=int, default=25)
    parser.add_argument("--nr-bins", type=int, default=60)
    parser.add_argument(
        "--embedding-model", default="all-mpnet-base-v2"
    )
    parser.add_argument("--model-dir", default="models/topics")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fit and print topics without saving the model or indexing results",
    )
    return parser.parse_args()


def fetch_documents(client, max_docs: int | None):
    from elasticsearch.helpers import scan

    hits = scan(
        client,
        index=read_alias("bill"),
        query={
            "query": {"term": {"source_type": "bill"}},
            "_source": [
                "title",
                "title_lemma",
                "summaries",
                "introduced_date",
                "latest_action",
            ],
        },
    )
    collected = []
    for hit in hits:
        collected.append(hit)
        if max_docs is not None and len(collected) >= max_docs:
            break
    return build_topic_documents(collected)


def index_results(client, *, model_version, summaries, assignments, over_time):
    from elasticsearch.helpers import bulk

    if not client.indices.exists(index=ANALYSIS_INDEX):
        client.indices.create(index=ANALYSIS_INDEX, mappings=_ANALYSIS_MAPPINGS)
    trained_at = datetime.now(UTC).isoformat()

    def actions():
        for topic in summaries:
            yield {
                "_index": ANALYSIS_INDEX,
                "_id": f"topic:{model_version}:{topic['topic_id']}",
                "kind": "topic",
                "model_version": model_version,
                "trained_at": trained_at,
                **topic,
            }
        for assignment in assignments:
            yield {
                "_index": ANALYSIS_INDEX,
                "_id": f"assignment:{model_version}:{assignment.doc_id}",
                "kind": "assignment",
                "model_version": model_version,
                "trained_at": trained_at,
                "doc_id": assignment.doc_id,
                "topic_id": assignment.topic_id,
                "probability": assignment.probability,
            }
        for row_number, row in enumerate(over_time):
            yield {
                "_index": ANALYSIS_INDEX,
                "_id": f"over_time:{model_version}:{row_number}",
                "kind": "topic_over_time",
                "model_version": model_version,
                "trained_at": trained_at,
                **row,
            }

    success, errors = bulk(client, actions(), raise_on_error=False)
    return success, errors


def main() -> None:
    args = parse_args()
    client = get_opensearch_client()

    print("Fetching documents...")
    documents = fetch_documents(client, args.max_docs)
    print(f"Corpus: {len(documents)} documents")
    if not documents:
        raise SystemExit("no documents found; is the legislation index populated?")

    modeler = TopicModeler(
        embedding_model=args.embedding_model,
        min_topic_size=args.min_topic_size,
    )
    assignments = modeler.fit(documents)
    summaries = modeler.topic_summaries()
    over_time = modeler.topics_over_time(nr_bins=args.nr_bins)

    print(f"\nTopics found: {len(summaries) - 1} (excluding outliers)")
    for topic in summaries[:20]:
        print(f"  {topic['topic_id']:>4}  {topic['size']:>6}  {topic['name']}")

    if args.dry_run:
        print("\nDry run: model not saved, results not indexed.")
        return

    model_version = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    model_path = Path(args.model_dir) / model_version
    modeler.save(model_path)
    print(f"\nModel saved to {model_path}")

    success, errors = index_results(
        client,
        model_version=model_version,
        summaries=summaries,
        assignments=assignments,
        over_time=over_time,
    )
    print(f"Indexed {success} docs to {ANALYSIS_INDEX} ({len(errors)} errors)")
    if errors:
        for error in errors[:5]:
            print(f"  {error}")


if __name__ == "__main__":
    main()
