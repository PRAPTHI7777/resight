import os
from pathlib import Path
from google import genai
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env", override=True)

client = genai.Client()

def generate_summary(title, description):

    prompt = f"""
You are summarizing a research paper for a technology news/research website called Resight.

Paper title:
{title}

Paper abstract:
{description}

Write a concise summary in 2-3 sentences.
Use simple language.
Explain what the researchers did and the main idea/result.
Do not use bullet points.
Do not say "this paper".
"""

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )

    return response.text