"""Build perspectives under the shared worker-owned analytics lifecycle."""

from collections.abc import Callable
from datetime import UTC, datetime

from cdm.jobs.analytics import AnalysisProgress, PerspectiveRequest
from cdm.perspectives.runner import PerspectiveRunner
from cdm.store.perspective_repository import PerspectiveRepository


class PerspectiveBuildJob:
    def __init__(
        self,
        runner: PerspectiveRunner,
        repository: PerspectiveRepository,
        report: Callable[[AnalysisProgress], None],
    ) -> None:
        self._runner = runner
        self._repository = repository
        self._report = report

    def run(self, request: PerspectiveRequest) -> None:
        version = self._runner.source_version()
        written = 0
        for congress in request.congresses:
            self._report(AnalysisProgress(stage=f"Congress {congress}"))
            results = self._runner.run(
                congress,
                model_version=version,
                topic_ids=request.topic_ids,
                top_topics=request.top_topics,
                on_topic=lambda topic: self._report(
                    AnalysisProgress(
                        stage=f"Congress {topic.congress}, topic {topic.topic_id}"
                    )
                ),
            )
            self._report(
                AnalysisProgress(
                    stage=f"publishing Congress {congress}",
                    model_version=version,
                )
            )
            if request.dry_run:
                for result in results:
                    print(result.model_dump_json())
            else:
                written += self._repository.replace(
                    congress,
                    version,
                    datetime.now(UTC),
                    results,
                )
        self._report(
            AnalysisProgress(
                stage="done", progress=1.0, message=f"wrote {written} topic documents"
            )
        )
