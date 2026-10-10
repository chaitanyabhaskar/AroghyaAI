"""Runtime configuration loaded from environment variables / .env file."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

# GenAI Generated code - Start

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
WEB_DIR = BASE_DIR / "web"


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def _float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


class Settings:
    """Plain settings object - no extra dependency, easy to override in tests."""

    def __init__(self) -> None:
        # --- LLM provider (any OpenAI-compatible endpoint) ---
        self.api_key: str = os.getenv("LLM_API_KEY", "").strip()
        self.base_url: str = os.getenv(
            "LLM_BASE_URL", "https://api.groq.com/openai/v1"
        ).rstrip("/")
        # Provider model IDs get retired regularly. If this one 404s, hit
        # /api/models to see what the key can actually use.
        self.text_model: str = os.getenv("LLM_TEXT_MODEL", "openai/gpt-oss-120b")
        self.vision_model: str = os.getenv("LLM_VISION_MODEL", self.text_model)
        self.model_label: str = os.getenv("MODEL_LABEL", "")
        self.temperature: float = _float("LLM_TEMPERATURE", 0.3)
        self.max_tokens: int = _int("LLM_MAX_TOKENS", 900)
        self.timeout: float = _float("LLM_TIMEOUT", 90.0)

        # --- storage ---
        raw_db = os.getenv("AROGYA_DB", str(BASE_DIR / "data" / "arogya.db"))
        self.db_path: Path = Path(raw_db)
        self.history_turns: int = _int("HISTORY_TURNS", 12)

        # --- hospital lookup (OpenStreetMap Overpass, no API key needed) ---
        self.overpass_url: str = os.getenv(
            "OVERPASS_URL", "https://overpass-api.de/api/interpreter"
        )
        self.overpass_timeout: float = _float("OVERPASS_TIMEOUT", 40.0)

        # --- limits ---
        self.max_message_chars: int = _int("MAX_MESSAGE_CHARS", 4000)
        self.max_image_bytes: int = _int("MAX_IMAGE_BYTES", 4 * 1024 * 1024)
        self.rate_limit_per_min: int = _int("RATE_LIMIT_PER_MIN", 20)

        # --- access gate ---
        # A single shared passcode. Not real authentication - it only stops
        # drive-by use of your model quota on a public URL. Empty = open access.
        self.access_code: str = os.getenv("ACCESS_CODE", "").strip()

        # --- http ---
        origins = os.getenv("ALLOWED_ORIGINS", "*")
        self.allowed_origins: list[str] = [
            o.strip() for o in origins.split(",") if o.strip()
        ] or ["*"]

    @property
    def configured(self) -> bool:
        """True when an API key is present, i.e. the chat endpoint can work."""
        return bool(self.api_key)

    @property
    def display_model(self) -> str:
        return self.model_label or self.text_model


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
# GenAI Generated code - End
