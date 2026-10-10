from __future__ import annotations

from datetime import UTC, datetime

import numpy as np

from cdm.utils.metasubjects import (
    AssignedBy,
    LargestTopicNamer,
    MetasubjectAssigner,
    MetasubjectBuilder,
    MetasubjectOverrides,
    QuarterlyTrendBuilder,
    StableIdMatcher,
    TopicVector,
    topic_to_metasubject,
)


def _builder(
    min_similarity: float = 0.85, overrides: MetasubjectOverrides | None = None
) -> MetasubjectBuilder:
    return MetasubjectBuilder(
        LargestTopicNamer(),
        StableIdMatcher(min_similarity),
        target_groups=2,
        overrides=overrides,
    )


def _topic(topic_id: int, size: int, vector: list[float], label: str) -> TopicVector:
    return TopicVector(
        topic_id=topic_id,
        size=size,
        label=label,
        top_words=[label.lower()],
        vector=np.array(vector, dtype=np.float32),
    )


def _topics() -> list[TopicVector]:
    return [
        _topic(-1, 99, [1, 1, 1], "Outliers"),
        _topic(0, 10, [1, 0.1, 0], "Tax Rates"),
        _topic(1, 30, [1, 0.2, 0], "Tax Credits"),
        _topic(2, 20, [0, 1, 0.1], "Hospital Funding"),
        _topic(3, 5, [0, 1, 0.2], "Drug Pricing"),
    ]


def test_groups_similar_topics_and_ignores_outliers() -> None:
    builder = _builder()

    groups = builder.build(_topics())

    assert sorted(g.topic_ids for g in groups) == [[0, 1], [2, 3]]
    by_topic = topic_to_metasubject(groups)
    assert -1 not in by_topic
    assert {g.name for g in groups} == {"Tax Credits", "Hospital Funding"}


def test_ids_and_names_survive_a_retrain_with_renumbered_topics() -> None:
    builder = _builder()
    first = builder.build(_topics())
    renamed = [
        topic.model_copy(update={"topic_id": topic.topic_id + 10, "label": "New"})
        for topic in _topics()
        if topic.topic_id != -1
    ]

    second = builder.build(renamed, previous=first)

    assert {g.metasubject_id: g.name for g in second} == {
        g.metasubject_id: g.name for g in first
    }


def test_unmatched_group_gets_a_fresh_id() -> None:
    builder = _builder(min_similarity=0.99)
    first = builder.build(_topics())
    shifted = [
        topic.model_copy(update={"vector": topic.vector[::-1].copy()})
        for topic in _topics()
    ]

    second = builder.build(shifted, previous=first)

    assert {g.metasubject_id for g in second}.isdisjoint({
        g.metasubject_id for g in first
    })


def test_override_beats_generated_and_carried_names() -> None:
    builder = _builder()
    first = builder.build(_topics())
    target = first[0]
    overridden = _builder(
        overrides=MetasubjectOverrides(names={target.metasubject_id: "Custom"})
    ).build(_topics(), previous=first)

    assert {g.metasubject_id: g.name for g in overridden}[
        target.metasubject_id
    ] == "Custom"


def test_outliers_go_to_nearest_metasubject_with_confidence() -> None:
    groups = _builder().build(_topics())
    tax = next(g for g in groups if 0 in g.topic_ids)
    embeddings = np.array([[1, 0.15, 0], [0, 1, 0.1], [0.5, -1, -1]], dtype=np.float32)

    assigned = MetasubjectAssigner(groups, low_confidence_below=0.9).assign(
        ["a", "b", "c"], [0, -1, -1], embeddings
    )

    assert (assigned[0].metasubject_id, assigned[0].assigned_by) == (
        tax.metasubject_id,
        AssignedBy.CLUSTER,
    )
    assert assigned[1].assigned_by == AssignedBy.NEAREST
    assert assigned[1].metasubject_id != tax.metasubject_id
    assert not assigned[1].low_confidence
    assert assigned[2].low_confidence


def test_quarterly_trend_counts_assignments_and_skips_undated() -> None:
    groups = _builder().build(_topics())
    embeddings = np.array([[1, 0.1, 0]] * 3, dtype=np.float32)
    assigned = MetasubjectAssigner(groups, low_confidence_below=0.35).assign(
        ["a", "b", "c"], [0, 0, 0], embeddings
    )
    dates = [datetime(2020, 1, 5, tzinfo=UTC), datetime(2020, 3, 30, tzinfo=UTC), None]

    rows = QuarterlyTrendBuilder().build(assigned, dates)

    assert [(r.timestamp[:10], r.frequency) for r in rows] == [("2020-01-01", 2)]
