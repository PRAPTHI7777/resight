import logging
import threading
import time

import feedparser
import requests
from sqlalchemy import text

from config import ARXIV_TIMEOUT_SECONDS
from database import engine
from gemini_service import generate_summaries


logger = logging.getLogger(__name__)
BASE_URL = "https://export.arxiv.org/api/query"
DEFAULT_SEARCH_QUERY = "artificial intelligence"
ARXIV_RATE_LIMIT_LOCK_KEY = 0x4152584956524154
ARXIV_MIN_REQUEST_INTERVAL_SECONDS = 3.0
_http_sessions = threading.local()


class ArxivFeedError(ValueError):
    """Raised when arXiv returns a response that is not a valid feed."""


def _get_http_session() -> requests.Session:
    session = getattr(_http_sessions, "session", None)
    if session is None:
        session = requests.Session()
        _http_sessions.session = session
    return session


def _send_arxiv_request(params: dict[str, int | str]) -> requests.Response:
    lock_wait_started_at = time.perf_counter()
    with engine.connect() as connection:
        connection.execute(
            text("SELECT pg_advisory_lock(:lock_key)"),
            {"lock_key": ARXIV_RATE_LIMIT_LOCK_KEY},
        )
        logger.info(
            "arXiv stage=rate_limit_lock_wait duration_ms=%.3f",
            (time.perf_counter() - lock_wait_started_at) * 1000,
        )
        request_started_at = time.perf_counter()
        try:
            return _get_http_session().get(
                BASE_URL,
                params=params,
                timeout=ARXIV_TIMEOUT_SECONDS,
            )
        finally:
            request_duration = time.perf_counter() - request_started_at
            logger.info(
                "arXiv stage=http_request duration_ms=%.3f",
                request_duration * 1000,
            )
            remaining_interval = (
                ARXIV_MIN_REQUEST_INTERVAL_SECONDS
                - request_duration
            )
            interval_wait_duration = 0.0
            if remaining_interval > 0:
                interval_wait_started_at = time.perf_counter()
                time.sleep(remaining_interval)
                interval_wait_duration = (
                    time.perf_counter() - interval_wait_started_at
                )
            logger.info(
                "arXiv stage=minimum_interval_wait duration_ms=%.3f",
                interval_wait_duration * 1000,
            )
            try:
                connection.execute(
                    text("SELECT pg_advisory_unlock(:lock_key)"),
                    {"lock_key": ARXIV_RATE_LIMIT_LOCK_KEY},
                )
            except Exception:
                connection.invalidate()
                logger.exception("Could not release the arXiv rate-limit lock.")
                raise


def fetch_papers(
    query: str | None = DEFAULT_SEARCH_QUERY,
    max_results: int = 10,
    category: str = "Artificial Intelligence",
    sort_by: str = "relevance",
):
    fetch_started_at = time.perf_counter()
    params = {
        "start": 0,
        "max_results": max_results,
        "sortBy": sort_by,
        "sortOrder": "descending",
    }
    search_query = (query or "").strip() or DEFAULT_SEARCH_QUERY
    params["search_query"] = f"all:{search_query}"

    response = _send_arxiv_request(params)

    response.raise_for_status()

    parse_started_at = time.perf_counter()
    try:
        feed = feedparser.parse(response.text)
    except Exception as error:
        logger.exception("Could not parse the arXiv Atom response.")
        raise ArxivFeedError("arXiv returned an unparseable feed.") from error
    finally:
        logger.info(
            "arXiv stage=feed_parse duration_ms=%.3f",
            (time.perf_counter() - parse_started_at) * 1000,
        )

    if getattr(feed, "bozo", False) or not feed.get("version"):
        parse_error = getattr(feed, "bozo_exception", None)
        logger.error(
            "arXiv returned an invalid Atom feed (%s): %s",
            type(parse_error).__name__ if parse_error else "unknown parse error",
            parse_error or "response did not contain a recognized feed",
        )
        raise ArxivFeedError("arXiv returned an invalid Atom feed.") from parse_error

    papers = []

    for entry in feed.entries:
        authors = [
            author.get("name", "")
            for author in entry.get("authors", [])
            if author.get("name")
        ]
        papers.append({
            "id": entry.get("id") or entry.get("link", ""),
            "title": entry.get("title", "Untitled paper"),
            "abstract": entry.get("summary", ""),
            "authors": authors,
            "date": entry.get("published", ""),
            "category": category,
            "link": entry.get("link", ""),
        })


    summary_started_at = time.perf_counter()
    try:
        summaries = generate_summaries(papers)
    except Exception:
        logger.exception("Summary generation failed for %d arXiv papers.", len(papers))
        raise
    finally:
        logger.info(
            "arXiv stage=summary_generation duration_ms=%.3f",
            (time.perf_counter() - summary_started_at) * 1000,
        )
    if len(summaries) != len(papers):
        logger.error(
            "Summary generation returned %d summaries for %d arXiv papers.",
            len(summaries),
            len(papers),
        )
        raise RuntimeError("Summary generation returned an incomplete result.")

    for paper, summary in zip(papers, summaries):
        paper["description"] = summary["summary"]
        paper["summary_source"] = summary["source"]

    logger.info(
        "arXiv stage=fetch_papers_total duration_ms=%.3f papers=%d",
        (time.perf_counter() - fetch_started_at) * 1000,
        len(papers),
    )
    return papers