"""Preview Ollama topic titles for a few topics of the latest model, nothing is written.

Usage:
    uv run python scripts/preview_topic_labels.py --count 8 --seed 1
    uv run python scripts/preview_topic_labels.py --topic-ids 0 3 255
"""

from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from elasticsearch import Elasticsearch

from cdm.config import get_config
from cdm.container import Container
from cdm.store.opensearch import read_alias
from cdm.utils.topic_labeler import TopicLabeler
from cdm.utils.topic_modeler import build_topic_documents
from cdm.utils.topic_records import TopicSummaryRow

SAMPLE_DOCS = 8
MIN_SIZE = 15


class LabelPreview:
    """Compare keyword names with Ollama titles for a handful of topics."""

    def __init__(
        self, client: Elasticsearch, labeler: TopicLabeler, analysis_index: str
    ) -> None:
        self._client = client
        self._labeler = labeler
        self._index = analysis_index
        self._version = self._latest_version()

    def _latest_version(self) -> str:
        response = self._client.search(
            index=self._index,
            size=0,
            aggs={"v": {"terms": {"field": "model_version", "size": 1, "order": {"_key": "desc"}}}},
        )
        return str(response["aggregations"]["v"]["buckets"][0]["key"])

    def _topics(self, topic_ids: list[int] | None, count: int, seed: int) -> list[TopicSummaryRow]:
        response = self._client.search(
            index=self._index,
            size=10000,
            query={
                "bool": {
                    "filter": [
                        {"term": {"kind": "topic"}},
                        {"term": {"model_version": self._version}},
                    ]
                }
            },
        )
        topics = [TopicSummaryRow(**hit["_source"]) for hit in response["hits"]["hits"]]
        topics = [topic for topic in topics if topic.topic_id != -1]
        if topic_ids:
            return [topic for topic in topics if topic.topic_id in topic_ids]
        eligible = [topic for topic in topics if topic.size >= MIN_SIZE]
        return random.Random(seed).sample(eligible, min(count, len(eligible)))

    def _sample_texts(self, topic_id: int) -> list[str]:
        assignments = self._client.search(
            index=self._index,
            size=SAMPLE_DOCS,
            query={
                "bool": {
                    "filter": [
                        {"term": {"kind": "assignment"}},
                        {"term": {"model_version": self._version}},
                        {"term": {"topic_id": topic_id}},
                    ]
                }
            },
            sort=[{"probability": "desc"}],
        )
        doc_ids = [hit["_source"]["doc_id"] for hit in assignments["hits"]["hits"]]
        bills = self._client.search(
            index=read_alias("bill"), size=len(doc_ids), query={"ids": {"values": doc_ids}}
        )
        return [doc.embed_text for doc in build_topic_documents(bills["hits"]["hits"])]

    def run(self, topic_ids: list[int] | None, count: int, seed: int) -> None:
        print(f"Model version: {self._version}\n")
        for topic in self._topics(topic_ids, count, seed):
            texts = self._sample_texts(topic.topic_id)
            label = self._labeler.generate(topic.top_words, texts)
            print(f"[{topic.topic_id}] size={topic.size}")
            print(f"  keywords: {topic.name}")
            print(f"  ollama:   {label or '(no label)'}")
            for text in texts[:2]:
                print(f"    - {text[:140]}")
            print()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=8)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--topic-ids", type=int, nargs="*")
    args = parser.parse_args()
    config = get_config()
    container = Container(config)
    LabelPreview(
        container.elastic_client, container.topic_labeler, config.elastic.analysis_index
    ).run(args.topic_ids, args.count, args.seed)


if __name__ == "__main__":
    main()
