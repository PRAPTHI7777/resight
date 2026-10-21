import requests
import feedparser

from config import ARXIV_TIMEOUT_SECONDS
from gemini_service import generate_summaries


BASE_URL = "https://export.arxiv.org/api/query"


def fetch_papers(
    query: str = "artificial intelligence",
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
    if query.strip():
        params["search_query"] = f"all:{query}"

    response = requests.get(
        BASE_URL,
        params=params,
        timeout=ARXIV_TIMEOUT_SECONDS,
    )

    response.raise_for_status()

    feed = feedparser.parse(response.text)

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


    # Generate summaries for ALL papers in one Gemini request

    summaries = generate_summaries(papers)

    for paper, summary in zip(papers, summaries):
        paper["description"] = summary["summary"]
        paper["summary_source"] = summary["source"]

    return papers