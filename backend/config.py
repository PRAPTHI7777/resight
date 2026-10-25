import os
import logging
from pathlib import Path

from dotenv import load_dotenv


logger = logging.getLogger(__name__)
ENV_FILE = Path(__file__).with_name(".env")
GEMINI_API_KEY_ENV_NAME = "GEMINI_API_KEY"
GEMINI_API_KEY_PREEXISTED_DOTENV = GEMINI_API_KEY_ENV_NAME in os.environ
load_dotenv(ENV_FILE)
GEMINI_API_KEY_SOURCE = (
    "process_environment"
    if GEMINI_API_KEY_PREEXISTED_DOTENV
    else "backend/.env"
    if os.getenv(GEMINI_API_KEY_ENV_NAME)
    else "unset"
)
if GEMINI_API_KEY_PREEXISTED_DOTENV:
    logger.warning(
        "%s was already set before loading backend/.env; dotenv does not "
        "override existing process environment values.",
        GEMINI_API_KEY_ENV_NAME,
    )


def _required_secret(name: str, minimum_length: int = 1) -> str:
    value = os.getenv(name, "").strip()
    if len(value) < minimum_length or value.lower().startswith(
        ("replace_", "change_me", "your_")
    ):
        raise RuntimeError(
            f"{name} must be configured with a non-placeholder value "
            f"of at least {minimum_length} characters."
        )
    return value


def _optional_secret(name: str, minimum_length: int = 32) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        return ""
    if len(value) < minimum_length or value.lower().startswith(
        ("replace_", "change_me", "your_")
    ):
        raise RuntimeError(
            f"{name} must be a non-placeholder value of at least "
            f"{minimum_length} characters when configured."
        )
    return value


def _integer_setting(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError as error:
        raise RuntimeError(f"{name} must be an integer.") from error


def _positive_float_setting(name: str, default: float) -> float:
    try:
        value = float(os.getenv(name, str(default)))
    except ValueError as error:
        raise RuntimeError(f"{name} must be a number.") from error
    if value <= 0:
        raise RuntimeError(f"{name} must be greater than zero.")
    return value


DATABASE_URL = _required_secret("DATABASE_URL")
if not DATABASE_URL.startswith("postgresql"):
    raise RuntimeError("DATABASE_URL must use a PostgreSQL SQLAlchemy URL.")
JWT_SECRET_KEY = _required_secret("JWT_SECRET_KEY", minimum_length=32)
DATABASE_CONNECT_TIMEOUT_SECONDS = _integer_setting(
    "DATABASE_CONNECT_TIMEOUT_SECONDS",
    5,
)
if DATABASE_CONNECT_TIMEOUT_SECONDS <= 0:
    raise RuntimeError("DATABASE_CONNECT_TIMEOUT_SECONDS must be greater than zero.")

ALLOWED_ORIGINS = tuple(
    origin.strip().rstrip("/")
    for origin in os.getenv(
        "CORS_ALLOWED_ORIGINS",
        "http://localhost:5500,http://127.0.0.1:5500,"
        "http://localhost:5501,http://127.0.0.1:5501",
    ).split(",")
    if origin.strip()
)
if "*" in ALLOWED_ORIGINS:
    raise RuntimeError(
        "CORS_ALLOWED_ORIGINS must list exact origins; wildcard origins are not allowed."
    )

DIGEST_SCHEDULER_ENABLED = (
    os.getenv("DIGEST_SCHEDULER_ENABLED", "false").strip().lower()
    in {"1", "true", "yes"}
)
DIGEST_INTERVAL_MINUTES = _integer_setting("DIGEST_INTERVAL_MINUTES", 1440)
if DIGEST_INTERVAL_MINUTES < 1440:
    raise RuntimeError(
        "DIGEST_INTERVAL_MINUTES must be at least 1440 (one day) "
        "to prevent repeated digest emails."
    )
DIGEST_MANUAL_TOKEN = _optional_secret("DIGEST_MANUAL_TOKEN")
ARTICLE_ADMIN_TOKEN = _optional_secret("ARTICLE_ADMIN_TOKEN")

ARXIV_TIMEOUT_SECONDS = _positive_float_setting("ARXIV_TIMEOUT_SECONDS", 15)
GEMINI_TIMEOUT_MILLISECONDS = _integer_setting("GEMINI_TIMEOUT_MILLISECONDS", 20000)
if GEMINI_TIMEOUT_MILLISECONDS <= 0:
    raise RuntimeError("GEMINI_TIMEOUT_MILLISECONDS must be greater than zero.")
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = _integer_setting("SMTP_PORT", 587)
if not 1 <= SMTP_PORT <= 65535:
    raise RuntimeError("SMTP_PORT must be between 1 and 65535.")
SMTP_TIMEOUT_SECONDS = _positive_float_setting("SMTP_TIMEOUT_SECONDS", 10)
