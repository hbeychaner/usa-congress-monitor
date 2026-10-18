"""Builds every topic's party perspectives for one Congress from the latest topic model."""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Callable
from dataclasses import dataclass

from cdm.config import PerspectiveConfig
from cdm.graph.topics import TopicModelReader
from cdm.perspectives.boilerplate import BoilerplateLearner
from cdm.perspectives.builder import PerspectiveBuilder
from cdm.perspectives.corpus import CongressCorpusReader
from cdm.perspectives.lexicon import BoilerplateLexicon
from cdm.perspectives.models import TopicPerspectives

BuilderFactory = Callable[[BoilerplateLexicon], PerspectiveBuilder]
TopicCallback = Callable[[TopicPerspectives], None]


@dataclass(frozen=True)
class PerspectiveRun:
    congress: int
    model_version: str
    lexicon: BoilerplateLexicon
    bills: int
    assigned: int
    results: list[TopicPerspectives]


class NoTopicModelError(RuntimeError):
    """Raised when no topic model has been trained yet."""


class PerspectiveRunner:
    """Learns a Congress's boilerplate, then builds each sufficiently large topic."""

    def __init__(
        self,
        config: PerspectiveConfig,
        topics: TopicModelReader,
        corpus: CongressCorpusReader,
        learner: BoilerplateLearner,
        builders: BuilderFactory,
    ) -> None:
        self.config = config
        self.topics = topics
        self.corpus = corpus
        self.learner = learner
        self.builders = builders

    def run(
        self,
        congress: int,
        *,
        topic_ids: list[int] | None = None,
        top_topics: int | None = None,
        on_topic: TopicCallback | None = None,
    ) -> PerspectiveRun:
        version = self.topics.latest_version()
        if version is None:
            raise NoTopicModelError("no trained topic model")
        assignments = self.topics.assignments(version)
        labels = self.topics.labels(version)
        corpus = self.corpus.read(congress)
        bills_by_topic: defaultdict[int, list[str]] = defaultdict(list)
        for doc_id, topic in sorted(assignments.items()):
            if topic >= 0 and doc_id in corpus.bills:
                bills_by_topic[topic].append(doc_id)
        lexicon = self.learner.learn(
            {
                topic: [corpus.bills[doc_id].text for doc_id in doc_ids]
                for topic, doc_ids in bills_by_topic.items()
            }
        )
        builder = self.builders(lexicon)
        results: list[TopicPerspectives] = []
        for topic in self._selected(bills_by_topic, topic_ids, top_topics):
            result = builder.build(
                congress=congress,
                topic_id=topic,
                topic_label=labels.get(topic, f"Topic {topic}"),
                bills=[corpus.bills[doc_id] for doc_id in bills_by_topic[topic]],
            )
            results.append(result)
            if on_topic:
                on_topic(result)
        return PerspectiveRun(
            congress=congress,
            model_version=version,
            lexicon=lexicon,
            bills=len(corpus.bills),
            assigned=sum(len(ids) for ids in bills_by_topic.values()),
            results=results,
        )

    def _selected(
        self,
        bills_by_topic: dict[int, list[str]],
        topic_ids: list[int] | None,
        top_topics: int | None,
    ) -> list[int]:
        if topic_ids:
            return [topic for topic in topic_ids if topic in bills_by_topic]
        sizes = Counter({topic: len(ids) for topic, ids in bills_by_topic.items()})
        ranked = [topic for topic, _ in sizes.most_common(top_topics)]
        floor = self.config.perspective_min_topic_bills
        return [topic for topic in ranked if sizes[topic] >= floor]
