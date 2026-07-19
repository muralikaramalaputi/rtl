import os
from dotenv import load_dotenv
from groq import Groq

# Load .env file
load_dotenv()

# Read Groq API Key
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    raise RuntimeError(
        "GROQ_API_KEY not found. Please add it to your .env file."
    )

# Create Groq client
client = Groq(
    api_key=GROQ_API_KEY
)

# Model name
# Change this to any model available in your Groq account.
MODEL = "llama-3.3-70b-versatile"