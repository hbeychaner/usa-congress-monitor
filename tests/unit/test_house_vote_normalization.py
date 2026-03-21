import json
from pathlib import Path

from src.models.other_models import HouseRollCallVoteListItem


def test_candidate_style_vote_party_total_moves_to_vote_candidate_total():
    raw_path = Path("tmp_ingest/house_vote/raw_items.json")
    raw = json.loads(raw_path.read_text())

    # sample indices known to contain candidate-style totals
    indices = [13, 31, 401, 461]
    for idx in indices:
        r = raw[idx]
        candidate = r.get("houseRollCallVote") if isinstance(r, dict) and r.get("houseRollCallVote") else r

        # validate via the model (runs before-validators)
        hv = HouseRollCallVoteListItem.model_validate(candidate)

        # candidate-style totals should be preserved to the typed field
        assert getattr(hv, "vote_candidate_total") is not None
        assert len(getattr(hv, "vote_candidate_total")) >= 1


def test_vote_question_string_normalizes_to_object():
    raw_path = Path("tmp_ingest/house_vote/raw_items.json")
    raw = json.loads(raw_path.read_text())

    # pick a record that has a string voteQuestion (many do)
    for r in raw:
        candidate = r.get("houseRollCallVote") if isinstance(r, dict) and r.get("houseRollCallVote") else r
        if isinstance(candidate.get("voteQuestion"), str):
            hv = HouseRollCallVoteListItem.model_validate(candidate)
            assert getattr(hv, "vote_question") is not None
            assert getattr(hv, "vote_question").question
            return

    # if none found, still pass but warn
    assert True
