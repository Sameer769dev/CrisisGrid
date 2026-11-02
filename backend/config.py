"""CrisisGrid backend settings.

Authentication & Model Endpoints:
- Meta Model API default: https://api.meta.ai/v1 (MODEL_API_KEY)
- Open-Weight Model Track ($10,000 Special Prize): Supports Muse Spark Open
  (`muse-spark-open`) and Muse Glimmer (`muse-glimmer`), served on participants'
  own hardware (vLLM / Ollama / GPU / Modal) or partner-provided inference.
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

# Open-Weight Model Track: defaults to muse-spark-1.3 on api.meta.ai/v1,
# but seamlessly switches to muse-spark-open or muse-glimmer on self-hosted
# or partner-provided inference endpoints.
TRIAGE_MODEL = os.getenv("TRIAGE_MODEL", os.getenv("OPEN_WEIGHT_MODEL", "muse-spark-1.3")).strip()
OPEN_WEIGHT_TRACK_MODELS = ["muse-spark-open", "muse-glimmer", "muse-spark-1.3"]


def is_open_weight_endpoint() -> bool:
    """Return True if pointing to self-hosted or partner open-weight inference."""
    return (
        "api.meta.ai" not in META_API_BASE_URL
        or TRIAGE_MODEL in ("muse-spark-open", "muse-glimmer")
        or os.getenv("OPEN_WEIGHT_MODE", "").lower() in ("true", "1", "yes")
    )


def model_api_key_configured() -> bool:
    """Check if API credentials or open-weight inference endpoint are ready."""
    if is_open_weight_endpoint():
        return True
    return bool(MODEL_API_KEY)


def get_meta_client():
    """Return an OpenAI SDK client pointed at the Meta Model API or partner inference.

    Raises RuntimeError with a human-readable message if credentials are missing.
    """
    key = MODEL_API_KEY
    if not key and is_open_weight_endpoint():
        key = "EMPTY"  # Standard vLLM / self-hosted dummy auth
    if not key:
        raise RuntimeError(
            "MODEL_API_KEY is not set. Copy .env.example to .env and set "
            "MODEL_API_KEY=<your Meta Model API key>, or configure an open-weight inference endpoint."
        )
    from openai import OpenAI

    return OpenAI(api_key=key, base_url=META_API_BASE_URL)


def get_async_meta_client():
    """Async variant of get_meta_client() - supports hosted Meta API and open-weight inference."""
    key = MODEL_API_KEY
    if not key and is_open_weight_endpoint():
        key = "EMPTY"  # Standard vLLM / self-hosted dummy auth
    if not key:
        raise RuntimeError(
            "MODEL_API_KEY is not set. Copy .env.example to .env and set "
            "MODEL_API_KEY=<your Meta Model API key>, or configure an open-weight inference endpoint."
        )
    from openai import AsyncOpenAI

    return AsyncOpenAI(api_key=key, base_url=META_API_BASE_URL, timeout=180.0)
