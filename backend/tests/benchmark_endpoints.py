import json
import math
import os
import statistics
import sys
import time
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.update(
    DATABASE_URL="postgresql+psycopg2://benchmark:benchmark@127.0.0.1/unused",
    JWT_SECRET_KEY="isolated-benchmark-key-with-more-than-32-chars",
    DIGEST_SCHEDULER_ENABLED="false",
    DIGEST_INTERVAL_MINUTES="1440",
    GEMINI_API_KEY="",
)

from fastapi.testclient import TestClient
from sqlalchemy import ARRAY, JSON, create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import arxiv_service
import database
import gemini_service
import main
import models
from auth_handler import create_access_token


REQUEST_COUNT = int(os.getenv("BENCHMARK_REQUESTS", "60"))
WARMUP_COUNT = 5
MOCK_FEED = """<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Mock arXiv</title><id>https://example.test/</id>
  <updated>2026-01-01T00:00:00Z</updated>
  <entry>
    <id>https://arxiv.org/abs/2601.12345</id>
    <title>Mock live article</title><summary>Mock abstract</summary>
    <author><name>Benchmark Author</name></author>
    <published>2026-01-01T00:00:00Z</published>
    <link href="https://arxiv.org/abs/2601.12345"/>
  </entry>
</feed>
"""


def _timed_get(client, path, headers):
    started = time.perf_counter()
    try:
        response = client.get(path, headers=headers or {})
    except Exception as error:
        response = error
    return response, (time.perf_counter() - started) * 1000


def _percentile(values, fraction):
    return sorted(values)[max(0, math.ceil(fraction * len(values)) - 1)]


def _benchmark(client, label, path, expected_status=200, headers=None):
    cold_response, cold_ms = _timed_get(client, path, headers)
    for _ in range(WARMUP_COUNT):
        _timed_get(client, path, headers)

    started = time.perf_counter()
    measured = [
        _timed_get(client, path, headers)
        for _ in range(REQUEST_COUNT)
    ]
    wall_seconds = time.perf_counter() - started
    responses = [response for response, _ in measured]
    latencies = [latency for _, latency in measured]
    statuses = [
        response.status_code if hasattr(response, "status_code") else None
        for response in responses
    ]
    non_2xx = sum(
        status is None or not 200 <= status < 300 for status in statuses
    )
    final_response = responses[-1]
    items_returned = 0
    if (
        hasattr(final_response, "status_code")
        and final_response.status_code == 200
    ):
        body = final_response.json()
        items_returned = len(body) if isinstance(body, list) else 1

    return {
        "scenario": label,
        "path": path,
        "requests": REQUEST_COUNT,
        "2xx_successes": REQUEST_COUNT - non_2xx,
        "non_2xx_responses": non_2xx,
        "http_error_rate_pct": round(non_2xx * 100 / REQUEST_COUNT, 2),
        "unexpected_statuses": sum(
            status != expected_status for status in statuses
        ),
        "status_counts": {
            str(status): statuses.count(status)
            for status in sorted(set(statuses), key=str)
        },
        "mean_ms": round(statistics.mean(latencies), 3),
        "p50_ms": round(statistics.median(latencies), 3),
        "p95_ms": round(_percentile(latencies, 0.95), 3),
        "min_ms": round(min(latencies), 3),
        "max_ms": round(max(latencies), 3),
        "throughput_rps": round(REQUEST_COUNT / wall_seconds, 2),
        "cold_request_ms_excluded": round(cold_ms, 3),
        "cold_status": (
            cold_response.status_code
            if hasattr(cold_response, "status_code")
            else type(cold_response).__name__
        ),
        "warmup_requests_excluded": WARMUP_COUNT,
        "items_returned": items_returned,
    }


def main_benchmark():
    for table in database.Base.metadata.tables.values():
        for column in table.columns:
            if isinstance(column.type, ARRAY):
                column.type = JSON()

    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    database.Base.metadata.create_all(test_engine)
    test_session = sessionmaker(
        bind=test_engine,
        autoflush=False,
        autocommit=False,
    )

    def override_db():
        db = test_session()
        try:
            yield db
        finally:
            db.close()

    main.app.dependency_overrides[database.get_db] = override_db
    client = TestClient(main.app)
    results = [
        _benchmark(client, "empty article list", "/articles/"),
        _benchmark(
            client,
            "empty category",
            "/articles/category/Benchmark",
        ),
        _benchmark(
            client,
            "missing article (expected 404)",
            "/articles/1",
            expected_status=404,
        ),
    ]

    with test_session() as db:
        user = models.User(
            username="benchmark-user",
            email="benchmark@example.test",
            hashed_password="not-a-real-password-hash",
        )
        db.add(user)
        db.flush()
        article = models.Article(
            title="Benchmark article",
            description="Seeded benchmark description.",
            authors=["Benchmark Author"],
            date="2026-01-01",
            category="Benchmark",
        )
        db.add(article)
        db.flush()
        db.add_all(
            [
                models.Like(
                    user_id=user.id,
                    article_id="benchmark-like",
                    title="Liked paper",
                    authors=["Author"],
                    summary="Summary",
                    link="https://example.test/like",
                ),
                models.Bookmark(
                    user_id=user.id,
                    article_id="benchmark-bookmark",
                    title="Bookmarked paper",
                    authors=["Author"],
                    summary="Summary",
                    link="https://example.test/bookmark",
                ),
            ]
        )
        db.commit()
        article_id = article.id

    auth_headers = {
        "Authorization": (
            "Bearer "
            + create_access_token({"sub": "benchmark@example.test"})
        )
    }
    results.extend(
        [
            _benchmark(client, "seeded article list", "/articles/"),
            _benchmark(
                client,
                "seeded category",
                "/articles/category/Benchmark",
            ),
            _benchmark(
                client,
                "seeded article detail",
                f"/articles/{article_id}",
            ),
            _benchmark(
                client,
                "likes unauthenticated (expected 401)",
                "/likes/",
                expected_status=401,
            ),
            _benchmark(
                client,
                "bookmarks unauthenticated (expected 401)",
                "/bookmarks/",
                expected_status=401,
            ),
            _benchmark(
                client,
                "likes authenticated and seeded",
                "/likes/",
                headers=auth_headers,
            ),
            _benchmark(
                client,
                "bookmarks authenticated and seeded",
                "/bookmarks/",
                headers=auth_headers,
            ),
        ]
    )

    mock_response = Mock(text=MOCK_FEED)
    mock_response.raise_for_status.return_value = None
    with (
        patch.object(
            arxiv_service,
            "_send_arxiv_request",
            return_value=mock_response,
        ),
        patch.object(
            arxiv_service,
            "generate_summaries",
            side_effect=lambda papers: [
                {"summary": "Mocked summary", "source": "mocked"}
                for _ in papers
            ],
        ),
    ):
        results.append(
            _benchmark(
                client,
                "live route (arXiv and summaries mocked)",
                "/articles/live?sort_by=relevance&max_results=10",
            )
        )

    mock_gemini_client = Mock()
    mock_gemini_client.models.generate_content.return_value.text = json.dumps(
        [{"index": 0, "summary": "A mocked generated summary."}]
    )
    gemini_service.clear_summary_cache()
    with (
        patch.dict(os.environ, {"GEMINI_API_KEY": "benchmark-test-key"}),
        patch.object(
            arxiv_service,
            "_send_arxiv_request",
            return_value=mock_response,
        ),
        patch(
            "gemini_service.genai.Client",
            return_value=mock_gemini_client,
        ),
    ):
        cache_result = _benchmark(
            client,
            "live route with Gemini cache enabled (Gemini client mocked)",
            "/articles/live?sort_by=relevance&max_results=10",
        )
        cache_result["mock_gemini_requests"] = (
            mock_gemini_client.models.generate_content.call_count
        )
        results.append(cache_result)

    mock_gemini_client.models.generate_content.reset_mock()
    gemini_service.clear_summary_cache()
    with (
        patch.dict(os.environ, {"GEMINI_API_KEY": "benchmark-test-key"}),
        patch.object(
            arxiv_service,
            "_send_arxiv_request",
            return_value=mock_response,
        ),
        patch(
            "gemini_service.genai.Client",
            return_value=mock_gemini_client,
        ),
        patch.object(gemini_service, "_get_cached_summary", return_value=None),
        patch.object(gemini_service, "_cache_summary"),
    ):
        uncached_result = _benchmark(
            client,
            "live route with summary cache disabled (mocked comparator)",
            "/articles/live?sort_by=relevance&max_results=10",
        )
        uncached_result["mock_gemini_requests"] = (
            mock_gemini_client.models.generate_content.call_count
        )
        results.append(uncached_result)
    gemini_service.clear_summary_cache()

    print(
        json.dumps(
            {
                "environment": {
                    "client": "FastAPI TestClient / in-process ASGI",
                    "database": (
                        "isolated in-memory SQLite; PostgreSQL ARRAY columns "
                        "mapped to SQLite JSON in this process only"
                    ),
                    "live_route": (
                        "arXiv HTTP and summary generation mocked; "
                        "not live-service latency"
                    ),
                    "requests_per_scenario": REQUEST_COUNT,
                    "warmups_excluded": WARMUP_COUNT,
                },
                "results": results,
            },
            indent=2,
        )
    )
    main.app.dependency_overrides.clear()
    test_engine.dispose()


if __name__ == "__main__":
    main_benchmark()
