import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock

import httpx
import pytest
from fastapi.openapi.models import OpenAPI

from cdm.backend.app import app
from cdm.backend.dependencies import (
    get_neighborhood_service,
    get_state_service,
    get_topic_service,
)
from cdm.backend.services.neighborhood_service import NeighborhoodService
from cdm.backend.services.state_service import StateService
from cdm.backend.services.topic_service import TopicService
from cdm.contracts.analysis import AnalysisState, AnalysisStatus
from cdm.contracts.api import NeighborhoodResponse, TopicsResponse, TopicSummary
from scripts.export_openapi import OpenAPIExporter


def test_cold_exports_are_deterministic_without_network_database_or_worker() -> None:
    command = """
import runpy
from unittest.mock import patch
with (
    patch("socket.socket.connect", side_effect=AssertionError("network forbidden")),
    patch("socket.create_connection", side_effect=AssertionError("network forbidden")),
    patch("sqlite3.connect", side_effect=AssertionError("database forbidden")),
    patch("sqlalchemy.create_engine", side_effect=AssertionError("engine forbidden")),
):
    runpy.run_module("scripts.export_openapi", run_name="__main__")
"""
    root = Path(__file__).resolve().parents[2]
    exports = [
        subprocess.run(
            [sys.executable, "-c", command],
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
            timeout=90,
        ).stdout
        for _ in range(2)
    ]
    assert exports[0] == exports[1]
    assert OpenAPI.model_validate_json(exports[0]).openapi == "3.1.0"
    assert exports[0] == OpenAPIExporter(app).render()


@pytest.mark.asyncio
async def test_response_schema_matches_present_defaults_nullability_and_wire_shapes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    topics = Mock(spec=TopicService)
    topics.list_topics.return_value = TopicsResponse(
        topics=[TopicSummary(topic_id=1, name="topic", label="Topic", size=2)],
        analysis=AnalysisStatus(state=AnalysisState.UNKNOWN),
    )
    states = Mock(spec=StateService)
    districts = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "id": "CA-1",
                "properties": {"state": "CA", "district": 1},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[0.0, 0.0], [1.0, 1.0], [0.0, 0.0]]],
                },
            }
        ],
    }
    states.get_districts.return_value = districts
    monkeypatch.setitem(app.dependency_overrides, get_topic_service, lambda: topics)
    monkeypatch.setitem(app.dependency_overrides, get_state_service, lambda: states)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://fixture"
    ) as client:
        response = await client.get("/api/v1/topics")
        health = await client.get("/health")
        boundary = await client.get("/api/v1/states/CA/districts")
    assert response.status_code == health.status_code == boundary.status_code == 200
    assert health.json() == {"status": "ok"}
    assert boundary.json() == districts
    assert response.json() == {
        "analysis": {
            "state": "unknown",
            "source_model_version": None,
            "published_model_version": None,
        },
        "topics": [
            {
                "topic_id": 1,
                "name": "topic",
                "label": "Topic",
                "size": 2,
                "top_words": [],
                "metasubject_id": None,
                "label_source": "unknown",
                "fallback_reason": None,
            }
        ],
        "model_version": None,
        "trained_at": None,
    }
    schema = json.loads(OpenAPIExporter(app).render())["components"]["schemas"]
    assert set(schema["TopicsResponse"]["required"]) == {
        "topics",
        "model_version",
        "trained_at",
        "analysis",
    }
    assert schema["TopicsResponse"]["properties"]["model_version"]["anyOf"] == [
        {"type": "string"},
        {"type": "null"},
    ]
    assert "top_words" in schema["TopicSummary"]["required"]
    for kind in ("TopicSummary", "MetasubjectSummary", "Perspective"):
        assert {"label_source", "fallback_reason"} <= set(schema[kind]["required"])
    assert "party_terms" in schema["TopicPerspectives"]["required"]
    assert schema["BillSummary"]["properties"]["number"]["anyOf"] == [
        {"type": "string"},
        {"type": "null"},
    ]
    assert set(TopicsResponse.model_json_schema(mode="validation")["required"]) == {
        "topics",
        "analysis",
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("query", "status"),
    [
        ("member=A&chamber=house&congress=119&limit=50", 200),
        ("member=A", 200),
        ("member=A&chamber=House", 422),
        ("member=A&congress=0", 422),
        ("member=A&limit=51", 422),
        ("member=A&party=invalid", 422),
    ],
)
async def test_generated_query_enums_and_bounds_match_backend_validation(
    monkeypatch: pytest.MonkeyPatch, query: str, status: int
) -> None:
    service = Mock(spec=NeighborhoodService)
    service.neighborhood.return_value = NeighborhoodResponse(seeds=["A"], analysis={})
    monkeypatch.setitem(
        app.dependency_overrides, get_neighborhood_service, lambda: service
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://fixture"
    ) as client:
        response = await client.get(f"/api/v1/graph/neighborhood?{query}")
    assert response.status_code == status
    if status == 200:
        service.neighborhood.assert_called_once()
        request = service.neighborhood.call_args.args[0]
        assert request.congress == (119 if "congress=119" in query else None)
    else:
        service.neighborhood.assert_not_called()
