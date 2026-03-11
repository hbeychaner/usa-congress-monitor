"""Congress.gov API client and retry-capable session factory.

This module enforces a JSON-only contract and returns strongly-typed
Pydantic model instances from `iterate_pages`. It intentionally avoids
returning mixed types or raw byte fallbacks.
"""

from typing import Iterator
from urllib.parse import urljoin
import importlib
import inspect
import threading
import time

import requests
from pydantic import BaseModel

from settings import CONGRESS_API_KEY
from src.models.endpoint_spec import EndpointSpec
from src.utils.logger import get_logger

logger = get_logger(__name__)


API_VERSION = "v3"
ROOT_URL = "https://api.congress.gov/"
RESPONSE_FORMAT = "json"


# Helper: detect JSON responses
def _is_json_response(response: requests.Response) -> bool:
    ct = response.headers.get("content-type", "")
    return ct.lower().startswith("application/json")


def _to_int(value: object, default: int) -> int:
    try:
        if value is None:
            return default
        return int(str(value))
    except Exception:
        return default


# Explicit JSON helper method is implemented on the client class below.


class CDGClient:
    """Client for Congress.gov API requests.

    This client enforces a JSON-only contract and yields Pydantic model
    instances from `iterate_pages` when `spec.response_model` is provided.
    """

    def __init__(
        self,
        api_key: str,
        api_version: str = API_VERSION,
        response_format: str = RESPONSE_FORMAT,
        raise_on_error: bool = True,
        added_headers: dict[str, str] | None = None,
    ) -> None:
        self.base_url = urljoin(ROOT_URL, api_version) + "/"
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": "congress-tracker/1.0"})
        self._session.params = {"format": response_format}
        self._session.headers.update({"x-api-key": api_key})
        if added_headers:
            self._session.headers.update(added_headers)

        if raise_on_error:
            # keep behavior but avoid requiring Response in type hints
            self._session.hooks = {
                "response": lambda r, *a, **k: (
                    r.raise_for_status() if isinstance(r, requests.Response) else None
                )
            }

        self._rate_limit_lock = threading.Lock()
        self._rate_limit_last_call = 0.0
        self._rate_limit_interval = 3600.0 / 5000.0
        # configurable retry total wait (seconds). If cumulative backoff
        # exceeds this, requests will raise a RuntimeError.
        self._max_total_retry_wait = 10.0

    @property
    def session(self) -> requests.Session:
        return self._session

    def get_json(
        self, endpoint: str, params: dict[str, object] | None = None, timeout: int = 10
    ) -> dict[str, object]:
        """Perform a GET against `endpoint` (relative path), enforce JSON, return mapping.

        This explicit helper makes behavior clear and is easy to stub in tests.
        """
        self._rate_limited()
        p = {k: str(v) for k, v in (params or {}).items()}
        resp = self._request_with_backoff(
            urljoin(self.base_url, endpoint), params=p, timeout=timeout
        )
        if not _is_json_response(resp):
            raise ValueError("Non-JSON response received from Congress.gov API")
        parsed = resp.json()
        if not isinstance(parsed, dict):
            raise ValueError("JSON response is not an object mapping")
        return parsed

    def request_for_spec(
        self, spec: EndpointSpec, runtime_params: dict[str, object], timeout: int = 10
    ) -> dict[str, object]:
        """Render path + query for `spec`, perform request, return JSON object mapping.

        Raises ValueError for non-JSON responses or unexpected JSON shapes.
        """
        spec.validate_params(runtime_params)
        url = spec.render_path(self.base_url, runtime_params)
        query = spec.build_query(runtime_params)

        self._rate_limited()
        resp = self._session.get(url, params=query, timeout=timeout)
        resp = self._request_with_backoff(
            url, params={k: str(v) for k, v in (query or {}).items()}, timeout=timeout
        )
        if not _is_json_response(resp):
            raise ValueError("Non-JSON response received from Congress.gov API")
        parsed = resp.json()
        if not isinstance(parsed, dict):
            raise ValueError("Unexpected JSON shape: expected object mapping")
        return parsed

    def _request_with_backoff(
        self,
        url: str,
        params: dict | None = None,
        timeout: int = 10,
        *,
        base_delay: float = 0.5,
        max_delay: float = 10.0,
        max_attempts: int = 5,
    ):
        """Perform GET with exponential backoff. Raises RuntimeError if
        cumulative backoff exceeds `self._max_total_retry_wait`.
        """
        attempts = 0
        cumulative_sleep = 0.0
        while True:
            try:
                resp = self._session.get(url, params=params, timeout=timeout)
                # Treat 5xx as retryable when a real status_code is present.
                if hasattr(resp, "status_code") and getattr(resp, "status_code") >= 500:
                    raise requests.HTTPError(
                        f"server error: {getattr(resp, 'status_code', 'unknown')}",
                        response=resp,
                    )
                resp.raise_for_status()
                return resp
            except Exception as exc:
                attempts += 1
                if attempts >= max_attempts:
                    raise
                # exponential backoff (2**(attempts-1) * base_delay)
                delay = min(max_delay, base_delay * (2 ** (attempts - 1)))
                remaining = self._max_total_retry_wait - cumulative_sleep
                if remaining <= 0:
                    raise RuntimeError(
                        f"Exceeded total retry wait of {self._max_total_retry_wait}s"
                    ) from exc
                sleep_for = min(delay, remaining)
                time.sleep(sleep_for)
                cumulative_sleep += sleep_for
                continue

    def iterate_pages(
        self, spec: EndpointSpec, base_params: dict[str, object] | None = None
    ) -> Iterator[tuple[list[BaseModel], dict[str, object], dict[str, object]]]:
        """Yield lists of `BaseModel` instances coerced from responses.

        `spec.response_model` must be present and resolve to a Pydantic model
        class; otherwise this method raises `ValueError` to keep the API
        strongly typed.
        """
        params: dict[str, object] = dict(base_params or {})
        pagination = spec.pagination
        model_cls = self._resolve_response_model(spec)
        if model_cls is None:
            raise ValueError(
                "spec.response_model must be set to a Pydantic BaseModel subclass for iterate_pages"
            )

        # Single-shot
        if not pagination:
            resp = self.request_for_spec(spec, params)
            records = self._extract_records_from_response(spec, resp)
            coerced = self.coerce_records(model_cls, records)
            yield coerced, resp, {}
            return

    def fetch_list(
        self, spec: EndpointSpec, params: dict[str, object] | None = None
    ) -> list[BaseModel]:
        """Convenience: fetch a single-shot list endpoint and return coerced models.

        This wraps `request_for_spec` + `_extract_records_from_response` + `coerce_records`.
        """
        resp = self.request_for_spec(spec, params or {})
        records = self._extract_records_from_response(spec, resp)
        model_cls = self._resolve_response_model(spec)
        return self.coerce_records(model_cls, records)

    def fetch_one(
        self, spec: EndpointSpec, runtime_params: dict[str, object]
    ) -> BaseModel:
        """Fetch a single-item endpoint and return one coerced model instance.

        Raises ValueError if response does not contain an item.
        """
        resp = self.request_for_spec(spec, runtime_params)
        records = self._extract_records_from_response(spec, resp)
        if not records:
            raise ValueError("no item found in response")
        model_cls = self._resolve_response_model(spec)
        insts = self.coerce_records(model_cls, records)
        return insts[0]

    def resolve_runtime_params_from_record(
        self, spec: EndpointSpec, record: object
    ) -> dict[str, object]:
        """Given a spec and a list-item (mapping or BaseModel), return runtime params.

        Uses `ParamSpec.source_field` and `ParamSpec.extract_from_url_segment` when
        present on path/query params so calling code doesn't need resource-specific
        parsing logic.
        """
        params: dict[str, object] = {}
        # accept either mapping or pydantic BaseModel
        if isinstance(record, BaseModel):
            mapping = record.model_dump()
        elif isinstance(record, dict):
            mapping = record
        else:
            # fallback: try vars()
            try:
                mapping = vars(record)
            except Exception:
                mapping = {}

        def _resolve_source_field(mapping, source_field: str):
            # support dotted paths like 'laws.0.type'
            parts = source_field.split(".") if source_field else []
            v = mapping
            for part in parts:
                if v is None:
                    return None
                if isinstance(v, list):
                    if part.isdigit():
                        idx = int(part)
                        v = v[idx] if 0 <= idx < len(v) else None
                    else:
                        # unsupported non-numeric traversal into list
                        return None
                elif isinstance(v, dict):
                    v = v.get(part)
                else:
                    return None
            return v

        for p in getattr(spec, "param_specs", []) or []:
            if p.location == p.location.PATH or p.location == p.location.QUERY:
                value = None
                if p.source_field:
                    # try dotted-path resolution first
                    def _resolve_source_field(mapping, source_field: str):
                        parts = source_field.split(".") if source_field else []
                        v = mapping
                        for part in parts:
                            if v is None:
                                return None
                            if isinstance(v, list):
                                if part.isdigit():
                                    idx = int(part)
                                    v = v[idx] if 0 <= idx < len(v) else None
                                else:
                                    return None
                            elif isinstance(v, dict):
                                v = v.get(part)
                            else:
                                return None
                        return v

                    for p in getattr(spec, "param_specs", []) or []:
                        if (
                            p.location == p.location.PATH
                            or p.location == p.location.QUERY
                        ):
                            value = None
                            if getattr(p, "source_field", None):
                                value = _resolve_source_field(mapping, p.source_field)
                                if value is None and p.source_field in mapping:
                                    value = mapping.get(p.source_field)
                            if value is None and getattr(
                                p, "extract_from_url_segment", None
                            ):
                                url = mapping.get("url")
                                if url is not None:
                                    url_str = str(url)
                                    if f"/{p.extract_from_url_segment}/" in url_str:
                                        tail = url_str.split(
                                            f"/{p.extract_from_url_segment}/"
                                        )[-1]
                                        value = tail.split("?")[0]
                            if value is not None:
                                # Map law type strings like 'Public Law' -> 'pub'
                                if p.name == "lawType" and isinstance(value, str):
                                    low = value.strip().lower()
                                    if "public" in low:
                                        value = "pub"
                                    elif "private" in low:
                                        value = "priv"
                                # Normalize law number: strip optional congress prefix like '119-44' -> '44'
                                if p.name == "lawNumber" and isinstance(value, str) and "-" in value:
                                    value = value.split("-", 1)[-1]
                                if (
                                    isinstance(value, str)
                                    and p.location == p.location.PATH
                                ):
                                    value = value.lower()
                                params[p.name] = value
        return params

    def _resolve_response_model(self, spec: EndpointSpec) -> type[BaseModel]:
        model = spec.response_model
        if model is None:
            raise ValueError("spec.response_model is not set")
        if isinstance(model, str):
            mod_name, _, cls_name = model.rpartition(".")
            if not mod_name:
                raise ValueError(f"response_model string has no module path: {model}")
            try:
                mod = importlib.import_module(mod_name)
                cls = getattr(mod, cls_name)
                if inspect.isclass(cls) and issubclass(cls, BaseModel):
                    return cls
                raise ValueError(f"resolved attribute is not a BaseModel: {model}")
            except Exception as exc:
                logger.exception("failed to import response_model %s", model)
                raise ValueError(
                    f"failed to import response_model {model}: {exc}"
                ) from exc
        if inspect.isclass(model) and issubclass(model, BaseModel):
            return model
        raise ValueError(f"response_model is not a Pydantic BaseModel: {model}")

    def coerce_records(
        self, model_cls: type[BaseModel], records: list[dict[str, object]]
    ) -> list[BaseModel]:
        """Coerce mapping records into instances of `model_cls`.

        Raises `ValueError` on validation failure to keep contract explicit.
        """
        coerced: list[BaseModel] = []
        for r in records:
            if not isinstance(r, dict):
                raise ValueError("record is not a mapping")
            try:
                inst = model_cls.model_validate(r)
            except Exception as exc:  # validation error
                logger.exception("failed to validate record against %s", model_cls)
                raise ValueError(f"failed to validate record: {exc}") from exc
            coerced.append(inst)
        return coerced

    def _extract_records_from_response(
        self, spec: EndpointSpec, resp_json: dict
    ) -> list[dict[str, object]]:
        """Extract a list of record mappings from a response JSON object.

        Handles `unwrap_key`, first-list heuristics, and single-inner-dict envelopes.
        """
        # If the API returned a paginated wrapper (common for sub-endpoints),
        # and the spec does not declare a `data_key` (i.e. it's not a list
        # endpoint), treat the entire response as a single record so wrapper
        # response models (which expect `pagination` + `request` + payload)
        # can be validated directly.
        if (
            isinstance(resp_json, dict)
            and "pagination" in resp_json
            and "request" in resp_json
            and not getattr(spec, "data_key", None)
        ):
            return [resp_json]

        # explicit unwrap_key
        if getattr(spec, "unwrap_key", None) and spec.unwrap_key in resp_json:
            inner = resp_json.get(spec.unwrap_key)
            if isinstance(inner, list):
                return [i if isinstance(i, dict) else {"value": i} for i in inner]
            if isinstance(inner, dict):
                return [inner]

        # first list found
        for v in resp_json.values():
            if isinstance(v, list):
                return [i if isinstance(i, dict) else {"value": i} for i in v]

        # single inner dict envelope
        dict_vals = [v for v in resp_json.values() if isinstance(v, dict)]
        if len(dict_vals) == 1:
            return [dict_vals[0]]

        return []

    def _rate_limited(self) -> None:
        with self._rate_limit_lock:
            now = time.time()
            elapsed = now - self._rate_limit_last_call
            if elapsed < self._rate_limit_interval:
                time.sleep(self._rate_limit_interval - elapsed)
            self._rate_limit_last_call = time.time()


def get_client(api_key: str | None = None, **kwargs) -> CDGClient:
    key = api_key or CONGRESS_API_KEY
    return CDGClient(api_key=key, **kwargs)


def resolve_runtime_params_from_record(
    client_obj: CDGClient, spec: EndpointSpec, record: object
) -> dict[str, object]:
    """Module-level helper to derive runtime params from a record.

    Calls the instance method if present; otherwise falls back to the
    same resolution logic so callers can import this function directly.
    """
    if hasattr(client_obj, "resolve_runtime_params_from_record"):
        return client_obj.resolve_runtime_params_from_record(spec, record)

    # Fallback implementation (mirrors the instance method)
    params: dict[str, object] = {}
    if isinstance(record, BaseModel):
        mapping = record.model_dump()
    elif isinstance(record, dict):
        mapping = record
    else:
        try:
            mapping = vars(record)
        except Exception:
            mapping = {}

    for p in getattr(spec, "param_specs", []) or []:
        if p.location == p.location.PATH or p.location == p.location.QUERY:
            value = None
            if getattr(p, "source_field", None) and p.source_field in mapping:
                value = mapping.get(p.source_field)
            if value is None and getattr(p, "extract_from_url_segment", None):
                url = mapping.get("url")
                if url is not None:
                    url_str = str(url)
                    if f"/{p.extract_from_url_segment}/" in url_str:
                        tail = url_str.split(f"/{p.extract_from_url_segment}/")[-1]
                        value = tail.split("?")[0]
            if value is not None:
                # Map law type strings like 'Public Law' -> 'pub'
                if p.name == "lawType" and isinstance(value, str):
                    low = value.strip().lower()
                    if "public" in low:
                        value = "pub"
                    elif "private" in low:
                        value = "priv"
                # Normalize law number: strip optional congress prefix like '119-44' -> '44'
                if p.name == "lawNumber" and isinstance(value, str) and "-" in value:
                    value = value.split("-", 1)[-1]
                # Normalize path parameter strings to lowercase so API slugs match
                if isinstance(value, str) and p.location == p.location.PATH:
                    value = value.lower()
                params[p.name] = value
    return params
