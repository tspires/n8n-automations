"""Tests for site_seo_check snippet."""

import pytest
from unittest.mock import patch, Mock
import requests

from conftest import load_snippet_function

check_seo = load_snippet_function("site_seo_check", "check_seo")


class TestCheckSeo:
    """Tests for the check_seo function."""

    def test_empty_url(self):
        """Should return failure for empty URL."""
        result = check_seo("")
        assert result["seo_passed"] is False
        assert "No URL provided" in result["seo_issues"]

    @patch("requests.get")
    @patch("requests.head")
    def test_good_seo(self, mock_head, mock_get, sample_html):
        """Should pass for well-optimized page."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = sample_html
        mock_response.content = sample_html.encode()
        mock_response.url = "https://example.com"
        mock_response.headers = {"Content-Encoding": "gzip"}
        mock_get.return_value = mock_response
        mock_head.return_value = Mock(status_code=200)

        with patch("time.time", side_effect=[0, 0.5]):
            result = check_seo("example.com")

        assert result["seo_passed"] is True
        assert result["seo_score"] >= 50
        assert result["seo_data"]["title"] is not None
        assert result["seo_data"]["has_https"] is True
        assert result["seo_data"]["has_viewport"] is True

    @patch("requests.get")
    @patch("requests.head")
    def test_missing_title(self, mock_head, mock_get):
        """Should flag missing title."""
        html = "<html><head></head><body><h1>Welcome</h1></body></html>"
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = html
        mock_response.content = html.encode()
        mock_response.url = "https://example.com"
        mock_response.headers = {}
        mock_get.return_value = mock_response

        with patch("time.time", side_effect=[0, 0.5]):
            result = check_seo("example.com")

        assert "Missing title" in result["seo_issues"]
        assert result["seo_data"]["title"] is None

    @patch("requests.get")
    @patch("requests.head")
    def test_missing_description(self, mock_head, mock_get):
        """Should flag missing meta description."""
        html = "<html><head><title>Test</title></head><body></body></html>"
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = html
        mock_response.content = html.encode()
        mock_response.url = "https://example.com"
        mock_response.headers = {}
        mock_get.return_value = mock_response

        with patch("time.time", side_effect=[0, 0.5]):
            result = check_seo("example.com")

        assert "Missing meta description" in result["seo_issues"]

    @patch("requests.get")
    @patch("requests.head")
    def test_not_https(self, mock_head, mock_get):
        """Should flag non-HTTPS sites."""
        html = "<html><head><title>Test</title></head><body></body></html>"
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = html
        mock_response.content = html.encode()
        mock_response.url = "http://example.com"  # HTTP, not HTTPS
        mock_response.headers = {}
        mock_get.return_value = mock_response

        with patch("time.time", side_effect=[0, 0.5]):
            result = check_seo("http://example.com")

        assert result["seo_passed"] is False
        assert "Not using HTTPS" in result["seo_issues"]
        assert result["seo_data"]["has_https"] is False

    @patch("requests.get")
    @patch("requests.head")
    def test_missing_viewport(self, mock_head, mock_get):
        """Should flag missing viewport meta (not mobile-friendly)."""
        html = "<html><head><title>Test</title></head><body></body></html>"
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = html
        mock_response.content = html.encode()
        mock_response.url = "https://example.com"
        mock_response.headers = {}
        mock_get.return_value = mock_response

        with patch("time.time", side_effect=[0, 0.5]):
            result = check_seo("example.com")

        assert "Missing viewport (not mobile-friendly)" in result["seo_issues"]
        assert result["seo_data"]["has_viewport"] is False

    @patch("requests.get")
    @patch("requests.head")
    def test_multiple_h1(self, mock_head, mock_get):
        """Should flag multiple H1 tags."""
        html = """
        <html>
        <head><title>Test</title></head>
        <body>
            <h1>First Heading</h1>
            <h1>Second Heading</h1>
            <h1>Third Heading</h1>
        </body>
        </html>
        """
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = html
        mock_response.content = html.encode()
        mock_response.url = "https://example.com"
        mock_response.headers = {}
        mock_get.return_value = mock_response

        with patch("time.time", side_effect=[0, 0.5]):
            result = check_seo("example.com")

        assert "Multiple H1 tags (3)" in result["seo_issues"]
        assert result["seo_data"]["h1_count"] == 3

    @patch("requests.get")
    @patch("requests.head")
    def test_nested_h1(self, mock_head, mock_get):
        """Should handle H1 with nested elements."""
        html = """
        <html>
        <head><title>Test</title></head>
        <body>
            <h1><span class="icon"></span>Welcome to Our Site</h1>
        </body>
        </html>
        """
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = html
        mock_response.content = html.encode()
        mock_response.url = "https://example.com"
        mock_response.headers = {}
        mock_get.return_value = mock_response

        with patch("time.time", side_effect=[0, 0.5]):
            result = check_seo("example.com")

        assert result["seo_data"]["h1_text"] == "Welcome to Our Site"
        assert result["seo_data"]["h1_count"] == 1

    @patch("requests.get")
    @patch("requests.head")
    def test_images_without_alt(self, mock_head, mock_get):
        """Should count images without alt text."""
        html = """
        <html>
        <head><title>Test</title></head>
        <body>
            <img src="1.jpg" alt="Good image">
            <img src="2.jpg">
            <img src="3.jpg">
            <img src="4.jpg">
            <img src="5.jpg">
        </body>
        </html>
        """
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = html
        mock_response.content = html.encode()
        mock_response.url = "https://example.com"
        mock_response.headers = {}
        mock_get.return_value = mock_response

        with patch("time.time", side_effect=[0, 0.5]):
            result = check_seo("example.com")

        assert result["seo_data"]["images_without_alt"] == 4
        assert "4 images missing alt" in result["seo_issues"]

    @patch("requests.get")
    @patch("requests.head")
    def test_detects_structured_data(self, mock_head, mock_get):
        """Should detect JSON-LD structured data."""
        html = """
        <html>
        <head>
            <title>Test</title>
            <script type="application/ld+json">{"@context": "https://schema.org"}</script>
        </head>
        <body></body>
        </html>
        """
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = html
        mock_response.content = html.encode()
        mock_response.url = "https://example.com"
        mock_response.headers = {}
        mock_get.return_value = mock_response

        with patch("time.time", side_effect=[0, 0.5]):
            result = check_seo("example.com")

        assert result["seo_data"]["has_structured_data"] is True

    @patch("requests.get")
    def test_timeout(self, mock_get):
        """Should handle timeout."""
        mock_get.side_effect = requests.exceptions.Timeout()

        result = check_seo("example.com")

        assert result["seo_passed"] is False
        assert "Timeout" in result["seo_issues"]
