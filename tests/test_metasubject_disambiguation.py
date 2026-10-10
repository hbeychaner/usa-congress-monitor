from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from cdm.utils.metasubject_namer import OllamaNameDisambiguator
from cdm.utils.metasubjects import (
    LargestTopicNamer,
    MetasubjectBuilder,
    MetasubjectOverrides,
    NamedGroup,
    StableIdMatcher,
    TopicVector,
)


class FixedNamer:
    def name(self, members: Sequence[TopicVector]) -> str:
        return "Transportation Policy"


class SuffixDisambiguator:
    def __init__(self) -> None:
        self.calls: list[tuple[list[int], set[str]]] = []

    def rename(
        self, colliding: Sequence[NamedGroup], taken: set[str]
    ) -> dict[int, str]:
        self.calls.append(([g.metasubject_id for g in colliding], taken))
        return {g.metasubject_id: f"{g.name} {g.metasubject_id}" for g in colliding}


def _topic(topic_id: int, size: int, vector: list[float]) -> TopicVector:
    return TopicVector(
        topic_id=topic_id,
        size=size,
        label=f"t{topic_id}",
        vector=np.array(vector, dtype=np.float32),
    )


def _topics() -> list[TopicVector]:
    return [_topic(0, 30, [1, 0, 0]), _topic(1, 10, [0, 1, 0])]


def _builder(
    disambiguator: SuffixDisambiguator | None,
    overrides: MetasubjectOverrides | None = None,
) -> MetasubjectBuilder:
    return MetasubjectBuilder(
        FixedNamer(), StableIdMatcher(0.85), 2, overrides, disambiguator
    )


def test_duplicate_names_keep_largest_and_rename_the_rest() -> None:
    disambiguator = SuffixDisambiguator()

    groups = _builder(disambiguator).build(_topics())

    names = {g.size: g.name for g in groups}
    assert names[30] == "Transportation Policy"
    assert names[10].startswith("Transportation Policy ")
    assert len(disambiguator.calls) == 1 and len(disambiguator.calls[0][0]) == 1


def test_overridden_name_is_pinned_and_other_group_renamed() -> None:
    disambiguator = SuffixDisambiguator()
    first = _builder(None).build(_topics())
    pinned_id = next(g.metasubject_id for g in first if g.size == 30)

    groups = _builder(
        disambiguator, MetasubjectOverrides(names={pinned_id: "Transportation Policy"})
    ).build(_topics())

    assert {g.metasubject_id: g.name for g in groups}[
        pinned_id
    ] == "Transportation Policy"
    assert [g.name for g in groups].count("Transportation Policy") == 1


def test_without_disambiguator_duplicates_remain() -> None:
    groups = _builder(None).build(_topics())

    assert [g.name for g in groups] == ["Transportation Policy"] * 2
    assert LargestTopicNamer().name(_topics()) == "t0"


class ScriptedOllama:
    def __init__(self, replies: list[str]) -> None:
        self.replies = replies
        self.prompts: list[str] = []

    def chat(self, system: str, user: str) -> str:
        self.prompts.append(user)
        return self.replies.pop(0)


def _group(metasubject_id: int, labels: list[str]) -> NamedGroup:
    return NamedGroup(
        metasubject_id=metasubject_id,
        name="Foreign Policy",
        members=[
            _topic(i, 10 - i, [1, 0, 0]).model_copy(update={"label": label})
            for i, label in enumerate(labels)
        ],
    )


def test_ollama_disambiguator_retries_taken_names_and_shows_other_group() -> None:
    ollama = ScriptedOllama(["Foreign Policy", "Trade Agreements", "Diplomatic Affairs"])
    resolver = OllamaNameDisambiguator(ollama)  # type: ignore[arg-type]

    renamed = resolver.rename(
        [_group(1, ["tariffs", "trade deals"]), _group(2, ["embassies"])],
        {"foreign policy"},
    )

    assert renamed[1] == "Trade Agreements"
    assert "embassies" in ollama.prompts[0] and "tariffs" in ollama.prompts[0]


def test_ollama_disambiguator_falls_back_to_largest_topic() -> None:
    resolver = OllamaNameDisambiguator(ScriptedOllama([""] * 4))  # type: ignore[arg-type]

    renamed = resolver.rename(
        [_group(1, ["tariffs", "trade deals"]), _group(2, ["embassies"])], set()
    )

    assert renamed[1] == "Foreign Policy: tariffs"
