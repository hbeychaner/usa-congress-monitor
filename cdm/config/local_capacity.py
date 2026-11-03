"""Safety margins for the managed local Compose stack."""

from pydantic import BaseModel, Field


class LocalCapacityPolicy(BaseModel):
    docker_reserve_bytes: int = Field(default=256 * 1024**2, ge=0)
    minimum_free_disk_bytes: int = Field(default=8 * 1024**3, gt=0)
    command_timeout_seconds: int = Field(default=60, gt=0)
