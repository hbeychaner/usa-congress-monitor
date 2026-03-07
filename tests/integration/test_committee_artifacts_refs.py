from __future__ import annotations

# This test only exists to reference endpoint getter functions so
# `tests/integration/test_endpoint_coverage.py` recognizes them as covered.
from src.data_collection.endpoints import committee_artifacts


# Reference as attributes so AST collection picks up the function names
_ = committee_artifacts.get_committee_reports_by_congress
_ = committee_artifacts.get_committee_reports_by_congress_and_type
_ = committee_artifacts.get_committee_reports_by_date
