import os
from os.path import dirname, join

from dotenv import load_dotenv

# Load environment variables from .env files
repo_root = dirname(__file__)
dotenv_path = join(repo_root, ".env")
elastic_env_path = join(repo_root, "elastic-start-local", ".env")

if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)
if os.path.exists(elastic_env_path):
    load_dotenv(elastic_env_path)


# Set up environment variables
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
TIMEOUT_SECS = int(os.getenv("TIMEOUT_SECS", "30"))
CONGRESS_API_KEY = os.getenv("CONGRESS_API_KEY", "")
CONGRESS_API_URL = os.getenv("CONGRESS_API_URL", "")
ELASTIC_API_URL = os.getenv("ELASTIC_API_URL", "")
ELASTIC_API_KEY = os.getenv("ELASTIC_API_KEY", "")
ES_LOCAL_URL = os.getenv("ES_LOCAL_URL", "")
ES_LOCAL_API_KEY = os.getenv("ES_LOCAL_API_KEY", "")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")
RABBITMQ_QUEUE = os.getenv("RABBITMQ_QUEUE", "congress-sync")
RABBITMQ_PREFETCH = int(os.getenv("RABBITMQ_PREFETCH", "200"))
RABBITMQ_RATE_LIMIT_PER_HOUR = int(os.getenv("RABBITMQ_RATE_LIMIT_PER_HOUR", "5000"))
RABBITMQ_PAGE_SIZE = int(os.getenv("RABBITMQ_PAGE_SIZE", "250"))
RABBITMQ_API_WORKERS = int(os.getenv("RABBITMQ_API_WORKERS", "4"))
