from typing import Dict, Tuple, Type, Optional

from pydantic import BaseModel

from src.models.endpoint_spec import EndpointSpec, ParamSpec, ParamLocation


_REGISTRY: Dict[str, EndpointSpec] = {}


def make_list_and_item_specs(
    resource_name: str,
    path_root: str,
    list_model: Type[BaseModel],
    item_model: Type[BaseModel],
    data_key: Optional[str] = None,
    id_param_name: str = "id",
) -> Tuple[EndpointSpec, EndpointSpec]:
    """Return an EndpointSpec pair for list and item using separate models.

    Using a lighter `list_model` for list endpoints avoids validating
    list entries against the full item schema.
    """
    data_key = data_key or f"{resource_name}s"
    list_spec = EndpointSpec(
        name=f"{resource_name}_list",
        path_template=path_root,
        param_specs=[],
        data_key=data_key,
        response_model=list_model,
    )

    item_spec = EndpointSpec(
        name=f"{resource_name}_item",
        path_template=f"{path_root}/{{{id_param_name}}}",
        param_specs=[
            ParamSpec(
                name=id_param_name,
                location=ParamLocation.PATH,
                required=True,
                source_field=id_param_name,
                extract_from_url_segment=resource_name,
            )
        ],
        data_key=None,
        unwrap_key=resource_name,
        response_model=item_model,
    )

    return list_spec, item_spec


def register_specs(list_spec: EndpointSpec, item_spec: EndpointSpec) -> None:
    _REGISTRY[list_spec.name] = list_spec
    _REGISTRY[item_spec.name] = item_spec


def register_spec(spec: EndpointSpec) -> None:
    """Register a single EndpointSpec under its name."""
    _REGISTRY[spec.name] = spec


def register_from_model(
    resource_name: str,
    path_root: str,
    list_model: Type[BaseModel],
    item_model: Type[BaseModel],
    data_key: Optional[str] = None,
    id_param_name: str = "id",
) -> Tuple[EndpointSpec, EndpointSpec]:
    list_spec, item_spec = make_list_and_item_specs(
        resource_name, path_root, list_model, item_model, data_key, id_param_name
    )
    register_specs(list_spec, item_spec)
    return list_spec, item_spec


def get_spec(name: str) -> EndpointSpec:
    return _REGISTRY[name]


def all_specs() -> Dict[str, EndpointSpec]:
    return dict(_REGISTRY)


__all__ = [
    "make_list_and_item_specs",
    "register_specs",
    "register_spec",
    "register_from_model",
    "get_spec",
    "all_specs",
]
