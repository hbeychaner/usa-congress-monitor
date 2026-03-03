"""ID helpers for knowledgebase documents."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse


def _api_path_from_url(url: str) -> list[str]:
    """Extract the API path segments following /v3/ from a URL."""
    if not url:
        return []
    parsed = urlparse(url)
    path = parsed.path.strip("/")
    if not path:
        return []
    parts = [part for part in path.split("/") if part]
    if "v3" in parts:
        parts = parts[parts.index("v3") + 1 :]
    return parts


def _id_from_url(record: dict[str, Any]) -> str:
    """Build an id from the record's API URL when available."""
    url = str(record.get("url", ""))
    parts = _api_path_from_url(url)
    if not parts:
        return ""
    return "-".join(parts)


def _set_if(record: dict[str, Any], key: str, value: str | None) -> None:
    """Set a value on the record if it is non-empty."""
    if value:
        record[key] = value


def _set_record_type(record: dict[str, Any], record_type: str) -> None:
    """Set the recordType on the record."""
    record["recordType"] = record_type


def bill_id(record: dict[str, Any]) -> str:
    """Build a stable bill document id."""
    _set_record_type(record, "congress-bills")
    api_id = _id_from_url(record)
    congress = record.get("congress")
    bill_type = str(record.get("type", "")).lower()
    number = record.get("number")
    param_id = f"bill-{congress}-{bill_type}-{number}"
    _set_if(record, "api_id", api_id)
    _set_if(record, "param_id", param_id)
    return api_id or param_id


def member_id(record: dict[str, Any]) -> str:
    """Build a stable member document id."""
    _set_record_type(record, "congress-members")
    api_id = _id_from_url(record)
    param_id = str(record.get("bioguideId") or record.get("bioguide_id") or "")
    _set_if(record, "api_id", api_id)
    _set_if(record, "param_id", param_id)
    return api_id or param_id


def amendment_id(record: dict[str, Any]) -> str:
    """Build a stable amendment document id."""
    _set_record_type(record, "congress-amendments")
    api_id = _id_from_url(record)
    congress = record.get("congress")
    amendment_type = str(record.get("type", "")).lower()
    number = record.get("number")
    param_id = f"amendment-{congress}-{amendment_type}-{number}"
    _set_if(record, "api_id", api_id)
    _set_if(record, "param_id", param_id)
    return api_id or param_id


def committee_id(record: dict[str, Any]) -> str:
    """Build a stable committee document id."""
    _set_record_type(record, "congress-committees")
    api_id = _id_from_url(record)
    param_id = str(record.get("systemCode") or "")
    _set_if(record, "api_id", api_id)
    _set_if(record, "param_id", param_id)
    return api_id or param_id


def committee_meeting_id(record: dict[str, Any]) -> str:
    """Build a stable committee meeting document id."""
    _set_record_type(record, "congress-committee-meetings")
    api_id = _id_from_url(record)
    congress = record.get("congress")
    chamber = str(record.get("chamber", "")).lower()
    event_id = record.get("eventId")
    param_id = f"committee-meeting-{congress}-{chamber}-{event_id}"
    _set_if(record, "api_id", api_id)
    _set_if(record, "param_id", param_id)
    return api_id or param_id


def committee_print_id(record: dict[str, Any]) -> str:
    """Build a stable committee print document id."""
    _set_record_type(record, "congress-committee-prints")
    api_id = _id_from_url(record)
    congress = record.get("congress")
    chamber = str(record.get("chamber", "")).lower()
    jacket_number = record.get("jacketNumber")
    param_id = f"committee-print-{congress}-{chamber}-{jacket_number}"
    _set_if(record, "api_id", api_id)
    _set_if(record, "param_id", param_id)
    return api_id or param_id


def committee_report_id(record: dict[str, Any]) -> str:
    """Build a stable committee report document id."""
    _set_record_type(record, "congress-committee-reports")
    api_id = _id_from_url(record)
    report_id = record.get("cmte_rpt_id")
    if report_id is not None:
        param_id = f"committee-report-{report_id}"
    else:
        congress = record.get("congress")
        report_type = str(record.get("type", "")).lower()
        number = record.get("number")
        part = record.get("part")
        param_id = f"committee-report-{congress}-{report_type}-{number}-{part}"
    citation_id = str(record.get("citation") or "")
    _set_if(record, "api_id", api_id)
    _set_if(record, "param_id", param_id)
    _set_if(record, "citation_id", citation_id)
    return api_id or param_id


def congress_id(record: dict[str, Any]) -> str:
    """Build a stable congress document id."""
    _set_record_type(record, "congress-congresses")
    api_id = _id_from_url(record)
    name = str(record.get("name", "")).split(" ")[0]
    param_id = f"congress-{name}"
    _set_if(record, "api_id", api_id)
    _set_if(record, "param_id", param_id)
    return api_id or param_id


def congressional_record_id(record: dict[str, Any]) -> str:
    """Build a stable congressional record document id."""
    _set_record_type(record, "congress-congressional-records")
    api_id = _id_from_url(record)
    record_id = record.get("Id")
    if record_id is not None:
        param_id = f"congressional-record-{record_id}"
    else:
        congress = record.get("Congress")
        volume = record.get("Volume")
        issue = record.get("Issue")
        param_id = f"congressional-record-{congress}-{volume}-{issue}"
    _set_if(record, "api_id", api_id)
    _set_if(record, "param_id", param_id)
    return api_id or param_id


def daily_congressional_record_id(record: dict[str, Any]) -> str:
    """Build a stable daily congressional record document id."""
    _set_record_type(record, "congress-daily-congressional-records")
    api_id = _id_from_url(record)
    congress = record.get("congress")
    volume = record.get("volumeNumber")
    issue = record.get("issueNumber")
    param_id = f"daily-congressional-record-{congress}-{volume}-{issue}"
    _set_if(record, "api_id", api_id)
    _set_if(record, "param_id", param_id)
    return api_id or param_id


def crs_report_id(record: dict[str, Any]) -> str:
    """Build a stable CRS report document id."""
    _set_record_type(record, "congress-crs-reports")
    api_id = _id_from_url(record)
    param_id = str(record.get("id") or "")
    _set_if(record, "api_id", api_id)
    _set_if(record, "param_id", param_id)
    return api_id or param_id


def hearing_id(record: dict[str, Any]) -> str:
    """Build a stable hearing document id."""
    _set_record_type(record, "congress-hearings")
    api_id = _id_from_url(record)
    congress = record.get("congress")
    chamber = str(record.get("chamber", "")).lower()
    jacket_number = record.get("jacketNumber")
    param_id = f"hearing-{congress}-{chamber}-{jacket_number}"
    citation_id = str(record.get("citation") or "")
    _set_if(record, "api_id", api_id)
    _set_if(record, "param_id", param_id)
    _set_if(record, "citation_id", citation_id)
    return api_id or param_id


def house_communication_id(record: dict[str, Any]) -> str:
    """Build a stable house communication document id."""
    _set_record_type(record, "congress-house-communications")
    api_id = _id_from_url(record)
    congress = record.get("congress")
    comm_type = record.get("communicationType", {}).get("code")
    number = record.get("number")
    param_id = f"house-communication-{congress}-{str(comm_type).lower()}-{number}"
    _set_if(record, "api_id", api_id)
    _set_if(record, "param_id", param_id)
    return api_id or param_id


def house_requirement_id(record: dict[str, Any]) -> str:
    """Build a stable house requirement document id."""
    _set_record_type(record, "congress-house-requirements")
    api_id = _id_from_url(record)
    number = record.get("number")
    param_id = f"house-requirement-{number}"
    _set_if(record, "api_id", api_id)
    _set_if(record, "param_id", param_id)
    return api_id or param_id


def house_vote_id(record: dict[str, Any]) -> str:
    """Build a stable house vote document id."""
    _set_record_type(record, "congress-house-votes")
    api_id = _id_from_url(record)
    identifier = record.get("identifier")
    if identifier is not None:
        param_id = f"house-vote-{identifier}"
    else:
        congress = record.get("congress")
        session = record.get("sessionNumber")
        roll_call = record.get("rollCallNumber")
        param_id = f"house-vote-{congress}-{session}-{roll_call}"
    _set_if(record, "api_id", api_id)
    _set_if(record, "param_id", param_id)
    return api_id or param_id


def law_id(record: dict[str, Any]) -> str:
    """Build a stable law document id."""
    _set_record_type(record, "congress-laws")
    api_id = _id_from_url(record)
    congress = record.get("congress")
    law_type = str(record.get("type", "")).lower()
    number = record.get("number")
    param_id = f"law-{congress}-{law_type}-{number}"
    _set_if(record, "api_id", api_id)
    _set_if(record, "param_id", param_id)
    return api_id or param_id


def nomination_id(record: dict[str, Any]) -> str:
    """Build a stable nomination document id."""
    _set_record_type(record, "congress-nominations")
    citation = record.get("citation")
    citation_id = f"nomination-{citation}" if citation else ""
    api_id = _id_from_url(record)
    congress = record.get("congress")
    number = record.get("number")
    part = record.get("partNumber")
    param_id = f"nomination-{congress}-{number}-{part}"
    _set_if(record, "api_id", api_id)
    _set_if(record, "param_id", param_id)
    _set_if(record, "citation_id", citation_id)
    return api_id or param_id


def senate_communication_id(record: dict[str, Any]) -> str:
    """Build a stable senate communication document id."""
    _set_record_type(record, "congress-senate-communications")
    api_id = _id_from_url(record)
    congress = record.get("congress")
    comm_type = record.get("communicationType", {}).get("code")
    number = record.get("number")
    param_id = f"senate-communication-{congress}-{str(comm_type).lower()}-{number}"
    _set_if(record, "api_id", api_id)
    _set_if(record, "param_id", param_id)
    return api_id or param_id


def summary_id(record: dict[str, Any]) -> str:
    """Build a stable summary document id."""
    _set_record_type(record, "congress-summaries")
    bill = record.get("bill", {})
    bill_url = str(bill.get("url", ""))
    bill_parts = _api_path_from_url(bill_url)
    if bill_parts:
        version = record.get("versionCode")
        api_id = "-".join(["summary", *bill_parts[1:], str(version)])
    else:
        api_id = _id_from_url(record)
    bill = record.get("bill", {})
    congress = bill.get("congress")
    bill_type = str(bill.get("type", "")).lower()
    number = bill.get("number")
    version = record.get("versionCode")
    param_id = f"summary-{congress}-{bill_type}-{number}-{version}"
    _set_if(record, "api_id", api_id)
    _set_if(record, "param_id", param_id)
    return api_id or param_id


def treaty_id(record: dict[str, Any]) -> str:
    """Build a stable treaty document id."""
    _set_record_type(record, "congress-treaties")
    api_id = _id_from_url(record)
    congress_received = record.get("congressReceived")
    number = record.get("number")
    suffix = record.get("suffix") or ""
    param_id = f"treaty-{congress_received}-{number}{suffix}"
    _set_if(record, "api_id", api_id)
    _set_if(record, "param_id", param_id)
    return api_id or param_id


def bound_congressional_record_id(record: dict[str, Any]) -> str:
    """Build a stable bound congressional record document id."""
    _set_record_type(record, "congress-bound-congressional-records")
    api_id = _id_from_url(record)
    congress = record.get("congress")
    volume = record.get("volumeNumber")
    date = record.get("date")
    param_id = f"bound-congressional-record-{congress}-{volume}-{date}"
    _set_if(record, "api_id", api_id)
    _set_if(record, "param_id", param_id)
    return api_id or param_id
