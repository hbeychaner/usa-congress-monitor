"""Export deterministic OpenAPI to stdout without starting the API or services."""

import json

from fastapi import FastAPI

from cdm.backend.app import app


class OpenAPIExporter:
    def __init__(self, application: FastAPI) -> None:
        self._application = application

    def render(self) -> str:
        return json.dumps(self._application.openapi(), sort_keys=True, indent=2) + "\n"


def main() -> None:
    print(OpenAPIExporter(app).render(), end="")


if __name__ == "__main__":
    main()
