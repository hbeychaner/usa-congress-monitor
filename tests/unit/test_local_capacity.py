from pathlib import Path
from unittest.mock import Mock

import pytest
from pydantic import TypeAdapter

from cdm.config.local_capacity import LocalCapacityPolicy
from cdm.deployment.capacity import (
    CapacityAssessment,
    ComposeService,
    ComposeTopology,
    DockerCapacityProbe,
    DockerInfo,
    RunningContainer,
    ServiceName,
)
from scripts.check_stack_capacity import main


class TestLocalCapacity:
    policy = LocalCapacityPolicy(docker_reserve_bytes=10, minimum_free_disk_bytes=20)

    def topology(self) -> ComposeTopology:
        return ComposeTopology.model_validate(
            {
                "name": "application",
                "services": {
                    "api": {"mem_limit": 30},
                    "operations": {"mem_limit": 20, "profiles": ["operations"]},
                    "analytics": {"mem_limit": 80, "profiles": ["analytics"]},
                    "observability": {"profiles": ["observability"]},
                },
            }
        )

    def running(
        self, memory: int, service: str = "operations", project: str = "application"
    ) -> RunningContainer:
        return RunningContainer.model_validate(
            {
                "Name": f"/{project}-{service}",
                "Config": {
                    "Labels": {
                        "com.docker.compose.project": project,
                        "com.docker.compose.service": service,
                    }
                },
                "HostConfig": {"Memory": memory},
            }
        )

    @pytest.mark.parametrize(
        ("profiles", "admitted", "requested"),
        [
            (["operations"], True, 50),
            (["analytics"], False, 110),
            (["operations", "analytics"], False, 130),
            ([], True, 30),
            (["typo"], False, 30),
            (["observability"], False, 30),
            (["*"], False, 130),
        ],
    )
    def test_selected_topology(
        self, profiles: list[str], admitted: bool, requested: int
    ) -> None:
        report = CapacityAssessment(self.policy).assess(
            [self.topology()],
            [],
            DockerInfo.model_validate({"MemTotal": 100}),
            profiles,
            20,
        )
        assert report.admitted is admitted
        assert report.requested_memory_bytes == requested
        assert bool(report.blockers) is not admitted
        assert report.model_dump(mode="json")["admitted"] is admitted

    @pytest.mark.parametrize(
        ("running", "profiles", "additional", "admitted"),
        [
            (("operations", "application", 20), ["operations"], 0, True),
            (("operations", "application", 40), ["operations"], 20, True),
            (("analytics", "application", 80), ["operations"], 80, False),
            (("api", "another-project", 60), ["operations"], 60, False),
            (("operations", "application", 0), ["operations"], 0, False),
        ],
    )
    def test_existing_containers_are_not_hidden(
        self,
        running: tuple[str, str, int],
        profiles: list[str],
        additional: int,
        admitted: bool,
    ) -> None:
        service, project, memory = running
        report = CapacityAssessment(self.policy).assess(
            [self.topology()],
            [self.running(memory, service, project)],
            DockerInfo.model_validate({"MemTotal": 100}),
            profiles,
            20,
        )
        assert report.additional_running_memory_bytes == additional
        assert report.admitted is admitted

    def test_disk_reserve_blocks_even_when_memory_fits(self) -> None:
        report = CapacityAssessment(self.policy).assess(
            [self.topology()],
            [],
            DockerInfo.model_validate({"MemTotal": 100}),
            ["operations"],
            19,
        )
        assert report.blockers == ["Host disk free space is below the safety reserve"]

    @pytest.mark.parametrize(("memory", "admitted"), [(59, False), (60, True)])
    def test_exact_memory_admission_threshold(
        self, memory: int, admitted: bool
    ) -> None:
        report = CapacityAssessment(self.policy).assess(
            [self.topology()],
            [],
            DockerInfo.model_validate({"MemTotal": memory}),
            ["operations"],
            20,
        )
        assert report.admitted is admitted

    def test_deploy_limits_and_separate_projects_are_counted(self) -> None:
        infrastructure = ComposeTopology.model_validate(
            {
                "name": "infrastructure",
                "services": {
                    "api": {"deploy": {"resources": {"limits": {"memory": "50"}}}}
                },
            }
        )
        report = CapacityAssessment(self.policy).assess(
            [self.topology(), infrastructure],
            [],
            DockerInfo.model_validate({"MemTotal": 100}),
            ["operations"],
            20,
        )
        assert report.requested_memory_bytes == 100
        assert not report.admitted

    def test_compose_limits_use_the_tighter_bound(self) -> None:
        service = ComposeService.model_validate(
            {"mem_limit": 40, "deploy": {"resources": {"limits": {"memory": 30}}}}
        )
        assert service.memory_limit == 30

    def test_probe_uses_all_profiles_and_actual_compose_directories(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        topology = self.topology()
        container = self.running(20)
        run = Mock(
            side_effect=[
                topology.model_dump_json(),
                ComposeTopology(
                    name="infrastructure",
                    services={ServiceName("search"): ComposeService(mem_limit=30)},
                ).model_dump_json(),
                '{"MemTotal": 100}',
                "container-id\n",
                TypeAdapter(list[RunningContainer])
                .dump_json([container], by_alias=True)
                .decode(),
            ]
        )
        monkeypatch.setattr(DockerCapacityProbe, "_run", run)
        disk = Mock()
        disk.free = 20
        monkeypatch.setattr(
            "cdm.deployment.capacity.shutil.disk_usage", Mock(return_value=disk)
        )
        report = DockerCapacityProbe(tmp_path, self.policy).inspect(["operations"])
        assert report.admitted
        assert run.call_args_list[0].args[1] == tmp_path
        assert run.call_args_list[1].args[1] == tmp_path / "elastic-start-local"
        assert run.call_args_list[0].args[0][2:4] == ["--profile", "*"]
        assert run.call_args_list[4].args[0] == ["docker", "inspect", "container-id"]

    def test_command_failure_propagates_without_success_report(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        run = Mock(side_effect=OSError("Docker unavailable"))
        monkeypatch.setattr(DockerCapacityProbe, "_run", run)
        with pytest.raises(OSError, match="Docker unavailable"):
            DockerCapacityProbe(tmp_path, self.policy).inspect(["operations"])

    def test_cli_fails_closed_without_printing_sensitive_metadata(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setattr("sys.argv", ["check_stack_capacity.py"])
        monkeypatch.setattr(
            DockerCapacityProbe,
            "inspect",
            Mock(side_effect=OSError("sensitive command output")),
        )
        with pytest.raises(SystemExit) as failure:
            main()
        assert failure.value.code == 2
        captured = capsys.readouterr()
        assert "startup refused" in captured.err
        assert "sensitive" not in captured.err
        assert not captured.out

    def test_managed_startup_checks_capacity_before_starting_infrastructure(
        self,
    ) -> None:
        root = Path(__file__).resolve().parents[2]
        recipe = (root / "Makefile").read_text().split("stack-up:\n", 1)[1]
        recipe = recipe.split("\nstack-capacity:", 1)[0]
        assert (
            recipe.index("$(MAKE) env-init ensure-docker")
            < recipe.index("$(MAKE) stack-capacity")
            < recipe.index("$(MAKE) local")
            < recipe.index("$(COMPOSE) -f docker-compose.fullstack.yml up")
        )
