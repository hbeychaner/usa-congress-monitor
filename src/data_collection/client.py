"""
CDG Client - An example client for the Congress.gov API.

@copyright: 2022, Library of Congress
@license: CC0 1.0
"""

import logging
from typing import Any
from urllib.parse import urljoin

import requests
from requests import Response

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


API_VERSION = "v3"
ROOT_URL = "https://api.congress.gov/"
RESPONSE_FORMAT = "json"


class _MethodWrapper:
    """Wrap request method to facilitate queries.  Supports requests signature."""

    def __init__(self, parent: "CDGClient", http_method: str) -> None:
        self._parent: CDGClient = parent
        self._method = getattr(parent.session, http_method)

    def __call__(
        self, endpoint: str, *args: Any, **kwargs: Any
    ) -> dict[str, Any] | bytes:
        response = self._method(
            urljoin(self._parent.base_url, endpoint), *args, **kwargs
        )
        if response.headers.get("content-type", "").startswith("application/json"):
            return response.json()
        else:
            return response.content


class CDGClient:
    """A sample client to interface with Congress.gov."""

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

        # do not use url parameters, even if offered, use headers
        self._session.params = {"format": response_format}
        self._session.headers.update({"x-api-key": api_key})
        if added_headers:
            self._session.headers.update(added_headers)

        if raise_on_error:
            self._session.hooks = {
                "response": lambda r, *args, **kwargs: ( # type: ignore
                    r.raise_for_status() if isinstance(r, Response) else None
                )
            }

    @property
    def session(self) -> requests.Session:
        return self._session

    def __getattr__(self, method_name: str) -> Any:
        """Find the session method dynamically and cache for later."""
        method = _MethodWrapper(self, method_name)
        self.__dict__[method_name] = method
        return method
