
from src.models.people import Congress, CongressMetadata
from src.data_collection.endpoint_registry import register_from_model, get_spec


# Register programmatically: use a lightweight `CongressMetadata` for the
# list endpoint and the full `Congress` model for individual item responses.
register_from_model(
    resource_name="congress",
    path_root="/congress",
    list_model=CongressMetadata,
    item_model=Congress,
    data_key="congresses",
    id_param_name="number",
)


CONGRESS_LIST_SPEC = get_spec("congress_list")
CONGRESS_ITEM_SPEC = get_spec("congress_item")

__all__ = ["CONGRESS_LIST_SPEC", "CONGRESS_ITEM_SPEC"]
