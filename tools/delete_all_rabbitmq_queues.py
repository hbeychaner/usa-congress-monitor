"""Delete all RabbitMQ queues using HTTP API authentication from settings.py."""

import os
import requests
import argparse
from urllib.parse import quote

# Load RabbitMQ URL and credentials from settings.py
try:
    from settings import RABBITMQ_URL, ELASTIC_API_URL, ELASTIC_API_KEY
except ImportError:
    RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")
    ELASTIC_API_URL = os.getenv("ELASTIC_API_URL")
    ELASTIC_API_KEY = os.getenv("ELASTIC_API_KEY")


def parse_rabbitmq_url(url):
    import re

    m = re.match(r"amqp://([^:]+):([^@]+)@([^:/]+)(?::(\d+))?(/.*)?", url)
    if not m:
        raise ValueError(f"Could not parse RabbitMQ URL: {url}")
    user, password, host, port, vhost = m.groups()
    port = port or "15672"  # default management port
    vhost = vhost[1:] if vhost else "%2F"  # remove leading /, default to /
    return user, password, host, port, vhost


def delete_all_queues():
    user, password, host, port, vhost = parse_rabbitmq_url(RABBITMQ_URL)
    url = f"http://{host}:15672/api/queues"
    try:
        resp = requests.get(url, auth=(user, password))
        resp.raise_for_status()
        queues = resp.json()
        print(f"Found {len(queues)} queues. Deleting...")
        for q in queues:
            qname = q["name"]
            qvhost = q["vhost"]
            del_url = f"http://{host}:15672/api/queues/{quote(qvhost, safe='')}/{quote(qname, safe='')}"
            del_resp = requests.delete(del_url, auth=(user, password))
            if del_resp.status_code in (204, 200):
                print(f"Deleted: {qname} (vhost: {qvhost})")
            else:
                print(
                    f"Failed to delete: {qname} (vhost: {qvhost}) status: {del_resp.status_code} resp: {del_resp.text}"
                )
    except Exception as e:
        print(f"Error deleting queues: {e}")


def delete_congress_elasticsearch_indices(confirm: bool = False):
    """Delete Elasticsearch indices whose names start with 'congress-'.

    This is destructive for those indices. Pass `confirm=True` to proceed
    without an interactive prompt.
    """
    if not ELASTIC_API_URL:
        print("ELASTIC_API_URL not configured; skipping ES deletion.")
        return
    # List indices via _cat API
    cat_url = ELASTIC_API_URL.rstrip("/") + "/_cat/indices?format=json"
    headers = {"Content-Type": "application/json"}
    if ELASTIC_API_KEY:
        headers["Authorization"] = f"ApiKey {ELASTIC_API_KEY}"
    try:
        resp = requests.get(cat_url, headers=headers, timeout=30)
        resp.raise_for_status()
        indices = [entry.get("index") for entry in resp.json() if entry.get("index")]
    except Exception as e:
        print(f"Error listing indices: {e}")
        return

    target = [i for i in indices if i.startswith("congress-")]
    # Ensure the progress tracking index is included explicitly (it follows the
    # congress-* naming convention, but include defensively in case naming
    # changes or was omitted).
    progress_idx = "congress-progress-tracking"
    if progress_idx in indices and progress_idx not in target:
        target.append(progress_idx)
    if not target:
        print("No congress-* indices found to delete.")
        return

    print(
        f"Found {len(target)} congress-* indices to delete (includes progress tracker):"
    )
    for i in target:
        print(f" - {i}")

    if not confirm:
        ans = input("Proceed to delete the above indices? [y/N]: ")
        if ans.lower() not in ("y", "yes"):
            print("Aborting ES deletion.")
            return

    # Delete each index individually
    for idx in target:
        del_url = ELASTIC_API_URL.rstrip("/") + f"/{idx}"
        try:
            dresp = requests.delete(del_url, headers=headers, timeout=30)
            if dresp.status_code in (200, 202):
                print(f"Deleted index: {idx}")
            else:
                print(f"Failed to delete {idx}: {dresp.status_code} {dresp.text}")
        except Exception as e:
            print(f"Error deleting {idx}: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--delete-es",
        action="store_true",
        help="Also delete all Elasticsearch indices (destructive)",
    )
    parser.add_argument(
        "--yes", action="store_true", help="Assume yes for ES deletion prompt"
    )
    args = parser.parse_args()
    delete_all_queues()
    if args.delete_es:
        delete_congress_elasticsearch_indices(confirm=args.yes)
