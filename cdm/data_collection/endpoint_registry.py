from pydantic import BaseModel

from cdm.models.endpoint_spec import (
    EndpointSpec,
    ParamLocation,
    ParamSpec,
    ReferenceSource,
)
from cdm.models.endpoint_spec import EndpointSpec as _ES


class SpecRegistry:
    """Name-indexed store of endpoint specs."""

    def __init__(self) -> None:
        self._specs: dict[str, EndpointSpec] = {}

    @staticmethod
    def make_list_and_item_specs(
        resource_name: str,
        path_root: str,
        list_model: type[BaseModel],
        item_model: type[BaseModel],
        data_key: str | None = None,
        id_param_name: str = "id",
    ) -> tuple[EndpointSpec, EndpointSpec]:
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
            id_strategy=_ES.IdStrategy(reference_from=ReferenceSource.URL),
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
            id_strategy=_ES.IdStrategy(reference_from=ReferenceSource.URL),
            unwrap_key=resource_name,
            response_model=item_model,
        )

        return list_spec, item_spec

    def register_specs(self, list_spec: EndpointSpec, item_spec: EndpointSpec) -> None:
        """Register a list/item pair under their names."""
        self.register_spec(list_spec)
        self.register_spec(item_spec)

    def register_spec(self, spec: EndpointSpec) -> None:
        """Register a single spec under its name."""
        self._specs[spec.name] = spec

    def register_from_model(
        self,
        resource_name: str,
        path_root: str,
        list_model: type[BaseModel],
        item_model: type[BaseModel],
        data_key: str | None = None,
        id_param_name: str = "id",
    ) -> tuple[EndpointSpec, EndpointSpec]:
        """Create list/item specs from models and register them."""
        pair = self.make_list_and_item_specs(
            resource_name, path_root, list_model, item_model, data_key, id_param_name
        )
        self.register_specs(*pair)
        return pair

    def get_spec(self, name: str) -> EndpointSpec:
        """Return the named spec; raises ``KeyError`` when unregistered."""
        return self._specs[name]

    def all_specs(self) -> dict[str, EndpointSpec]:
        """Return a shallow copy of the registry mapping."""
        return dict(self._specs)


REGISTRY = SpecRegistry()
make_list_and_item_specs = SpecRegistry.make_list_and_item_specs
register_specs = REGISTRY.register_specs
register_spec = REGISTRY.register_spec
register_from_model = REGISTRY.register_from_model
get_spec = REGISTRY.get_spec
all_specs = REGISTRY.all_specs

__all__ = [
    "REGISTRY",
    "SpecRegistry",
    "all_specs",
    "get_spec",
    "make_list_and_item_specs",
    "register_from_model",
    "register_spec",
    "register_specs",
]
