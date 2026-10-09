from pathlib import Path

from cdm.utils.log_trimmer import LogTrimmer


def _write(path: Path, count: int) -> None:
    path.write_text("".join(f"line {n}\n" for n in range(count)))


def test_keeps_only_newest_lines(tmp_path: Path):
    log = tmp_path / "a.log"
    _write(log, 25)
    results = LogTrimmer(tmp_path, max_lines=10).trim_all()
    lines = log.read_text().splitlines()
    assert lines == [f"line {n}" for n in range(15, 25)]
    assert results[0].bytes_after < results[0].bytes_before


def test_short_files_are_untouched(tmp_path: Path):
    log = tmp_path / "a.log"
    _write(log, 10)
    before = log.read_bytes()
    assert LogTrimmer(tmp_path, max_lines=10).trim_all() == []
    assert log.read_bytes() == before


def test_handles_missing_trailing_newline_and_non_logs(tmp_path: Path):
    log = tmp_path / "a.log"
    log.write_text("one\ntwo\nthree")
    (tmp_path / "keep.txt").write_text("x\n" * 50)
    LogTrimmer(tmp_path, max_lines=2).trim_all()
    assert log.read_text() == "two\nthree"
    assert len((tmp_path / "keep.txt").read_text().splitlines()) == 50
