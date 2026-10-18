"""Build each topic's party contrast and perspectives for Congresses (writes unless --dry-run).

Usage:
    uv run python scripts/build_perspectives.py --congress 119 --top-topics 5 --dry-run
    uv run python scripts/build_perspectives.py --congress 118 --congress 119 --all-topics
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cdm.config import get_config
from cdm.container import Container
from cdm.graph.runner import BuildState, GraphBuildRunner
from cdm.perspectives.models import TopicPerspectives
from cdm.perspectives.runner import NoTopicModelError

DEFAULT_CONGRESS = 119
DEFAULT_TOP_TOPICS = 5


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--congress",
        type=int,
        action="append",
        help=f"Repeatable (default {DEFAULT_CONGRESS})",
    )
    parser.add_argument("--top-topics", type=int, default=DEFAULT_TOP_TOPICS)
    parser.add_argument(
        "--all-topics", action="store_true", help="Every topic above the size floor"
    )
    parser.add_argument(
        "--topic-id", type=int, action="append", help="Only these topics"
    )
    parser.add_argument("--no-llm-labels", action="store_true")
    parser.add_argument(
        "--dry-run", action="store_true", help="Print results, write nothing"
    )
    parser.add_argument("--status-file", type=Path, help="Report progress here")
    return parser.parse_args()


def print_topic(result: TopicPerspectives) -> None:
    print(
        f"\n=== [{result.topic_id}] {result.topic_label} ({result.bills} bills, Congress {result.congress})"
    )
    if result.bilateral:
        bilateral = result.bilateral
        tag = "BILATERAL" if bilateral.bilateral else "partisan"
        print(
            f"  {tag}: {bilateral.bipartisan_bills}/{bilateral.bills} bipartisan "
            f"({bilateral.share:.0%}); bipartisan bills lean on: "
            f"{', '.join(use.term for use in bilateral.terms[:8])}"
        )
        if bilateral.summary:
            print(f"    summary: {bilateral.summary}")
    for contrast in result.party_terms:
        print(
            f"  {contrast.party.value} ({contrast.bills} bills) leans on: "
            f"{', '.join(use.term + f' [{use.bills}b/{use.sponsors}s]' for use in contrast.terms)}"
        )
        print(
            "    subjects: "
            + ", ".join(f"{use.name} ({use.bills})" for use in contrast.subjects)
        )
        if contrast.summary:
            print(f"    summary: {contrast.summary}")
    if not result.perspectives:
        print(f"  not split: {result.skipped_reason}")
        return
    verdict = "PASS" if result.passed else "FAIL"
    print(
        f"  clusters {verdict}: silhouette {result.silhouette:.3f}, "
        f"stability {result.stability:.3f}"
    )
    for perspective in result.perspectives:
        mix = ", ".join(
            f"{share.party.value} {share.bills} ({share.share:.0%}, lean {share.lean:+.2f})"
            for share in perspective.parties
        )
        print(
            f"\n  - {perspective.label} ({perspective.size} bills)\n    parties: {mix}"
        )
        print(f"    terms: {', '.join(perspective.terms)}")
        for title in perspective.sample_titles[:4]:
            print(f"    * {title[:110]}")


def main() -> None:
    args = parse_args()
    status = GraphBuildRunner(args.status_file) if args.status_file else None
    try:
        message = build(args, status)
    except (Exception, SystemExit) as exc:
        if status:
            status.update(
                state=BuildState.FAILED,
                finished_at=datetime.now(UTC),
                message=str(exc) or type(exc).__name__,
            )
        raise
    if status:
        status.update(
            state=BuildState.SUCCEEDED,
            finished_at=datetime.now(UTC),
            stage=None,
            message=message,
        )


def build(args: argparse.Namespace, status: GraphBuildRunner | None) -> str:
    container = Container(get_config())
    runner = container.perspective_runner(use_llm=not args.no_llm_labels)
    top = None if args.all_topics else args.top_topics
    written_total = 0
    for congress in args.congress or [DEFAULT_CONGRESS]:
        if status:
            status.update(stage=f"Congress {congress}")
        try:
            run = runner.run(
                congress, topic_ids=args.topic_id, top_topics=top, on_topic=print_topic
            )
        except NoTopicModelError as exc:
            raise SystemExit(str(exc)) from exc
        print(
            f"\nCongress {congress}: {run.bills} bills, {run.assigned} assigned; "
            f"boilerplate {len(run.lexicon.words)} words, {len(run.lexicon.phrases)} phrases"
        )
        if args.dry_run:
            continue
        written = container.perspective_repository.replace(
            congress,
            run.model_version,
            datetime.now(UTC).isoformat(),
            run.results,
        )
        written_total += written
        print(f"wrote {written} topic documents for Congress {congress}")
    return f"wrote {written_total} topic documents"


if __name__ == "__main__":
    main()
