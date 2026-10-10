"""Endpoint pagination resolution across the API's varied conventions."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse


@dataclass(frozen=True)
class PaginationMeta:
    """Next offset (-1 when none), total records and effective page size."""

    next_offset: int
    total: int
    page_size: int


class PaginationResolver:
    """Resolves pagination metadata from a list response."""

    def __init__(
        self,
        offset_param_names: tuple[str, ...] = ("offset", "start", "skip"),
        page_param_names: tuple[str, ...] = ("page", "pageNumber", "page_number"),
    ) -> None:
        self._offset_params = offset_param_names
        self._page_params = page_param_names

    @staticmethod
    def _query_int(url: str, keys: tuple[str, ...]) -> int | None:
        params = parse_qs(urlparse(url).query)
        for key in keys:
            if params.get(key):
                try:
                    return int(params[key][0])
                except (TypeError, ValueError):
                    return None
        return None

    def offset_from_url(self, url: str, page_size: int | None = None) -> int | None:
        """Extract an offset (or page converted to an offset) from a URL query."""
        offset = self._query_int(url, self._offset_params)
        if offset is not None:
            return offset
        page = self._query_int(url, self._page_params)
        if page is not None and page_size:
            return max(0, (page - 1) * page_size)
        return None

    def resolve(
        self,
        response: Mapping[str, object],
        *,
        records_len: int,
        offset: int,
        page_size: int,
    ) -> PaginationMeta:
        pagination = response.get("pagination")
        if isinstance(pagination, dict):
            return self._from_pagination(pagination, records_len, page_size)
        results = response.get("Results")
        if isinstance(results, dict):
            return self._from_results(results, records_len, offset, page_size)
        return PaginationMeta(-1, 0, page_size or records_len or 0)

    def _from_pagination(
        self, pagination: dict, records_len: int, page_size: int
    ) -> PaginationMeta:
        total = int(pagination.get("total") or pagination.get("count") or 0)
        effective = int(
            pagination.get("limit")
            or pagination.get("pageSize")
            or pagination.get("pagesize")
            or page_size
            or records_len
            or 0
        )
        next_offset = -1
        next_url = pagination.get("next") or pagination.get("nextPage")
        if isinstance(next_url, str):
            extracted = self.offset_from_url(next_url, effective or page_size)
            if extracted is not None:
                next_offset = extracted
        elif pagination.get("offset") is not None:
            try:
                next_offset = int(pagination["offset"])
            except (TypeError, ValueError):
                next_offset = -1
        return PaginationMeta(next_offset, total, effective)

    @staticmethod
    def _from_results(
        results: dict, records_len: int, offset: int, page_size: int
    ) -> PaginationMeta:
        total = int(results.get("TotalCount") or results.get("total") or 0)
        effective = page_size or records_len or 0
        index_start = results.get("IndexStart")
        if index_start is None:
            return PaginationMeta(-1, total, effective)
        try:
            start = int(index_start)
        except (TypeError, ValueError):
            start = offset
        next_offset = start + records_len
        if total and next_offset >= total:
            next_offset = -1
        return PaginationMeta(next_offset, total, effective)
