"""Pytest configuration for project path setup.

This file ensures the project is on `sys.path` and loads a repository `.env`
so tests receive environment variables (like `CONGRESS_API_KEY`) even when
the shell hasn't exported them.
"""

from __future__ import annotations

from dotenv import load_dotenv

# Import shared fixtures (kept at module level for backwards compatibility)
from tests.integration.test_endpoints import client as client  # noqa: E402,F401

load_dotenv()
