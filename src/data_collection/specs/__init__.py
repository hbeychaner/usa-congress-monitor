"""Package exposing organized spec modules.

Importing submodules registers their EndpointSpecs via side-effects.
"""

from . import (
    amendment_specs,
    bill_specs,
    bound_congressional_record_specs,
    committee_report_specs,
    committee_specs,
    congress_specs,
    daily_congressional_record_specs,
    law_specs,
    nomination_specs,
    member_specs,
    crsreport_specs,
    hearing_specs,
    communication_specs,
    house_requirement_specs,
    house_vote_specs,
    treaty_specs,
)

__all__ = [
    "amendment_specs",
    "bill_specs",
    "bound_congressional_record_specs",
    "committee_report_specs",
    "committee_specs",
    "congress_specs",
    "daily_congressional_record_specs",
    "law_specs",
    "nomination_specs",
    "member_specs",
    "crsreport_specs",
    "hearing_specs",
    "communication_specs",
    "house_requirement_specs",
    "house_vote_specs",
    "treaty_specs",
]
