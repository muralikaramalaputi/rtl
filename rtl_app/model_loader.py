import os
from dotenv import load_dotenv
from google import genai
from google.genai import types

# Load .env file
load_dotenv()

# Read Gemini API Key
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "openrouter/free")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

RETIRED_GROQ_MODELS = {
    "llama-3.1-8b-instant": "openai/gpt-oss-20b",
    "llama-3.3-70b-versatile": "openai/gpt-oss-20b",
}


def normalize_provider(provider):
    """Validate and normalize the requested LLM provider."""
    normalized = (provider or "gemini").strip().lower()

    if normalized not in {"gemini", "groq", "openrouter"}:
        raise RuntimeError(
            "Choose the Gemini, Groq, or OpenRouter provider."
        )

    return normalized


def get_model(provider="gemini"):
    """Return the configured model for the selected provider."""
    provider = normalize_provider(provider)

    if provider == "gemini":
        return GEMINI_MODEL

    if provider == "openrouter":
        return OPENROUTER_MODEL

    return RETIRED_GROQ_MODELS.get(GROQ_MODEL, GROQ_MODEL)


def get_client(provider="gemini"):
    """Create the selected provider's client only for a generation request."""
    provider = normalize_provider(provider)

    if provider == "gemini":
        if not GEMINI_API_KEY:
            raise RuntimeError(
                "GEMINI_API_KEY not found. Add it to your .env file and restart the server."
            )

        return genai.Client(api_key=GEMINI_API_KEY)

    if provider == "groq":
        if not GROQ_API_KEY:
            raise RuntimeError(
                "GROQ_API_KEY not found. Add it to your .env file and restart the server."
            )

        try:
            from groq import Groq
        except ImportError as exc:
            raise RuntimeError(
                "Groq support is not installed. Run 'pip install -r requirements.txt'."
            ) from exc

        return Groq(api_key=GROQ_API_KEY)

    if not OPENROUTER_API_KEY:
        raise RuntimeError(
            "OPENROUTER_API_KEY not found. Add it to your .env file and restart the server."
        )

    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError(
            "OpenRouter support is not installed. Run 'pip install -r requirements.txt'."
        ) from exc

    return OpenAI(
        base_url=OPENROUTER_BASE_URL,
        api_key=OPENROUTER_API_KEY,
    )
