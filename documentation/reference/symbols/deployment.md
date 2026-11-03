# deployment source reference

[All source areas](README.md)

Generated from declarations; see the catalogue scope in the index.

## cdm/deployment/__init__.py

[Source](../../../cdm/deployment/__init__.py)

No declarations in this module.


## cdm/deployment/capacity.py

[Source](../../../cdm/deployment/capacity.py)

- class: [`ResourceLimits(BaseModel)`](../../../cdm/deployment/capacity.py#L18)
- field: [`ResourceLimits.memory: int \| None`](../../../cdm/deployment/capacity.py#L19)
- class: [`Resources(BaseModel)`](../../../cdm/deployment/capacity.py#L22)
- field: [`Resources.limits: ResourceLimits`](../../../cdm/deployment/capacity.py#L23)
- class: [`Deployment(BaseModel)`](../../../cdm/deployment/capacity.py#L26)
- field: [`Deployment.resources: Resources`](../../../cdm/deployment/capacity.py#L27)
- class: [`ComposeService(BaseModel)`](../../../cdm/deployment/capacity.py#L30)
- field: [`ComposeService.profiles: list[str]`](../../../cdm/deployment/capacity.py#L31)
- field: [`ComposeService.mem_limit: int \| None`](../../../cdm/deployment/capacity.py#L32)
- field: [`ComposeService.deploy: Deployment`](../../../cdm/deployment/capacity.py#L33)
- function: [`ComposeService.memory_limit(self) -> int \| None`](../../../cdm/deployment/capacity.py#L36)
- class: [`ComposeTopology(BaseModel)`](../../../cdm/deployment/capacity.py#L45)
- field: [`ComposeTopology.name: str`](../../../cdm/deployment/capacity.py#L46)
- field: [`ComposeTopology.services: dict[ServiceName, ComposeService]`](../../../cdm/deployment/capacity.py#L47)
- class: [`DockerInfo(BaseModel)`](../../../cdm/deployment/capacity.py#L50)
- field: [`DockerInfo.memory_bytes: int`](../../../cdm/deployment/capacity.py#L51)
- class: [`ComposeLabels(BaseModel)`](../../../cdm/deployment/capacity.py#L54)
- field: [`ComposeLabels.project: str \| None`](../../../cdm/deployment/capacity.py#L55)
- field: [`ComposeLabels.service: str \| None`](../../../cdm/deployment/capacity.py#L56)
- class: [`ContainerConfig(BaseModel)`](../../../cdm/deployment/capacity.py#L59)
- field: [`ContainerConfig.labels: ComposeLabels`](../../../cdm/deployment/capacity.py#L60)
- class: [`HostConfig(BaseModel)`](../../../cdm/deployment/capacity.py#L63)
- field: [`HostConfig.memory: int`](../../../cdm/deployment/capacity.py#L64)
- class: [`RunningContainer(BaseModel)`](../../../cdm/deployment/capacity.py#L67)
- field: [`RunningContainer.name: str`](../../../cdm/deployment/capacity.py#L68)
- field: [`RunningContainer.config: ContainerConfig`](../../../cdm/deployment/capacity.py#L69)
- field: [`RunningContainer.host: HostConfig`](../../../cdm/deployment/capacity.py#L70)
- class: [`CapacityReport(BaseModel)`](../../../cdm/deployment/capacity.py#L73)
- field: [`CapacityReport.profiles: list[str]`](../../../cdm/deployment/capacity.py#L74)
- field: [`CapacityReport.docker_memory_bytes: int`](../../../cdm/deployment/capacity.py#L75)
- field: [`CapacityReport.requested_memory_bytes: int`](../../../cdm/deployment/capacity.py#L76)
- field: [`CapacityReport.additional_running_memory_bytes: int`](../../../cdm/deployment/capacity.py#L77)
- field: [`CapacityReport.reserve_bytes: int`](../../../cdm/deployment/capacity.py#L78)
- field: [`CapacityReport.free_disk_bytes: int`](../../../cdm/deployment/capacity.py#L79)
- field: [`CapacityReport.minimum_free_disk_bytes: int`](../../../cdm/deployment/capacity.py#L80)
- field: [`CapacityReport.unbounded_services: list[str]`](../../../cdm/deployment/capacity.py#L81)
- field: [`CapacityReport.unknown_profiles: list[str]`](../../../cdm/deployment/capacity.py#L82)
- function: [`CapacityReport.blockers(self) -> list[str]`](../../../cdm/deployment/capacity.py#L86)
- function: [`CapacityReport.admitted(self) -> bool`](../../../cdm/deployment/capacity.py#L104)
- class: [`CapacityAssessment()`](../../../cdm/deployment/capacity.py#L108)
- function: [`CapacityAssessment.__init__(self, policy: LocalCapacityPolicy) -> None`](../../../cdm/deployment/capacity.py#L109)
- function: [`CapacityAssessment.assess(self, topologies: list[ComposeTopology], running: list[RunningContainer], docker: DockerInfo, profiles: list[str], free_disk_bytes: int) -> CapacityReport`](../../../cdm/deployment/capacity.py#L112)
- field: [`CapacityAssessment.assess.selected: dict[tuple[str, ServiceName], int]`](../../../cdm/deployment/capacity.py#L120)
- field: [`CapacityAssessment.assess.unbounded: list[str]`](../../../cdm/deployment/capacity.py#L121)
- field: [`CapacityAssessment.assess.known_profiles: set[str]`](../../../cdm/deployment/capacity.py#L122)
- class: [`DockerCapacityProbe()`](../../../cdm/deployment/capacity.py#L160)
- function: [`DockerCapacityProbe.__init__(self, root: Path, policy: LocalCapacityPolicy) -> None`](../../../cdm/deployment/capacity.py#L161)
- function: [`DockerCapacityProbe._run(self, arguments: list[str], cwd: Path) -> str`](../../../cdm/deployment/capacity.py#L166)
- function: [`DockerCapacityProbe.inspect(self, profiles: list[str]) -> CapacityReport`](../../../cdm/deployment/capacity.py#L177)
