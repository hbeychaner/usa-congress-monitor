"""Convert OpenAPI/Swagger JSON to EndpointSpec objects.

This is a lightweight converter intended for initial scaffolding. It
creates a JSON file with serialized EndpointSpec dictionaries under
`documentation/generated_endpoint_specs.json`.

Limitations: supports basic parameter extraction and simple pagination
heuristics (looks for 'offset'/'limit' or 'page'/'pageSize' params).
"""

import json
from pathlib import Path
from typing import Any, Dict, List

from src.models.endpoint_spec import (
    EndpointSpec,
    ParamSpec,
    SchemaSpec,
    PaginationSpec,
    PaginationType,
)


SWAGGER_PATH = Path("documentation/original/swagger.json")
OUT_PATH = Path("documentation/generated_endpoint_specs.json")


def schema_from_param(p: Dict[str, Any]) -> Dict[str, Any]:
    s = p.get("schema") or {}
    return {
        "type": s.get("type"),
        "format": s.get("format"),
        "enum": s.get("enum"),
        "items": s.get("items"),
        "minimum": s.get("minimum"),
        "maximum": s.get("maximum"),
    }


def convert():
    if not SWAGGER_PATH.exists():
        raise SystemExit(f"Swagger file not found at {SWAGGER_PATH}")
    root = json.loads(SWAGGER_PATH.read_text())
    paths = root.get("paths", {})
    out: List[Dict[str, Any]] = []
    for path, methods in paths.items():
        for method, op in methods.items():
            m = method.upper()
            op_id = op.get("operationId") or f"{m}_{path}"
            # collect parameters (path-level + op-level)
            params = []
            if isinstance(methods, dict):
                # path-level parameters if present under methods (some specs put parameters on the path dict)
                pass
            for p in op.get("parameters", []) or []:
                param = ParamSpec(
                    name=p.get("name"),
                    location=p.get("in"),
                    required=bool(p.get("required", False)),
                    schema_spec=SchemaSpec(**schema_from_param(p)),
                    description=p.get("description"),
                    example=p.get("example"),
                )
                params.append(param)

            # simple pagination heuristics
            pagination = None
            names = {p.name for p in params}
            if "offset" in names or "limit" in names:
                pagination = PaginationSpec(type=PaginationType.OFFSET)
            elif "page" in names or "pageSize" in names or "page_size" in names:
                pagination = PaginationSpec(type=PaginationType.PAGE)

            # try to detect data_key from 200 response schema
            data_key = None
            responses = op.get("responses", {})
            success = responses.get("200") or responses.get("201") or {}
            content = success.get("content") or {}
            if isinstance(content, dict):
                appl = content.get("application/json") or {}
                schema = appl.get("schema") or {}
                # if schema has properties and one of them is an array, pick that
                props = schema.get("properties") or {}
                for k, v in props.items():
                    if v.get("type") == "array":
                        data_key = k
                        break
            spec = EndpointSpec(
                name=op_id,
                method=m,
                path_template=path,
                param_specs=params,
                pagination=pagination,
                data_key=data_key,
            )
            out.append(spec.model_dump())
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(out, indent=2))
    print(f"Wrote {len(out)} endpoint specs to {OUT_PATH}")


if __name__ == "__main__":
    convert()
