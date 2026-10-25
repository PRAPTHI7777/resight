"""Run a direct Gemini summary check without making an arXiv request."""

import sys

from gemini_service import clear_summary_cache, generate_summaries


def main() -> int:
    clear_summary_cache()
    result = generate_summaries(
        [
            {
                "title": "A compact test of scientific summarization",
                "abstract": (
                    "This study evaluates a new method for organizing "
                    "scientific findings and measures how well it helps "
                    "readers identify the central result."
                ),
            }
        ]
    )
    if len(result) != 1 or result[0].get("source") != "gemini":
        print(
            "FAIL: Gemini did not generate a summary; an abstract fallback "
            "was returned."
        )
        return 1

    summary = result[0].get("summary", "").strip()
    if not summary:
        print("FAIL: Gemini returned an empty summary.")
        return 1

    print("PASS: Gemini generated a summary.")
    print(summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
