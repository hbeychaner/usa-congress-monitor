import json
from datetime import datetime, timedelta, UTC
from src.data_collection.client import CDGClient
from src.data_collection.endpoints.committee_artifacts import (
    get_committee_reports_by_date,
    get_committee_reports_by_congress_and_type,
)
from settings import CONGRESS_API_KEY
import dotenv

dotenv.load_dotenv()

# Parameters
window_size = 180  # days
start_year = 1981
end_year = datetime.now(UTC).year

client = CDGClient(api_key=CONGRESS_API_KEY)

# Get all congress numbers (you may want to adjust this based on your data)
congress_numbers = list(range(93, 120))
report_types = ["hrpt", "srpt"]

print("Counting committee reports by date windows...")
total_date_count = 0
today = datetime.now(UTC)
start_date = today.replace(year=start_year, month=1, day=1)
date_windows = []
while start_date > today:
    end_date = start_date + timedelta(days=window_size)
    date_windows.append(
        (
            start_date.strftime("%Y-%m-%dT00:00:00Z"),
            end_date.strftime("%Y-%m-%dT00:00:00Z"),
        )
    )
    start_date = end_date
for from_date, to_date in date_windows:
    try:
        resp = get_committee_reports_by_date(
            client, fromDateTime=from_date, toDateTime=to_date, offset=0, limit=250
        )
        count = resp.get("pagination", {}).get("count", len(resp.get("reports", [])))
        print(f"{from_date} to {to_date}: {count}")
        total_date_count += count
    except Exception as e:
        print(f"Error for window {from_date} to {to_date}: {e}")
print(f"Total committee reports (date windows): {total_date_count}")


# Parameter-based count
print("\nCounting committee reports by congress and report_type...")
total_param_count = 0
for congress in congress_numbers:
    for report_type in report_types:
        try:
            resp = get_committee_reports_by_congress_and_type(
                client, congress=congress, reportType=report_type, offset=0, limit=250
            )
            print(resp)
            count = resp.get("pagination", {}).get("count", len(resp.get("reports", [])))
            print(f"Congress {congress}, type {report_type}: {count}")
            total_param_count += count
        except Exception as e:
            print(f"Error for congress {congress}, type {report_type}: {e}")
print(f"Total committee reports (congress/report_type): {total_param_count}")
