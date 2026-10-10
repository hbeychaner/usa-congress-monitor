"""Wrappers around external generative AI clients used by services.

This module centralizes client construction for third-party generative
AI providers so callers may import a configured client from a single
place. Keep this module small and focused on configuration.
"""

from openai import OpenAI

from cdm.config import get_config
from cdm.utils.logger import get_logger

logger = get_logger(__name__)


def get_client() -> OpenAI:
    """Create and return a configured OpenAI client.

    The client is constructed using project-level settings for API key
    and timeout. Callers should not modify the client configuration.

    Returns:
        OpenAI: an initialized OpenAI client instance.
    """
    client = OpenAI(api_key=get_config().openai.openai_api_key, timeout=get_config().congress_api.timeout_secs, max_retries=5)
    return client
