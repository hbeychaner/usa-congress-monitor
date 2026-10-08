from cdm.graph.models import BillSignature, MemberEdge, Signal
from cdm.graph.topics import TopicGraphBuilder, TopicSettings


def _bill(bill_id: str, sponsor: str, congress: int = 118) -> BillSignature:
    return BillSignature(id=bill_id, congress=congress, sponsor_ids=[sponsor])


def _edges(bills: list[BillSignature], assignments: dict[str, int]) -> dict[tuple[str, str], MemberEdge]:
    labels = {1: "health care", 2: "taxes", 3: "defense"}
    builder = TopicGraphBuilder(bills, assignments, labels, "v1", TopicSettings())
    return {(edge.member, edge.neighbor): edge for edge in builder.build()}


def test_shared_topic_members_are_linked_with_labels():
    bills = [_bill("b1", "A"), _bill("b2", "B"), _bill("b3", "B"), _bill("b4", "C")]
    edges = _edges(bills, {"b1": 1, "b2": 1, "b3": 2, "b4": 2})
    forward = edges[("A", "B")]
    assert forward.signal is Signal.TOPIC
    assert forward.shared_topics == ["health care"]
    assert forward.score == edges[("B", "A")].score
    assert ("A", "C") not in edges


def test_outlier_and_unassigned_bills_are_ignored():
    edges = _edges([_bill("b1", "A"), _bill("b2", "B")], {"b1": -1})
    assert edges == {}


def test_more_bills_raise_confidence():
    few = _edges([_bill("a1", "A"), _bill("b1", "B")], {"a1": 1, "b1": 1})
    many = _edges(
        [_bill(f"a{n}", "A") for n in range(10)] + [_bill(f"b{n}", "B") for n in range(10)],
        {f"{who}{n}": 1 for who in "ab" for n in range(10)},
    )
    assert many[("A", "B")].score > few[("A", "B")].score
