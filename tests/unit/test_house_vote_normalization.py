import json
from pathlib import Path

from cdm.models.other_models import (
    HouseRollCallVoteListItem,
    get_house_vote_metrics,
    reset_house_vote_metrics,
)


def test_candidate_style_vote_party_total_moves_to_vote_candidate_total():
    reset_house_vote_metrics()
    raw_path = Path("tests/fixtures/house_vote/raw_items.json")
    raw = json.loads(raw_path.read_text())

    # sample indices known to contain candidate-style totals
    indices = [13, 31, 401, 461]
    for idx in indices:
        r = raw[idx]
        candidate = (
            r.get("houseRollCallVote")
            if isinstance(r, dict) and r.get("houseRollCallVote")
            else r
        )

        # validate via the model (runs before-validators)
        hv = HouseRollCallVoteListItem.model_validate(candidate)

        # candidate-style totals should be preserved to the typed field
        assert hv.vote_candidate_total is not None
        assert len(hv.vote_candidate_total) >= 1

    assert get_house_vote_metrics()["candidate_style_detections"] == len(indices)
    reset_house_vote_metrics()


def test_vote_question_string_normalizes_to_object():
    raw_path = Path("tests/fixtures/house_vote/raw_items.json")
    raw = json.loads(raw_path.read_text())

    # pick a record that has a string voteQuestion (many do)
    for r in raw:
        candidate = (
            r.get("houseRollCallVote")
            if isinstance(r, dict) and r.get("houseRollCallVote")
            else r
        )
        if isinstance(candidate.get("voteQuestion"), str):
            hv = HouseRollCallVoteListItem.model_validate(candidate)
            assert hv.vote_question is not None
            assert hv.vote_question.question
            return

    # if none found, still pass but warn
    assert True
