"""Group granular topics into ~30 broad metasubjects with stable ids across retrains."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from datetime import UTC, datetime
from enum import StrEnum
from typing import Protocol

import numpy as np
from pydantic import BaseModel, ConfigDict, Field
from scipy.optimize import linear_sum_assignment
from sklearn.cluster import AgglomerativeClustering

from cdm.utils.topic_terms import dedupe_terms

MAX_GROUP_WORDS = 10
MONTHS_PER_QUARTER = 3


class TopicVector(BaseModel):
    """A topic's centroid embedding plus the text used to describe it."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    topic_id: int
    size: int
    label: str
    top_words: list[str] = Field(default_factory=list)
    vector: np.ndarray


class Metasubject(BaseModel):
    metasubject_id: int
    name: str
    topic_ids: list[int]
    size: int
    top_words: list[str]
    centroid: list[float]


class MetasubjectOverTimeRow(BaseModel):
    metasubject_id: int
    frequency: int
    timestamp: str


class MetasubjectNamer(Protocol):
    def name(self, members: Sequence[TopicVector]) -> str: ...


class MetasubjectOverrides(BaseModel):
    """Hand-curated names that win over generated and carried-over ones."""

    names: dict[int, str] = Field(default_factory=dict)


class AssignedBy(StrEnum):
    CLUSTER = "cluster"
    NEAREST = "nearest"


class MetasubjectAssignment(BaseModel):
    doc_id: str
    metasubject_id: int
    confidence: float
    assigned_by: AssignedBy
    low_confidence: bool


class LargestTopicNamer:
    """Fallback namer: the label of the group's largest topic."""

    def name(self, members: Sequence[TopicVector]) -> str:
        return max(members, key=lambda topic: topic.size).label


def _unit(vector: np.ndarray) -> np.ndarray:
    norm = np.linalg.norm(vector)
    return vector / norm if norm else vector


class StableIdMatcher:
    """Assigns each new group the id of its most similar previous group."""

    def __init__(self, min_similarity: float) -> None:
        self.min_similarity = min_similarity

    def match(
        self, centroids: Sequence[np.ndarray], previous: Sequence[Metasubject]
    ) -> list[Metasubject | None]:
        """For each new centroid, the matched previous group or None when new."""
        matches: list[Metasubject | None] = [None] * len(centroids)
        if not centroids or not previous:
            return matches
        old = np.vstack([_unit(np.asarray(p.centroid)) for p in previous])
        new = np.vstack([_unit(c) for c in centroids])
        rows, cols = linear_sum_assignment(-(new @ old.T))
        for row, col in zip(rows, cols):
            if float(new[row] @ old[col]) >= self.min_similarity:
                matches[row] = previous[col]
        return matches


class MetasubjectBuilder:
    """Clusters topic centroids and names the groups."""

    def __init__(
        self,
        namer: MetasubjectNamer,
        matcher: StableIdMatcher,
        target_groups: int,
        overrides: MetasubjectOverrides | None = None,
    ) -> None:
        self.namer = namer
        self.matcher = matcher
        self.target_groups = target_groups
        self.overrides = overrides or MetasubjectOverrides()

    def _cluster(self, topics: Sequence[TopicVector]) -> list[list[TopicVector]]:
        if len(topics) <= 1:
            return [list(topics)] if topics else []
        vectors = np.vstack([_unit(topic.vector) for topic in topics])
        count = min(self.target_groups, len(topics))
        labels = AgglomerativeClustering(
            n_clusters=count, metric="cosine", linkage="average"
        ).fit_predict(vectors)
        groups: dict[int, list[TopicVector]] = defaultdict(list)
        for topic, label in zip(topics, labels):
            groups[int(label)].append(topic)
        return list(groups.values())

    @staticmethod
    def _centroid(members: Sequence[TopicVector]) -> np.ndarray:
        weights = np.array([topic.size for topic in members], dtype=np.float64)
        stacked = np.vstack([_unit(topic.vector) for topic in members])
        return _unit(np.average(stacked, axis=0, weights=weights))

    def build(
        self,
        topics: Sequence[TopicVector],
        previous: Sequence[Metasubject] = (),
    ) -> list[Metasubject]:
        """Group non-outlier topics; ids and names carry over from ``previous``."""
        groups = self._cluster([topic for topic in topics if topic.topic_id != -1])
        centroids = [self._centroid(members) for members in groups]
        matches = self.matcher.match(centroids, previous)
        next_id = max((p.metasubject_id for p in previous), default=0) + 1
        results: list[Metasubject] = []
        for members, centroid, match in zip(groups, centroids, matches):
            if match is None:
                metasubject_id, name = next_id, self.namer.name(members)
                next_id += 1
            else:
                metasubject_id, name = match.metasubject_id, match.name
            ranked = sorted(members, key=lambda topic: topic.size, reverse=True)
            name = self.overrides.names.get(metasubject_id, name)
            words = dedupe_terms(word for topic in ranked for word in topic.top_words)
            results.append(
                Metasubject(
                    metasubject_id=metasubject_id,
                    name=name,
                    topic_ids=sorted(topic.topic_id for topic in members),
                    size=sum(topic.size for topic in members),
                    top_words=list(words)[:MAX_GROUP_WORDS],
                    centroid=centroid.tolist(),
                )
            )
        return sorted(results, key=lambda group: group.size, reverse=True)


def topic_to_metasubject(metasubjects: Sequence[Metasubject]) -> dict[int, int]:
    return {
        topic_id: group.metasubject_id
        for group in metasubjects
        for topic_id in group.topic_ids
    }


class MetasubjectAssigner:
    """Gives every document a metasubject; outliers go to the nearest centroid."""

    def __init__(
        self,
        metasubjects: Sequence[Metasubject],
        low_confidence_below: float,
    ) -> None:
        self.metasubjects = list(metasubjects)
        self.ids = [group.metasubject_id for group in metasubjects]
        self.centroids = np.vstack([
            _unit(np.asarray(g.centroid)) for g in metasubjects
        ])
        self.by_topic = topic_to_metasubject(metasubjects)
        self.low_confidence_below = low_confidence_below

    def assign(
        self,
        doc_ids: Sequence[str],
        topic_ids: Sequence[int],
        embeddings: np.ndarray,
    ) -> list[MetasubjectAssignment]:
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        similarities = (embeddings / np.where(norms == 0, 1, norms)) @ self.centroids.T
        column_of = {
            metasubject_id: column for column, metasubject_id in enumerate(self.ids)
        }
        nearest = similarities.argmax(axis=1)
        results: list[MetasubjectAssignment] = []
        for row, (doc_id, topic_id) in enumerate(zip(doc_ids, topic_ids)):
            mapped = self.by_topic.get(topic_id)
            if mapped is not None:
                column, assigned_by = column_of[mapped], AssignedBy.CLUSTER
            else:
                column, assigned_by = int(nearest[row]), AssignedBy.NEAREST
            confidence = float(similarities[row, column])
            results.append(
                MetasubjectAssignment(
                    doc_id=doc_id,
                    metasubject_id=self.ids[column],
                    confidence=confidence,
                    assigned_by=assigned_by,
                    low_confidence=confidence < self.low_confidence_below,
                )
            )
        return results

    def with_sizes(
        self, assignments: Sequence[MetasubjectAssignment]
    ) -> list[Metasubject]:
        """Metasubjects resized to count every assigned document, outliers included."""
        counts: dict[int, int] = defaultdict(int)
        for assignment in assignments:
            counts[assignment.metasubject_id] += 1
        return sorted(
            (
                g.model_copy(update={"size": counts[g.metasubject_id]})
                for g in self.metasubjects
            ),
            key=lambda group: group.size,
            reverse=True,
        )


class QuarterlyTrendBuilder:
    """Counts documents per metasubject and calendar quarter."""

    @staticmethod
    def _quarter_start(moment: datetime) -> str:
        month = MONTHS_PER_QUARTER * ((moment.month - 1) // MONTHS_PER_QUARTER) + 1
        return datetime(moment.year, month, 1, tzinfo=UTC).isoformat()

    def build(
        self,
        assignments: Sequence[MetasubjectAssignment],
        timestamps: Sequence[datetime | None],
    ) -> list[MetasubjectOverTimeRow]:
        totals: dict[tuple[int, str], int] = defaultdict(int)
        for assignment, moment in zip(assignments, timestamps):
            if moment is not None:
                totals[(assignment.metasubject_id, self._quarter_start(moment))] += 1
        return [
            MetasubjectOverTimeRow(
                metasubject_id=metasubject_id, frequency=frequency, timestamp=timestamp
            )
            for (metasubject_id, timestamp), frequency in sorted(totals.items())
        ]
