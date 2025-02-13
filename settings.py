import os 
from os.path import join, dirname
from dotenv import load_dotenv

# Load environment variables from .env file
dotenv_path = join(dirname(__file__), '.env')
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)


# Set up environment variables
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TIMEOUT_SECS = int(os.getenv("TIMEOUT_SECS"))
CONGRESS_API_KEY = os.getenv("CONGRESS_API_KEY")
CONGRESS_API_URL = os.getenv("CONGRESS_API_URL")