"""Package exposing organized spec modules.

Importing submodules registers their EndpointSpecs via side-effects.
"""

from . import (
    amendment_specs,
    bill_specs,
    bound_congressional_record_specs,
    committee_report_specs,
    committee_specs,
    communication_specs,
    congress_specs,
    crsreport_specs,
    daily_congressional_record_specs,
    hearing_specs,
    house_requirement_specs,
    house_vote_specs,
    law_specs,
    member_specs,
    nomination_specs,
    treaty_specs,
)
from . import congress_list_specs  # noqa: E402  (must follow the specs it derives from)

__all__ = [
    "amendment_specs",
    "bill_specs",
    "bound_congressional_record_specs",
    "committee_report_specs",
    "committee_specs",
    "communication_specs",
    "congress_specs",
    "crsreport_specs",
    "daily_congressional_record_specs",
    "hearing_specs",
    "house_requirement_specs",
    "house_vote_specs",
    "law_specs",
    "member_specs",
    "nomination_specs",
    "treaty_specs",
]
