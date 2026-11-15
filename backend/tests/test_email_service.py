import os
import sys
import unittest
from email.message import EmailMessage
from pathlib import Path
from unittest.mock import Mock, patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import email_service
import email_utils


class AppsScriptEmailRelayTests(unittest.TestCase):
    def setUp(self):
        self.secret = "unit-test-shared-secret-with-at-least-32-characters"
        self.environment = patch.dict(
            os.environ,
            {
                "GAS_EMAIL_RELAY_URL": (
                    "https://script.google.com/macros/s/test-deployment/exec"
                ),
                "GAS_EMAIL_RELAY_SECRET": self.secret,
            },
        )
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def test_sends_plain_text_message_over_https_with_shared_secret(self):
        message = self._plain_message()
        response = Mock(status_code=200)
        response.json.return_value = {"ok": True}

        with patch.object(email_service.requests, "post", return_value=response) as post:
            email_service.send_message(message)

        self.assertEqual(
            post.call_args.args[0],
            "https://script.google.com/macros/s/test-deployment/exec",
        )
        self.assertEqual(
            post.call_args.kwargs["json"],
            {
                "to": ["reader@example.test"],
                "subject": "Your Resight verification code",
                "text": "Your code is 123456.\n",
                "secret": self.secret,
            },
        )
        self.assertEqual(
            post.call_args.kwargs["timeout"],
            email_service.GAS_EMAIL_RELAY_TIMEOUT_SECONDS,
        )
        self.assertTrue(post.call_args.kwargs["allow_redirects"])

    def test_preserves_html_message_body(self):
        message = EmailMessage()
        message["To"] = "reader@example.test"
        message["Subject"] = "Research digest"
        message.add_alternative("<p>New research</p>", subtype="html")
        response = Mock(status_code=200)
        response.json.return_value = {"ok": True}

        with patch.object(email_service.requests, "post", return_value=response) as post:
            email_service.send_message(message)

        payload = post.call_args.kwargs["json"]
        self.assertEqual(payload["html"], "<p>New research</p>\n")
        self.assertEqual(payload["to"], ["reader@example.test"])
        self.assertEqual(payload["secret"], self.secret)

    def test_signup_otp_email_content_is_preserved(self):
        with patch.object(email_utils, "send_message") as send_message:
            email_utils.send_otp_email("reader@example.test", "123456")

        message = send_message.call_args.args[0]
        self.assertEqual(message["Subject"], "Your Resight verification code")
        self.assertEqual(message["To"], "reader@example.test")
        self.assertIn(
            "Your Resight verification code is:\n\n123456",
            message.get_content(),
        )
        self.assertIn("This code expires shortly.", message.get_content())

    def test_http_error_is_reported_without_logging_response_body(self):
        response = Mock(status_code=403)
        response.text = "private provider response with 123456"

        with (
            patch.object(email_service.requests, "post", return_value=response),
            self.assertLogs("email_service", level="WARNING") as captured,
        ):
            with self.assertRaisesRegex(RuntimeError, "HTTP error"):
                email_service.send_message(self._plain_message())

        log_output = "\n".join(captured.output)
        self.assertIn("HTTP 403", log_output)
        self.assertNotIn(self.secret, log_output)
        self.assertNotIn("123456", log_output)
        self.assertNotIn("private provider response", log_output)

    def test_relay_delivery_failure_is_reported_without_logging_otp(self):
        response = Mock(status_code=200)
        response.json.return_value = {"ok": False, "error": "delivery_failed"}

        with (
            patch.object(email_service.requests, "post", return_value=response),
            self.assertLogs("email_service", level="WARNING") as captured,
        ):
            with self.assertRaisesRegex(RuntimeError, "could not deliver"):
                email_service.send_message(self._plain_message())

        log_output = "\n".join(captured.output)
        self.assertIn("delivery_failed", log_output)
        self.assertNotIn(self.secret, log_output)
        self.assertNotIn("123456", log_output)

    def test_unexpected_relay_error_codes_are_redacted(self):
        response = Mock(status_code=200)
        response.json.return_value = {
            "ok": False,
            "error": "unexpected-error-with-user-content-123456",
        }

        with (
            patch.object(email_service.requests, "post", return_value=response),
            self.assertLogs("email_service", level="WARNING") as captured,
        ):
            with self.assertRaises(RuntimeError):
                email_service.send_message(self._plain_message())

        self.assertNotIn("unexpected-error-with-user-content", "\n".join(captured.output))

    def test_invalid_json_response_fails_safely(self):
        response = Mock(status_code=200)
        response.json.side_effect = ValueError("private content 123456")

        with (
            patch.object(email_service.requests, "post", return_value=response),
            self.assertLogs("email_service", level="WARNING") as captured,
        ):
            with self.assertRaisesRegex(RuntimeError, "invalid response"):
                email_service.send_message(self._plain_message())

        log_output = "\n".join(captured.output)
        self.assertNotIn(self.secret, log_output)
        self.assertNotIn("123456", log_output)
        self.assertNotIn("private content", log_output)

    def test_timeout_fails_safely_without_logging_exception_text(self):
        error_text = f"private timeout containing {self.secret} and 123456"

        with (
            patch.object(
                email_service.requests,
                "post",
                side_effect=email_service.requests.Timeout(error_text),
            ),
            self.assertLogs("email_service", level="WARNING") as captured,
        ):
            with self.assertRaisesRegex(RuntimeError, "timed out"):
                email_service.send_message(self._plain_message())

        log_output = "\n".join(captured.output)
        self.assertIn("timed out", log_output)
        self.assertNotIn(self.secret, log_output)
        self.assertNotIn("123456", log_output)
        self.assertNotIn("private timeout", log_output)

    def test_connection_failure_logs_only_exception_type(self):
        error_text = f"private connection data {self.secret}"

        with (
            patch.object(
                email_service.requests,
                "post",
                side_effect=email_service.requests.ConnectionError(error_text),
            ),
            self.assertLogs("email_service", level="WARNING") as captured,
        ):
            with self.assertRaisesRegex(RuntimeError, "request failed"):
                email_service.send_message(self._plain_message())

        log_output = "\n".join(captured.output)
        self.assertIn("ConnectionError", log_output)
        self.assertNotIn(self.secret, log_output)
        self.assertNotIn("private connection data", log_output)

    def test_missing_configuration_is_reported_without_values(self):
        with (
            patch.dict(os.environ, {}, clear=True),
            self.assertLogs("email_service", level="ERROR") as captured,
        ):
            with self.assertRaisesRegex(RuntimeError, "GAS_EMAIL_RELAY_URL"):
                email_service.send_message(self._plain_message())

        self.assertNotIn(self.secret, "\n".join(captured.output))

    def test_invalid_relay_url_is_rejected_before_request(self):
        with (
            patch.dict(
                os.environ,
                {"GAS_EMAIL_RELAY_URL": "http://example.test/exec"},
            ),
            patch.object(email_service.requests, "post") as post,
            self.assertLogs("email_service", level="ERROR"),
        ):
            with self.assertRaisesRegex(RuntimeError, "HTTPS web-app URL"):
                email_service.send_message(self._plain_message())

        post.assert_not_called()

    def test_short_secret_is_rejected_before_request(self):
        with (
            patch.dict(os.environ, {"GAS_EMAIL_RELAY_SECRET": "too-short"}),
            patch.object(email_service.requests, "post") as post,
            self.assertLogs("email_service", level="ERROR"),
        ):
            with self.assertRaisesRegex(RuntimeError, "32 to 256"):
                email_service.send_message(self._plain_message())

        post.assert_not_called()

    def test_invalid_recipient_subject_and_empty_body_are_rejected(self):
        invalid_messages = []

        invalid_recipient = self._plain_message()
        invalid_recipient.replace_header("To", "not-an-email")
        invalid_messages.append((invalid_recipient, "recipient"))

        missing_subject = self._plain_message()
        del missing_subject["Subject"]
        invalid_messages.append((missing_subject, "subject"))

        control_subject = self._plain_message()
        control_subject.replace_header("Subject", "Invalid\tsubject")
        invalid_messages.append((control_subject, "subject"))

        long_subject = self._plain_message()
        long_subject.replace_header("Subject", "x" * 251)
        invalid_messages.append((long_subject, "subject"))

        empty_body = EmailMessage()
        empty_body["To"] = "reader@example.test"
        empty_body["Subject"] = "Test"
        empty_body.set_content("")
        invalid_messages.append((empty_body, "body"))

        oversized_body = self._plain_message()
        oversized_body.set_content("x" * (email_service.MAX_EMAIL_BODY_BYTES + 1))
        invalid_messages.append((oversized_body, "size limit"))

        with patch.object(email_service.requests, "post") as post:
            for message, expected_error in invalid_messages:
                with self.subTest(expected_error=expected_error):
                    with self.assertRaisesRegex(RuntimeError, expected_error):
                        email_service.send_message(message)

        post.assert_not_called()

    @staticmethod
    def _plain_message() -> EmailMessage:
        message = EmailMessage()
        message["To"] = "reader@example.test"
        message["Subject"] = "Your Resight verification code"
        message.set_content("Your code is 123456.")
        return message


if __name__ == "__main__":
    unittest.main()
