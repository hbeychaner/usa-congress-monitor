"""Congress.gov API client and retry-capable session factory.

Provides `CDGClient` for authenticated API access and a `create_session_with_retries`
helper that configures robust HTTP retry behavior.
"""

import threading
from typing import Any
from urllib.parse import urljoin
import time

import requests
from requests import Response
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from settings import CONGRESS_API_KEY
from src.utils.logger import get_logger

congress_api_key = CONGRESS_API_KEY

logger = get_logger(__name__)


API_VERSION = "v3"
ROOT_URL = "https://api.congress.gov/"
RESPONSE_FORMAT = "json"


class _MethodWrapper:
    """Wrap a requests method to add base URL resolution and JSON handling."""

    def __init__(self, parent: "CDGClient", http_method: str) -> None:
        self._parent: CDGClient = parent
        self._method = getattr(parent.session, http_method)

    def __call__(
        self, endpoint: str, *args: Any, **kwargs: Any
    ) -> dict[str, Any] | bytes:
        """Invoke the HTTP method and return JSON or raw bytes based on content type."""
        self._parent._rate_limited()
        # Enforce a sensible request timeout to avoid hanging indefinitely during tests
        if "timeout" not in kwargs:
            kwargs["timeout"] = 10
        response = self._method(urljoin(self._parent.base_url, endpoint), *args, **kwargs)
        if response.headers.get("content-type", "").startswith("application/json"):
            return response.json()
        else:
            return response.content


class CDGClient:
    """Client for Congress.gov API requests with optional error raising."""

    def __init__(
        self,
        api_key: str,
        api_version: str = API_VERSION,
        response_format: str = RESPONSE_FORMAT,
        raise_on_error: bool = True,
        added_headers: dict[str, str] | None = None,
    ) -> None:
        """Initialize the client with API key, format, and retry-enabled session."""
        self.base_url = urljoin(ROOT_URL, api_version) + "/"
        self._session = create_session_with_retries()

        # do not use url parameters, even if offered, use headers
        self._session.params = {"format": response_format}
        self._session.headers.update({"x-api-key": api_key})
        if added_headers:
            self._session.headers.update(added_headers)

        if raise_on_error:
            self._session.hooks = {
                "response": lambda r, *args, **kwargs: (  # type: ignore
                    r.raise_for_status() if isinstance(r, Response) else None
                )
            }
        # Rate limiting: 5000 requests per hour = 1 request every 0.72 seconds
        self._rate_limit_lock = threading.Lock()
        self._rate_limit_last_call = 0.0
        self._rate_limit_interval = 3600.0 / 5000.0  # ~0.72 seconds

    @property
    def session(self) -> requests.Session:
        """Return the underlying requests session."""
        return self._session

    def __getattr__(self, method_name: str) -> Any:
        """Find the session method dynamically and cache it for later reuse."""
        method = _MethodWrapper(self, method_name)
        self.__dict__[method_name] = method
        return method

    def _rate_limited(self):
        with self._rate_limit_lock:
            now = time.time()
            elapsed = now - self._rate_limit_last_call
            if elapsed < self._rate_limit_interval:
                time.sleep(self._rate_limit_interval - elapsed)
            self._rate_limit_last_call = time.time()


def create_session_with_retries(
    retries=3, backoff_factor=0.3, status_forcelist=(500, 502, 504)
):
    """Create a requests session configured with retry and backoff behavior."""
    session = requests.Session()
    retry = Retry(
        total=retries,
        read=retries,
        connect=retries,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
        raise_on_status=False,
        allowed_methods=["HEAD", "GET", "OPTIONS"],
        respect_retry_after_header=True,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)

    # Set a User-Agent header
    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"
        }
    )
    return session


client = CDGClient(api_key=congress_api_key)
