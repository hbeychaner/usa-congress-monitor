"""Legacy data collection helpers.

Prefer the endpoint modules in src.data_collection.endpoints and shared utilities in
src.data_collection.utils for new code.
"""

import json
import logging
import os
import time
from datetime import datetime
from typing import Any, Callable, Optional, Tuple
from urllib.parse import parse_qs, urlparse

from pydantic import HttpUrl
from requests.exceptions import ChunkedEncodingError
from selenium import webdriver
from tqdm import tqdm
from urllib3.exceptions import ProtocolError

from src.data_collection.client import CDGClient

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

API_VERSION = "v3"
ROOT_URL = "https://api.congress.gov/"
RESPONSE_FORMAT = "json"
RESULT_LIMIT = 100
RATE_LIMIT_CONSTANT = 5000 / 60 / 60  # 5000 requests per hour, divided into seconds


def checkpointed_paginate(
    endpoint_func,
    *args,
    from_date=None,
    to_date=None,
    max_retries=3,
    start_offset=0,
    **kwargs,
):
    """
    Generic checkpointed pagination and batch saving for any endpoint function.
    Filenames are derived from the endpoint function name.
    Args:
        endpoint_func: Function that returns (results, next_offset, total_count).
        *args, **kwargs: Arguments to pass to the endpoint function.
        from_date, to_date: Optional, for endpoint functions that require them.
        max_retries: Number of retries for recoverable errors.
        start_offset: Offset to start from (default 0).
    Returns:
        None (results and progress are saved to disk)
    """
    func_name = endpoint_func.__name__
    checkpoint_file = f"{func_name}_checkpoint.json"
    results_file = f"{func_name}_results.json"
    offset = start_offset
    # Try to load checkpoint if exists
    try:
        with open(checkpoint_file, "r") as f:
            offset = json.load(f)["offset"]
    except FileNotFoundError:
        pass
    # Try to load existing results
    try:
        with open(results_file, "r") as f:
            all_results = json.load(f)
    except FileNotFoundError:
        all_results = []
    while offset != -1:
        for attempt in range(max_retries):
            try:
                # Build call signature
                call_kwargs = dict(kwargs)
                call_kwargs["offset"] = offset
                if from_date is not None:
                    call_kwargs["from_date"] = from_date
                if to_date is not None:
                    call_kwargs["to_date"] = to_date
                results, next_offset, count = endpoint_func(*args, **call_kwargs)
                break
            except (ChunkedEncodingError, ProtocolError) as e:
                print(f"Request failed: {e}. Retrying ({attempt + 1}/{max_retries})...")
                time.sleep(2)
        else:
            print("Max retries exceeded. Stopping pagination.")
            break
        all_results.extend(results)
        with open(results_file, "w") as f:
            json.dump(all_results, f)
        with open(checkpoint_file, "w") as f:
            json.dump({"offset": next_offset}, f)
        offset = next_offset
    print(
        f"Done. Results saved to {results_file}. Progress saved to {checkpoint_file}."
    )


def datetime_convert(date_str: str) -> str:
    """
    Convert a date string to the format YYYY-MM-DDTHH:MM:SSZ from format YYYY-MM-DD.

    Args:
        date_str (str): The date string to convert.

    Returns:
        str: The converted date string in the format YYYY-MM-DDTHH:MM:SSZ.
    """
    # Convert the date string to a datetime object
    date_obj = datetime.strptime(date_str, "%Y-%m-%d")
    # Format the datetime object to the desired format
    formatted_date = date_obj.strftime("%Y-%m-%dT%H:%M:%SZ")
    return formatted_date


def get_bills_metadata(
    client: CDGClient, from_date: str, to_date: str, offset: int = 0
) -> tuple[list[Any], int, int]:
    """Legacy wrapper for date-range bill metadata retrieval."""
    from src.data_collection.endpoints.bill import get_bills_metadata_by_date

    return get_bills_metadata_by_date(client, from_date, to_date, offset)


def get_laws_metadata(
    client: CDGClient, congress: int, offset: int = 0
) -> tuple[list[Any], int, int]:
    """
    Retrieve metadata for laws.

    Args:
        client (CDGClient): The client object.
        congress (int): The congress number.

    Returns:
        list: A list of law metadata.
    """
    params = {
        "limit": RESULT_LIMIT,
    }
    if offset > 0:
        params["offset"] = offset
    response = client.get(f"law/{congress}", params=params)
    if isinstance(response, dict):
        laws = list(response.get("bills", []))  # type: ignore
        pagination = response.get("pagination", {})
        if isinstance(pagination, dict) and "next" in pagination:
            offset = extract_offset(pagination["next"])
            count = int(pagination.get("count", 0))
            return (laws, offset, count)
        return (laws, -1, 0)
    else:
        return ([], -1, 0)


def get_amendments_metadata(
    client: CDGClient,
    from_date: str,
    to_date: str,
    offset: int = 0,
    limit: int = RESULT_LIMIT,
) -> tuple[list[Any], int, int]:
    """
    Retrieve metadata for amendments.

    Args:
        from_date_time (str): The start date for the search in the format "YYYY-MM-DDTHH:MM:SSZ".
        to_date_time (str): The end date for the search in the format "YYYY-MM-DDTHH:MM:SSZ".
        offset (int): The offset for the request.
        limit (int): The number of results to return.

    Returns:
        list: A list of amendment metadata.
    """
    # Convert the date strings to the desired format
    from_date = datetime_convert(from_date)
    to_date = datetime_convert(to_date)
    params = {"limit": limit, "fromDateTime": from_date, "toDateTime": to_date}
    if offset > 0:
        params["offset"] = offset
    response = client.get("amendment", params=params)
    if isinstance(response, dict):
        amendments = list(response.get("amendments", []))  # type: ignore
        pagination = response.get("pagination", {})
        if isinstance(pagination, dict) and "next" in pagination:
            offset = extract_offset(pagination["next"])
            count = int(pagination.get("count", 0))
            return (amendments, offset, count)
        return (amendments, -1, 0)
    else:
        return ([], -1, 0)


def extract_offset(url: str) -> int:
    """Extract the pagination offset from a URL query string."""
    parsed_url = urlparse(url)
    offset = parse_qs(parsed_url.query).get("offset", [0])[0]
    return int(offset)


def get_congress_details(client: CDGClient, congress: int):
    """Retrieve detailed information for a specified congress."""
    return client.get(f"congress/{congress}")


def get_current_congress(client: CDGClient):
    """Retrieve detailed information for the current congress."""
    return client.get("congress/current")


def get_members_list(client: CDGClient):
    """Retrieve a list of congressional members."""
    return client.get("member")


def get_member_details(client: CDGClient, bioguide_id: str):
    """Retrieve detailed information for a specified congressional member."""
    return client.get(f"member/{bioguide_id}")


def get_member_sponsored_legislation(client: CDGClient, bioguide_id: str):
    """Retrieve the list of legislation sponsored by a specified congressional member."""
    return client.get(f"member/{bioguide_id}/sponsored-legislation")


def get_member_cosponsored_legislation(client: CDGClient, bioguide_id: str):
    """Retrieve the list of legislation cosponsored by a specified congressional member."""
    return client.get(f"member/{bioguide_id}/cosponsored-legislation")


def get_members_by_congress(client: CDGClient, congress: int):
    """Retrieve the list of members specified by Congress."""
    return client.get(f"member/congress/{congress}")


def get_members_by_state(client: CDGClient, state_code: str):
    """Retrieve a list of members filtered by state."""
    return client.get(f"member/{state_code}")


def get_members_by_state_and_district(
    client: CDGClient, state_code: str, district: int
):
    """Retrieve a list of members filtered by state and district."""
    return client.get(f"member/{state_code}/{district}")


def get_members_by_congress_state_and_district(
    client: CDGClient, congress: int, state_code: str, district: int
):
    """Retrieve a list of members filtered by congress, state, and district."""
    return client.get(f"member/congress/{congress}/{state_code}/{district}")


def get_committees(client: CDGClient):
    """Retrieve a list of congressional committees."""
    return client.get("committee")


def get_committees_by_chamber(client: CDGClient, chamber: str):
    """Retrieve a list of congressional committees filtered by the specified chamber."""
    return client.get(f"committee/{chamber}")


def get_committees_by_congress(client: CDGClient, congress: int):
    """Retrieve a list of congressional committees filtered by the specified congress."""
    return client.get(f"committee/{congress}")


def get_committees_by_congress_and_chamber(
    client: CDGClient, congress: int, chamber: str
):
    """Retrieve a list of committees filtered by the specified congress and chamber."""
    return client.get(f"committee/{congress}/{chamber}")


def get_committee_by_chamber_and_code(
    client: CDGClient, chamber: str, committee_code: str
):
    """Retrieve detailed information for a specified congressional committee."""
    return client.get(f"committee/{chamber}/{committee_code}")


def get_committee_bills(client: CDGClient, chamber: str, committee_code: str):
    """Retrieve the list of legislation associated with the specified congressional committee."""
    return client.get(f"committee/{chamber}/{committee_code}/bills")


def get_committee_reports_by_chamber_and_code(
    client: CDGClient, chamber: str, committee_code: str
):
    """Retrieve the list of committee reports associated with a specified congressional committee."""
    return client.get(f"committee/{chamber}/{committee_code}/reports")


def get_committee_nominations(client: CDGClient, chamber: str, committee_code: str):
    """Retrieve the list of nominations associated with a specified congressional committee."""
    return client.get(f"committee/{chamber}/{committee_code}/nominations")


def get_committee_house_communications(
    client: CDGClient, chamber: str, committee_code: str
):
    """Retrieve the list of House communications associated with a specified congressional committee."""
    return client.get(f"committee/{chamber}/{committee_code}/house-communication")


def get_committee_senate_communications(
    client: CDGClient, chamber: str, committee_code: str
):
    """Retrieve the list of Senate communications associated with a specified congressional committee."""
    return client.get(f"committee/{chamber}/{committee_code}/senate-communication")


def get_committee_reports(client: CDGClient):
    """Retrieve a list of committee reports."""
    return client.get("committee-report")


def get_committee_reports_by_congress(client: CDGClient, congress: int):
    """Retrieve a list of committee reports filtered by the specified congress."""
    return client.get(f"committee-report/{congress}")


def get_committee_reports_by_congress_and_type(
    client: CDGClient, congress: int, report_type: str
):
    """Retrieve a list of committee reports filtered by the specified congress and report type."""
    return client.get(f"committee-report/{congress}/{report_type}")


def get_committee_report_details(
    client: CDGClient, congress: int, report_type: str, report_number: int
):
    """Retrieve detailed information for a specified committee report."""
    return client.get(f"committee-report/{congress}/{report_type}/{report_number}")


def get_committee_report_text(
    client: CDGClient, congress: int, report_type: str, report_number: int
):
    """Retrieve the list of texts for a specified committee report."""
    return client.get(f"committee-report/{congress}/{report_type}/{report_number}/text")


def get_committee_prints(client: CDGClient):
    """Retrieve a list of committee prints."""
    return client.get("committee-print")


def get_committee_prints_by_congress(client: CDGClient, congress: int):
    """Retrieve a list of committee prints filtered by the specified congress."""
    return client.get(f"committee-print/{congress}")


def get_committee_prints_by_congress_and_chamber(
    client: CDGClient, congress: int, chamber: str
):
    """Retrieve a list of committee prints filtered by the specified congress and chamber."""
    return client.get(f"committee-print/{congress}/{chamber}")


def get_committee_print_details(
    client: CDGClient, congress: int, chamber: str, jacket_number: str
):
    """Retrieve detailed information for a specified committee print."""
    return client.get(f"committee-print/{congress}/{chamber}/{jacket_number}")


def get_committee_print_text(
    client: CDGClient, congress: int, chamber: str, jacket_number: str
):
    """Retrieve the list of texts for a specified committee print."""
    return client.get(f"committee-print/{congress}/{chamber}/{jacket_number}/text")


def get_committee_meetings(client: CDGClient):
    """Retrieve a list of committee meetings."""
    return client.get("committee-meeting")


def get_committee_meetings_by_congress(client: CDGClient, congress: int):
    """Retrieve a list of committee meetings filtered by the specified congress."""
    return client.get(f"committee-meeting/{congress}")


def get_committee_meetings_by_congress_and_chamber(
    client: CDGClient, congress: int, chamber: str
):
    """Retrieve a list of committee meetings filtered by the specified congress and chamber."""
    return client.get(f"committee-meeting/{congress}/{chamber}")


def get_committee_meeting_details(
    client: CDGClient, congress: int, chamber: str, event_id: str
):
    """Retrieve detailed information for a specified committee meeting."""
    return client.get(f"committee-meeting/{congress}/{chamber}/{event_id}")


def get_hearings(client: CDGClient):
    """Retrieve a list of hearings."""
    return client.get("hearing")


def get_hearings_by_congress(client: CDGClient, congress: int):
    """Retrieve a list of hearings filtered by the specified congress."""
    return client.get(f"hearing/{congress}")


def get_hearings_by_congress_and_chamber(
    client: CDGClient, congress: int, chamber: str
):
    """Retrieve a list of hearings filtered by the specified congress and chamber."""
    return client.get(f"hearing/{congress}/{chamber}")


def get_hearing_details(
    client: CDGClient, congress: int, chamber: str, jacket_number: str
):
    """Retrieve detailed information for a specified hearing."""
    return client.get(f"hearing/{congress}/{chamber}/{jacket_number}")


def get_congressional_records(client: CDGClient, offset: int = 0):
    """Retrieve a list of congressional record issues sorted by most recent.

    Args:
        offset (int): The offset for the request.

    Returns:
        tuple: A tuple containing the list of records, the offset, and the count.
    """
    params = {"limit": RESULT_LIMIT}
    if offset > 0:
        params["offset"] = offset
    response = client.get("congressional-record", params=params)
    records = response.get("Results", {}).get("Issues", [])
    total_results = response.get("Results", {}).get("TotalCount")
    current_offset = response.get("Results", {}).get("IndexStart")
    new_offset = current_offset + len(response.get("Results", {}).get("Issues", []))
    if new_offset >= total_results:
        new_offset = -1
    return (records, new_offset, total_results)


def get_daily_congressional_records(client: CDGClient):
    """Retrieve a list of daily congressional record issues sorted by most recent."""
    return client.get("daily-congressional-record")


def get_daily_congressional_records_by_volume(client: CDGClient, volume_number: int):
    """Retrieve a list of daily Congressional Records filtered by the specified volume number."""
    return client.get(f"daily-congressional-record/{volume_number}")


def get_daily_congressional_records_by_volume_and_issue(
    client: CDGClient, volume_number: int, issue_number: int
):
    """Retrieve a list of daily Congressional Records filtered by the specified volume number and specified issue number."""
    return client.get(f"daily-congressional-record/{volume_number}/{issue_number}")


def get_daily_congressional_record_articles(
    client: CDGClient, volume_number: int, issue_number: int
):
    """Retrieve a list of daily Congressional Record articles filtered by the specified volume number and specified issue number."""
    return client.get(
        f"daily-congressional-record/{volume_number}/{issue_number}/articles"
    )


def get_bound_congressional_records(client: CDGClient):
    """Retrieve a list of bound Congressional Records sorted by most recent."""
    return client.get("bound-congressional-record")


def get_bound_congressional_records_by_year(client: CDGClient, year: int):
    """Retrieve a list of bound Congressional Records filtered by the specified year."""
    return client.get(f"bound-congressional-record/{year}")


def get_bound_congressional_records_by_year_and_month(
    client: CDGClient, year: int, month: int
):
    """Retrieve a list of bound Congressional Records filtered by the specified year and specified month."""
    return client.get(f"bound-congressional-record/{year}/{month}")


def get_bound_congressional_records_by_year_month_and_day(
    client: CDGClient, year: int, month: int, day: int
):
    """Retrieve a list of bound Congressional Records filtered by the specified year, specified month, and specified day."""
    return client.get(f"bound-congressional-record/{year}/{month}/{day}")


def get_house_communications(client: CDGClient):
    """Retrieve a list of House communications."""
    return client.get("house-communication")


def get_house_communications_by_congress(client: CDGClient, congress: int):
    """Retrieve a list of House communications filtered by the specified congress."""
    return client.get(f"house-communication/{congress}")


def get_house_communications_by_congress_and_type(
    client: CDGClient, congress: int, communication_type: str
):
    """Retrieve a list of House communications filtered by the specified congress and communication type."""
    return client.get(f"house-communication/{congress}/{communication_type}")


def get_house_communication_details(
    client: CDGClient, congress: int, communication_type: str, communication_number: int
):
    """Retrieve detailed information for a specified House communication."""
    return client.get(
        f"house-communication/{congress}/{communication_type}/{communication_number}"
    )


def get_house_requirements(client: CDGClient):
    """Retrieve a list of House requirements."""
    return client.get("house-requirement")


def get_house_requirement_details(client: CDGClient, requirement_number: int):
    """Retrieve detailed information for a specified House requirement."""
    return client.get(f"house-requirement/{requirement_number}")


def get_matching_communications_for_house_requirement(
    client: CDGClient, requirement_number: int
):
    """Retrieve a list of matching communications to a House requirement."""
    return client.get(f"house-requirement/{requirement_number}/matching-communications")


def get_senate_communications(client: CDGClient):
    """Retrieve a list of Senate communications."""
    return client.get("senate-communication")


def get_senate_communications_by_congress(client: CDGClient, congress: int):
    """Retrieve a list of Senate communications filtered by the specified congress."""
    return client.get(f"senate-communication/{congress}")


def get_senate_communications_by_congress_and_type(
    client: CDGClient, congress: int, communication_type: str
):
    """Retrieve a list of Senate communications filtered by the specified congress and communication type."""
    return client.get(f"senate-communication/{congress}/{communication_type}")


def get_senate_communication_details(
    client: CDGClient, congress: int, communication_type: str, communication_number: int
):
    """Retrieve detailed information for a specified Senate communication."""
    return client.get(
        f"senate-communication/{congress}/{communication_type}/{communication_number}"
    )


def get_nominations(client: CDGClient):
    """Retrieve a list of nominations sorted by date received from the President."""
    return client.get("nomination")


def get_nominations_by_congress(client: CDGClient, congress: int):
    """Retrieve a list of nominations filtered by the specified congress and sorted by date received from the President."""
    return client.get(f"nomination/{congress}")


def get_nomination_details(client: CDGClient, congress: int, nomination_number: int):
    """Retrieve detailed information for a specified nomination."""
    return client.get(f"nomination/{congress}/{nomination_number}")


def get_nominees_for_nomination(
    client: CDGClient, congress: int, nomination_number: int, ordinal: int
):
    """Retrieve the list of nominees for a position within the nomination."""
    return client.get(f"nomination/{congress}/{nomination_number}/{ordinal}")


def get_nomination_actions(client: CDGClient, congress: int, nomination_number: int):
    """Retrieve the list of actions on a specified nomination."""
    return client.get(f"nomination/{congress}/{nomination_number}/actions")


def get_nomination_committees(client: CDGClient, congress: int, nomination_number: int):
    """Retrieve the list of committees associated with a specified nomination."""
    return client.get(f"nomination/{congress}/{nomination_number}/committees")


def get_nomination_hearings(client: CDGClient, congress: int, nomination_number: int):
    """Retrieve the list of printed hearings associated with a specified nomination."""
    return client.get(f"nomination/{congress}/{nomination_number}/hearings")


def get_crs_reports(client: CDGClient):
    """Retrieve Congressional Research Service (CRS) report data from the API."""
    return client.get("crsreport")


def get_crs_report_details(client: CDGClient, report_number: str):
    """Retrieve detailed information for a specified Congressional Research Service (CRS) report."""
    return client.get(f"crsreport/{report_number}")


def get_treaties(client: CDGClient):
    """Retrieve a list of treaties sorted by date of last update."""
    return client.get("treaty")


def get_treaties_by_congress(client: CDGClient, congress: int):
    """Retrieve a list of treaties for the specified congress, sorted by date of last update."""
    return client.get(f"treaty/{congress}")


def get_treaty_details(client: CDGClient, congress: int, treaty_number: int):
    """Retrieve detailed information for a specified treaty."""
    return client.get(f"treaty/{congress}/{treaty_number}")


def get_partitioned_treaty_details(
    client: CDGClient, congress: int, treaty_number: int, treaty_suffix: str
):
    """Retrieve detailed information for a specified partitioned treaty."""
    return client.get(f"treaty/{congress}/{treaty_number}/{treaty_suffix}")


def get_treaty_actions(client: CDGClient, congress: int, treaty_number: int):
    """Retrieve the list of actions on a specified treaty."""
    return client.get(f"treaty/{congress}/{treaty_number}/actions")


def get_partitioned_treaty_actions(
    client: CDGClient, congress: int, treaty_number: int, treaty_suffix: str
):
    """Retrieve the list of actions on a specified partitioned treaty."""
    return client.get(f"treaty/{congress}/{treaty_number}/{treaty_suffix}/actions")


def get_treaty_committees(client: CDGClient, congress: int, treaty_number: int):
    """Retrieve the list of committees associated with a specified treaty."""
    return client.get(f"treaty/{congress}/{treaty_number}/committees")


def determine_pagination_wait(start_time: float, offset: int):
    """
    Determine the wait time based on the rate limit constant.

    Args:
        start_time (float): The start time of the request.
        offset (int): The offset for the request.

    Returns:
        None
    """
    current_time = time.time()
    elapsed_time = current_time - start_time
    print(f"Elapsed time: {elapsed_time}")
    requests = max(RESULT_LIMIT, offset) / RESULT_LIMIT
    rate = elapsed_time / requests
    if rate < RATE_LIMIT_CONSTANT:
        wait_time = RATE_LIMIT_CONSTANT - rate
        print(f"Sleeping for {wait_time} seconds.")
        time.sleep(wait_time)


def resolve_pagination_wait(page_size: int, wait: Optional[float] = None) -> float:
    """
    Resolve the delay between paginated requests.

    Args:
        page_size (int): Number of items per page.
        wait (float | None): Override delay in seconds (if provided).

    Returns:
        float: The delay to use between requests.
    """
    if wait is not None:
        return wait
    # Default delay; can be tuned based on page size if needed.
    return 0.5


def determine_simple_wait(start_time: float, api_call_count: int):
    """
    Determine the wait time based on the rate limit constant.

    Args:
        start_time (float): The start time of the request.
        api_call_count (int): The number of API calls made.
    """
    current_time = time.time()
    elapsed_time = current_time - start_time
    rate = elapsed_time / api_call_count
    if rate < RATE_LIMIT_CONSTANT:
        wait_time = RATE_LIMIT_CONSTANT - rate
        print(f"Sleeping for {wait_time} seconds.")
        time.sleep(wait_time)


def gather_paginated_metadata(
    fetch_page: Callable[[int, int], dict],
    data_key: str,
    desc: str,
    unit: str,
    page_size: int = 250,
    wait: Optional[float] = None,
) -> list:
    """
    Generic pagination helper for endpoints that return a list under a data key.

    Args:
        fetch_page: Callable that accepts (offset, pageSize) and returns a response dict.
        data_key: Key in the response that contains the list of records.
        desc: Progress bar description.
        unit: Progress bar unit label.
        page_size: Number of items per page.
        wait: Seconds to wait between requests (default: auto).

    Returns:
        list: Aggregated list of records across all pages.
    """
    offset = 0
    all_records = []
    wait_val = resolve_pagination_wait(page_size, wait)
    pbar = tqdm(desc=desc, unit=unit)
    while True:
        response = fetch_page(offset, page_size)
        records = response.get(str(data_key), [])
        if not records:
            break
        all_records.extend(records)
        pbar.update(len(records))
        new_offset = extract_offset(response)
        if new_offset is None or new_offset == offset:
            break
        offset = new_offset
        time.sleep(wait_val)
    pbar.close()
    return all_records


def gather_single_page_metadata(
    fetch_page: Callable[[], dict],
    data_key: str,
) -> list:
    """
    Generic helper for endpoints that return all results in a single response.

    Args:
        fetch_page: Callable that returns a response dict.
        data_key: Key in the response that contains the list of records.

    Returns:
        list: The list of records from the response.
    """
    response = fetch_page()
    return response.get(str(data_key), [])


def gather_data(
    endpoint_func: Callable[..., Tuple[list, int, int]],
    *args,
    **kwargs
) -> list:
    """
    Generic data gathering function for paginated endpoints.
    Args:
        endpoint_func: Function that returns (results, next_offset, total_count).
        *args, **kwargs: Arguments to pass to the endpoint function.
    Returns:
        list: All results gathered from the endpoint.
    """
    start = time.time()
    all_results = []
    offset = kwargs.pop('offset', 0)
    total_count = None
    pbar = None
    while offset != -1:
        results, next_offset, count = endpoint_func(*args, offset=offset, **kwargs)
        all_results.extend(results)
        if total_count is None:
            total_count = count
            if total_count:
                pbar = tqdm(total=total_count)
        if pbar:
            pbar.update(len(results))
        determine_pagination_wait(start, offset)
        offset = next_offset
    if pbar:
        pbar.close()
    return all_results


# Paginated endpoint example
def gather_congress_bills(client: CDGClient, from_date: str, to_date: str) -> list:
    """
    Gather all bills for a given date range (paginated).
    """
    from_date = datetime_convert(from_date)
    to_date = datetime_convert(to_date)
    return gather_data(client.get_bills_metadata, from_date, to_date)


# Endpoints without pagination (call once)
def gather_bound_congressional_records(client: CDGClient) -> list:
    """
    Gather all bound congressional records. (No pagination supported)
    """
    return get_bound_congressional_records(client)


def gather_committees(client: CDGClient) -> list:
    """
    Gather all congressional committees. (No pagination supported)
    """
    return get_committees(client)


def gather_committee_meetings(client: CDGClient) -> list:
    """
    Gather all committee meetings. (No pagination supported)
    """
    return get_committee_meetings(client)


def gather_committee_prints(client: CDGClient) -> list:
    """
    Gather all committee prints. (No pagination supported)
    """
    return get_committee_prints(client)


def gather_committee_reports(client: CDGClient) -> list:
    """
    Gather all committee reports. (No pagination supported)
    """
    return get_committee_reports(client)


def gather_crs_reports(client: CDGClient) -> list:
    """
    Gather all CRS reports. (No pagination supported)
    """
    return get_crs_reports(client)


def gather_daily_congressional_records(client: CDGClient) -> list:
    """
    Gather all daily congressional records. (No pagination supported)
    """
    return get_daily_congressional_records(client)


def gather_hearings(client: CDGClient) -> list:
    """
    Gather all hearings. (No pagination supported)
    """
    return get_hearings(client)


def gather_house_communications(client: CDGClient) -> list:
    """
    Gather all House communications. (No pagination supported)
    """
    return get_house_communications(client)


def gather_house_requirements(client: CDGClient) -> list:
    """
    Gather all House requirements. (No pagination supported)
    """
    return get_house_requirements(client)


def gather_house_roll_call_votes(client: CDGClient) -> list:
    """
    Gather all House roll call votes. (No pagination supported)
    """
    # No pagination in docs/code
    return []


def gather_members(client: CDGClient) -> list:
    """
    Gather all congressional members. (No pagination supported)
    """
    return get_members_list(client)

def download_pdf(lnk: HttpUrl) -> str:
    """
    Download a PDF from a link using Selenium

    Args:
        lnk (HttpUrl): The link to the PDF

    Returns:
        str: The filename of the downloaded PDF
    """
    options = webdriver.ChromeOptions()
    download_folder = os.path.join(os.getcwd(), "tmp")
    profile = {
        "plugins.plugins_list": [{"enabled": False, "name": "Chrome PDF Viewer"}],
        "download.default_directory": download_folder,
        "download.extensions_to_open": "",
        "plugins.always_open_pdf_externally": True,
    }
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-software-rasterizer")
    options.add_argument("--disable-features=VizDisplayCompositor")
    options.add_experimental_option("prefs", profile)
    driver = webdriver.Chrome(options=options)
    driver.get(str(lnk))

    filename = str(lnk).split("/")[-1]
    print("File: {}".format(filename))
    print("Status: Download Complete.")
    print("Folder: {}".format(download_folder))
    # Save the file
    time.sleep(3)
    driver.close()
    return filename


def gather_congresses(client: CDGClient) -> list:
    congresses = []
    current_congress_id = client.get("congress/current")["congress"]["number"]
    for i in tqdm(range(1, current_congress_id + 1)):
        congresses.append(client.get(f"congress/{i}")["congress"])
    return congresses


def gather_laws(client: CDGClient, congress: int) -> list:
    """
    Gather all laws for a given congress.

    Args:
        client (CDGClient): The client object.
        congress (int): The congress number.

    Returns:
        list: A list of law metadata.
    """
    start = time.time()
    laws = []
    offset = 0
    total_count = None
    pbar = None
    while offset != -1:
        result, offset, count = client.get_laws_metadata(congress, offset)
        laws.extend(result)
        if total_count is None:
            total_count = count
            pbar = tqdm(total=total_count, desc="Retrieving laws")
        if pbar:
            pbar.update(len(result))
        determine_pagination_wait(start, offset)  # Prevent rate limiting
    if pbar:
        pbar.close()
    return laws

# Top-level gather functions missing from previous implementation
def gather_nominations(client: CDGClient) -> list:
    """
    Gather all nominations. (No pagination supported)
    Args:
        client (CDGClient): The client object.
    Returns:
        list: A list of nomination metadata.
    """
    return get_nominations(client)

def gather_senate_communications(client: CDGClient) -> list:
    """
    Gather all Senate communications. (No pagination supported)
    Args:
        client (CDGClient): The client object.
    Returns:
        list: A list of Senate communication metadata.
    """
    return get_senate_communications(client)

def gather_summaries(client: CDGClient) -> list:
    """
    Gather all summaries. (No pagination supported)
    Args:
        client (CDGClient): The client object.
    Returns:
        list: A list of summary metadata.
    """
    # No summaries endpoint implemented
    return []

def gather_treaties(client: CDGClient) -> list:
    """
    Gather all treaties. (No pagination supported)
    Args:
        client (CDGClient): The client object.
    Returns:
        list: A list of treaty metadata.
    """
    return get_treaties(client)