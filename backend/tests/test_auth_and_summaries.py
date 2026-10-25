import os
import json
import logging
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch

from google.genai import errors


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["DATABASE_URL"] = "postgresql+psycopg2://test:test@localhost/test"
os.environ["JWT_SECRET_KEY"] = "unit-test-key-with-more-than-thirty-two-characters"
os.environ["DIGEST_SCHEDULER_ENABLED"] = "false"
os.environ["DIGEST_INTERVAL_MINUTES"] = "1440"
os.environ["GEMINI_API_KEY"] = ""

import auth
import articles
import arxiv_service
import bookmarks
import benchmark_live_articles
import database
import digest
import gemini_service
import likes
import main
import schemas
import scheduler
from fastapi import HTTPException
from gemini_service import generate_summaries
import requests
from sqlalchemy.exc import SQLAlchemyError
from starlette.testclient import TestClient


class FakeQuery:
    def __init__(self, db):
        self.db = db

    def filter(self, *_conditions):
        self.conditions = _conditions
        return self

    def first(self):
        return self.db.user


class FakeDatabase:
    def __init__(self, user=None):
        self.user = user
        self.commits = 0
        self.deleted = []

    def query(self, _model):
        self.model = _model
        return FakeQuery(self)

    def add(self, user):
        self.user = user

    def refresh(self, _user):
        self.refreshed = _user
        return None

    def commit(self):
        self.commits += 1

    def delete(self, user):
        self.deleted.append(user)
        self.user = None


def make_user(otp, expiry):
    return SimpleNamespace(
        id=1,
        email="person@example.test",
        username="person",
        hashed_password="old-hash",
        otp=otp,
        otp_expires_at=expiry,
    )


class AuthFlowTests(unittest.TestCase):
    def test_login_issues_token_after_password_verification(self):
        user = make_user(None, None)
        db = FakeDatabase(user)
        with (
            patch.object(auth, "verify_password", return_value=True),
            patch.object(auth, "create_access_token", return_value="test-token"),
        ):
            result = auth.login(
                SimpleNamespace(username=user.email, password="correct-password"),
                db,
            )

        self.assertEqual(result, {
            "access_token": "test-token",
            "token_type": "bearer",
        })

    def test_login_rejects_unverified_signup(self):
        user = make_user(
            "signup:123456",
            datetime.now(timezone.utc) + timedelta(minutes=2),
        )
        db = FakeDatabase(user)
        with self.assertRaises(HTTPException) as error:
            auth.login(
                SimpleNamespace(username=user.email, password="password"),
                db,
            )
        self.assertEqual(error.exception.status_code, 403)

    def test_forgot_password_cooldown_prevents_repeated_email_sends(self):
        user = make_user(
            "reset:123456",
            datetime.now(timezone.utc) + timedelta(minutes=2),
        )
        db = FakeDatabase(user)

        with patch.object(auth, "send_otp_email") as send_email:
            result = auth.forgot_password(
                schemas.ForgotPasswordRequest(email=user.email),
                db,
            )

        self.assertIn("If the email is registered", result["message"])
        send_email.assert_not_called()

    def test_forgot_password_uses_same_response_for_unknown_email(self):
        result = auth.forgot_password(
            schemas.ForgotPasswordRequest(email="unknown@example.test"),
            FakeDatabase(),
        )
        self.assertIn("If the email is registered", result["message"])

    def test_password_reset_requires_completed_otp_verification(self):
        user = make_user("reset:123456", datetime.now(timezone.utc) + timedelta(minutes=2))
        db = FakeDatabase(user)
        request = schemas.ResetPasswordRequest(
            email=user.email,
            new_password="a-new-password",
        )

        with self.assertRaises(HTTPException) as error:
            auth.reset_password(request, db)
        self.assertEqual(error.exception.status_code, 400)
        self.assertEqual(user.hashed_password, "old-hash")

    def test_invalid_reset_otp_does_not_authorize_password_reset(self):
        user = make_user("reset:123456", datetime.now(timezone.utc) + timedelta(minutes=2))
        db = FakeDatabase(user)

        with self.assertRaises(HTTPException) as error:
            auth.verify_reset_otp(
                schemas.ResetOtpVerificationRequest(
                    email=user.email,
                    otp="654321",
                ),
                db,
            )
        self.assertEqual(error.exception.status_code, 400)
        self.assertEqual(user.otp, "reset:123456:1")

    def test_reset_otp_is_invalidated_after_five_failed_attempts(self):
        user = make_user(
            "reset:123456:4",
            datetime.now(timezone.utc) + timedelta(minutes=2),
        )
        db = FakeDatabase(user)

        with self.assertRaises(HTTPException) as error:
            auth.verify_reset_otp(
                schemas.ResetOtpVerificationRequest(
                    email=user.email,
                    otp="654321",
                ),
                db,
            )

        self.assertEqual(error.exception.status_code, 429)
        self.assertEqual(user.otp, "reset:locked")
        self.assertIsNotNone(user.otp_expires_at)

    def test_valid_otp_verification_allows_one_password_reset(self):
        expiry = datetime.now(timezone.utc) + timedelta(minutes=2)
        user = make_user("reset:123456", expiry)
        db = FakeDatabase(user)

        auth.verify_reset_otp(
            schemas.ResetOtpVerificationRequest(
                email=user.email,
                otp="123456",
            ),
            db,
        )
        self.assertEqual(user.otp, "reset-verified")

        with patch.object(auth, "hash_password", return_value="new-hash"):
            result = auth.reset_password(
                schemas.ResetPasswordRequest(
                    email=user.email,
                    new_password="a-new-password",
                ),
                db,
            )

        self.assertEqual(result["message"], "Password reset successfully")
        self.assertEqual(user.hashed_password, "new-hash")
        self.assertIsNone(user.otp)
        self.assertIsNone(user.otp_expires_at)

    def test_expired_verified_otp_cannot_reset_password(self):
        user = make_user(
            "reset-verified",
            datetime.now(timezone.utc) - timedelta(seconds=1),
        )
        db = FakeDatabase(user)

        with self.assertRaises(HTTPException) as error:
            auth.reset_password(
                schemas.ResetPasswordRequest(
                    email=user.email,
                    new_password="a-new-password",
                ),
                db,
            )

        self.assertEqual(error.exception.status_code, 400)
        self.assertEqual(user.otp, None)
        self.assertEqual(user.hashed_password, "old-hash")

    def test_expired_signup_otp_is_rejected(self):
        user = make_user(
            "signup:123456",
            datetime.now(timezone.utc) - timedelta(seconds=1),
        )
        db = FakeDatabase(user)

        with self.assertRaises(HTTPException) as error:
            auth.verify_signup_otp(
                schemas.ResetOtpVerificationRequest(
                    email=user.email,
                    otp="123456",
                ),
                db,
            )

        self.assertEqual(error.exception.status_code, 400)
        self.assertIsNone(user.otp)

    def test_signup_sends_code_and_verification_clears_pending_state(self):
        db = FakeDatabase()
        request = schemas.UserCreate(
            username="person",
            email="person@example.test",
            password="a-new-password",
        )
        with (
            patch.object(auth, "hash_password", return_value="hashed"),
            patch.object(auth, "send_otp_email") as send_email,
        ):
            result = auth.signup(request, db)
            self.assertEqual(result["message"], "Verification code sent")
            sent_otp = send_email.call_args.args[1]
            self.assertTrue(db.user.otp.startswith("signup:"))
            self.assertNotIn(sent_otp, db.user.otp)
            auth.verify_signup_otp(
                schemas.ResetOtpVerificationRequest(
                    email=request.email,
                    otp=sent_otp,
                ),
                db,
            )

        self.assertIsNone(db.user.otp)

    def test_password_reset_otp_is_hashed_in_existing_user_field(self):
        user = make_user(None, None)
        db = FakeDatabase(user)
        with patch.object(auth, "send_otp_email") as send_email:
            result = auth.forgot_password(
                schemas.ForgotPasswordRequest(email=user.email),
                db,
            )
            otp = send_email.call_args.args[1]

        self.assertIn("If the email is registered", result["message"])
        self.assertNotIn(otp, user.otp)
        auth.verify_reset_otp(
            schemas.ResetOtpVerificationRequest(email=user.email, otp=otp),
            db,
        )
        self.assertEqual(user.otp, "reset-verified")

    def test_signup_cleans_up_user_when_verification_email_fails(self):
        db = FakeDatabase()
        request = schemas.UserCreate(
            username="person",
            email="person@example.test",
            password="a-new-password",
        )
        with (
            patch.object(auth, "hash_password", return_value="hashed"),
            patch.object(auth, "send_otp_email", side_effect=RuntimeError("smtp")),
        ):
            with self.assertRaises(HTTPException) as error:
                auth.signup(request, db)

        self.assertEqual(error.exception.status_code, 503)
        self.assertIsNone(db.user)


class SummaryTests(unittest.TestCase):
    def setUp(self):
        gemini_service.clear_summary_cache()
        self.addCleanup(gemini_service.clear_summary_cache)
        self.papers = [
            {
                "title": "A test paper",
                "abstract": "Researchers evaluate a useful method.",
            }
        ]
        connection = MagicMock()
        connection.__enter__.return_value = connection
        connection.__exit__.return_value = False
        self.connection = connection
        engine_patch = patch(
            "arxiv_service.engine.connect",
            return_value=connection,
        )
        engine_patch.start()
        self.addCleanup(engine_patch.stop)
        sleep_patch = patch("arxiv_service.time.sleep")
        self.sleep = sleep_patch.start()
        self.addCleanup(sleep_patch.stop)

    def test_missing_gemini_key_returns_labeled_abstract_fallback(self):
        self.papers[0]["abstract"] = " ".join(["research"] * 75)
        with patch.dict(os.environ, {"GEMINI_API_KEY": ""}):
            result = generate_summaries(self.papers)

        self.assertEqual(result[0]["source"], "abstract_fallback")
        self.assertEqual(len(result[0]["summary"].split()), 60)

    def test_malformed_gemini_response_uses_fallback(self):
        client = Mock()
        client.models.generate_content.return_value.text = "not valid JSON"
        with (
            patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}),
            patch("gemini_service.genai.Client", return_value=client),
        ):
            result = generate_summaries(self.papers)

        self.assertEqual(result[0]["source"], "abstract_fallback")

    def test_missing_gemini_summary_uses_fallback_for_that_paper(self):
        client = Mock()
        client.models.generate_content.return_value.text = (
            '[{"index": 0, "summary": "A valid short summary."}]'
        )
        papers = self.papers + [
            {"title": "Second", "abstract": "Second paper abstract."}
        ]
        with (
            patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}),
            patch("gemini_service.genai.Client", return_value=client),
        ):
            result = generate_summaries(papers)

        self.assertEqual(result[0]["source"], "gemini")
        self.assertEqual(result[1]["source"], "abstract_fallback")

    def test_gemini_summary_is_limited_to_sixty_words(self):
        client = Mock()
        summary = " ".join(["insight"] * 75)
        client.models.generate_content.return_value.text = json.dumps(
            [{"index": 0, "summary": summary}]
        )
        with (
            patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}),
            patch("gemini_service.genai.Client", return_value=client),
        ):
            result = generate_summaries(self.papers)

        self.assertEqual(result[0]["source"], "gemini")
        self.assertEqual(len(result[0]["summary"].split()), 60)

    def test_gemini_summaries_are_cached_by_paper_content(self):
        client = Mock()
        client.models.generate_content.return_value.text = json.dumps(
            [{"index": 0, "summary": "A generated short summary."}]
        )
        with (
            patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}),
            patch("gemini_service.genai.Client", return_value=client),
        ):
            first = generate_summaries(self.papers)
            second = generate_summaries(self.papers)

        self.assertEqual(first, second)
        self.assertEqual(client.models.generate_content.call_count, 1)

    def test_live_benchmark_reports_nearest_rank_percentiles(self):
        runs = [{"duration_ms": float(value)} for value in range(1, 11)]

        self.assertEqual(
            benchmark_live_articles._statistics(runs),
            {
                "median_ms": 5.5,
                "p95_ms": 10.0,
                "minimum_ms": 1.0,
                "maximum_ms": 10.0,
            },
        )

    def test_live_benchmark_counts_gemini_and_fallback_sources(self):
        papers = [
            {"summary_source": "gemini"},
            {"summary_source": "abstract_fallback"},
        ]
        counts = benchmark_live_articles._summary_counts(papers)

        self.assertEqual(
            counts,
            {"gemini": 1, "abstract_fallback": 1},
        )
        self.assertEqual(
            benchmark_live_articles._summary_outcome(counts),
            "1 Gemini summaries; 1 abstract fallbacks",
        )

    def test_gemini_configuration_logs_are_redacted(self):
        api_key = "diagnostic-only-secret-value"
        client = Mock()
        client.models.generate_content.return_value.text = json.dumps(
            [{"index": 0, "summary": "A generated short summary."}]
        )
        with (
            patch.dict(os.environ, {"GEMINI_API_KEY": api_key}),
            patch("gemini_service.genai.Client", return_value=client),
            self.assertLogs("gemini_service", level="INFO") as log_output,
        ):
            result = generate_summaries(self.papers)

        logs = "\n".join(log_output.output)
        self.assertEqual(result[0]["source"], "gemini")
        self.assertIn("env_var=GEMINI_API_KEY", logs)
        self.assertIn("present=True", logs)
        self.assertIn(f"key_length={len(api_key)}", logs)
        self.assertIn("client_initialized=false", logs)
        self.assertIn("client initialized=true", logs)
        self.assertNotIn(api_key, logs)

    def test_gemini_server_error_logs_details_without_api_key(self):
        api_key = "diagnostic-only-secret-value"
        client = Mock()
        client.models.generate_content.side_effect = errors.ServerError(
            503,
            {
                "error": {
                    "message": f"temporary upstream failure ({api_key})",
                    "status": "UNAVAILABLE",
                }
            },
        )
        with (
            patch.dict(os.environ, {"GEMINI_API_KEY": api_key}),
            patch("gemini_service.genai.Client", return_value=client),
            self.assertLogs("gemini_service", level="WARNING") as log_output,
        ):
            result = generate_summaries(self.papers)

        logs = "\n".join(log_output.output)
        self.assertEqual(result[0]["source"], "abstract_fallback")
        self.assertIn("status_code=503", logs)
        self.assertIn("api_status=UNAVAILABLE", logs)
        self.assertIn("temporary upstream failure", logs)
        self.assertIn("[REDACTED]", logs)
        self.assertIn("model=gemini-2.5-flash", logs)
        self.assertIn("operation=generate_content", logs)
        self.assertIn("timeout_ms=", logs)
        self.assertNotIn(api_key, logs)

    def test_gemini_cache_misses_when_paper_content_changes(self):
        client = Mock()
        client.models.generate_content.return_value.text = json.dumps(
            [{"index": 0, "summary": "A generated short summary."}]
        )
        changed_paper = {
            "title": self.papers[0]["title"],
            "abstract": "A changed abstract.",
        }
        with (
            patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}),
            patch("gemini_service.genai.Client", return_value=client),
        ):
            generate_summaries(self.papers)
            generate_summaries([changed_paper])

        self.assertEqual(client.models.generate_content.call_count, 2)

    def test_gemini_cache_expires(self):
        key = "test-cache-entry"
        with patch("gemini_service.time.monotonic", return_value=100.0):
            gemini_service._cache_summary(
                key,
                {"summary": "Cached summary", "source": "gemini"},
            )

        with patch(
            "gemini_service.time.monotonic",
            return_value=100.0 + gemini_service.SUMMARY_CACHE_TTL_SECONDS + 1,
        ):
            self.assertIsNone(gemini_service._get_cached_summary(key))

    def test_abstract_fallback_is_not_cached(self):
        client = Mock()
        client.models.generate_content.side_effect = [
            RuntimeError("temporary failure"),
            Mock(
                text=json.dumps(
                    [{"index": 0, "summary": "A generated short summary."}]
                )
            ),
        ]
        with (
            patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}),
            patch("gemini_service.genai.Client", return_value=client),
        ):
            first = generate_summaries(self.papers)
            second = generate_summaries(self.papers)

        self.assertEqual(first[0]["source"], "abstract_fallback")
        self.assertEqual(second[0]["source"], "gemini")
        self.assertEqual(client.models.generate_content.call_count, 2)

    def test_identical_papers_in_one_batch_are_summarized_once(self):
        client = Mock()
        client.models.generate_content.return_value.text = json.dumps(
            [{"index": 0, "summary": "A generated short summary."}]
        )
        with (
            patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}),
            patch("gemini_service.genai.Client", return_value=client),
        ):
            result = generate_summaries(self.papers * 2)

        self.assertEqual(result[0], result[1])
        prompt = client.models.generate_content.call_args.kwargs["contents"]
        self.assertEqual(prompt.count("INDEX:"), 1)

    def test_distinct_papers_use_one_gemini_request_without_thinking(self):
        papers = [
            {"title": f"Paper {index}", "abstract": f"Abstract {index}"}
            for index in range(10)
        ]
        client = Mock()
        client.models.generate_content.return_value.text = json.dumps(
            [
                {"index": index, "summary": f"Generated summary {index}."}
                for index in range(len(papers))
            ]
        )
        with (
            patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}),
            patch("gemini_service.genai.Client", return_value=client),
        ):
            results = generate_summaries(papers)

        self.assertEqual(len(results), 10)
        self.assertTrue(all(item["source"] == "gemini" for item in results))
        client.models.generate_content.assert_called_once()
        config = client.models.generate_content.call_args.kwargs["config"]
        self.assertEqual(config.thinking_config.thinking_budget, 0)

    def test_http_session_is_reused_within_a_worker_thread(self):
        arxiv_service._http_sessions.__dict__.clear()
        with patch("arxiv_service.requests.Session") as session_factory:
            first_session = arxiv_service._get_http_session()
            second_session = arxiv_service._get_http_session()

        self.assertIs(first_session, second_session)
        session_factory.assert_called_once_with()

    def test_arxiv_fetch_logs_parse_and_summary_stage_durations(self):
        response = Mock(text='<feed xmlns="http://www.w3.org/2005/Atom"></feed>')
        response.raise_for_status.return_value = None
        with (
            patch("arxiv_service._send_arxiv_request", return_value=response),
            patch("arxiv_service.generate_summaries", return_value=[]),
            self.assertLogs("arxiv_service", level="INFO") as log_output,
        ):
            arxiv_service.fetch_papers("robotics")

        logged_stages = "\n".join(log_output.output)
        self.assertIn("stage=feed_parse", logged_stages)
        self.assertIn("stage=summary_generation", logged_stages)
        self.assertIn("stage=fetch_papers_total", logged_stages)

    def test_timing_loggers_write_info_to_console(self):
        for logger in (articles.logger, arxiv_service.logger):
            with self.subTest(logger=logger.name):
                self.assertEqual(logger.level, logging.INFO)
                self.assertFalse(logger.propagate)
                self.assertTrue(logger.handlers)

    def test_live_articles_logs_total_request_duration(self):
        with (
            patch("articles.fetch_papers", return_value=[]),
            self.assertLogs("articles", level="INFO") as log_output,
        ):
            articles.get_live_articles()

        self.assertRegex(
            "\n".join(log_output.output),
            r"stage=end_to_end duration_ms=\d+\.\d{3}",
        )

    def test_arxiv_request_logs_lock_http_and_interval_wait_durations(self):
        response = Mock()
        with (
            patch("arxiv_service._get_http_session") as get_session,
            self.assertLogs("arxiv_service", level="INFO") as log_output,
        ):
            get_session.return_value.get.return_value = response
            arxiv_service._send_arxiv_request({"search_query": "all:robotics"})

        logged_stages = "\n".join(log_output.output)
        self.assertIn("stage=rate_limit_lock_wait", logged_stages)
        self.assertIn("stage=http_request", logged_stages)
        self.assertIn("stage=minimum_interval_wait", logged_stages)

    def test_manual_digest_requires_server_secret_and_matching_header(self):
        with patch.object(digest, "DIGEST_MANUAL_TOKEN", ""):
            with self.assertRaises(HTTPException) as error:
                digest._validate_manual_digest_token("anything")
        self.assertEqual(error.exception.status_code, 503)

        with patch.object(digest, "DIGEST_MANUAL_TOKEN", "configured-test-token"):
            with self.assertRaises(HTTPException) as error:
                digest._validate_manual_digest_token("wrong-token")
            self.assertEqual(error.exception.status_code, 403)
            digest._validate_manual_digest_token("configured-test-token")

    def test_article_mutations_require_server_admin_token(self):
        with patch.object(articles, "ARTICLE_ADMIN_TOKEN", ""):
            with self.assertRaises(HTTPException) as error:
                articles._require_article_admin_token("unexpected-token")
        self.assertEqual(error.exception.status_code, 503)

        with patch.object(articles, "ARTICLE_ADMIN_TOKEN", "configured-test-token"):
            with self.assertRaises(HTTPException) as error:
                articles._require_article_admin_token("wrong-token")
            self.assertEqual(error.exception.status_code, 403)
            articles._require_article_admin_token("configured-test-token")

    def test_arxiv_network_failure_is_reported_as_a_gateway_error(self):
        with patch.object(articles, "fetch_papers", side_effect=requests.Timeout):
            with self.assertRaises(HTTPException) as error:
                articles.get_live_articles()

        self.assertEqual(error.exception.status_code, 502)

    def test_arxiv_request_has_a_configured_timeout(self):
        response = Mock()
        response.text = '<feed xmlns="http://www.w3.org/2005/Atom"></feed>'
        response.raise_for_status.return_value = None
        with (
            patch("arxiv_service._get_http_session") as get_session,
            patch("arxiv_service.generate_summaries", return_value=[]),
        ):
            get = get_session.return_value.get
            get.return_value = response
            arxiv_service.fetch_papers(
                "robotics",
                category="Robotics",
                sort_by="submittedDate",
            )

        self.assertGreater(get.call_args.kwargs["timeout"], 0)
        self.assertEqual(
            get.call_args.kwargs["params"]["search_query"],
            "all:robotics",
        )
        self.assertEqual(
            get.call_args.kwargs["params"]["sortBy"],
            "submittedDate",
        )
        self.assertEqual(get.call_args.kwargs["params"]["max_results"], 10)

    def test_arxiv_requests_are_spaced_by_the_official_minimum_interval(self):
        response = Mock()
        response.text = '<feed xmlns="http://www.w3.org/2005/Atom"></feed>'
        response.raise_for_status.return_value = None
        timestamps = iter(
            [9.5, 10.0, 10.0, 10.5, 11.0, 11.0, 13.5]
        )
        with (
            patch("arxiv_service._get_http_session") as get_session,
            patch(
                "arxiv_service.time.perf_counter",
                side_effect=lambda: next(timestamps, 13.5),
            ),
            patch("arxiv_service.generate_summaries", return_value=[]),
        ):
            get_session.return_value.get.return_value = response
            arxiv_service.fetch_papers("robotics")

        self.sleep.assert_called_once_with(2.5)
        self.assertEqual(self.connection.execute.call_count, 2)

    def test_blank_query_uses_a_valid_default_arxiv_search(self):
        response = Mock()
        response.text = '<feed xmlns="http://www.w3.org/2005/Atom"></feed>'
        response.raise_for_status.return_value = None
        with (
            patch("arxiv_service._get_http_session") as get_session,
            patch("arxiv_service.generate_summaries", return_value=[]),
        ):
            get = get_session.return_value.get
            get.return_value = response
            arxiv_service.fetch_papers("", category="All fields")

        self.assertEqual(
            get.call_args.kwargs["params"]["search_query"],
            "all:artificial intelligence",
        )
        self.assertEqual(get.call_args.kwargs["params"]["sortBy"], "relevance")

    def test_missing_query_uses_the_default_arxiv_search(self):
        response = Mock()
        response.text = '<feed xmlns="http://www.w3.org/2005/Atom"></feed>'
        response.raise_for_status.return_value = None
        with (
            patch("arxiv_service._get_http_session") as get_session,
            patch("arxiv_service.generate_summaries", return_value=[]),
        ):
            get = get_session.return_value.get
            get.return_value = response
            arxiv_service.fetch_papers(None)

        self.assertEqual(
            get.call_args.kwargs["params"]["search_query"],
            "all:artificial intelligence",
        )

    def test_invalid_arxiv_feed_is_reported_as_a_gateway_error(self):
        response = Mock()
        response.text = "this is not a feed"
        response.raise_for_status.return_value = None
        with (
            patch("arxiv_service._get_http_session") as get_session,
            patch("arxiv_service.generate_summaries", return_value=[]),
        ):
            get_session.return_value.get.return_value = response
            with self.assertRaises(HTTPException) as error:
                articles.get_live_articles()

        self.assertEqual(error.exception.status_code, 502)

    def test_arxiv_http_error_logs_the_upstream_response_body(self):
        response = Mock(status_code=400, text="search_query is required")
        upstream_error = requests.HTTPError("400 Client Error", response=response)
        with (
            patch.object(articles, "fetch_papers", side_effect=upstream_error),
            self.assertLogs(articles.logger, level="WARNING") as log_output,
        ):
            with self.assertRaises(HTTPException) as error:
                articles.get_live_articles()

        self.assertEqual(error.exception.status_code, 502)
        self.assertIn("search_query is required", "\n".join(log_output.output))

    def test_arxiv_rate_limit_response_maps_to_service_unavailable(self):
        response = Mock(status_code=429, text="rate limited")
        upstream_error = requests.HTTPError("429 Too Many Requests", response=response)
        with patch.object(articles, "fetch_papers", side_effect=upstream_error):
            with self.assertRaises(HTTPException) as error:
                articles.get_live_articles(query="robotics")

        self.assertEqual(error.exception.status_code, 503)

    def test_digest_invalid_arxiv_feed_maps_to_gateway_error(self):
        with (
            patch.object(digest, "DIGEST_MANUAL_TOKEN", "configured-test-token"),
            patch.object(
                digest,
                "fetch_papers",
                side_effect=arxiv_service.ArxivFeedError("invalid feed"),
            ),
        ):
            with self.assertRaises(HTTPException) as error:
                digest.send_digest(
                    FakeDatabase(),
                    SimpleNamespace(id=1),
                    "configured-test-token",
                )

        self.assertEqual(error.exception.status_code, 502)

    def test_live_article_route_preserves_query_sort_and_limit(self):
        with patch.object(articles, "fetch_papers", return_value=[]) as fetch:
            response = TestClient(main.app).get(
                "/articles/live?query=robotics&sort_by=submittedDate&max_results=2"
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])
        self.assertEqual(fetch.call_args.args[0], "robotics")
        self.assertEqual(fetch.call_args.kwargs["sort_by"], "submittedDate")
        self.assertEqual(fetch.call_args.kwargs["max_results"], 2)

    def test_automated_digest_scheduler_is_disabled_by_default(self):
        scheduler.start_scheduler()
        self.assertFalse(scheduler.scheduler.running)


class ApiReliabilityTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(main.app)

    def tearDown(self):
        main.app.dependency_overrides.clear()

    def test_private_read_endpoints_require_authentication(self):
        for endpoint in ("/likes/", "/bookmarks/", "/users/me"):
            with self.subTest(endpoint=endpoint):
                response = self.client.get(endpoint)
                self.assertEqual(response.status_code, 401)
                self.assertIn("detail", response.json())

    def test_live_article_parameters_reject_invalid_values(self):
        invalid_requests = (
            "/articles/live?sort_by=unknown",
            "/articles/live?max_results=21",
            "/articles/live?query=" + ("x" * 257),
            "/articles/live?max_results=0",
        )
        for endpoint in invalid_requests:
            with self.subTest(endpoint=endpoint[:50]):
                response = self.client.get(endpoint)
                self.assertEqual(response.status_code, 422)

    def test_non_positive_article_id_is_rejected(self):
        response = self.client.get("/articles/0")
        self.assertEqual(response.status_code, 422)

    def test_gemini_diagnostic_route_requires_admin_configuration(self):
        with (
            patch.object(articles, "ARTICLE_ADMIN_TOKEN", ""),
            patch.object(articles, "generate_summaries") as generate,
        ):
            response = self.client.get("/articles/test-gemini")

        self.assertEqual(response.status_code, 503)
        generate.assert_not_called()

    def test_database_failure_returns_sanitized_service_error(self):
        class FailingDatabase:
            def query(self, _model):
                raise SQLAlchemyError("private database connection details")

        def failing_database():
            yield FailingDatabase()

        main.app.dependency_overrides[database.get_db] = failing_database
        response = self.client.get("/articles/")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json(),
            {"detail": "A database operation failed. Please try again."},
        )
        self.assertNotIn("private database", response.text)

    def test_duplicate_like_and_bookmark_return_conflict(self):
        user = SimpleNamespace(id=1)
        payload = {
            "article_id": "arxiv:1234.56789",
            "title": "Test paper",
            "authors": ["Researcher"],
            "summary": "A short summary.",
            "link": "https://arxiv.org/abs/1234.56789",
        }
        duplicate = SimpleNamespace(id=1)

        for add_endpoint, schema in (
            (likes.add_like, schemas.LikeCreate),
            (bookmarks.add_bookmark, schemas.BookmarkCreate),
        ):
            with self.subTest(endpoint=add_endpoint.__name__):
                with self.assertRaises(HTTPException) as error:
                    add_endpoint(schema(**payload), FakeDatabase(duplicate), user)
                self.assertEqual(error.exception.status_code, 409)

    def test_like_and_bookmark_success_paths_commit(self):
        user = SimpleNamespace(id=1)
        payload = {
            "article_id": "arxiv:1234.56789",
            "title": "Test paper",
            "authors": ["Researcher"],
            "summary": "A short summary.",
            "link": "https://arxiv.org/abs/1234.56789",
        }

        for add_endpoint, schema in (
            (likes.add_like, schemas.LikeCreate),
            (bookmarks.add_bookmark, schemas.BookmarkCreate),
        ):
            with self.subTest(endpoint=add_endpoint.__name__):
                db = FakeDatabase()
                result = add_endpoint(schema(**payload), db, user)
                self.assertEqual(db.commits, 1)
                self.assertEqual(result.user_id, user.id)
                self.assertEqual(result.article_id, payload["article_id"])


if __name__ == "__main__":
    unittest.main()
