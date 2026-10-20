import os
from pathlib import Path

from dotenv import load_dotenv


load_dotenv(Path(__file__).with_name(".env"))


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

ARXIV_TIMEOUT_SECONDS = _positive_float_setting("ARXIV_TIMEOUT_SECONDS", 15)
GEMINI_TIMEOUT_MILLISECONDS = _integer_setting("GEMINI_TIMEOUT_MILLISECONDS", 20000)
if GEMINI_TIMEOUT_MILLISECONDS <= 0:
    raise RuntimeError("GEMINI_TIMEOUT_MILLISECONDS must be greater than zero.")
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = _integer_setting("SMTP_PORT", 587)
if not 1 <= SMTP_PORT <= 65535:
    raise RuntimeError("SMTP_PORT must be between 1 and 65535.")
SMTP_TIMEOUT_SECONDS = _positive_float_setting("SMTP_TIMEOUT_SECONDS", 10)
