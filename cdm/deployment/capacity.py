"""Read-only admission checks for the combined local Compose topology."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import NewType

from pydantic import BaseModel, Field, TypeAdapter, computed_field

from cdm.config.local_capacity import LocalCapacityPolicy

ServiceName = NewType("ServiceName", str)


class ResourceLimits(BaseModel):
    memory: int | None = Field(default=None, gt=0)


class Resources(BaseModel):
    limits: ResourceLimits = Field(default_factory=ResourceLimits)


class Deployment(BaseModel):
    resources: Resources = Field(default_factory=Resources)


class ComposeService(BaseModel):
    profiles: list[str] = Field(default_factory=list)
    mem_limit: int | None = Field(default=None, gt=0)
    deploy: Deployment = Field(default_factory=Deployment)

    @property
    def memory_limit(self) -> int | None:
        limits = [
            limit
            for limit in (self.mem_limit, self.deploy.resources.limits.memory)
            if limit is not None
        ]
        return min(limits) if limits else None


class ComposeTopology(BaseModel):
    name: str
    services: dict[ServiceName, ComposeService]


class DockerInfo(BaseModel):
    memory_bytes: int = Field(alias="MemTotal", gt=0)


class ComposeLabels(BaseModel):
    project: str | None = Field(default=None, alias="com.docker.compose.project")
    service: str | None = Field(default=None, alias="com.docker.compose.service")


class ContainerConfig(BaseModel):
    labels: ComposeLabels = Field(alias="Labels")


class HostConfig(BaseModel):
    memory: int = Field(alias="Memory", ge=0)


class RunningContainer(BaseModel):
    name: str = Field(alias="Name")
    config: ContainerConfig = Field(alias="Config")
    host: HostConfig = Field(alias="HostConfig")


class CapacityReport(BaseModel):
    profiles: list[str]
    docker_memory_bytes: int
    requested_memory_bytes: int
    additional_running_memory_bytes: int
    reserve_bytes: int
    free_disk_bytes: int
    minimum_free_disk_bytes: int
    unbounded_services: list[str]
    unknown_profiles: list[str]

    @computed_field
    @property
    def blockers(self) -> list[str]:
        blockers = [f"No memory limit for {name}" for name in self.unbounded_services]
        blockers.extend(
            f"Unknown Compose profile: {name}" for name in self.unknown_profiles
        )
        if (
            self.requested_memory_bytes
            + self.additional_running_memory_bytes
            + self.reserve_bytes
            > self.docker_memory_bytes
        ):
            blockers.append("Combined memory limits plus reserve exceed Docker memory")
        if self.free_disk_bytes < self.minimum_free_disk_bytes:
            blockers.append("Host disk free space is below the safety reserve")
        return blockers

    @computed_field
    @property
    def admitted(self) -> bool:
        return not self.blockers


class CapacityAssessment:
    def __init__(self, policy: LocalCapacityPolicy) -> None:
        self._policy = policy

    def assess(
        self,
        topologies: list[ComposeTopology],
        running: list[RunningContainer],
        docker: DockerInfo,
        profiles: list[str],
        free_disk_bytes: int,
    ) -> CapacityReport:
        selected: dict[tuple[str, ServiceName], int] = {}
        unbounded: list[str] = []
        known_profiles: set[str] = set()
        for topology in topologies:
            for name, service in topology.services.items():
                known_profiles.update(service.profiles)
                if service.profiles and not (
                    "*" in profiles or set(service.profiles).intersection(profiles)
                ):
                    continue
                limit = service.memory_limit
                if limit is None:
                    unbounded.append(f"{topology.name}/{name}")
                else:
                    selected[(topology.name, name)] = limit
        additional = 0
        for container in running:
            labels = container.config.labels
            requested = (
                selected.get((labels.project, ServiceName(labels.service)), 0)
                if labels.project is not None and labels.service is not None
                else 0
            )
            if not container.host.memory:
                unbounded.append(container.name)
            else:
                additional += max(0, container.host.memory - requested)
        return CapacityReport(
            profiles=profiles,
            docker_memory_bytes=docker.memory_bytes,
            requested_memory_bytes=sum(selected.values()),
            additional_running_memory_bytes=additional,
            reserve_bytes=self._policy.docker_reserve_bytes,
            free_disk_bytes=free_disk_bytes,
            minimum_free_disk_bytes=self._policy.minimum_free_disk_bytes,
            unbounded_services=unbounded,
            unknown_profiles=sorted(set(profiles) - known_profiles - {"*"}),
        )


class DockerCapacityProbe:
    def __init__(self, root: Path, policy: LocalCapacityPolicy) -> None:
        self._root = root
        self._policy = policy
        self._assessment = CapacityAssessment(policy)

    def _run(self, arguments: list[str], cwd: Path) -> str:
        return subprocess.run(
            arguments,
            cwd=cwd,
            env={**os.environ, "PWD": str(cwd)},
            capture_output=True,
            text=True,
            check=True,
            timeout=self._policy.command_timeout_seconds,
        ).stdout

    def inspect(self, profiles: list[str]) -> CapacityReport:
        topologies = [
            ComposeTopology.model_validate_json(
                self._run(
                    [
                        "docker",
                        "compose",
                        "--profile",
                        "*",
                        "-f",
                        str(path),
                        "config",
                        "--format",
                        "json",
                    ],
                    path.parent,
                )
            )
            for path in (
                self._root / "docker-compose.fullstack.yml",
                self._root / "elastic-start-local/docker-compose.yml",
            )
        ]
        docker = DockerInfo.model_validate_json(
            self._run(["docker", "info", "--format", "{{json .}}"], self._root)
        )
        identifiers = self._run(["docker", "ps", "-q"], self._root).split()
        running = (
            self._run(["docker", "inspect", *identifiers], self._root)
            if identifiers
            else "[]"
        )
        return self._assessment.assess(
            topologies,
            TypeAdapter(list[RunningContainer]).validate_json(running),
            docker,
            profiles,
            shutil.disk_usage(self._root).free,
        )
