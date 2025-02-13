from openai import OpenAI

from settings import (OPENAI_API_KEY, TIMEOUT_SECS)

def get_client():
    """
    A helper function to get an OpenAI client with the API key and timeout set.

    Args:
        None

    Returns:
        client (OpenAI): An OpenAI client object with the API key and timeout set.
    """
    client = OpenAI(
        api_key=OPENAI_API_KEY,
        timeout=TIMEOUT_SECS,
        max_retries=5)
    return client
