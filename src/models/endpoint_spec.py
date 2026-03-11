from __future__ import annotations

from typing import Any, Dict, List, Optional, Type
from enum import Enum
from collections import OrderedDict as _OrderedDict

from pydantic import BaseModel, Field, model_validator, PrivateAttr, ConfigDict


class ParamLocation(str, Enum):
    PATH = "path"
    QUERY = "query"
    HEADER = "header"
    COOKIE = "cookie"
    BODY = "body"


class SchemaSpec(BaseModel):
    """A lightweight JSON-schema-like fragment for parameter typing."""

    type: Optional[str] = None
    format: Optional[str] = None
    enum: Optional[List[Any]] = None
    items: Optional[dict] = None
    minimum: Optional[float] = None
    maximum: Optional[float] = None


class ParamSpec(BaseModel):
    name: str
    location: ParamLocation = ParamLocation.QUERY
    required: bool = False
    # Optional: where to read this param from when deriving runtime params
    # from a list-item or metadata record. If `source_field` is set, the
    # record's mapping or attribute will be read. If `extract_from_url_segment`
    # is set, the URL found in `source_field` (or `url`) will be split on the
    # segment and the trailing part used (useful for IDs embedded in hrefs).
    source_field: Optional[str] = None
    extract_from_url_segment: Optional[str] = None
    # Avoid clashing with BaseModel.schema(); use `schema_spec` instead.
    schema_spec: Optional[SchemaSpec] = None
    style: Optional[str] = None
    explode: Optional[bool] = None
    allow_empty_value: Optional[bool] = False
    default: Optional[Any] = None
    description: Optional[str] = None
    example: Optional[Any] = None
    deprecated: Optional[bool] = False


class PaginationType(str, Enum):
    OFFSET = "offset"
    PAGE = "page"
    CURSOR = "cursor"


class PaginationSpec(BaseModel):
    type: PaginationType = PaginationType.OFFSET
    offset_param: str = "offset"
    limit_param: str = "limit"
    page_param: Optional[str] = None
    cursor_param: Optional[str] = None
    cursor_response_field: Optional[str] = None
    default_limit: Optional[int] = None
    max_limit: Optional[int] = None


class EndpointSpec(BaseModel):
    """Describe how to call an API endpoint and parse responses.

    Helper methods provide runtime URL building and basic validation.
    """

    name: str
    method: str = "GET"
    path_template: str
    param_specs: List[ParamSpec] = Field(default_factory=list)
    pagination: Optional[PaginationSpec] = None
    data_key: Optional[str] = None
    unwrap_key: Optional[str] = None
    response_model: Optional[Type[BaseModel]] = None
    # dotted path to id builder or name; resolution can be performed at runtime
    id_builder_name: Optional[str] = None

    # Internal map of param name -> ParamSpec (private attr so Pydantic
    # doesn't treat this as a model field but static checkers still see it)
    _param_map: Dict[str, "ParamSpec"] = PrivateAttr(default_factory=dict)

    @model_validator(mode="after")
    def _build_param_map(self):
        specs = getattr(self, "param_specs", []) or []
        object.__setattr__(self, "_param_map", {p.name: p for p in specs})
        return self

    def render_path(self, base_url: str, params: Dict[str, Any]) -> str:
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

    def build_query(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Return dict of query params from runtime params using `param_specs`."""
        q: Dict[str, Any] = {}
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

    def validate_params(self, params: Dict[str, Any]) -> None:
        """Basic validation of required params and simple type checks."""
        for name, p in self._param_map.items():
            if p.required and name not in params:
                raise ValueError(f"Missing required param: {name}")
            if name in params and p.schema_spec and p.schema_spec.type:
                typ = p.schema_spec.type
                val = params[name]
                if typ == "integer":
                    if not isinstance(val, int):
                        raise ValueError(
                            f"Param {name} expected integer, got {type(val)}"
                        )
                if typ == "number":
                    if not isinstance(val, (int, float)):
                        raise ValueError(
                            f"Param {name} expected number, got {type(val)}"
                        )


class MetadataRecord(BaseModel):
    endpoint: EndpointSpec
    runtime_params: _OrderedDict = Field(default_factory=_OrderedDict)
    offset: Optional[int] = None
    limit: Optional[int] = None
    page: Optional[int] = None

    model_config = ConfigDict(arbitrary_types_allowed=True)
