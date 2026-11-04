"""Explicit target and request bounds for non-overwriting bill replay."""

from typing import NewType

from pydantic import BaseModel, ConfigDict, Field

IndexName = NewType("IndexName", str)
AliasName = NewType("AliasName", str)


class CreateOnlyTarget(BaseModel):
    model_config = ConfigDict(frozen=True)

    cluster_uuid: str = Field(min_length=1)
    index_name: IndexName = Field(min_length=1)
    index_uuid: str = Field(min_length=1)
    aliases: tuple[AliasName, ...] = ()


class CreateOnlySettings(BaseModel):
    model_config = ConfigDict(frozen=True)

    maximum_batch_size: int = Field(default=200, ge=1, le=1000)
    request_timeout: float = Field(default=60, gt=0)
