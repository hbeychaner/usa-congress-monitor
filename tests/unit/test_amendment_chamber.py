from datetime import datetime

from src.models.bills import Amendment
from src.models.people import Chamber


def mk(base_chamber):
    return Amendment(congress=118, number="1", type="HAMDT", updateDate=datetime.now(), chamber=base_chamber)


def test_chamber_variants():
    assert mk("House of Representatives").chamber == Chamber.HOUSE
    assert mk("house").chamber == Chamber.HOUSE
    assert mk("H").chamber == Chamber.HOUSE
    assert mk("hr").chamber == Chamber.HOUSE
    assert mk("Senate").chamber == Chamber.SENATE
    assert mk("S").chamber == Chamber.SENATE
    assert mk("Sen.").chamber == Chamber.SENATE


def test_unknown_chamber_normalizes_to_none():
    assert mk("Unknown Chamber").chamber is None
