from cdm.data_collection.endpoint_registry import (
    EndpointSpec,
    ParamLocation,
    ParamSpec,
    get_spec,
    register_spec,
)

# Resources whose Congress.gov list endpoint also exists as /<root>/{congress}.
CONGRESS_LISTABLE = (
    "amendment",
    "committee_report",
    "hearing",
    "house_communication",
    "house_vote",
    "senate_communication",
)


def _by_congress(base: EndpointSpec) -> EndpointSpec:
    fields = {name: getattr(base, name) for name in type(base).model_fields}
    fields["name"] = f"{base.name}_by_congress"
    fields["path_template"] = f"{base.path_template}/{{congress}}"
    fields["param_specs"] = [
        ParamSpec(
            name="congress",
            location=ParamLocation.PATH,
            required=True,
            source_field="congress",
        ),
        *base.param_specs,
    ]
    return EndpointSpec(**fields)


for _resource in CONGRESS_LISTABLE:
    register_spec(_by_congress(get_spec(f"{_resource}_list")))
