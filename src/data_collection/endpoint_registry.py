from typing import Dict, Optional, Tuple, Type

from pydantic import BaseModel

from src.models.endpoint_spec import EndpointSpec, ParamLocation, ParamSpec
from src.models.endpoint_spec import EndpointSpec as _ES

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

    Args:
        resource_name (str): A short name for the resource, used in spec names
            and as a default key for unwrapping item responses.
        path_root (str): The root path for the resource (e.g. "/bill").
        list_model (Type[BaseModel]): The Pydantic model for list endpoint items.
        item_model (Type[BaseModel]): The Pydantic model for item endpoint responses.
        data_key (Optional[str]): The key in list responses containing the items list.
            Defaults to "{resource_name}s" (e.g. "bills").
        id_param_name (str): The name of the path parameter for item endpoints.
            Defaults to "id". This should match the field name in the item model
            used to identify individual records (e.g. "bill_id") and will be used to extract the item ID from list record URLs or path segments.

    Returns:
        Tuple[EndpointSpec, EndpointSpec]: The list and item EndpointSpec objects.
    """
    data_key = data_key or f"{resource_name}s"
    list_spec = EndpointSpec(
        name=f"{resource_name}_list",
        path_template=path_root,
        param_specs=[],
        data_key=data_key,
        id_strategy=_ES.IdStrategy(reference_from="url"),
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
        id_strategy=_ES.IdStrategy(reference_from="url"),
        unwrap_key=resource_name,
        response_model=item_model,
    )

    return list_spec, item_spec


def register_specs(list_spec: EndpointSpec, item_spec: EndpointSpec) -> None:
    """Register a pair of list and item ``EndpointSpec`` objects.

    The specs are stored in the module-level registry under their
    ``name`` attributes so callers can retrieve them via ``get_spec``.

    Args:
        list_spec (EndpointSpec): The spec for the list endpoint.
        item_spec (EndpointSpec): The spec for the item endpoint.

    Returns:
        None
    """
    _REGISTRY[list_spec.name] = list_spec
    _REGISTRY[item_spec.name] = item_spec


def register_spec(spec: EndpointSpec) -> None:
    """Register a single EndpointSpec under its name.

    Args:
        spec (EndpointSpec): The EndpointSpec to register.
    """
    _REGISTRY[spec.name] = spec


def register_from_model(
    resource_name: str,
    path_root: str,
    list_model: Type[BaseModel],
    item_model: Type[BaseModel],
    data_key: Optional[str] = None,
    id_param_name: str = "id",
) -> Tuple[EndpointSpec, EndpointSpec]:
    """Create list/item specs from Pydantic models and register them.

    This helper is a convenience wrapper around :func:`make_list_and_item_specs`
    and :func:`register_specs`.
    """
    list_spec, item_spec = make_list_and_item_specs(
        resource_name, path_root, list_model, item_model, data_key, id_param_name
    )
    register_specs(list_spec, item_spec)
    return list_spec, item_spec


def get_spec(name: str) -> EndpointSpec:
    """Return the named ``EndpointSpec`` from the registry.

    Raises ``KeyError`` if the spec name is not registered.
    """
    return _REGISTRY[name]


def all_specs() -> Dict[str, EndpointSpec]:
    """Return a shallow copy of the internal spec registry mapping.

    Useful for iteration or inspection without mutating the module state.
    """
    return dict(_REGISTRY)


__all__ = [
    "make_list_and_item_specs",
    "register_specs",
    "register_spec",
    "register_from_model",
    "get_spec",
    "all_specs",
]
