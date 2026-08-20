import requests
import feedparser
from gemini_service import generate_summary

BASE_URL = "http://export.arxiv.org/api/query"

def fetch_papers(query: str="artificial intelligence"):
    params={
        "search_query": f"all:{query}",
        "start":0,
        "max_results":1
    }
    response = requests.get(BASE_URL, params=params)#send request
    feed = feedparser.parse(response.text) #extract response (inxml) -> convert into python objects

    papers = []

    for entry in feed.entries:
        papers.append({
        "id": entry.id,
        "title": entry.title,
        "description": generate_summary(entry.title, 
                                        entry.summary),
        "authors": [author.name for author in entry.authors],
        "date": entry.published,
        "category": "Artificial Intelligence",
        "link": entry.link
})
    return papers

