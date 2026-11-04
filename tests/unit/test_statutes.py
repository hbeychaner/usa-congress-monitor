import hashlib
from pathlib import Path

import pytest
from pydantic import AnyHttpUrl

from cdm.config.statutes import StatutesSettings
from cdm.ingest.statutes import (
    StatuteLawKind,
    StatuteRejectedLaw,
    StatutesParseError,
    StatutesReader,
    StatuteVolume,
)


class Fixture:
    @staticmethod
    def law(*, kind: str = "public", number: int = 1, body: str | None = None) -> str:
        content = (
            "<longTitle><ref href='/us/bill/94/hr/1'>H.R. 1</ref></longTitle>"
            "<p>An inter<i>national</i> program.</p><p>Second paragraph.</p>"
            if body is None
            else body
        )
        return (
            "<component><pLaw><meta><dc:title>An Act</dc:title>"
            f"<publicPrivate>{kind}</publicPrivate><docNumber>{number}</docNumber>"
            f"<citableAs>{kind.title()} Law 94-{number}</citableAs>"
            "<citableAs>90 Stat. 3</citableAs>"
            "<congress>94</congress><session>2</session>"
            "<approvedDate>1976-01-28</approvedDate></meta>"
            "<preface><page identifier='/us/stat/90/3'/></preface>"
            f"<main>{content}</main></pLaw></component>"
        )

    @staticmethod
    def volume(
        tmp_path: Path, laws: str, *, root: str = "statutesAtLarge"
    ) -> StatuteVolume:
        path = tmp_path / "STATUTE-90.xml"
        path.write_text(
            f"<{root} xmlns='http://schemas.gpo.gov/xml/uslm' "
            "xmlns:dc='http://purl.org/dc/elements/1.1/'>"
            "<meta><congress>94</congress><session>2</session><volume>90</volume></meta>"
            f"<main>{laws}</main></{root}>"
        )
        return StatuteVolume(
            path=path,
            volume=90,
            congress=94,
            session=2,
            source_url=AnyHttpUrl(
                "https://www.govinfo.gov/bulkdata/STATUTE/90/STATUTE-90.xml"
            ),
            sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        )


def test_streams_distinct_public_private_laws_and_preserves_inline_words(
    tmp_path: Path,
) -> None:
    volume = Fixture.volume(tmp_path, Fixture.law() + Fixture.law(kind="private"))
    records = list(StatutesReader(StatutesSettings()).records(volume))
    assert [record.identity.kind for record in records] == [
        StatuteLawKind.PUBLIC,
        StatuteLawKind.PRIVATE,
    ]
    assert records[0].text == "H.R. 1\nAn international program.\nSecond paragraph."
    assert records[0].bill_references == ["/us/bill/94/hr/1"]
    assert records[0].volume_sha256 == volume.sha256
    assert records[0].source_url == volume.source_url


def test_rejects_repeated_law_identity(tmp_path: Path) -> None:
    volume = Fixture.volume(tmp_path, Fixture.law() + Fixture.law())
    with pytest.raises(StatutesParseError, match="Repeated"):
        list(StatutesReader(StatutesSettings()).records(volume))


@pytest.mark.parametrize(
    ("field", "value"), [("volume", 89), ("congress", 95), ("session", 1)]
)
def test_rejects_wrong_volume_scope(tmp_path: Path, field: str, value: int) -> None:
    volume = Fixture.volume(tmp_path, Fixture.law()).model_copy(update={field: value})
    with pytest.raises(StatutesParseError, match="volume metadata differs"):
        list(StatutesReader(StatutesSettings()).records(volume))


def test_reprint_retains_its_own_scope_and_original_citation(tmp_path: Path) -> None:
    law = (
        Fixture.law()
        .replace("<congress>94</congress>", "<congress>91</congress>")
        .replace("Law 94-1", "Law 91-1")
        .replace("90 Stat. 3", "84 Stat. 2080-1")
        .replace("/us/stat/90/3", "/us/stat/84/2080-1")
    )
    volume = Fixture.volume(tmp_path, law)
    record = next(StatutesReader(StatutesSettings()).records(volume))
    assert record.identity.congress == 91
    assert record.volume == 84
    assert record.first_page == "2080-1"
    assert record.source_volume == 90


def test_rejects_conflicting_citations(tmp_path: Path) -> None:
    law = Fixture.law().replace("/us/stat/90/3", "/us/stat/90/4")
    volume = Fixture.volume(tmp_path, law)
    with pytest.raises(StatutesParseError, match="conflicting"):
        list(StatutesReader(StatutesSettings()).records(volume))


def test_rejects_law_number_disagreeing_with_its_citation(tmp_path: Path) -> None:
    law = Fixture.law().replace("<docNumber>1</docNumber>", "<docNumber>2</docNumber>")
    volume = Fixture.volume(tmp_path, law)
    with pytest.raises(StatutesParseError, match="conflicting enacted-law identity"):
        list(StatutesReader(StatutesSettings()).records(volume))


def test_scan_surfaces_quarantine_and_continues_to_independent_laws(
    tmp_path: Path,
) -> None:
    invalid = Fixture.law().replace("/us/stat/90/3", "/us/stat/90/4")
    volume = Fixture.volume(tmp_path, invalid + Fixture.law(number=2))
    records = list(StatutesReader(StatutesSettings()).scan(volume))
    rejected = records[0]
    assert isinstance(rejected, StatuteRejectedLaw)
    assert rejected.congress_raw == "94"
    assert rejected.number_raw == "1"
    assert "conflicting" in rejected.error
    accepted = records[1]
    assert not isinstance(accepted, StatuteRejectedLaw)
    assert accepted.identity.number == 2


@pytest.mark.parametrize("session_element", ["", "<session/>", "<session> </session>"])
def test_missing_law_session_stays_unknown_not_inferred_from_volume(
    tmp_path: Path, session_element: str
) -> None:
    law = Fixture.law().replace("<session>2</session>", session_element)
    volume = Fixture.volume(tmp_path, law)
    record = next(StatutesReader(StatutesSettings()).records(volume))
    assert record.session is None


def test_rejects_missing_or_blank_text(tmp_path: Path) -> None:
    volume = Fixture.volume(tmp_path, Fixture.law(body="   "))
    with pytest.raises(StatutesParseError, match="nonblank"):
        list(StatutesReader(StatutesSettings()).records(volume))


def test_rejects_unknown_root(tmp_path: Path) -> None:
    volume = Fixture.volume(tmp_path, Fixture.law(), root="bill")
    with pytest.raises(StatutesParseError, match="root or namespace"):
        list(StatutesReader(StatutesSettings()).records(volume))


def test_rejects_volume_without_laws(tmp_path: Path) -> None:
    volume = Fixture.volume(tmp_path, "")
    with pytest.raises(StatutesParseError, match="no verified"):
        list(StatutesReader(StatutesSettings()).records(volume))


def test_rejects_changed_sealed_file(tmp_path: Path) -> None:
    volume = Fixture.volume(tmp_path, Fixture.law())
    volume.path.write_text("changed")
    with pytest.raises(StatutesParseError, match="checksum"):
        list(StatutesReader(StatutesSettings()).records(volume))


def test_rechecks_seal_when_stream_is_exhausted(tmp_path: Path) -> None:
    volume = Fixture.volume(tmp_path, Fixture.law())
    records = StatutesReader(StatutesSettings()).records(volume)
    assert next(records).identity.number == 1
    with volume.path.open("a") as source:
        source.write("\n")
    with pytest.raises(StatutesParseError, match="checksum"):
        list(records)


def test_rejects_wrong_namespace(tmp_path: Path) -> None:
    volume = Fixture.volume(tmp_path, Fixture.law())
    volume.path.write_text(
        volume.path.read_text().replace(
            "http://schemas.gpo.gov/xml/uslm", "https://example.invalid"
        )
    )
    volume.sha256 = hashlib.sha256(volume.path.read_bytes()).hexdigest()
    with pytest.raises(StatutesParseError, match="namespace"):
        list(StatutesReader(StatutesSettings()).records(volume))
