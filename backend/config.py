"""CrisisGrid backend settings.

Single secret: MODEL_API_KEY for the official Meta Model API.
Never log or return the key value.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

# Load repo-root .env first, then backend/.env (either location works for devs).
_root = Path(__file__).resolve().parent.parent
load_dotenv(_root / ".env")
load_dotenv(Path(__file__).resolve().parent / ".env")

META_API_BASE_URL = os.getenv("META_API_BASE_URL", "https://api.meta.ai/v1").rstrip("/")
MODEL_API_KEY = os.getenv("MODEL_API_KEY", "").strip()
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://localhost:3000")


def model_api_key_configured() -> bool:
    return bool(MODEL_API_KEY)


def get_meta_client():
    """Return an OpenAI SDK client pointed ONLY at the Meta Model API.

    Raises RuntimeError with a human-readable message if the key is missing.
    """
    if not MODEL_API_KEY:
        raise RuntimeError(
            "MODEL_API_KEY is not set. Copy .env.example to .env and set "
            "MODEL_API_KEY=<your Meta Model API key>, then restart the backend."
        )
    from openai import OpenAI

    return OpenAI(api_key=MODEL_API_KEY, base_url=META_API_BASE_URL)


def get_async_meta_client():
    """Async variant of get_meta_client() - same base URL, same single key."""
    if not MODEL_API_KEY:
        raise RuntimeError(
            "MODEL_API_KEY is not set. Copy .env.example to .env and set "
            "MODEL_API_KEY=<your Meta Model API key>, then restart the backend."
        )
    from openai import AsyncOpenAI

    return AsyncOpenAI(api_key=MODEL_API_KEY, base_url=META_API_BASE_URL, timeout=180.0)
