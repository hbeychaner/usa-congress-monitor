"""Shared utilities for endpoint pagination and date handling."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse


def _extract_query_int(url: str, keys: tuple[str, ...]) -> int | None:
    """Extract the first integer query parameter found for ``keys`` from ``url``.

    Args:
        url: URL string containing query parameters.
        keys: Tuple of parameter names to search for in order.

    Returns:
        The integer value of the first matching query parameter, or ``None``
        when no integer value could be parsed.
    """
    parsed_url = urlparse(url)
    params = parse_qs(parsed_url.query)
    for key in keys:
        if params.get(key):
            try:
                return int(params[key][0])
            except (TypeError, ValueError):
                return None
    return None


def extract_offset_from_url(
    url: str,
    *,
    offset_param_names: tuple[str, ...] = ("offset", "start", "skip"),
    page_param_names: tuple[str, ...] = ("page", "pageNumber", "page_number"),
    page_size: int | None = None,
) -> int | None:
    """Extract an offset or page from a URL query string."""
    offset = _extract_query_int(url, offset_param_names)
    if offset is not None:
        return offset
    page = _extract_query_int(url, page_param_names)
    if page is not None and page_size:
        return max(0, (page - 1) * page_size)
    return None


@dataclass(frozen=True)
class PaginationMeta:
    """Pagination metadata describing the next offset and totals.

    Attributes:
        next_offset: The offset to request for the next page, or -1 when none.
        total: Total number of available records when known.
        page_size: Effective page size used for pagination calculations.
    """

    next_offset: int
    total: int
    page_size: int


def resolve_pagination(
    response: dict,
    *,
    records_len: int,
    offset: int,
    page_size: int,
    offset_param_names: tuple[str, ...] = ("offset", "start", "skip"),
    page_param_names: tuple[str, ...] = ("page", "pageNumber", "page_number"),
) -> PaginationMeta:
    """Resolve pagination metadata from a response with varied conventions."""
    pagination = response.get("pagination")
    if isinstance(pagination, dict):
        total = int(pagination.get("total") or pagination.get("count") or 0)
        effective_page_size = int(
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
            extracted = extract_offset_from_url(
                next_url,
                offset_param_names=offset_param_names,
                page_param_names=page_param_names,
                page_size=effective_page_size or page_size,
            )
            if extracted is not None:
                next_offset = extracted
        else:
            offset_value = pagination.get("offset")
            if offset_value is not None:
                try:
                    next_offset = int(offset_value)
                except (TypeError, ValueError):
                    next_offset = -1
        return PaginationMeta(
            next_offset=next_offset, total=total, page_size=effective_page_size
        )

    results = response.get("Results")
    if isinstance(results, dict):
        total = int(results.get("TotalCount") or results.get("total") or 0)
        index_start = results.get("IndexStart")
        effective_page_size = page_size or records_len or 0
        if index_start is None:
            return PaginationMeta(
                next_offset=-1, total=total, page_size=effective_page_size
            )
        try:
            index_start_int = int(index_start)
        except (TypeError, ValueError):
            index_start_int = offset
        next_offset = index_start_int + records_len
        if total and next_offset >= total:
            next_offset = -1
        return PaginationMeta(
            next_offset=next_offset, total=total, page_size=effective_page_size
        )

    return PaginationMeta(
        next_offset=-1, total=0, page_size=page_size or records_len or 0
    )
