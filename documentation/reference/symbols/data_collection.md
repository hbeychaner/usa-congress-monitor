# data_collection source reference

[All source areas](README.md)

Generated from declarations; see the catalogue scope in the index.

## cdm/data_collection/client.py

[Source](../../../cdm/data_collection/client.py)

- function: [`_is_json_response(response: requests.Response) -> bool`](../../../cdm/data_collection/client.py#L44)
- class: [`CDGClient()`](../../../cdm/data_collection/client.py#L62)
- function: [`CDGClient.__init__(self, api_key: str, api_version: str=API_VERSION, response_format: str=RESPONSE_FORMAT, raise_on_error: bool=True, added_headers: dict[str, str] \| None=None, rate_limiter: TokenBucket \| None=None, id_strategy: IdStrategyApplier \| None=None, sleeper: Callable[[float], None]=time.sleep) -> None`](../../../cdm/data_collection/client.py#L69)
- function: [`CDGClient.session(self) -> requests.Session`](../../../cdm/data_collection/client.py#L123)
- function: [`CDGClient.get_json(self, endpoint: str, params: Mapping[str, Json] \| None=None, timeout: int=10) -> Mapping[str, Json]`](../../../cdm/data_collection/client.py#L127)
- function: [`CDGClient.request_for_spec(self, spec: EndpointSpec, runtime_params: dict[str, Json], timeout: int=10) -> Mapping[str, Json]`](../../../cdm/data_collection/client.py#L146)
- function: [`CDGClient._request_with_backoff(self, url: str, params: Mapping[str, Json] \| None=None, timeout: int=10, *, base_delay: float=0.5, max_delay: float=10.0, max_attempts: int=5, max_rate_limit_attempts: int=8) -> requests.Response`](../../../cdm/data_collection/client.py#L168)
- function: [`CDGClient._retry_after_seconds(value: str \| None) -> float \| None`](../../../cdm/data_collection/client.py#L241)
- function: [`CDGClient.iterate_pages(self, spec: EndpointSpec, base_params: Mapping[str, Json] \| None=None) -> Iterator[tuple[list[BaseModel], Mapping[str, Json], Mapping[str, Json]]]`](../../../cdm/data_collection/client.py#L255)
- field: [`CDGClient.iterate_pages.params: dict[str, Json]`](../../../cdm/data_collection/client.py#L264)
- function: [`CDGClient.fetch_list(self, spec: EndpointSpec, params: Mapping[str, Json] \| None=None) -> list[BaseModel]`](../../../cdm/data_collection/client.py#L280)
- function: [`CDGClient.fetch_one(self, spec: EndpointSpec, runtime_params: dict[str, Json], *, validation_failure_sink: Callable[[dict[str, Json], ValidationError], None] \| None=None) -> BaseModel`](../../../cdm/data_collection/client.py#L292)
- function: [`CDGClient.resolve_runtime_params_from_record(self, spec: EndpointSpec, record: BaseModel \| Mapping[str, Json]) -> dict[str, Json]`](../../../cdm/data_collection/client.py#L316)
- field: [`CDGClient.resolve_runtime_params_from_record.params: dict[str, Json]`](../../../cdm/data_collection/client.py#L325)
- function: [`CDGClient.resolve_runtime_params_from_record._resolve_source_field(mapping: Mapping[str, Json] \| list[Json] \| None, source_field: str) -> Json \| None`](../../../cdm/data_collection/client.py#L337)
- field: [`CDGClient.resolve_runtime_params_from_record.value: Json \| None`](../../../cdm/data_collection/client.py#L365)
- function: [`CDGClient._resolve_response_model(self, spec: EndpointSpec) -> type[BaseModel]`](../../../cdm/data_collection/client.py#L406)
- function: [`CDGClient.coerce_records(self, model_cls: type[BaseModel], records: list[dict[str, Json]], spec=None, validation_failure_sink: Callable[[dict[str, Json], ValidationError], None] \| None=None) -> list[BaseModel]`](../../../cdm/data_collection/client.py#L440)
- field: [`CDGClient.coerce_records.coerced: list[BaseModel]`](../../../cdm/data_collection/client.py#L452)
- field: [`CDGClient.coerce_records.normalized_notes: list[dict[str, Json]]`](../../../cdm/data_collection/client.py#L462)
- function: [`CDGClient._extract_records_from_response(self, spec: EndpointSpec, resp_json: Mapping[str, Json]) -> list[dict[str, Json]]`](../../../cdm/data_collection/client.py#L576)
- function: [`CDGClient._rate_limited(self) -> None`](../../../cdm/data_collection/client.py#L626)
- function: [`get_client(api_key: str \| None=None, **kwargs) -> CDGClient`](../../../cdm/data_collection/client.py#L637)
- function: [`resolve_runtime_params_from_record(client_obj: CDGClient, spec: EndpointSpec, record: BaseModel \| Mapping[str, Json]) -> dict[str, Json]`](../../../cdm/data_collection/client.py#L648)
- field: [`resolve_runtime_params_from_record.params: dict[str, Json]`](../../../cdm/data_collection/client.py#L660)

## cdm/data_collection/endpoint_registry.py

[Source](../../../cdm/data_collection/endpoint_registry.py)

- class: [`SpecRegistry()`](../../../cdm/data_collection/endpoint_registry.py#L12)
- function: [`SpecRegistry.__init__(self) -> None`](../../../cdm/data_collection/endpoint_registry.py#L15)
- function: [`SpecRegistry.make_list_and_item_specs(resource_name: str, path_root: str, list_model: type[BaseModel], item_model: type[BaseModel], data_key: str \| None=None, id_param_name: str='id') -> tuple[EndpointSpec, EndpointSpec]`](../../../cdm/data_collection/endpoint_registry.py#L19)
- function: [`SpecRegistry.register_specs(self, list_spec: EndpointSpec, item_spec: EndpointSpec) -> None`](../../../cdm/data_collection/endpoint_registry.py#L77)
- function: [`SpecRegistry.register_spec(self, spec: EndpointSpec) -> None`](../../../cdm/data_collection/endpoint_registry.py#L82)
- function: [`SpecRegistry.register_from_model(self, resource_name: str, path_root: str, list_model: type[BaseModel], item_model: type[BaseModel], data_key: str \| None=None, id_param_name: str='id') -> tuple[EndpointSpec, EndpointSpec]`](../../../cdm/data_collection/endpoint_registry.py#L86)
- function: [`SpecRegistry.get_spec(self, name: str) -> EndpointSpec`](../../../cdm/data_collection/endpoint_registry.py#L102)
- function: [`SpecRegistry.all_specs(self) -> dict[str, EndpointSpec]`](../../../cdm/data_collection/endpoint_registry.py#L106)

## cdm/data_collection/id_strategy.py

[Source](../../../cdm/data_collection/id_strategy.py)

- class: [`IdStrategyApplier()`](../../../cdm/data_collection/id_strategy.py#L22)
- function: [`IdStrategyApplier.__init__(self, url_parser: type[UrlIdParser]=UrlIdParser) -> None`](../../../cdm/data_collection/id_strategy.py#L25)
- function: [`IdStrategyApplier.resolve_path(source: Mapping[str, object] \| BaseModel \| None, path: str) -> Node`](../../../cdm/data_collection/id_strategy.py#L29)
- field: [`IdStrategyApplier.resolve_path.node: Node`](../../../cdm/data_collection/id_strategy.py#L35)
- function: [`IdStrategyApplier.apply(self, inst: T, original: Mapping[str, object] \| None, spec: EndpointSpec) -> T`](../../../cdm/data_collection/id_strategy.py#L48)
- field: [`IdStrategyApplier.apply.updates: dict[str, str]`](../../../cdm/data_collection/id_strategy.py#L55)
- function: [`IdStrategyApplier._base_id(self, inst: BaseModel, url: object) -> str \| None`](../../../cdm/data_collection/id_strategy.py#L75)
- function: [`IdStrategyApplier._section_id(self, inst: BaseModel, original: Mapping[str, object] \| None, path: str, base_id: str) -> str \| None`](../../../cdm/data_collection/id_strategy.py#L90)

## cdm/data_collection/id_utils.py

[Source](../../../cdm/data_collection/id_utils.py)

- class: [`IdPrefix(StrEnum)`](../../../cdm/data_collection/id_utils.py#L17)
- class: [`UrlIdParser()`](../../../cdm/data_collection/id_utils.py#L26)
- function: [`UrlIdParser.normalize_segment(segment: str) -> str`](../../../cdm/data_collection/id_utils.py#L30)
- function: [`UrlIdParser.parse(cls, url: str) -> str`](../../../cdm/data_collection/id_utils.py#L37)
- class: [`CanonicalIdBuilder()`](../../../cdm/data_collection/id_utils.py#L54)
- function: [`CanonicalIdBuilder.__init__(self, url_parser: type[UrlIdParser]=UrlIdParser) -> None`](../../../cdm/data_collection/id_utils.py#L60)
- function: [`CanonicalIdBuilder.build(self, record: BaseModel \| Mapping[str, Json] \| object) -> str`](../../../cdm/data_collection/id_utils.py#L63)
- function: [`CanonicalIdBuilder._from_builder(record: object) -> str \| None`](../../../cdm/data_collection/id_utils.py#L89)
- function: [`CanonicalIdBuilder._as_mapping(record: object) -> Mapping[str, object]`](../../../cdm/data_collection/id_utils.py#L104)

## cdm/data_collection/specs/__init__.py

[Source](../../../cdm/data_collection/specs/__init__.py)

No declarations in this module.


## cdm/data_collection/specs/amendment_specs.py

[Source](../../../cdm/data_collection/specs/amendment_specs.py)

No declarations in this module.


## cdm/data_collection/specs/bill_specs.py

[Source](../../../cdm/data_collection/specs/bill_specs.py)

- function: [`_path_params_for_bill()`](../../../cdm/data_collection/specs/bill_specs.py#L72)

## cdm/data_collection/specs/bound_congressional_record_specs.py

[Source](../../../cdm/data_collection/specs/bound_congressional_record_specs.py)

No declarations in this module.


## cdm/data_collection/specs/committee_report_specs.py

[Source](../../../cdm/data_collection/specs/committee_report_specs.py)

No declarations in this module.


## cdm/data_collection/specs/committee_specs.py

[Source](../../../cdm/data_collection/specs/committee_specs.py)

No declarations in this module.


## cdm/data_collection/specs/communication_specs.py

[Source](../../../cdm/data_collection/specs/communication_specs.py)

No declarations in this module.


## cdm/data_collection/specs/congress_list_specs.py

[Source](../../../cdm/data_collection/specs/congress_list_specs.py)

- function: [`_by_congress(base: EndpointSpec) -> EndpointSpec`](../../../cdm/data_collection/specs/congress_list_specs.py#L20)

## cdm/data_collection/specs/congress_specs.py

[Source](../../../cdm/data_collection/specs/congress_specs.py)

No declarations in this module.


## cdm/data_collection/specs/crsreport_specs.py

[Source](../../../cdm/data_collection/specs/crsreport_specs.py)

No declarations in this module.


## cdm/data_collection/specs/daily_congressional_record_specs.py

[Source](../../../cdm/data_collection/specs/daily_congressional_record_specs.py)

No declarations in this module.


## cdm/data_collection/specs/hearing_specs.py

[Source](../../../cdm/data_collection/specs/hearing_specs.py)

No declarations in this module.


## cdm/data_collection/specs/house_requirement_specs.py

[Source](../../../cdm/data_collection/specs/house_requirement_specs.py)

No declarations in this module.


## cdm/data_collection/specs/house_vote_specs.py

[Source](../../../cdm/data_collection/specs/house_vote_specs.py)

No declarations in this module.


## cdm/data_collection/specs/law_specs.py

[Source](../../../cdm/data_collection/specs/law_specs.py)

No declarations in this module.


## cdm/data_collection/specs/member_specs.py

[Source](../../../cdm/data_collection/specs/member_specs.py)

No declarations in this module.


## cdm/data_collection/specs/nomination_specs.py

[Source](../../../cdm/data_collection/specs/nomination_specs.py)

No declarations in this module.


## cdm/data_collection/specs/treaty_specs.py

[Source](../../../cdm/data_collection/specs/treaty_specs.py)

No declarations in this module.


## cdm/data_collection/utils.py

[Source](../../../cdm/data_collection/utils.py)

- class: [`PaginationMeta()`](../../../cdm/data_collection/utils.py#L11)
- field: [`PaginationMeta.next_offset: int`](../../../cdm/data_collection/utils.py#L14)
- field: [`PaginationMeta.total: int`](../../../cdm/data_collection/utils.py#L15)
- field: [`PaginationMeta.page_size: int`](../../../cdm/data_collection/utils.py#L16)
- class: [`PaginationResolver()`](../../../cdm/data_collection/utils.py#L19)
- function: [`PaginationResolver.__init__(self, offset_param_names: tuple[str, ...]=('offset', 'start', 'skip'), page_param_names: tuple[str, ...]=('page', 'pageNumber', 'page_number')) -> None`](../../../cdm/data_collection/utils.py#L22)
- function: [`PaginationResolver._query_int(url: str, keys: tuple[str, ...]) -> int \| None`](../../../cdm/data_collection/utils.py#L31)
- function: [`PaginationResolver.offset_from_url(self, url: str, page_size: int \| None=None) -> int \| None`](../../../cdm/data_collection/utils.py#L41)
- function: [`PaginationResolver.resolve(self, response: Mapping[str, object], *, records_len: int, offset: int, page_size: int) -> PaginationMeta`](../../../cdm/data_collection/utils.py#L51)
- function: [`PaginationResolver._from_pagination(self, pagination: dict, records_len: int, page_size: int) -> PaginationMeta`](../../../cdm/data_collection/utils.py#L67)
- function: [`PaginationResolver._from_results(results: dict, records_len: int, offset: int, page_size: int) -> PaginationMeta`](../../../cdm/data_collection/utils.py#L93)
