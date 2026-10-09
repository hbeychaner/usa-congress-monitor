"""Cap log files at a maximum number of lines by dropping the oldest ones."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel

REPO_ROOT = Path(__file__).resolve().parents[2]
LOG_DIRECTORY = REPO_ROOT / "logs"
MAX_LOG_LINES = 10_000
BLOCK_SIZE = 1 << 20


class TrimResult(BaseModel):
    path: str
    bytes_before: int
    bytes_after: int


class LogTrimmer:
    """Rewrites each log in place so writers holding it open in append mode keep working."""

    def __init__(
        self, directory: Path = LOG_DIRECTORY, max_lines: int = MAX_LOG_LINES
    ) -> None:
        self.directory = directory
        self.max_lines = max_lines

    def _tail(self, path: Path) -> bytes | None:
        """The last ``max_lines`` lines, or None when the file is already short enough."""
        blocks: list[bytes] = []
        newlines = 0
        with path.open("rb") as handle:
            position = handle.seek(0, 2)
            if position == 0:
                return None
            handle.seek(position - 1)
            # A trailing partial line counts as a line, a trailing newline does not.
            wanted = self.max_lines + (1 if handle.read(1) == b"\n" else 0)
            while position > 0 and newlines < wanted:
                step = min(BLOCK_SIZE, position)
                position -= step
                handle.seek(position)
                block = handle.read(step)
                blocks.append(block)
                newlines += block.count(b"\n")
        if newlines < wanted:
            return None
        data = b"".join(reversed(blocks))
        offset = 0
        for _ in range(newlines - wanted + 1):
            offset = data.index(b"\n", offset) + 1
        return data[offset:]

    def trim(self, path: Path) -> TrimResult | None:
        tail = self._tail(path)
        if tail is None:
            return None
        before = path.stat().st_size
        with path.open("r+b") as handle:
            handle.write(tail)
            handle.truncate(len(tail))
        return TrimResult(path=str(path), bytes_before=before, bytes_after=len(tail))

    def trim_all(self) -> list[TrimResult]:
        results = (self.trim(path) for path in sorted(self.directory.glob("*.log")))
        return [result for result in results if result is not None]
