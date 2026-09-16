from datetime import datetime

from cdm.utils.topic_modeler import (
    TopicAssignment,
    TopicDocument,
    _assignments,
    build_topic_documents,
)


def _hit(doc_id="bill:119:hr:1", **source):
    return {"_id": doc_id, "_source": source}


def test_builds_document_from_title_only():
    docs = build_topic_documents([_hit(title="Clean Water Act Amendments")])
    assert docs == [
        TopicDocument(doc_id="bill:119:hr:1", text="Clean Water Act Amendments")
    ]


def test_appends_latest_summary_by_action_date():
    docs = build_topic_documents([
        _hit(
            title="A bill",
            summaries=[
                {"action_date": "2025-01-01", "text": "Old summary."},
                {"action_date": "2025-06-01", "text": "<p>New   summary.</p>"},
            ],
        )
    ])
    assert docs[0].text == "A bill. New summary."


def test_timestamp_prefers_introduced_date():
    docs = build_topic_documents([
        _hit(
            title="A bill",
            introduced_date="2025-03-04",
            latest_action={"action_date": "2025-09-01"},
        )
    ])
    assert docs[0].timestamp == datetime(2025, 3, 4)


def test_timestamp_falls_back_to_latest_action():
    docs = build_topic_documents([
        _hit(title="A bill", latest_action={"action_date": "2025-09-01"})
    ])
    assert docs[0].timestamp == datetime(2025, 9, 1)


def test_skips_hits_without_text():
    docs = build_topic_documents([
        _hit(title=""),
        _hit(doc_id="bill:119:hr:2", title="Kept"),
    ])
    assert [doc.doc_id for doc in docs] == ["bill:119:hr:2"]


def test_ignores_unparseable_dates():
    docs = build_topic_documents([_hit(title="A bill", introduced_date="not-a-date")])
    assert docs[0].timestamp is None


def test_assignments_handle_scalar_and_array_probabilities():
    docs = [
        TopicDocument(doc_id="a", text="x"),
        TopicDocument(doc_id="b", text="y"),
    ]

    class ArrayLike:
        def max(self):
            return 0.75

    result = _assignments(docs, [3, -1], [0.5, ArrayLike()])
    assert result == [
        TopicAssignment(doc_id="a", topic_id=3, probability=0.5),
        TopicAssignment(doc_id="b", topic_id=-1, probability=0.75),
    ]


def test_assignments_without_probabilities():
    docs = [TopicDocument(doc_id="a", text="x")]
    assert _assignments(docs, [0], None) == [
        TopicAssignment(doc_id="a", topic_id=0, probability=0.0)
    ]
