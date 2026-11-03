"""Shared schema policy for fully serialized API responses."""

from pydantic import BaseModel, ConfigDict


class ResponseModel(BaseModel):
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)
