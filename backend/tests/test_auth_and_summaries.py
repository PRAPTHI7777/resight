import os
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
        self.assertEqual(user.otp, "reset:123456")

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
            auth.verify_signup_otp(
                schemas.ResetOtpVerificationRequest(
                    email=request.email,
                    otp=sent_otp,
                ),
                db,
            )

        self.assertIsNone(db.user.otp)

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
        with patch.dict(os.environ, {"GEMINI_API_KEY": ""}):
            result = generate_summaries(self.papers)

        self.assertEqual(result[0]["source"], "abstract_fallback")
        self.assertIn("Abstract-based fallback:", result[0]["summary"])
        self.assertIn(self.papers[0]["abstract"], result[0]["summary"])

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
            arxiv_service.fetch_papers("robotics", category="Robotics")

        self.assertGreater(get.call_args.kwargs["timeout"], 0)

    def test_automated_digest_scheduler_is_disabled_by_default(self):
        scheduler.start_scheduler()
        self.assertFalse(scheduler.scheduler.running)


if __name__ == "__main__":
    unittest.main()
