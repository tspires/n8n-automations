"""Tests for business_legitimacy snippet."""

import pytest
from unittest.mock import patch, Mock
import requests

from conftest import load_snippet_function

check_legitimacy = load_snippet_function("business_legitimacy", "check_legitimacy")


class TestCheckLegitimacy:
    """Tests for the check_legitimacy function."""

    def test_empty_url(self):
        """Should return failure for empty URL."""
        result = check_legitimacy("")
        assert result["legitimacy_passed"] is False
        assert "No URL provided" in result["legitimacy_issues"]

    @patch("requests.get")
    def test_legitimate_business(self, mock_get, sample_html):
        """Should pass for legitimate business site."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = sample_html
        mock_response.url = "https://example.com"
        mock_get.return_value = mock_response

        result = check_legitimacy("example.com")

        assert result["legitimacy_passed"] is True
        assert result["legitimacy_score"] >= 80
        assert result["legitimacy_issues"] == []
        assert result["legitimacy_data"]["word_count"] > 50

    @patch("requests.get")
    def test_parked_domain(self, mock_get, parked_domain_html):
        """Should detect parked domain."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = parked_domain_html
        mock_response.url = "https://example.com"
        mock_get.return_value = mock_response

        result = check_legitimacy("example.com")

        assert result["legitimacy_passed"] is False
        assert "Parked domain" in result["legitimacy_issues"]

    @patch("requests.get")
    def test_under_construction(self, mock_get, under_construction_html):
        """Should detect under construction page."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = under_construction_html
        mock_response.url = "https://example.com"
        mock_get.return_value = mock_response

        result = check_legitimacy("example.com")

        assert result["legitimacy_passed"] is False
        assert "Under construction" in result["legitimacy_issues"]

    @patch("requests.get")
    def test_low_word_count(self, mock_get, minimal_html):
        """Should flag low word count."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = minimal_html
        mock_response.url = "https://example.com"
        mock_get.return_value = mock_response

        result = check_legitimacy("example.com")

        assert result["legitimacy_passed"] is False
        assert "Low word count" in result["legitimacy_issues"]
        assert result["legitimacy_data"]["word_count"] < 50

    @patch("requests.get")
    def test_redirect_to_different_domain(self, mock_get):
        """Should flag redirect to different domain."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "<html><body>" + ("word " * 100) + "</body></html>"
        mock_response.url = "https://other-domain.com"
        mock_get.return_value = mock_response

        result = check_legitimacy("https://example.com")

        assert "Redirects to other-domain.com" in result["legitimacy_issues"]
        assert result["legitimacy_data"]["redirected_to"] == "other-domain.com"

    @patch("requests.get")
    def test_http_error(self, mock_get):
        """Should handle HTTP errors."""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.url = "https://example.com"
        mock_get.return_value = mock_response

        result = check_legitimacy("example.com")

        assert result["legitimacy_passed"] is False
        assert "HTTP 500" in result["legitimacy_issues"]

    @patch("requests.get")
    def test_timeout(self, mock_get):
        """Should handle timeout."""
        mock_get.side_effect = requests.exceptions.Timeout()

        result = check_legitimacy("example.com")

        assert result["legitimacy_passed"] is False
        assert "Timeout" in result["legitimacy_issues"]

    @patch("requests.get")
    def test_lorem_ipsum(self, mock_get):
        """Should detect placeholder lorem ipsum content."""
        html = "<html><body>" + ("word " * 60) + "Lorem ipsum dolor sit amet</body></html>"
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = html
        mock_response.url = "https://example.com"
        mock_get.return_value = mock_response

        result = check_legitimacy("example.com")

        assert "Placeholder content" in result["legitimacy_issues"]

    @patch("requests.get")
    def test_score_calculation(self, mock_get):
        """Should calculate score correctly based on issues."""
        # 2 issues = 100 - 50 = 50
        html = "<html><body>Lorem ipsum " + ("word " * 10) + "</body></html>"
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = html
        mock_response.url = "https://example.com"
        mock_get.return_value = mock_response

        result = check_legitimacy("example.com")

        # Should have "Placeholder content" and "Low word count"
        assert len(result["legitimacy_issues"]) >= 2
        assert result["legitimacy_score"] <= 50
