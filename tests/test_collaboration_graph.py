from cdm.graph.collaboration import CollaborationGraphBuilder, CollaborationSettings
from cdm.graph.models import BillSignature, MemberEdge, Signal


def _bill(congress: int, sponsor: str, cosponsors: list[str]) -> BillSignature:
    return BillSignature(
        congress=congress, sponsor_ids=[sponsor], cosponsor_ids=cosponsors
    )


def _edges(bills: list[BillSignature], **settings: float) -> dict[tuple[str, str], MemberEdge]:
    builder = CollaborationGraphBuilder(
        bills, "v1", CollaborationSettings(**settings)
    )
    return {(edge.member, edge.neighbor): edge for edge in builder.build()}


def test_edges_are_symmetric_and_carry_counts():
    edges = _edges([_bill(118, "A", ["B"]), _bill(118, "B", ["A"]), _bill(118, "C", ["A"])])
    forward, backward = edges[("A", "B")], edges[("B", "A")]
    assert forward.signal is Signal.COLLABORATION
    assert forward.score == backward.score
    stats = forward.by_congress[0]
    assert (stats.member_sponsored, stats.neighbor_sponsored) == (1, 1)
    assert backward.by_congress[0].member_sponsored == 1
    assert forward.shared_bills == 2


def test_all_time_score_spans_congresses_and_keeps_breakdown():
    edges = _edges([_bill(117, "A", ["B"]), _bill(118, "A", ["B"])])
    edge = edges[("A", "B")]
    assert [stats.congress for stats in edge.by_congress] == [117, 118]
    assert edge.score > edge.by_congress[0].score


def test_top_k_limits_neighbors_per_signal_scope():
    bills = [_bill(118, "A", [name]) for name in ("B", "C", "D", "E")]
    edges = _edges(bills, top_k=2)
    assert len([key for key in edges if key[0] == "A"]) == 2


def test_cosigners_of_same_bill_are_linked():
    edges = _edges([_bill(118, "A", ["B", "C"])])
    assert edges[("B", "C")].by_congress[0].co_signed == 1.0
