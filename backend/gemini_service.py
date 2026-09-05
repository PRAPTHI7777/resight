import os
import json
from pathlib import Path

from google import genai
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env", override=True)

client = genai.Client()


def generate_summaries(papers):

    prompt = """
You are summarizing research papers for a technology research website
called Resight.

For each paper below, write a concise summary in 2-3 sentences.

Use simple language.
Explain what the researchers did and the main idea/result.
Do not use bullet points.
Do not say "this paper".

Return ONLY a JSON array.

Each object must have:
- "index"
- "summary"

Example:

[
    {
        "index": 0,
        "summary": "Researchers..."
    },
    {
        "index": 1,
        "summary": "Researchers..."
    }
]

Papers:
"""

    for i, paper in enumerate(papers):

        prompt += f"""

INDEX: {i}

TITLE:
{paper["title"]}

ABSTRACT:
{paper["abstract"]}

"""

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )

    text = response.text.strip()

    # Remove markdown code fences if Gemini adds them
    if text.startswith("```"):
        text = text.replace("```json", "")
        text = text.replace("```", "")
        text = text.strip()

    results = json.loads(text)

    summaries = [""] * len(papers)

    for result in results:

        index = result["index"]

        if 0 <= index < len(summaries):
            summaries[index] = result["summary"]

    return summaries