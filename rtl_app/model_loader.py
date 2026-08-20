import os
from dotenv import load_dotenv
from google import genai
from google.genai import types

# Load .env file
load_dotenv()

# Read Gemini API Key
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Gemini 2.5 Flash is retired for new API users; use the supported model directly.
MODEL = "gemini-3.6-flash"


def get_client():
    """Create the Gemini client only when a generation request is made."""
    if not GEMINI_API_KEY:
        raise RuntimeError(
            "GEMINI_API_KEY not found. Add it to your .env file and restart the server."
        )

    return genai.Client(api_key=GEMINI_API_KEY)
