import os

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()

OMNIROUTE_BASE_URL = (
    os.getenv("OMNIROUTE_BASE_URL")
    or os.getenv("OPENAI_BASE_URL")
    or "http://localhost:20128/v1"
)
OMNIROUTE_API_KEY = os.getenv("OMNIROUTE_API_KEY") or os.getenv("OPENAI_API_KEY")
MODEL_NAME = os.getenv("OMNIROUTE_MODEL") or os.getenv("MODEL_NAME") or "auto"

if not OMNIROUTE_API_KEY:
    raise RuntimeError(
        "OMNIROUTE_API_KEY is not set. Please set OMNIROUTE_API_KEY in your .env file."
    )


def get_llm():
    """Return a fresh ChatOpenAI client bound to the current event loop."""
    return ChatOpenAI(
        model=MODEL_NAME,
        base_url=OMNIROUTE_BASE_URL,
        api_key=OMNIROUTE_API_KEY,
        temperature=0,
    )


llm = get_llm()
