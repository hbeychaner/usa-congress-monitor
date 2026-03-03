"""Enumeration of API response keys for Congress.gov collections."""

from enum import StrEnum


class CongressDataType(StrEnum):
    """String enum mapping for list keys in API responses."""
    AMENDMENTS = "amendments"
    BILLS = "bills"
    MEMBERS = "members"
    COMMITTEES = "committees"
    REPORTS = "reports"
    COMMITTEE_REPORTS = "committeeReports"
    COMMITTEE_PRINTS = "committeePrints"
    COMMITTEE_MEETINGS = "committeeMeetings"
    HEARINGS = "hearings"
    HOUSE_COMMUNICATIONS = "houseCommunications"
    HOUSE_REQUIREMENTS = "houseRequirements"
    HOUSE_ROLL_CALL_VOTES = "houseRollCallVotes"
    LAWS = "bills"
    SENATE_COMMUNICATIONS = "senateCommunications"
    NOMINATIONS = "nominations"
    CRS_REPORTS = "CRSReports"
    SUMMARIES = "summaries"
    TREATIES = "treaties"
    BOUND_CONGRESSIONAL_RECORD = "boundCongressionalRecord"
    DAILY_CONGRESSIONAL_RECORD = "dailyCongressionalRecord"
    CONGRESSIONAL_RECORDS = "congressionalRecords"
