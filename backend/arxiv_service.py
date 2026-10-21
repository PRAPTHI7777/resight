import logging

import feedparser
import requests

from config import ARXIV_TIMEOUT_SECONDS
from gemini_service import generate_summaries


logger = logging.getLogger(__name__)
BASE_URL = "https://export.arxiv.org/api/query"
DEFAULT_SEARCH_QUERY = "artificial intelligence"


class ArxivFeedError(ValueError):
    """Raised when arXiv returns a response that is not a valid feed."""


def fetch_papers(
    query: str | None = DEFAULT_SEARCH_QUERY,
    max_results: int = 10,
    category: str = "Artificial Intelligence",
    sort_by: str = "relevance",
):
    params = {
        "start": 0,
        "max_results": max_results,
        "sortBy": sort_by,
        "sortOrder": "descending",
    }
    search_query = (query or "").strip() or DEFAULT_SEARCH_QUERY
    params["search_query"] = f"all:{search_query}"

    response = requests.get(
        BASE_URL,
        params=params,
        timeout=ARXIV_TIMEOUT_SECONDS,
    )

    response.raise_for_status()

    try:
        feed = feedparser.parse(response.text)
    except Exception as error:
        logger.exception("Could not parse the arXiv Atom response.")
        raise ArxivFeedError("arXiv returned an unparseable feed.") from error

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


    try:
        summaries = generate_summaries(papers)
    except Exception:
        logger.exception("Summary generation failed for %d arXiv papers.", len(papers))
        raise
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

    return papers