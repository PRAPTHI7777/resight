import os
import json
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["DATABASE_URL"] = "postgresql+psycopg2://test:test@localhost/test"
os.environ["JWT_SECRET_KEY"] = "unit-test-key-with-more-than-thirty-two-characters"
os.environ["DIGEST_SCHEDULER_ENABLED"] = "false"
os.environ["DIGEST_INTERVAL_MINUTES"] = "1440"
os.environ["GEMINI_API_KEY"] = ""

import auth
import articles
import arxiv_service
import digest
import schemas
import scheduler
from fastapi import HTTPException
from gemini_service import generate_summaries
import requests


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
        self.papers = [
            {
                "title": "A test paper",
                "abstract": "Researchers evaluate a useful method.",
            }
        ]

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
            patch("arxiv_service.requests.get", return_value=response) as get,
            patch("arxiv_service.generate_summaries", return_value=[]),
        ):
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

    def test_blank_query_uses_a_valid_default_arxiv_search(self):
        response = Mock()
        response.text = '<feed xmlns="http://www.w3.org/2005/Atom"></feed>'
        response.raise_for_status.return_value = None
        with (
            patch("arxiv_service.requests.get", return_value=response) as get,
            patch("arxiv_service.generate_summaries", return_value=[]),
        ):
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
            patch("arxiv_service.requests.get", return_value=response) as get,
            patch("arxiv_service.generate_summaries", return_value=[]),
        ):
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
            patch("arxiv_service.requests.get", return_value=response),
            patch("arxiv_service.generate_summaries", return_value=[]),
        ):
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

    def test_automated_digest_scheduler_is_disabled_by_default(self):
        scheduler.start_scheduler()
        self.assertFalse(scheduler.scheduler.running)


if __name__ == "__main__":
    unittest.main()
