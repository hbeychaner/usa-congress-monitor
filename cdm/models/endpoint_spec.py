from __future__ import annotations

from collections import OrderedDict as _OrderedDict
from collections.abc import Mapping
from enum import Enum, StrEnum

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, model_validator


class HttpMethod(StrEnum):
    """HTTP methods supported by endpoint specifications."""

    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"


class ReferenceSource(StrEnum):
    """Sources supported for deriving a related record identifier."""

    URL = "url"


class ParamLocation(StrEnum):
    """Enumeration of locations where a parameter can appear in a request."""

    PATH = "path"
    QUERY = "query"
    HEADER = "header"
    COOKIE = "cookie"
    BODY = "body"


class SchemaSpec(BaseModel):
    """A lightweight JSON-schema-like fragment for parameter typing."""

    type: str | None = None
    format: str | None = None
    enum: list[str] | None = None
    items: dict | None = None
    minimum: float | None = None
    maximum: float | None = None


# JSON-like alias for parameter values in endpoint specs.
type Json = str | int | float | bool | None | list["Json"] | Mapping[str, "Json"]


class ParamSpec(BaseModel):
    """Specification for a single parameter used in an endpoint.

    Attributes:
        name: Parameter name as used in path or query.
        location: Where the parameter appears (path, query, header, etc.).
        required: Whether the parameter is required for requests.
        source_field: Optional field on a list-item used to derive the value.
        extract_from_url_segment: Optional URL segment token to extract an id.
        schema_spec: Optional lightweight schema describing expected type.
        default: Optional default value when not provided at runtime.
        description: Human-friendly description of the parameter.
    """

    name: str
    location: ParamLocation = ParamLocation.QUERY
    required: bool = False
    # Optional: where to read this param from when deriving runtime params
    # from a list-item or metadata record. If `source_field` is set, the
    # record's mapping or attribute will be read. If `extract_from_url_segment`
    # is set, the URL found in `source_field` (or `url`) will be split on the
    # segment and the trailing part used (useful for IDs embedded in hrefs).
    source_field: str | None = None
    extract_from_url_segment: str | None = None
    # Avoid clashing with BaseModel.schema(); use `schema_spec` instead.
    schema_spec: SchemaSpec | None = None
    style: str | None = None
    explode: bool | None = None
    allow_empty_value: bool | None = False
    default: object | None = None
    description: str | None = None
    example: object | None = None
    deprecated: bool | None = False


class PaginationType(str, Enum):
    """Enumeration of pagination strategies supported by endpoints.

    - OFFSET: classic offset/limit pagination.
    - PAGE: page-number based pagination.
    - CURSOR: cursor-based pagination.
    """

    OFFSET = "offset"
    PAGE = "page"
    CURSOR = "cursor"


class PaginationSpec(BaseModel):
    """Describe how an endpoint paginates results.

    Supports common pagination styles (offset/limit, page numbers, cursors)
    and the names used for parameters and response cursor fields.
    """

    type: PaginationType = PaginationType.OFFSET
    offset_param: str = "offset"
    limit_param: str = "limit"
    page_param: str | None = None
    cursor_param: str | None = None
    cursor_response_field: str | None = None
    default_limit: int | None = None
    max_limit: int | None = None


class EndpointSpec(BaseModel):
    """Describe how to call an API endpoint and parse responses.

    Helper methods provide runtime URL building and basic validation.
    """

    name: str
    method: HttpMethod = HttpMethod.GET
    path_template: str
    param_specs: list[ParamSpec] = Field(default_factory=list)
    pagination: PaginationSpec | None = None
    data_key: str | None = None
    unwrap_key: str | None = None
    response_model: type[BaseModel] | None = None

    # optional typed strategy to drive id/reference population and custom hooks
    class IdStrategy(BaseModel):
        reference_from: ReferenceSource | None = None
        unique_from: list[str] | None = None
        section_bounds: str | None = None

    id_strategy: IdStrategy | None = None
    # dotted path to id builder or name; resolution can be performed at runtime
    id_builder_name: str | None = None

    # Internal map of param name -> ParamSpec (private attr so Pydantic
    # doesn't treat this as a model field but static checkers still see it)
    _param_map: dict[str, ParamSpec] = PrivateAttr(default_factory=dict)

    @model_validator(mode="after")
    def _build_param_map(self):
        """Pydantic post-init validator that builds a name->ParamSpec map.

        This populates the private ``_param_map`` attribute from
        ``param_specs`` so lookup by name is efficient at runtime.
        """
        specs = getattr(self, "param_specs", []) or []
        object.__setattr__(self, "_param_map", {p.name: p for p in specs})
        return self

    def render_path(self, base_url: str, params: Mapping[str, object]) -> str:
        """Render the full URL by substituting path params into `path_template`.

        Raises ValueError when required path params are missing.
        """
        path = self.path_template
        # Validate required path params
        for name, p in self._param_map.items():
            if p.location == ParamLocation.PATH and p.required and name not in params:
                raise ValueError(f"Missing required path param: {name}")
        try:
            rendered = path.format(
                **{
                    k: v
                    for k, v in params.items()
                    if k in self._param_map
                    and self._param_map[k].location == ParamLocation.PATH
                }
            )
        except KeyError as e:
            raise ValueError(f"Missing path parameter for template: {e}")
        return base_url.rstrip("/") + rendered

    def build_query(self, params: Mapping[str, object]) -> dict[str, object]:
        """Return dict of query params from runtime params using `param_specs`."""
        q: dict[str, object] = {}
        for name, p in self._param_map.items():
            if p.location == ParamLocation.QUERY and name in params:
                q[name] = params[name]
            elif (
                p.location == ParamLocation.QUERY
                and p.default is not None
                and name not in params
            ):
                q[name] = p.default
        return q

    def validate_params(self, params: Mapping[str, object]) -> None:
        """Basic validation of required params and simple type checks."""
        for name, p in self._param_map.items():
            if p.required and name not in params:
                raise ValueError(f"Missing required param: {name}")
            if name in params and p.schema_spec and p.schema_spec.type:
                typ = p.schema_spec.type
                val = params[name]
                if typ == "integer" and not isinstance(val, int):
                    raise ValueError(f"Param {name} expected integer, got {type(val)}")
                if typ == "number" and not isinstance(val, (int, float)):
                    raise ValueError(f"Param {name} expected number, got {type(val)}")


class MetadataRecord(BaseModel):
    """Container describing a specific endpoint invocation and its state.

    Attributes:
        endpoint: The ``EndpointSpec`` describing the endpoint to call.
        runtime_params: Ordered runtime parameters resolved for the call.
        offset: Optional pagination offset for list-style endpoints.
        limit: Optional page size for list-style endpoints.
        page: Optional page number when using page-based pagination.
    """

    endpoint: EndpointSpec
    runtime_params: _OrderedDict = Field(default_factory=_OrderedDict)
    offset: int | None = None
    limit: int | None = None
    page: int | None = None

    model_config = ConfigDict(arbitrary_types_allowed=True)
