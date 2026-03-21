"""Congress.gov API client and retry-capable session factory.

This module enforces a JSON-only contract and returns strongly-typed
Pydantic model instances from `iterate_pages`. It intentionally avoids
returning mixed types or raw byte fallbacks.
"""

import importlib
import inspect
import threading
import time
from typing import Iterator, Mapping, Union, TypeAlias, cast
from urllib.parse import urljoin

import requests
from pydantic import BaseModel

from settings import CONGRESS_API_KEY, CONGRESS_STRICT_FIELD_CHECK
from src.models.endpoint_spec import EndpointSpec
from src.utils.logger import get_logger

logger = get_logger(__name__)


API_VERSION = "v3"
ROOT_URL = "https://api.congress.gov/"
RESPONSE_FORMAT = "json"

# JSON-like value type used for request/response mappings. This is a
# conservative, recursive alias that avoids `Any` while accurately
# representing permitted JSON structures used throughout the client.
Json: TypeAlias = Union[
    str,
    int,
    float,
    bool,
    None,
    list["Json"],
    Mapping[str, "Json"],
]


# Helper: detect JSON responses
def _is_json_response(response: requests.Response) -> bool:
    """Return True if the HTTP response is a JSON response.

    Args:
        response: requests.Response object to inspect.

    Returns:
        bool: True when the Content-Type header indicates JSON.
    """
    ct = response.headers.get("content-type", "")
    return ct.lower().startswith("application/json")


def _to_int(value: object, default: int) -> int:
    """Convert a value to int with a safe default.

    Args:
        value: value to coerce to int (may be None or non-int).
        default: fallback integer if conversion fails or value is None.

    Returns:
        int: converted integer or the provided default.
    """
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
        """Initialize the CDGClient.

        Args:
            api_key: API key for Congress.gov.
            api_version: API version token (e.g. 'v3').
            response_format: desired response format (default 'json').
            raise_on_error: if True, attach a response hook to raise on HTTP errors.
            added_headers: additional headers to include on the session.
        """
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
        """Return the underlying :class:`requests.Session` used by the client."""
        return self._session

    def get_json(
        self, endpoint: str, params: Mapping[str, Json] | None = None, timeout: int = 10
    ) -> Mapping[str, Json]:
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
        self, spec: EndpointSpec, runtime_params: dict[str, Json], timeout: int = 10
    ) -> Mapping[str, Json]:
        """Render path + query for `spec`, perform request, return JSON object mapping.

        Raises ValueError for non-JSON responses or unexpected JSON shapes.
        """
        spec.validate_params(runtime_params)
        url = spec.render_path(self.base_url, runtime_params)
        query = spec.build_query(runtime_params)

        self._rate_limited()
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
        params: Mapping[str, Json] | None = None,
        timeout: int = 10,
        *,
        base_delay: float = 0.5,
        max_delay: float = 10.0,
        max_attempts: int = 5,
    ) -> requests.Response:
        """Perform GET with exponential backoff. Raises RuntimeError if
        cumulative backoff exceeds `self._max_total_retry_wait`.
        """
        """Perform a GET using an internal session with exponential backoff.

        Raises:
            RuntimeError: if cumulative backoff exceeds configured threshold.

        Returns:
            requests.Response: the successful HTTP response.
        """
        attempts = 0
        cumulative_sleep = 0.0
        while True:
            try:
                req_params = {k: str(v) for k, v in (params or {}).items()}
                resp = self._session.get(url, params=req_params, timeout=timeout)
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
        self, spec: EndpointSpec, base_params: Mapping[str, Json] | None = None
    ) -> Iterator[tuple[list[BaseModel], Mapping[str, Json], Mapping[str, Json]]]:
        """Yield lists of `BaseModel` instances coerced from responses.

        `spec.response_model` must be present and resolve to a Pydantic model
        class; otherwise this method raises `ValueError` to keep the API
        strongly typed.
        """
        params: dict[str, Json] = dict(base_params or {})
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
        self, spec: EndpointSpec, params: Mapping[str, Json] | None = None
    ) -> list[BaseModel]:
        """Convenience: fetch a single-shot list endpoint and return coerced models.

        This wraps `request_for_spec` + `_extract_records_from_response` + `coerce_records`.
        """
        resp = self.request_for_spec(spec, dict(params or {}))
        records = self._extract_records_from_response(spec, resp)
        model_cls = self._resolve_response_model(spec)
        return self.coerce_records(model_cls, records)

    def fetch_one(
        self, spec: EndpointSpec, runtime_params: dict[str, Json]
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
        self, spec: EndpointSpec, record: BaseModel | Mapping[str, Json]
    ) -> dict[str, Json]:
        """Given a spec and a list-item (mapping or BaseModel), return runtime params.

        Uses `ParamSpec.source_field` and `ParamSpec.extract_from_url_segment` when
        present on path/query params so calling code doesn't need resource-specific
        parsing logic.
        """
        params: dict[str, Json] = {}
        # accept either mapping or pydantic BaseModel
        if isinstance(record, BaseModel):
            mapping = record.model_dump()
        elif isinstance(record, dict):
            mapping = record
        else:
            try:
                mapping = vars(record)
            except Exception:
                mapping = {}

        def _resolve_source_field(
            mapping: Mapping[str, Json] | list[Json] | None, source_field: str
        ) -> Json | None:
            """Resolve a dotted `source_field` path from a mapping or model dump.

            Supports list-index segments like 'laws.0.type'. Returns `None` when
            the path cannot be resolved.
            """
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
                        return None
                elif isinstance(v, dict):
                    v = v.get(part)
                else:
                    return None
            return v

        for p in getattr(spec, "param_specs", []) or []:
            if p.location == p.location.PATH or p.location == p.location.QUERY:
                value: Json | None = None
                if getattr(p, "source_field", None):
                    value = _resolve_source_field(mapping, p.source_field)
                    if value is None and p.source_field in mapping:
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
                    if (
                        p.name == "lawNumber"
                        and isinstance(value, str)
                        and "-" in value
                    ):
                        value = value.split("-", 1)[-1]
                    # Normalize path parameter strings to lowercase so API slugs match,
                    # but preserve original casing for id-like params (e.g., CRS report ids)
                    if isinstance(value, str) and p.location == p.location.PATH:
                        if p.name == "id":
                            # Keep id casing as provided by the source record
                            value = value
                        else:
                            value = value.lower()
                    params[p.name] = value  # type: ignore[assignment]

        return params

    def _resolve_response_model(self, spec: EndpointSpec) -> type[BaseModel]:
        """Resolve and return the Pydantic model class for `spec.response_model`.

        `spec.response_model` may be a direct BaseModel subclass or a
        string in the form ``module.ClassName``. This helper imports the
        module when necessary and validates that the resolved attribute is
        a Pydantic ``BaseModel`` subclass.

        Raises:
            ValueError: when the response model is not set or cannot be
                resolved to a BaseModel subclass.
        """
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
        self,
        model_cls: type[BaseModel],
        records: list[dict[str, Json]],
        spec=None,
    ) -> list[BaseModel]:
        """Coerce mapping records into instances of `model_cls`.

        Raises `ValueError` on validation failure to keep contract explicit.
        """
        coerced: list[BaseModel] = []
        for r in records:
            if not isinstance(r, dict):
                raise ValueError("record is not a mapping")
            # Normalize common shape differences to keep model input stable.
            # Specifically, coerce various `notes` shapes into a list of
            # note dicts: {"notes": [{"text": "..."}, ...]}
            try:
                notes_val = r.get("notes") if isinstance(r, dict) else None
            except Exception:
                notes_val = None
            if notes_val is not None:
                normalized_notes: list[dict[str, Json]] = []
                # If it's already a list, normalize each element
                if isinstance(notes_val, list):
                    for item in notes_val:
                        if isinstance(item, dict) and "text" in item:
                            # if text is a list, split into multiple notes
                            t = item.get("text")
                            if isinstance(t, list):
                                for s in t:
                                    normalized_notes.append({"text": str(s)})
                            else:
                                normalized_notes.append(
                                    {"text": str(t) if t is not None else ""}
                                )
                        elif isinstance(item, str):
                            normalized_notes.append({"text": item})
                        else:
                            # fallback to string coercion of the whole item
                            normalized_notes.append({"text": str(item)})
                elif isinstance(notes_val, dict):
                    # dict shapes like {"text": "..."} or {"text": ["a","b"]}
                    t = notes_val.get("text") if "text" in notes_val else None
                    if isinstance(t, list):
                        for s in t:
                            normalized_notes.append({"text": str(s)})
                    elif t is not None:
                        normalized_notes.append({"text": str(t)})
                    else:
                        # If dict contains other fields, stringify it
                        normalized_notes.append({"text": str(notes_val)})
                else:
                    # single string or other scalar value
                    normalized_notes.append({"text": str(notes_val)})

                # Assign the normalized shape back into the record so model
                # validation sees a consistent list-of-note-dicts shape.
                # Use `cast` to satisfy static type checkers: the normalized
                # structure is JSON-compatible but the recursive `Json` alias
                # confuses some checkers when used directly.
                r["notes"] = cast(Json, normalized_notes)
            try:
                inst = model_cls.model_validate(r)
            except Exception as exc:  # validation error
                logger.exception("failed to validate record against %s", model_cls)
                raise ValueError(f"failed to validate record: {exc}") from exc
            # Allow model instances to provide their own canonical id via
            # a `build_id()` method. If the model exposes `build_id()` and
            # the instance has no truthy `id`, attempt to set it from the
            # model-level builder. Any unexpected errors raised by the
            # builder will propagate so callers can observe and fix them.
            builder = getattr(inst, "build_id", None)
            if callable(builder) and not getattr(inst, "id", None):
                # Call builder(); try common call patterns but do not
                # allow arbitrary builder failures to abort coercion. If
                # the builder cannot produce an id we leave the instance
                # as-is and allow callers to compute a canonical id
                # later (e.g., scripts/ingest.py uses canonical_id()).
                bid = None
                try:
                    bid = builder()
                except TypeError:
                    try:
                        bid = builder(inst)
                    except Exception as exc:
                        logger.debug("builder raised while called with inst: %s", exc)
                        bid = None
                except Exception as exc:
                    logger.debug("builder raised while called without args: %s", exc)
                    bid = None

                if bid:
                    # Use model_copy to produce a new instance with `id`
                    # populated to preserve immutability expectations.
                    try:
                        inst = inst.model_copy(update={"id": str(bid)})
                    except Exception:
                        # If model_copy is unavailable fall back to setattr;
                        # allow exceptions to surface rather than swallowing.
                        setattr(inst, "id", str(bid))

            # Apply spec-driven id/reference strategy if available
            try:
                if spec is not None:
                    from src.data_collection.id_strategy import apply_id_strategy

                    inst = apply_id_strategy(inst, r, spec)
            except Exception:
                # Be conservative: do not fail coercion when strategy fails
                logger.debug("id_strategy application failed for %s", model_cls)

            # Check for unprocessed top-level fields: compare the original
            # record keys against the model's exported keys (using aliases)
            # so we can warn when the API returns fields that are not
            # represented by our Pydantic models. This helps detect
            # accidental data loss during validation/coercion.
            try:
                original_keys = set(r.keys())
                processed_dump = inst.model_dump(by_alias=True)
                processed_keys = set(processed_dump.keys())
                # Common wrapper/aux keys that may legitimately be present
                # in responses but not part of item models.
                ignored_keys = {"value"}
                unprocessed = original_keys - processed_keys - ignored_keys
                if unprocessed:
                    msg = (
                        f"Unprocessed fields for {model_cls.__name__} id={r.get('id')}: "
                        f"{sorted(unprocessed)}"
                    )
                    if CONGRESS_STRICT_FIELD_CHECK:
                        raise ValueError(msg)
                    else:
                        logger.warning(msg)
            except Exception:
                # Keep original behavior if anything goes wrong here.
                logger.debug("field-coverage check failed for %s", model_cls.__name__)

            coerced.append(inst)
        return coerced

    def _extract_records_from_response(
        self, spec: EndpointSpec, resp_json: Mapping[str, Json]
    ) -> list[dict[str, Json]]:
        """Extract a list of record mappings from a response JSON object.

        Handles `unwrap_key`, first-list heuristics, and single-inner-dict envelopes.
        """
        # If the API returned a paginated wrapper (common for sub-endpoints),
        # and the spec does not declare a `data_key` (i.e. it's not a list
        # endpoint), prefer extracting the inner payload when present. Many
        # item endpoints wrap the real payload alongside a `pagination`
        # object; prefer returning that payload (dict or list) so item
        # response models validate correctly. If no inner payload can be
        # found, fall back to returning the entire wrapper (some response
        # models expect the envelope shape).
        if (
            isinstance(resp_json, dict)
            and "pagination" in resp_json
            and not getattr(spec, "data_key", None)
        ):
            for k, v in resp_json.items():
                if k == "pagination":
                    continue
                if isinstance(v, list):
                    return [i if isinstance(i, dict) else {"value": i} for i in v]
                if isinstance(v, dict):
                    return [v]
            return [resp_json]

        # explicit unwrap_key
        key = getattr(spec, "unwrap_key", None)
        if key is not None and key in resp_json:
            inner = resp_json.get(key)
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
        """Enforce client-wide rate limiting between HTTP calls.

        Uses a thread-safe lock and a per-call interval derived from the
        configured rate limit settings. This method blocks the caller when
        the last request occurred more recently than the allowed interval.
        """
        with self._rate_limit_lock:
            now = time.time()
            elapsed = now - self._rate_limit_last_call
            if elapsed < self._rate_limit_interval:
                time.sleep(self._rate_limit_interval - elapsed)
            self._rate_limit_last_call = time.time()


def get_client(api_key: str | None = None, **kwargs) -> CDGClient:
    """Return a configured :class:`CDGClient` instance.

    If ``api_key`` is not provided the module-level ``CONGRESS_API_KEY`` is used.
    Additional keyword arguments are forwarded to the ``CDGClient``
    constructor.
    """
    key = api_key or CONGRESS_API_KEY
    return CDGClient(api_key=key, **kwargs)


def resolve_runtime_params_from_record(
    client_obj: CDGClient, spec: EndpointSpec, record: BaseModel | Mapping[str, Json]
) -> dict[str, Json]:
    """Module-level helper to derive runtime params from a record.

    Calls the instance method if present; otherwise falls back to the
    same resolution logic so callers can import this function directly.
    """
    if hasattr(client_obj, "resolve_runtime_params_from_record"):
        return client_obj.resolve_runtime_params_from_record(spec, record)

    # Fallback implementation (mirrors the instance method)
    params: dict[str, Json] = {}
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
