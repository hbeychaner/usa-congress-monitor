from urllib.parse import urljoin, urlparse, parse_qs
import requests
import logging
import os
import time
from tqdm import tqdm
from src.data_structures.bills import *

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

API_VERSION = "v3"
ROOT_URL = "https://api.congress.gov/"
RESPONSE_FORMAT = "json"
RESULT_LIMIT = 250
RATE_LIMIT_CONSTANT = 5000 / 60 / 60  # 5000 requests per hour

class _MethodWrapper:
    """ Wrap request method to facilitate queries.  Supports requests signature. """

    def __init__(self, parent, http_method):
        self._parent = parent
        self._method = getattr(parent._session, http_method)

    def __call__(self, endpoint, *args, **kwargs):  # full signature passed here
        response = self._method(
            urljoin(self._parent.base_url, endpoint), *args, **kwargs
        )
        if response.headers.get("content-type", "").startswith("application/json"):
            return response.json()
        else:
            return response.content

class CDGClient:
    """ A sample client to interface with Congress.gov. """

    def __init__(
        self,
        api_key,
        api_version=API_VERSION,
        response_format=RESPONSE_FORMAT,
        raise_on_error=True,
        added_headers=None
    ):
        self.base_url = urljoin(ROOT_URL, api_version) + "/"
        self._session = requests.Session()

        # do not use url parameters, even if offered, use headers
        self._session.params = {"format": response_format}
        self._session.headers.update({"x-api-key": api_key})
        if added_headers:
            self._session.headers.update(added_headers)

        if raise_on_error:
            self._session.hooks = {
                "response": lambda r, *args, **kwargs: r.raise_for_status()
            }

    def __getattr__(self, method_name):
        """Find the session method dynamically and cache for later."""
        method = _MethodWrapper(self, method_name)
        self.__dict__[method_name] = method
        return method

    def get_bills_metadata(self, from_date: str, to_date: str, offset: int = 0):
        params = {
            "limit": RESULT_LIMIT,
            "fromDateTime": from_date,
            "toDateTime": to_date
        }
        
        if offset > 0:
            params["offset"] = offset

        response = self.get("bill", params=params)
        bills = response.get("bills", [])
        if "next" in response.get("pagination", {}):
            offset = self.extract_offset(response["pagination"]["next"])
            return (bills, response, offset, response["pagination"]["count"])
        return (bills, response, -1, 0)
    
    def get_bill_details(self, bill_metadata: BillMetadata) -> Bill:
        """
        Retrieve additional data for a bill.

        Args:
            client (CDGClient): The client object.
            bill_data (BillMetadata): The bill metadata.

        Returns:
            Bill: The bill object.
        """
        bill_data = {}
        # Currently available endpoints for additional data on bills
        additional_bill_data = {
            'actions': 'actions',
            'amendments': 'amendments',
            'committees': 'committees',
            'cosponsors': 'cosponsors',
            'relatedBills': 'relatedbills',
            'subjects': 'subjects',
            'summaries': 'summaries',
            'textVersions': 'text',
            'titles': 'titles'
        }
        congress = bill_metadata.congress
        bill_type = bill_metadata.type.lower()
        bill_number = bill_metadata.number
        for key, endpoint in additional_bill_data.items():
            data = self.get(f"bill/{congress}/{bill_type}/{bill_number}/{endpoint}")
            bill_data[key] = data[key]
        bill_data.update(bill_metadata.model_dump())
        return bill_data
    
    def get_laws_metadata(self, start_date: str, end_date: str, congress: int, offset: int = 0):
        params = {
            "fromDateTime": start_date,
            "toDateTime": end_date
        }
        if offset > 0:
            params["offset"] = offset
        response = self.get(f"law/{congress}", params=params)
        laws = response.get("laws", [])
        if "next" in response.get("pagination", {}):
            offset = self.extract_offset(response["pagination"]["next"])
            return (laws, offset, response["pagination"]["count"])
        return (laws, -1, 0)
    
    def get_law_details(self, law_metadata: LawMetadata) -> Law:
        """
        Retrieve additional data for a law.

        Args:
            client (CDGClient): The client object.
            law_metadata (LawMetadata): The law metadata.

        Returns:
            Law: The law object.
        """
        law_data = {}
        congress = law_metadata.congress
        law_type = law_metadata.type.lower()
        law_number = law_metadata.number
        additional_law_data = {
            'actions': 'actions',
            'amendments': 'amendments',
            'cosponsors': 'cosponsors',
            'textVersions': 'text'
        }
        for key, endpoint in additional_law_data.items():
            data = self.get(f"law/{congress}/{law_type}/{law_number}/{endpoint}")
            law_data[key] = data[key]
        law_data.update(law_metadata.model_dump())
        law = Law(**law_data)
        return law
    
    def get_amendments_metadata(self, bill_number: int, congress: int, amendment_type: AmendmentType):
        response = self.get(f"amendment/{congress}/{amendment_type.type_url}/{bill_number}")

        return response
    
    def get_amendment_details(self, amendment_metadata: AmendmentMetadata) -> Amendment:
        """
        Retrieve additional data for an amendment.

        Args:
            client (CDGClient): The client object.
            amendment_metadata (AmendmentMetadata): The amendment metadata.

        Returns:
            Amendment: The amendment object.
        """
        amendment_data = {}
        congress = amendment_metadata.congress
        amendment_type = amendment_metadata.type
        amendment_number = amendment_metadata.number
        additional_amendment_data = {
            'actions': 'actions',
            'amendedBill': 'bill',
            'cosponsors': 'cosponsors', 
            'text': 'textVersions'
        }

        for key, endpoint in additional_amendment_data.items():
            data = self.get(f"amendment/{congress}/{amendment_type.type_url}/{amendment_number}/{endpoint}")
            amendment_data[key] = data[key]
        amendment_data.update(amendment_metadata.model_dump())
        amendment = Amendment(**amendment_data)
        return amendment
        
    def extract_offset(self, url: str) -> int:
        parsed_url = urlparse(url)
        offset = parse_qs(parsed_url.query).get('offset', [0])[0]
        return int(offset)

    def get_congresses(self):
        """Retrieve a list of congresses and congressional sessions."""
        return self.get("congress")

    def get_congress_details(self, congress: int):
        """Retrieve detailed information for a specified congress."""
        return self.get(f"congress/{congress}")

    def get_current_congress(self):
        """Retrieve detailed information for the current congress."""
        return self.get("congress/current")

    def get_members(self):
        """Retrieve a list of congressional members."""
        return self.get("member")

    def get_member_details(self, bioguide_id: str):
        """Retrieve detailed information for a specified congressional member."""
        return self.get(f"member/{bioguide_id}")

    def get_member_sponsored_legislation(self, bioguide_id: str):
        """Retrieve the list of legislation sponsored by a specified congressional member."""
        return self.get(f"member/{bioguide_id}/sponsored-legislation")

    def get_member_cosponsored_legislation(self, bioguide_id: str):
        """Retrieve the list of legislation cosponsored by a specified congressional member."""
        return self.get(f"member/{bioguide_id}/cosponsored-legislation")

    def get_members_by_congress(self, congress: int):
        """Retrieve the list of members specified by Congress."""
        return self.get(f"member/congress/{congress}")

    def get_members_by_state(self, state_code: str):
        """Retrieve a list of members filtered by state."""
        return self.get(f"member/{state_code}")

    def get_members_by_state_and_district(self, state_code: str, district: int):
        """Retrieve a list of members filtered by state and district."""
        return self.get(f"member/{state_code}/{district}")

    def get_members_by_congress_state_and_district(self, congress: int, state_code: str, district: int):
        """Retrieve a list of members filtered by congress, state, and district."""
        return self.get(f"member/congress/{congress}/{state_code}/{district}")

    def get_committees(self):
        """Retrieve a list of congressional committees."""
        return self.get("committee")

    def get_committees_by_chamber(self, chamber: str):
        """Retrieve a list of congressional committees filtered by the specified chamber."""
        return self.get(f"committee/{chamber}")

    def get_committees_by_congress(self, congress: int):
        """Retrieve a list of congressional committees filtered by the specified congress."""
        return self.get(f"committee/{congress}")

    def get_committees_by_congress_and_chamber(self, congress: int, chamber: str):
        """Retrieve a list of committees filtered by the specified congress and chamber."""
        return self.get(f"committee/{congress}/{chamber}")

    def get_committee_details(self, chamber: str, committee_code: str):
        """Retrieve detailed information for a specified congressional committee."""
        return self.get(f"committee/{chamber}/{committee_code}")

    def get_committee_bills(self, chamber: str, committee_code: str):
        """Retrieve the list of legislation associated with the specified congressional committee."""
        return self.get(f"committee/{chamber}/{committee_code}/bills")

    def get_committee_reports(self, chamber: str, committee_code: str):
        """Retrieve the list of committee reports associated with a specified congressional committee."""
        return self.get(f"committee/{chamber}/{committee_code}/reports")

    def get_committee_nominations(self, chamber: str, committee_code: str):
        """Retrieve the list of nominations associated with a specified congressional committee."""
        return self.get(f"committee/{chamber}/{committee_code}/nominations")

    def get_committee_house_communications(self, chamber: str, committee_code: str):
        """Retrieve the list of House communications associated with a specified congressional committee."""
        return self.get(f"committee/{chamber}/{committee_code}/house-communication")

    def get_committee_senate_communications(self, chamber: str, committee_code: str):
        """Retrieve the list of Senate communications associated with a specified congressional committee."""
        return self.get(f"committee/{chamber}/{committee_code}/senate-communication")

    def get_committee_reports(self):
        """Retrieve a list of committee reports."""
        return self.get("committee-report")

    def get_committee_reports_by_congress(self, congress: int):
        """Retrieve a list of committee reports filtered by the specified congress."""
        return self.get(f"committee-report/{congress}")

    def get_committee_reports_by_congress_and_type(self, congress: int, report_type: str):
        """Retrieve a list of committee reports filtered by the specified congress and report type."""
        return self.get(f"committee-report/{congress}/{report_type}")

    def get_committee_report_details(self, congress: int, report_type: str, report_number: int):
        """Retrieve detailed information for a specified committee report."""
        return self.get(f"committee-report/{congress}/{report_type}/{report_number}")

    def get_committee_report_text(self, congress: int, report_type: str, report_number: int):
        """Retrieve the list of texts for a specified committee report."""
        return self.get(f"committee-report/{congress}/{report_type}/{report_number}/text")

    def get_committee_prints(self):
        """Retrieve a list of committee prints."""
        return self.get("committee-print")

    def get_committee_prints_by_congress(self, congress: int):
        """Retrieve a list of committee prints filtered by the specified congress."""
        return self.get(f"committee-print/{congress}")

    def get_committee_prints_by_congress_and_chamber(self, congress: int, chamber: str):
        """Retrieve a list of committee prints filtered by the specified congress and chamber."""
        return self.get(f"committee-print/{congress}/{chamber}")

    def get_committee_print_details(self, congress: int, chamber: str, jacket_number: str):
        """Retrieve detailed information for a specified committee print."""
        return self.get(f"committee-print/{congress}/{chamber}/{jacket_number}")

    def get_committee_print_text(self, congress: int, chamber: str, jacket_number: str):
        """Retrieve the list of texts for a specified committee print."""
        return self.get(f"committee-print/{congress}/{chamber}/{jacket_number}/text")

    def get_committee_meetings(self):
        """Retrieve a list of committee meetings."""
        return self.get("committee-meeting")

    def get_committee_meetings_by_congress(self, congress: int):
        """Retrieve a list of committee meetings filtered by the specified congress."""
        return self.get(f"committee-meeting/{congress}")

    def get_committee_meetings_by_congress_and_chamber(self, congress: int, chamber: str):
        """Retrieve a list of committee meetings filtered by the specified congress and chamber."""
        return self.get(f"committee-meeting/{congress}/{chamber}")

    def get_committee_meeting_details(self, congress: int, chamber: str, event_id: str):
        """Retrieve detailed information for a specified committee meeting."""
        return self.get(f"committee-meeting/{congress}/{chamber}/{event_id}")

    def get_hearings(self):
        """Retrieve a list of hearings."""
        return self.get("hearing")

    def get_hearings_by_congress(self, congress: int):
        """Retrieve a list of hearings filtered by the specified congress."""
        return self.get(f"hearing/{congress}")

    def get_hearings_by_congress_and_chamber(self, congress: int, chamber: str):
        """Retrieve a list of hearings filtered by the specified congress and chamber."""
        return self.get(f"hearing/{congress}/{chamber}")

    def get_hearing_details(self, congress: int, chamber: str, jacket_number: str):
        """Retrieve detailed information for a specified hearing."""
        return self.get(f"hearing/{congress}/{chamber}/{jacket_number}")

    def get_congressional_records(self):
        """Retrieve a list of congressional record issues sorted by most recent."""
        return self.get("congressional-record")

    def get_daily_congressional_records(self):
        """Retrieve a list of daily congressional record issues sorted by most recent."""
        return self.get("daily-congressional-record")

    def get_daily_congressional_records_by_volume(self, volume_number: int):
        """Retrieve a list of daily Congressional Records filtered by the specified volume number."""
        return self.get(f"daily-congressional-record/{volume_number}")

    def get_daily_congressional_records_by_volume_and_issue(self, volume_number: int, issue_number: int):
        """Retrieve a list of daily Congressional Records filtered by the specified volume number and specified issue number."""
        return self.get(f"daily-congressional-record/{volume_number}/{issue_number}")

    def get_daily_congressional_record_articles(self, volume_number: int, issue_number: int):
        """Retrieve a list of daily Congressional Record articles filtered by the specified volume number and specified issue number."""
        return self.get(f"daily-congressional-record/{volume_number}/{issue_number}/articles")

    def get_bound_congressional_records(self):
        """Retrieve a list of bound Congressional Records sorted by most recent."""
        return self.get("bound-congressional-record")

    def get_bound_congressional_records_by_year(self, year: int):
        """Retrieve a list of bound Congressional Records filtered by the specified year."""
        return self.get(f"bound-congressional-record/{year}")

    def get_bound_congressional_records_by_year_and_month(self, year: int, month: int):
        """Retrieve a list of bound Congressional Records filtered by the specified year and specified month."""
        return self.get(f"bound-congressional-record/{year}/{month}")

    def get_bound_congressional_records_by_year_month_and_day(self, year: int, month: int, day: int):
        """Retrieve a list of bound Congressional Records filtered by the specified year, specified month, and specified day."""
        return self.get(f"bound-congressional-record/{year}/{month}/{day}")

    def get_house_communications(self):
        """Retrieve a list of House communications."""
        return self.get("house-communication")

    def get_house_communications_by_congress(self, congress: int):
        """Retrieve a list of House communications filtered by the specified congress."""
        return self.get(f"house-communication/{congress}")

    def get_house_communications_by_congress_and_type(self, congress: int, communication_type: str):
        """Retrieve a list of House communications filtered by the specified congress and communication type."""
        return self.get(f"house-communication/{congress}/{communication_type}")

    def get_house_communication_details(self, congress: int, communication_type: str, communication_number: int):
        """Retrieve detailed information for a specified House communication."""
        return self.get(f"house-communication/{congress}/{communication_type}/{communication_number}")

    def get_house_requirements(self):
        """Retrieve a list of House requirements."""
        return self.get("house-requirement")

    def get_house_requirement_details(self, requirement_number: int):
        """Retrieve detailed information for a specified House requirement."""
        return self.get(f"house-requirement/{requirement_number}")

    def get_matching_communications_for_house_requirement(self, requirement_number: int):
        """Retrieve a list of matching communications to a House requirement."""
        return self.get(f"house-requirement/{requirement_number}/matching-communications")

    def get_senate_communications(self):
        """Retrieve a list of Senate communications."""
        return self.get("senate-communication")

    def get_senate_communications_by_congress(self, congress: int):
        """Retrieve a list of Senate communications filtered by the specified congress."""
        return self.get(f"senate-communication/{congress}")

    def get_senate_communications_by_congress_and_type(self, congress: int, communication_type: str):
        """Retrieve a list of Senate communications filtered by the specified congress and communication type."""
        return self.get(f"senate-communication/{congress}/{communication_type}")

    def get_senate_communication_details(self, congress: int, communication_type: str, communication_number: int):
        """Retrieve detailed information for a specified Senate communication."""
        return self.get(f"senate-communication/{congress}/{communication_type}/{communication_number}")

    def get_nominations(self):
        """Retrieve a list of nominations sorted by date received from the President."""
        return self.get("nomination")

    def get_nominations_by_congress(self, congress: int):
        """Retrieve a list of nominations filtered by the specified congress and sorted by date received from the President."""
        return self.get(f"nomination/{congress}")

    def get_nomination_details(self, congress: int, nomination_number: int):
        """Retrieve detailed information for a specified nomination."""
        return self.get(f"nomination/{congress}/{nomination_number}")

    def get_nominees_for_nomination(self, congress: int, nomination_number: int, ordinal: int):
        """Retrieve the list of nominees for a position within the nomination."""
        return self.get(f"nomination/{congress}/{nomination_number}/{ordinal}")

    def get_nomination_actions(self, congress: int, nomination_number: int):
        """Retrieve the list of actions on a specified nomination."""
        return self.get(f"nomination/{congress}/{nomination_number}/actions")

    def get_nomination_committees(self, congress: int, nomination_number: int):
        """Retrieve the list of committees associated with a specified nomination."""
        return self.get(f"nomination/{congress}/{nomination_number}/committees")

    def get_nomination_hearings(self, congress: int, nomination_number: int):
        """Retrieve the list of printed hearings associated with a specified nomination."""
        return self.get(f"nomination/{congress}/{nomination_number}/hearings")

    def get_crs_reports(self):
        """Retrieve Congressional Research Service (CRS) report data from the API."""
        return self.get("crsreport")

    def get_crs_report_details(self, report_number: str):
        """Retrieve detailed information for a specified Congressional Research Service (CRS) report."""
        return self.get(f"crsreport/{report_number}")

    def get_treaties(self):
        """Retrieve a list of treaties sorted by date of last update."""
        return self.get("treaty")

    def get_treaties_by_congress(self, congress: int):
        """Retrieve a list of treaties for the specified congress, sorted by date of last update."""
        return self.get(f"treaty/{congress}")

    def get_treaty_details(self, congress: int, treaty_number: int):
        """Retrieve detailed information for a specified treaty."""
        return self.get(f"treaty/{congress}/{treaty_number}")

    def get_partitioned_treaty_details(self, congress: int, treaty_number: int, treaty_suffix: str):
        """Retrieve detailed information for a specified partitioned treaty."""
        return self.get(f"treaty/{congress}/{treaty_number}/{treaty_suffix}")

    def get_treaty_actions(self, congress: int, treaty_number: int):
        """Retrieve the list of actions on a specified treaty."""
        return self.get(f"treaty/{congress}/{treaty_number}/actions")

    def get_partitioned_treaty_actions(self, congress: int, treaty_number: int, treaty_suffix: str):
        """Retrieve the list of actions on a specified partitioned treaty."""
        return self.get(f"treaty/{congress}/{treaty_number}/{treaty_suffix}/actions")

    def get_treaty_committees(self, congress: int, treaty_number: int):
        """Retrieve the list of committees associated with a specified treaty."""
        return self.get(f"treaty/{congress}/{treaty_number}/committees")


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


def gather_congress_bills(client: CDGClient, from_date: str, to_date: str) -> list:
    """
    Gather all bills for a given date range.

    Args:
        client (CDGClient): The client object.
        from_date (str): The start date for the search in the format "YYYY-MM-DDTHH:MM:SSZ".
        to_date (str): The end date for the search in the format "YYYY-MM-DDTHH:MM:SSZ".

    Returns:
        list: A list of bill metadata
    """
    start = time.time()
    bills = []
    offset = 0
    total_count = None
    pbar = None

    while offset != -1:
        result, offset, count = client.get_bills_metadata(from_date, to_date, offset)
        bills.extend(result)
        if total_count is None:
            total_count = count
            pbar = tqdm(total=total_count, desc="Retrieving bills")
        pbar.update(len(result))
        determine_pagination_wait(start, offset)  # Prevent rate limiting
    if pbar:
        pbar.close()
    return bills
