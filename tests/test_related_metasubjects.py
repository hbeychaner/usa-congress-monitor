from typing import Any

from cdm.backend.services.topic_service import TopicService


class CentroidTopics(TopicService):
    def __init__(self) -> None:
        pass

    def _search(self, body: dict[str, Any]) -> dict[str, Any] | None:
        groups = [
            (1, "Labor and Employment", [1.0, 0.0]),
            (2, "Labor Rights", [0.9, 0.1]),
            (3, "Taxation", [0.0, 1.0]),
        ]
        return {
            "hits": {
                "hits": [
                    {"_source": {"metasubject_id": i, "name": name, "centroid": vector}}
                    for i, name, vector in groups
                ]
            }
        }


def test_related_metasubjects_rank_by_centroid_similarity() -> None:
    related = CentroidTopics().related_metasubjects("v1", 1)

    assert [item.metasubject_id for item in related] == [2, 3]
    assert related[0].similarity > 0.99 and related[1].similarity == 0.0


def test_related_metasubjects_empty_for_unknown_id() -> None:
    assert CentroidTopics().related_metasubjects("v1", 99) == []
