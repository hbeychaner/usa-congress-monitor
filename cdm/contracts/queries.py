"""Shared pagination metadata and explicit unsupported-query errors."""

from pydantic import Field, computed_field

from cdm.contracts.base import ResponseModel


class QueryReadError(ValueError):
    def __init__(self, message: str, parameter: str) -> None:
        super().__init__(message)
        self.parameter = parameter


class WindowedResponse(ResponseModel):
    total: int
    page: int = 1
    limit: int = Field(default=50, gt=0)
    max_result_window: int = Field(gt=0)

    @computed_field
    @property
    def max_page(self) -> int:
        return max(
            1,
            min(
                (self.total + self.limit - 1) // self.limit,
                self.max_result_window // self.limit,
            ),
        )

    @computed_field
    @property
    def window_limited(self) -> bool:
        return self.total > (self.max_result_window // self.limit) * self.limit
