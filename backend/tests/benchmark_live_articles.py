"""Measure /articles/live with a synthetic arXiv feed and live Gemini."""

import argparse
import json
import math
import os
import statistics
import sys
import time
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql://benchmark:benchmark@127.0.0.1/unused",
)
os.environ.setdefault(
    "JWT_SECRET_KEY",
    "isolated-benchmark-key-with-more-than-32-chars",
)
os.environ.setdefault("DIGEST_SCHEDULER_ENABLED", "false")
os.environ.setdefault("DIGEST_INTERVAL_MINUTES", "1440")

import arxiv_service
import articles
import gemini_service
from config import GEMINI_API_KEY_ENV_NAME


DEFAULT_RUNS = 10
MIN_RUNS = 10
REQUEST_DELAY_SECONDS = 15.0
PAPER_COUNT = 10
LIVE_PATH = "/articles/live?sort_by=relevance&max_results=10"


def _make_feed() -> str:
    entries = "".join(
        f"""
        <entry>
          <id>https://arxiv.org/abs/test{index}</id>
          <title>Latency benchmark paper {index}: research method</title>
          <summary>This benchmark study number {index} examines a distinct
          research method and its measured outcomes. It compares the proposed
          technique with established baselines and reports improvements in
          accuracy and efficiency under realistic conditions.</summary>
          <author><name>Benchmark Author</name></author>
          <published>2026-01-01T00:00:00Z</published>
          <link href="https://arxiv.org/abs/test{index}"/>
        </entry>
        """
        for index in range(PAPER_COUNT)
    )
    return (
        '<?xml version="1.0"?>'
        '<feed xmlns="http://www.w3.org/2005/Atom">'
        "<title>Benchmark</title><id>https://example.test</id>"
        f"{entries}</feed>"
    )


def _summary_counts(papers: list[dict]) -> dict[str, int]:
    return {
        "gemini": sum(
            paper.get("summary_source") == "gemini" for paper in papers
        ),
        "abstract_fallback": sum(
            paper.get("summary_source") == "abstract_fallback"
            for paper in papers
        ),
    }


def _summary_outcome(counts: dict[str, int]) -> str:
    if counts["gemini"] == PAPER_COUNT:
        return "10 Gemini summaries"
    return (
        f"{counts['gemini']} Gemini summaries; "
        f"{counts['abstract_fallback']} abstract fallbacks"
    )


def _run_once(response: Mock) -> dict:
    started_at = time.perf_counter()
    try:
        with patch.object(
            arxiv_service,
            "_send_arxiv_request",
            return_value=response,
        ):
            papers = articles.get_live_articles(
                sort_by="relevance",
                max_results=PAPER_COUNT,
            )
    except Exception as error:
        counts = {"gemini": 0, "abstract_fallback": 0}
        return {
            "duration_ms": round(
                (time.perf_counter() - started_at) * 1000,
                3,
            ),
            "papers": 0,
            "summary_sources": counts,
            "summary_outcome": _summary_outcome(counts),
            "error": type(error).__name__,
        }

    counts = _summary_counts(papers)
    return {
        "duration_ms": round(
            (time.perf_counter() - started_at) * 1000,
            3,
        ),
        "papers": len(papers),
        "summary_sources": counts,
        "summary_outcome": _summary_outcome(counts),
    }


def _percentile(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    return ordered[max(0, math.ceil(percentile * len(ordered)) - 1)]


def _statistics(runs: list[dict]) -> dict[str, float] | None:
    durations = [
        run["duration_ms"]
        for run in runs
        if "duration_ms" in run
    ]
    if not durations:
        return None
    return {
        "median_ms": round(statistics.median(durations), 3),
        "p95_ms": round(_percentile(durations, 0.95), 3),
        "minimum_ms": round(min(durations), 3),
        "maximum_ms": round(max(durations), 3),
    }


def _outcome_counts(runs: list[dict]) -> dict[str, int]:
    return {
        "complete_gemini_runs": sum(
            run["summary_sources"]["gemini"] == PAPER_COUNT for run in runs
        ),
        "fallback_or_error_runs": sum(
            run["summary_sources"]["gemini"] != PAPER_COUNT for run in runs
        ),
    }


def _wait_before_api_attempt() -> None:
    time.sleep(REQUEST_DELAY_SECONDS)


def _run_benchmark(run_count: int) -> dict:
    if not os.getenv(GEMINI_API_KEY_ENV_NAME, "").strip():
        raise RuntimeError(
            f"{GEMINI_API_KEY_ENV_NAME} is not configured; "
            "the live Gemini benchmark cannot run."
        )

    response = Mock(text=_make_feed())
    response.raise_for_status.return_value = None
    gemini_service.clear_summary_cache()

    warmup = _run_once(response)
    warmup["measured"] = False
    cold_runs = []
    warmup_succeeded = (
        warmup["summary_sources"]["gemini"] == PAPER_COUNT
    )
    if warmup_succeeded:
        for _ in range(run_count):
            gemini_service.clear_summary_cache()
            _wait_before_api_attempt()
            run = _run_once(response)
            cold_runs.append(run)
            if run["summary_sources"]["gemini"] != PAPER_COUNT:
                break

    cold_complete = (
        len(cold_runs) == run_count
        and all(
            run["summary_sources"]["gemini"] == PAPER_COUNT
            for run in cold_runs
        )
    )
    warm_runs = []
    warm_cache_status = (
        "skipped: warm-up did not generate ten Gemini summaries"
        if not warmup_succeeded
        else "skipped: cold series did not complete with ten Gemini summaries"
    )
    if cold_complete:
        warm_cache_status = "measured; outbound Gemini calls blocked"
        with patch(
            "gemini_service.genai.Client",
            side_effect=RuntimeError(
                "Benchmark blocked an outbound Gemini cache-miss request."
            ),
        ):
            for _ in range(run_count):
                run = _run_once(response)
                warm_runs.append(run)
                if run["summary_sources"]["gemini"] != PAPER_COUNT:
                    warm_cache_status = (
                        "stopped: cache miss detected; outbound call blocked"
                    )
                    break

    return {
        "benchmark": "GET /articles/live; synthetic arXiv feed, live Gemini",
        "endpoint": LIVE_PATH,
        "paper_count": PAPER_COUNT,
        "warmup": warmup,
        "cold_cache": {
            "target_runs": run_count,
            "measured_runs": len(cold_runs),
            "statistics": _statistics(cold_runs),
            "outcome_counts": _outcome_counts(cold_runs),
            "complete_gemini_statistics": _statistics(
                [
                    run for run in cold_runs
                    if run["summary_sources"]["gemini"] == PAPER_COUNT
                ]
            ),
            "runs": cold_runs,
        },
        "warm_cache": {
            "status": warm_cache_status,
            "measured_runs": len(warm_runs),
            "statistics": _statistics(warm_runs),
            "runs": warm_runs,
        },
        "complete": cold_complete and len(warm_runs) == run_count,
        "api_usage": {
            "warmup_requests": 1,
            "cold_cache_request_limit": run_count,
            "warm_cache_external_requests": 0,
            "maximum_requests": run_count + 1,
            "minimum_seconds_between_requests": REQUEST_DELAY_SECONDS,
            "retries": 0,
            "note": (
                "A warm-up and each measured cold sample can make one Gemini "
                "request for ten papers. The cold series stops at the first "
                "incomplete/fallback result. Warm-cache samples only run "
                "after the full cold series succeeds and block outbound "
                "Gemini calls. There are no retries. Charges and quotas "
                "depend on the Google account and model; check the applicable "
                "Google AI terms and quota before running."
            ),
        },
        "percentile_method": "nearest-rank: ceil(0.95 * sample_count)",
        "external_services": {
            "arxiv": "mocked synthetic feed",
            "gemini": "live external API",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--runs",
        type=int,
        default=DEFAULT_RUNS,
        help=f"Measured runs per cache condition (minimum {MIN_RUNS}).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional path for saving the JSON report.",
    )
    args = parser.parse_args()
    if args.runs < MIN_RUNS:
        parser.error(f"--runs must be at least {MIN_RUNS}")

    try:
        report = _run_benchmark(args.runs)
    except RuntimeError as error:
        print(str(error), file=sys.stderr)
        return 1

    output = json.dumps(report, indent=2)
    if args.output is None:
        print(output)
    else:
        args.output.write_text(output + "\n", encoding="utf-8")
        print(f"Benchmark report written to {args.output}")
    if not report["complete"]:
        print(
            "Benchmark incomplete: quota/error/fallback prevented the "
            "requested sample count.",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
