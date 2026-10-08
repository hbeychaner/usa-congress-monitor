from cdm.graph.models import MemberEdge, RollCallVotes, Signal
from cdm.graph.voting import VotingGraphBuilder, VotingSettings


def _roll(yea: list[str], nay: list[str], split: bool = True, congress: int = 118) -> RollCallVotes:
    return RollCallVotes(congress=congress, party_split=split, yea_ids=yea, nay_ids=nay)


def _edges(rolls: list[RollCallVotes], **settings: float) -> dict[tuple[str, str], MemberEdge]:
    builder = VotingGraphBuilder(rolls, "v1", VotingSettings(**settings))
    return {(edge.member, edge.neighbor): edge for edge in builder.build()}


def test_agreement_counts_and_symmetry():
    edges = _edges([_roll(["A", "B"], ["C"]), _roll(["A"], ["B", "C"]), _roll(["A", "B"], [], split=False)])
    forward = edges[("A", "B")]
    stats = forward.by_congress[0]
    assert forward.signal is Signal.VOTING
    assert (stats.shared_votes, stats.agreed_votes) == (3, 2)
    assert (stats.shared_split_votes, stats.agreed_split_votes) == (2, 1)
    assert forward.score == edges[("B", "A")].score


def test_more_agreement_scores_higher_and_shrinks_toward_prior():
    rolls = [_roll(["A", "B"], ["C"]) for _ in range(4)]
    edges = _edges(rolls, shrinkage_votes=10.0)
    assert edges[("A", "B")].score > 0.5 > edges[("A", "C")].score
    assert edges[("A", "B")].score < 1.0


def test_pairs_without_split_votes_have_no_edge():
    edges = _edges([_roll(["A", "B"], [], split=False)])
    assert edges == {}


def test_abstentions_do_not_count_as_shared():
    edges = _edges([_roll(["A"], ["B"]), _roll(["A", "B"], []), _roll(["A"], [])])
    assert edges[("A", "B")].by_congress[0].shared_votes == 2
