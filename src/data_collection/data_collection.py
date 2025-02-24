"""This module includes methods and classes for collecting data from the Congress API."""
import logging 
import os
import requests
from urllib.parse import urlparse
from urllib.parse import parse_qs
import time

from tqdm import tqdm

from src.data_collection.client import RESPONSE_FORMAT, CDGClient
from src.data_structures.bills import Bill, ResultType 

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Set up constants for the module
congress_api_key = os.environ["CONGRESS_API_KEY"]
BASE_URL = os.environ["CONGRESS_API_URL"]
BILL_ENDPOINT = "bill"
RESULT_LIMIT = 250
API_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.10; rv:39.0)',
    'accept': 'application/xml',
    "x-api-key": congress_api_key}
DATE_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
RATE_LIMIT_CONSTANT = 5000 / 60 / 60 # 5000 requests per hour
client = CDGClient(api_key=os.environ["CONGRESS_API_KEY"], response_format=RESPONSE_FORMAT)


def extract_offset(url: str) -> int:
    """
    Extract the offset from a URL.

    Args:
        url (str): The URL to extract the offset from.

    Returns:
        int: The offset value.
    """
    parsed_url = urlparse(url)
    offset = parse_qs(parsed_url.query)['offset'][0]
    if offset:
        offset = int(offset)
        return offset
    return -1


def retrieve_congress_bills(from_date: str, to_date: str, offset: int = 0) -> list[Bill]:
    """
    Retrieve bills from the Congress API within a date range.

    Args:
        from_date (str): The start date for the search in the format "YYYY-MM-DDTHH:MM:SSZ".
        to_date (str): The end date for the search in the format "YYYY-MM-DDTHH:MM:SSZ".
        offset (int): The offset for the search.

    Returns:
        list[Bill]: A list of Bill objects.

    Raises:
        HTTPError: An error occurred while making the request
    """
    params = {
        "api_key": congress_api_key,
        "format": ResultType.JSON,
        "limit": RESULT_LIMIT,
        "fromDateTime": from_date,
        "toDateTime": to_date
    }
    
    if offset > 0:
        params["offset"] = offset

    response = requests.get(BASE_URL + BILL_ENDPOINT, headers=API_HEADERS, params=params)
    
    if response.status_code == 200:
        data = response.json()
        bills = data.get("bills", [])
        try:
            prepared_bills = [Bill.model_validate(bill) for bill in bills]
        except: 
            print(f"Problem with the following metadata: {offset} offset, {from_date} from_date, {to_date} to_date")
            prepared_bills = []
            pass
        # Check if there is a next page
        if "next" in data.get("pagination", {}):
            offset = extract_offset(data["pagination"]["next"])
            return (prepared_bills, data, offset, data["pagination"]["count"])
        return (prepared_bills, data, -1, 0)
    else:
        response.raise_for_status()


def determine_wait(start_time: float, offset: int) -> float:
    """
    Determine the wait time based on the rate limit constant.

    Args:
        start_time (float): The start time of the request.
        offset (int): The offset for the request.
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


def gather_congress_bills(from_date: str, to_date: str) -> list[Bill]:
    """
    Gather all bills from the Congress API within a date range.
    
    Args:
        from_date (str): The start date for the search in the format "YYYY-MM-DDTHH:MM:SSZ".
        to_date (str): The end date for the search in the format "YYYY-MM-DDTHH:MM:SSZ".

    Returns:
        list[Bill]: A list of Bill objects.
    """
    start = time.time()
    bills = []
    responses = []
    offset = 0
    total_count = None
    pbar = None

    while offset != -1:

        result, response, offset, count = retrieve_congress_bills(from_date, to_date, offset)
        bills.extend(result)
        responses.append(response)
        if total_count is None:
            total_count = count
            pbar = tqdm(total=total_count, desc="Retrieving bills")
        pbar.update(len(result))
        determine_wait(start, offset) # Prevent rate limiting
    if pbar:
        pbar.close()
    return bills, responses


def get_additional_data(bill_data: dict) -> dict:
    """
    Get additional data for a bill.

    Args:
        bill_data (dict): The bill data.

    Returns:
        dict: The additional data.
    """
    additional_data = ['actions', 'amendments', 'committees', 'cosponsors', 'relatedbills', 'subjects', 'summaries', 'text', 'titles']
    congress = bill_data["congress"]
    bill_type = bill_data["type"].lower()
    bill_number = bill_data["number"]
    for s in additional_data:
        data = client.get(f"bill/{congress}/{bill_type}/{bill_number}/{s}")
        bill_data[s] = data
    return bill_data
