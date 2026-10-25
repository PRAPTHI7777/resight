import json
import hashlib
import logging
import os
import threading
import time
from collections import OrderedDict
from urllib.parse import quote, quote_plus

from google import genai
from google.genai import types

from config import (
    GEMINI_API_KEY_ENV_NAME,
    GEMINI_API_KEY_SOURCE,
    GEMINI_TIMEOUT_MILLISECONDS,
)


logger = logging.getLogger(__name__)
MODEL_NAME = "gemini-2.5-flash"
SUMMARY_WORD_LIMIT = 60
SUMMARY_CACHE_TTL_SECONDS = 24 * 60 * 60
SUMMARY_CACHE_MAX_ITEMS = 1024

_summary_cache: OrderedDict[str, tuple[float, dict[str, str]]] = OrderedDict()
_summary_cache_lock = threading.Lock()


def _limit_words(summary: str) -> str:
    return " ".join(summary.split()[:SUMMARY_WORD_LIMIT])


def _fallback(paper: dict) -> dict[str, str]:
    abstract = str(paper.get("abstract") or "").strip()
    if not abstract:
        abstract = "No abstract was provided by arXiv."
    return {
        "summary": _limit_words(abstract),
        "source": "abstract_fallback",
    }


def _summary_cache_key(paper: dict) -> str:
    content = json.dumps(
        [
            MODEL_NAME,
            str(paper.get("title") or ""),
            str(paper.get("abstract") or ""),
        ],
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _get_cached_summary(key: str) -> dict[str, str] | None:
    now = time.monotonic()
    with _summary_cache_lock:
        cached = _summary_cache.get(key)
        if cached is None:
            return None
        expires_at, summary = cached
        if expires_at <= now:
            del _summary_cache[key]
            return None
        _summary_cache.move_to_end(key)
        return summary.copy()


def _cache_summary(key: str, summary: dict[str, str]) -> None:
    with _summary_cache_lock:
        _summary_cache[key] = (
            time.monotonic() + SUMMARY_CACHE_TTL_SECONDS,
            summary.copy(),
        )
        _summary_cache.move_to_end(key)
        while len(_summary_cache) > SUMMARY_CACHE_MAX_ITEMS:
            _summary_cache.popitem(last=False)


def _redact_api_key(value: object, api_key: str) -> str:
    message = str(value)
    if not api_key:
        return message
    for secret in {api_key, quote(api_key, safe=""), quote_plus(api_key)}:
        message = message.replace(secret, "[REDACTED]")
    return message


def clear_summary_cache() -> None:
    with _summary_cache_lock:
        _summary_cache.clear()


def generate_summaries(papers: list[dict]) -> list[dict[str, str]]:
    fallbacks = [_fallback(paper) for paper in papers]
    api_key = os.getenv(GEMINI_API_KEY_ENV_NAME, "").strip()
    logger.info(
        "Gemini configuration env_var=%s present=%s key_length=%d "
        "source=%s client_initialized=false",
        GEMINI_API_KEY_ENV_NAME,
        bool(api_key),
        len(api_key),
        GEMINI_API_KEY_SOURCE,
    )
    if not papers:
        return []
    if not api_key or api_key.lower().startswith("replace_"):
        logger.warning(
            "%s is not configured; using abstract fallbacks.",
            GEMINI_API_KEY_ENV_NAME,
        )
        return fallbacks

    summaries = list(fallbacks)
    missing_by_key: dict[str, tuple[dict, list[int]]] = {}
    cache_hits = 0
    for index, paper in enumerate(papers):
        key = _summary_cache_key(paper)
        cached = _get_cached_summary(key)
        if cached is not None:
            summaries[index] = cached
            cache_hits += 1
            continue
        if key not in missing_by_key:
            missing_by_key[key] = (paper, [])
        missing_by_key[key][1].append(index)

    logger.info(
        "Gemini summary cache hits=%d misses=%d",
        cache_hits,
        len(missing_by_key),
    )
    if not missing_by_key:
        return summaries

    missing_papers = [
        missing_by_key[key][0] for key in missing_by_key
    ]
    prompt = """
You are summarizing research papers for Resight. For each paper, write a
concise 2-3 sentence summary in simple language. Explain what the researchers
did and the main idea/result. Do not use bullet points or say "this paper".
Return only a JSON array of objects with integer "index" and string "summary".

Papers:
"""
    for index, paper in enumerate(missing_papers):
        prompt += (
            f"\nINDEX: {index}\nTITLE:\n{paper.get('title', '')}"
            f"\nABSTRACT:\n{paper.get('abstract', '')}\n"
        )

    try:
        client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(timeout=GEMINI_TIMEOUT_MILLISECONDS),
        )
        logger.info(
            "Gemini client initialized=true env_var=%s source=%s",
            GEMINI_API_KEY_ENV_NAME,
            GEMINI_API_KEY_SOURCE,
        )
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
            config=types.GenerateContentConfig(
                thinking_config=types.ThinkingConfig(thinking_budget=0),
            ),
        )
        text = response.text
        if not isinstance(text, str) or not text.strip():
            raise ValueError("Gemini returned an empty response.")
        text = text.strip()
        if text.startswith("```"):
            text = "\n".join(
                line for line in text.splitlines()
                if not line.strip().startswith("```")
            ).strip()

        results = json.loads(text)
        if not isinstance(results, list):
            raise ValueError("Gemini response was not a JSON array.")
    except Exception as error:
        response = getattr(error, "response", None)
        status_code = getattr(error, "code", None)
        if status_code is None:
            status_code = getattr(response, "status_code", None)
        api_status = getattr(error, "status", None)
        error_message = getattr(error, "message", None) or str(error)
        logger.warning(
            "Gemini summary request or response validation failed "
            "(exception=%s status_code=%s api_status=%s "
            "error_message=%r model=%s operation=generate_content "
            "input_papers=%d prompt_chars=%d timeout_ms=%d "
            "response_format=prompt_json_array key_source=%s); "
            "using abstract fallbacks.",
            type(error).__name__,
            status_code if status_code is not None else "unavailable",
            api_status if api_status is not None else "unavailable",
            _redact_api_key(error_message, api_key),
            MODEL_NAME,
            len(missing_papers),
            len(prompt),
            GEMINI_TIMEOUT_MILLISECONDS,
            GEMINI_API_KEY_SOURCE,
        )
        return summaries

    generated: dict[int, dict[str, str]] = {}
    for result in results:
        if not isinstance(result, dict):
            continue
        index = result.get("index")
        summary = result.get("summary")
        if (
            isinstance(index, int)
            and not isinstance(index, bool)
            and 0 <= index < len(missing_papers)
            and isinstance(summary, str)
            and summary.strip()
        ):
            generated[index] = {
                "summary": _limit_words(summary.strip()),
                "source": "gemini",
            }

    for missing_index, key in enumerate(missing_by_key):
        result = generated.get(missing_index)
        if result is None:
            continue
        _cache_summary(key, result)
        for original_index in missing_by_key[key][1]:
            summaries[original_index] = result.copy()

    if any(item["source"] == "abstract_fallback" for item in summaries):
        logger.warning("Gemini returned incomplete summaries; using abstract fallbacks.")
    return summaries
