import os
from datetime import datetime
from dotenv import load_dotenv
from src.data_collection.client import CDGClient

load_dotenv()

API_KEY = os.getenv("CONGRESS_API_KEY")
if not API_KEY:
    print("Missing CONGRESS_API_KEY environment variable.")
    exit(1)

client = CDGClient(api_key=API_KEY)


def main():
    total = 0
    # Mimic chunk logic: enumerate all congress and bill type combinations
    bill_types = ["HR", "S", "HJRES", "SJRES", "HCONRES", "SCONRES", "HRES", "SRES"]
    # Get all congress numbers (use 1 to current, 119)
    current_year = datetime.utcnow().year
    congress_start = 1
    congress_end = (
        (current_year - 1788) // 2
    ) + 1  # Each congress is 2 years, starting in 1789
    total = 0
    for congress_num in range(congress_start, congress_end + 1):
        for bill_type in bill_types:
            endpoint = f"bill/{congress_num}/{bill_type}?limit=1"
            try:
                data = client.get(endpoint)
                count = data.get("pagination", {}).get("count", 0)
                total += count
                print(f"Congress {congress_num}, {bill_type}: {count}")
            except Exception as e:
                print(f"Congress {congress_num}, {bill_type}: Exception {e}")
    print("Total bills:", total)


if __name__ == "__main__":
    main()
