import json
import logging
import os

from google import genai
from google.genai import types

from config import GEMINI_TIMEOUT_MILLISECONDS


logger = logging.getLogger(__name__)
MODEL_NAME = "gemini-2.5-flash"


def _fallback(paper: dict) -> dict[str, str]:
    abstract = str(paper.get("abstract") or "").strip()
    if not abstract:
        abstract = "No abstract was provided by arXiv."
    elif len(abstract) > 600:
        abstract = abstract[:597].rstrip() + "..."

    return {
        "summary": f"Abstract-based fallback: {abstract}",
        "source": "abstract_fallback",
    }


def generate_summaries(papers: list[dict]) -> list[dict[str, str]]:
    fallbacks = [_fallback(paper) for paper in papers]
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not papers:
        return []
    if not api_key or api_key.lower().startswith("replace_"):
        logger.warning("GEMINI_API_KEY is not configured; using abstract fallbacks.")
        return fallbacks

    prompt = """
You are summarizing research papers for Resight. For each paper, write a
concise 2-3 sentence summary in simple language. Explain what the researchers
did and the main idea/result. Do not use bullet points or say "this paper".
Return only a JSON array of objects with integer "index" and string "summary".

Papers:
"""
    for index, paper in enumerate(papers):
        prompt += (
            f"\nINDEX: {index}\nTITLE:\n{paper.get('title', '')}"
            f"\nABSTRACT:\n{paper.get('abstract', '')}\n"
        )

    try:
        client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(timeout=GEMINI_TIMEOUT_MILLISECONDS),
        )
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
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
        logger.warning(
            "Gemini summary request or response validation failed (%s); "
            "using abstract fallbacks.",
            type(error).__name__,
        )
        return fallbacks

    summaries = list(fallbacks)
    for result in results:
        if not isinstance(result, dict):
            continue
        index = result.get("index")
        summary = result.get("summary")
        if (
            isinstance(index, int)
            and not isinstance(index, bool)
            and 0 <= index < len(summaries)
            and isinstance(summary, str)
            and summary.strip()
        ):
            summaries[index] = {
                "summary": summary.strip(),
                "source": "gemini",
            }

    if any(item["source"] == "abstract_fallback" for item in summaries):
        logger.warning("Gemini returned incomplete summaries; using abstract fallbacks.")
    return summaries
