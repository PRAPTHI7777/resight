import requests
import feedparser

from gemini_service import generate_summaries


BASE_URL = "http://export.arxiv.org/api/query"


def fetch_papers(query: str = "artificial intelligence", max_results: int = 10):

    params = {
        "search_query": f"all:{query}",
        "start": 0,
        "max_results": max_results
    }

    response = requests.get(
        BASE_URL,
        params=params
    )

    response.raise_for_status()

    feed = feedparser.parse(response.text)

    papers = []

    for entry in feed.entries:

        papers.append({
            "id": entry.id,
            "title": entry.title,
            "abstract": entry.summary,
            "authors": [
                author.name
                for author in entry.authors
            ],
            "date": entry.published,
            "category": "Artificial Intelligence",
            "link": entry.link
        })


    # Generate summaries for ALL papers in one Gemini request

    summaries = generate_summaries(papers)


    # Replace abstract with Gemini summary

    for i, paper in enumerate(papers):

        paper["description"] = summaries[i]

        del paper["abstract"]


    return papers