"""Tests for contactability snippet."""

import pytest
from unittest.mock import patch, Mock
import requests

from conftest import load_snippet_function

check_contactability = load_snippet_function("contactability", "check_contactability")


class TestCheckContactability:
    """Tests for the check_contactability function."""

    def test_empty_url(self):
        """Should return failure for empty URL."""
        result = check_contactability("")
        assert result["contactability_passed"] is False
        assert "No URL provided" in result["contactability_issues"]

    @patch("requests.get")
    @patch("requests.head")
    def test_finds_email(self, mock_head, mock_get):
        """Should extract email addresses."""
        html = """
        <html><body>
        Contact us at sales@example-company.com or support@example-company.com
        </body></html>
        """
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = html
        mock_get.return_value = mock_response

        result = check_contactability("example.com")

        assert result["contactability_passed"] is True
        assert "sales@example-company.com" in result["contactability_data"]["emails"]
        assert "support@example-company.com" in result["contactability_data"]["emails"]

    @patch("requests.get")
    @patch("requests.head")
    def test_finds_phone(self, mock_head, mock_get):
        """Should extract phone numbers."""
        html = """
        <html><body>
        Call us at (555) 123-4567 or 1-800-555-0199
        </body></html>
        """
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = html
        mock_get.return_value = mock_response

        result = check_contactability("example.com")

        assert result["contactability_passed"] is True
        assert len(result["contactability_data"]["phones"]) >= 1

    @patch("requests.get")
    @patch("requests.head")
    def test_finds_social_links(self, mock_head, mock_get):
        """Should extract social media links."""
        html = """
        <html><body>
        <a href="https://linkedin.com/company/example">LinkedIn</a>
        <a href="https://twitter.com/example">Twitter</a>
        <a href="https://facebook.com/example">Facebook</a>
        </body></html>
        """
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = html
        mock_get.return_value = mock_response

        result = check_contactability("example.com")

        social = result["contactability_data"]["social_links"]
        assert "linkedin" in social
        assert "twitter" in social
        assert "facebook" in social

    @patch("requests.get")
    @patch("requests.head")
    def test_filters_invalid_emails(self, mock_head, mock_get):
        """Should filter out invalid/placeholder emails."""
        html = """
        <html><body>
        test@example.com
        user@sentry.io
        real@company.com
        fake@wixpress.com
        </body></html>
        """
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = html
        mock_get.return_value = mock_response

        result = check_contactability("test-site.com")

        emails = result["contactability_data"]["emails"]
        assert "real@company.com" in emails
        assert "test@example.com" not in emails
        assert "user@sentry.io" not in emails
        assert "fake@wixpress.com" not in emails

    @patch("requests.get")
    @patch("requests.head")
    def test_no_contact_info(self, mock_head, mock_get, no_contact_html):
        """Should fail when no contact info found."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = no_contact_html
        mock_get.return_value = mock_response
        mock_head.side_effect = requests.exceptions.Timeout()

        result = check_contactability("example.com")

        assert result["contactability_passed"] is False
        assert "No email or phone found" in result["contactability_issues"]

    @patch("requests.get")
    @patch("requests.head")
    def test_score_with_linkedin(self, mock_head, mock_get):
        """Should give bonus score for LinkedIn presence."""
        html = """
        <html><body>
        <a href="https://linkedin.com/company/example">LinkedIn</a>
        Email: contact@company.com
        </body></html>
        """
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = html
        mock_get.return_value = mock_response

        result = check_contactability("example.com")

        # Email (35) + LinkedIn social (5) + LinkedIn bonus (10) = 50+
        assert result["contactability_score"] >= 50

    @patch("requests.get")
    def test_timeout(self, mock_get):
        """Should handle timeout."""
        mock_get.side_effect = requests.exceptions.Timeout()

        result = check_contactability("example.com")

        assert result["contactability_passed"] is False
        assert "Timeout" in result["contactability_issues"]

    @patch("requests.get")
    @patch("requests.head")
    def test_finds_contact_page(self, mock_head, mock_get):
        """Should find and scrape contact page."""
        main_html = '<html><body><a href="/contact">Contact Us</a></body></html>'
        contact_html = '<html><body>Email: sales@company.com Phone: 555-123-4567</body></html>'

        mock_get.side_effect = [
            Mock(status_code=200, text=main_html),
            Mock(status_code=200, text=contact_html),
        ]

        result = check_contactability("https://example.com")

        assert result["contactability_data"]["has_contact_page"] is True
        assert "sales@company.com" in result["contactability_data"]["emails"]

    @patch("requests.get")
    @patch("requests.head")
    def test_email_limit(self, mock_head, mock_get):
        """Should limit emails to 10."""
        emails = " ".join([f"user{i}@company.com" for i in range(20)])
        html = f"<html><body>{emails}</body></html>"

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = html
        mock_get.return_value = mock_response

        result = check_contactability("example.com")

        assert len(result["contactability_data"]["emails"]) <= 10
