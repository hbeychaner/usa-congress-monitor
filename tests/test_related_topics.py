from typing import Any

from cdm.backend.services.topic_service import TopicService


class CentroidTopics(TopicService):
    def __init__(self) -> None:
        pass

    def _search(self, body: dict[str, Any]) -> dict[str, Any] | None:
        topics = [
            (-1, [1.0, 0.0]),
            (1, [1.0, 0.0]),
            (2, [0.9, 0.1]),
            (3, [0.0, 1.0]),
            (4, None),
        ]
        return {
            "hits": {
                "hits": [
                    {"_source": {"topic_id": i, "centroid": vector}}
                    for i, vector in topics
                ]
            }
        }


def test_related_topics_skip_outlier_and_missing_centroids() -> None:
    related = CentroidTopics().related_topics("v1", 1, {})

    assert [item.topic_id for item in related] == [2, 3]
    assert related[0].label == "Topic 2"
    assert related[0].similarity > 0.99


def test_related_topics_empty_for_unknown_id() -> None:
    assert CentroidTopics().related_topics("v1", 99, {}) == []
