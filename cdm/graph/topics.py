"""Topic-profile edges: members who sponsor bills on similar topics.

Each member gets a topic vector from the topics of the bills they sponsor (and,
at lower weight, cosponsor), weighted by topic rarity. Edges score cosine
similarity, discounted for members with few bills.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from typing import Any

import numpy as np
from elasticsearch import Elasticsearch
from elasticsearch.helpers import scan
from numpy.typing import NDArray
from pydantic import BaseModel, ConfigDict

from cdm.graph.models import BillSignature, CongressEdgeStats, MemberEdge, Signal
from cdm.utils.topic_terms import dedupe_terms, keyword_label

OUTLIER_TOPIC = -1

Matrix = NDArray[np.float32]


class TopicSettings(BaseModel):
    model_config = ConfigDict(frozen=True)

    sponsor_weight: float = 1.0
    cosponsor_weight: float = 0.25
    confidence_bills: float = 5.0
    top_k: int = 50
    shared_topics: int = 3


class TopicModelReader:
    """Reads the latest topic model's labels and bill assignments."""

    def __init__(self, client: Elasticsearch, index: str) -> None:
        self.client = client
        self.index = index

    def latest_version(self) -> str | None:
        response = self.client.search(
            index=self.index,
            size=1,
            query={"term": {"kind": "topic"}},
            sort=[{"trained_at": {"order": "desc"}}],
            source_includes=["model_version"],
        )
        hits = response["hits"]["hits"]
        return hits[0]["_source"]["model_version"] if hits else None

    def _scan(self, version: str, kind: str) -> Iterator[dict[str, Any]]:
        query = {
            "bool": {
                "filter": [
                    {"term": {"kind": kind}},
                    {"term": {"model_version": version}},
                ]
            }
        }
        for hit in scan(self.client, index=self.index, query={"query": query}):
            yield hit["_source"]

    def assignments(self, version: str) -> dict[str, int]:
        return {
            source["doc_id"]: int(source["topic_id"])
            for source in self._scan(version, "assignment")
            if int(source["topic_id"]) != OUTLIER_TOPIC
        }

    def labels(self, version: str) -> dict[int, str]:
        labels: dict[int, str] = {}
        for source in self._scan(version, "topic"):
            topic_id = int(source["topic_id"])
            words = dedupe_terms(str(word) for word in source.get("top_words") or [])
            labels[topic_id] = (
                str(source.get("label") or "").strip()
                or keyword_label(words)
                or f"Topic {topic_id}"
            )
        return labels


class TopicGraphBuilder:
    """Turns bills and their topic assignments into top-k topic-similarity edges."""

    def __init__(
        self,
        bills: Sequence[BillSignature],
        assignments: dict[str, int],
        labels: dict[int, str],
        graph_version: str,
        settings: TopicSettings | None = None,
    ) -> None:
        self.bills = bills
        self.assignments = assignments
        self.labels = labels
        self.graph_version = graph_version
        self.settings = settings or TopicSettings()

    def _counts(
        self, members: dict[str, int], topics: dict[int, int]
    ) -> dict[int, Matrix]:
        """Weighted bills per member and topic, for each Congress."""
        settings = self.settings
        counts: dict[int, Matrix] = {}
        for bill in self.bills:
            topic = topics.get(self.assignments.get(bill.id, OUTLIER_TOPIC))
            if topic is None:
                continue
            matrix = counts.setdefault(
                bill.congress,
                np.zeros((len(members), len(topics)), dtype=np.float32),
            )
            for member in dict.fromkeys(bill.sponsor_ids):
                matrix[members[member], topic] += settings.sponsor_weight
            for member in dict.fromkeys(bill.cosponsor_ids):
                matrix[members[member], topic] += settings.cosponsor_weight
        return counts

    def _vectors(self, counts: Matrix, idf: NDArray[np.float32]) -> Matrix:
        vectors = np.log1p(counts) * idf
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        return np.divide(vectors, norms, out=np.zeros_like(vectors), where=norms > 0)

    def _scores(self, counts: Matrix, vectors: Matrix) -> Matrix:
        volume = counts.sum(axis=1)
        confidence = volume / (volume + self.settings.confidence_bills)
        scores = vectors @ vectors.T * np.sqrt(np.outer(confidence, confidence))
        np.fill_diagonal(scores, 0.0)
        return scores.astype(np.float32)

    def _top_indices(self, row: NDArray[np.float32]) -> NDArray[np.intp]:
        positive = np.flatnonzero(row > 0)
        if len(positive) <= self.settings.top_k:
            return positive
        best = np.argpartition(row[positive], -self.settings.top_k)[-self.settings.top_k :]
        return positive[best]

    def _shared_topics(
        self, first: NDArray[np.float32], second: NDArray[np.float32], topic_ids: list[int]
    ) -> list[str]:
        overlap = first * second
        best = np.argsort(overlap)[::-1][: self.settings.shared_topics]
        return [
            self.labels.get(topic_ids[position], f"Topic {topic_ids[position]}")
            for position in best
            if overlap[position] > 0
        ]

    def build(self) -> Iterator[MemberEdge]:
        member_ids = sorted({
            member
            for bill in self.bills
            if self.assignments.get(bill.id, OUTLIER_TOPIC) != OUTLIER_TOPIC
            for member in (*bill.sponsor_ids, *bill.cosponsor_ids)
        })
        members = {member: position for position, member in enumerate(member_ids)}
        topic_ids = sorted(set(self.assignments.values()) - {OUTLIER_TOPIC})
        topics = {topic: position for position, topic in enumerate(topic_ids)}
        by_congress = self._counts(members, topics)
        if not by_congress:
            return

        total = sum(by_congress.values())
        document_frequency = (total > 0).sum(axis=0)
        idf = (np.log((1 + len(members)) / (1 + document_frequency)) + 1).astype(np.float32)
        total_vectors = self._vectors(total, idf)
        total_scores = self._scores(total, total_vectors)
        congress_scores = {
            congress: self._scores(counts, self._vectors(counts, idf))
            for congress, counts in by_congress.items()
        }

        for position, member in enumerate(member_ids):
            candidates = set(self._top_indices(total_scores[position]).tolist())
            for scores in congress_scores.values():
                candidates.update(self._top_indices(scores[position]).tolist())
            for neighbor in sorted(candidates):
                yield MemberEdge(
                    graph_version=self.graph_version,
                    signal=Signal.TOPIC,
                    member=member,
                    neighbor=member_ids[neighbor],
                    score=float(total_scores[position, neighbor]),
                    shared_topics=self._shared_topics(
                        total_vectors[position], total_vectors[neighbor], topic_ids
                    ),
                    by_congress=[
                        CongressEdgeStats(
                            congress=congress,
                            score=float(scores[position, neighbor]),
                        )
                        for congress, scores in sorted(congress_scores.items())
                        if scores[position, neighbor] > 0
                    ],
                )
