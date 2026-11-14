import os
import sys
import unittest
from email.message import EmailMessage
from pathlib import Path
from unittest.mock import Mock, patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import email_service
import email_utils


class ResendEmailServiceTests(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict(
            os.environ,
            {
                "RESEND_API_KEY": "test-resend-key",
                "RESEND_FROM_EMAIL": "Resight <notifications@example.test>",
            },
        )
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def test_sends_plain_text_email_with_resend_api(self):
        message = EmailMessage()
        message["To"] = "Reader <reader@example.test>"
        message["Subject"] = "Your Resight verification code"
        message.set_content("Your code is 123456.")
        response = Mock(status_code=200)

        with patch.object(email_service.requests, "post", return_value=response) as post:
            email_service.send_message(message)

        self.assertEqual(post.call_args.args[0], email_service.RESEND_EMAILS_URL)
        self.assertEqual(
            post.call_args.kwargs["headers"]["Authorization"],
            "Bearer test-resend-key",
        )
        self.assertEqual(
            post.call_args.kwargs["json"],
            {
                "from": "Resight <notifications@example.test>",
                "to": ["reader@example.test"],
                "subject": "Your Resight verification code",
                "text": "Your code is 123456.\n",
            },
        )
        self.assertEqual(post.call_args.kwargs["timeout"], 10)

    def test_sends_html_email_body(self):
        message = EmailMessage()
        message["To"] = "reader@example.test"
        message["Subject"] = "Resight digest"
        message.add_alternative("<p>New research</p>", subtype="html")

        with patch.object(
            email_service.requests,
            "post",
            return_value=Mock(status_code=200),
        ) as post:
            email_service.send_message(message)

        payload = post.call_args.kwargs["json"]
        self.assertEqual(payload["html"], "<p>New research</p>\n")
        self.assertEqual(payload["to"], ["reader@example.test"])

    def test_signup_otp_email_content_is_preserved(self):
        with patch.object(email_utils, "send_message") as send_message:
            email_utils.send_otp_email("reader@example.test", "123456")

        message = send_message.call_args.args[0]
        self.assertEqual(message["Subject"], "Your Resight verification code")
        self.assertEqual(message["To"], "reader@example.test")
        self.assertIn("Your Resight verification code is:\n\n123456", message.get_content())
        self.assertIn("This code expires shortly.", message.get_content())

    def test_provider_error_logs_status_and_name_without_body_or_secrets(self):
        api_key = "test-resend-key"
        otp = "123456"
        response = Mock(status_code=403)
        response.json.return_value = {
            "name": "validation_error",
            "message": f"Sensitive response containing {api_key} and {otp}",
        }

        with (
            patch.object(email_service.requests, "post", return_value=response),
            self.assertLogs("email_service", level="WARNING") as captured,
        ):
            with self.assertRaisesRegex(RuntimeError, "HTTP 403"):
                email_service.send_message(self._plain_message())

        log_output = "\n".join(captured.output)
        self.assertIn("HTTP 403", log_output)
        self.assertIn("validation_error", log_output)
        self.assertNotIn(api_key, log_output)
        self.assertNotIn(otp, log_output)
        self.assertNotIn("Sensitive response", log_output)

    def test_request_failure_logs_exception_type_without_sensitive_text(self):
        api_key = "test-resend-key"
        otp = "123456"

        with (
            patch.object(
                email_service.requests,
                "post",
                side_effect=email_service.requests.Timeout(
                    f"failure {api_key} {otp}"
                ),
            ),
            self.assertLogs("email_service", level="WARNING") as captured,
        ):
            with self.assertRaisesRegex(RuntimeError, "provider request failed"):
                email_service.send_message(self._plain_message())

        log_output = "\n".join(captured.output)
        self.assertIn("Timeout", log_output)
        self.assertNotIn(api_key, log_output)
        self.assertNotIn(otp, log_output)

    def test_missing_resend_configuration_is_reported_without_values(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "RESEND_API_KEY"):
                email_service.send_message(self._plain_message())

    @staticmethod
    def _plain_message() -> EmailMessage:
        message = EmailMessage()
        message["To"] = "reader@example.test"
        message["Subject"] = "Test message"
        message.set_content("Test body")
        return message


if __name__ == "__main__":
    unittest.main()
