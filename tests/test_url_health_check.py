"""Tests for url_health_check snippet."""

import pytest
from unittest.mock import patch, Mock
import requests

from conftest import load_snippet_function

# Load the check function
check_health = load_snippet_function("url_health_check", "check_health")


class TestCheckHealth:
    """Tests for the check_health function."""

    def test_empty_url(self):
        """Should return failure for empty URL."""
        result = check_health("")
        assert result["health_passed"] is False
        assert result["health_score"] == 0
        assert "No URL provided" in result["health_issues"]

    def test_none_url(self):
        """Should return failure for None URL."""
        result = check_health(None)
        assert result["health_passed"] is False
        assert "No URL provided" in result["health_issues"]

    @patch("requests.head")
    def test_successful_fast_response(self, mock_head):
        """Should pass with high score for fast response."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.url = "https://example.com"
        mock_head.return_value = mock_response

        with patch("time.time", side_effect=[0, 0.3]):  # 300ms response
            result = check_health("example.com")

        assert result["health_passed"] is True
        assert result["health_score"] == 100
        assert result["health_issues"] == []
        assert result["url_checked"] == "https://example.com"
        assert result["health_data"]["status_code"] == 200

    @patch("requests.head")
    def test_successful_slow_response(self, mock_head):
        """Should pass with lower score for slow response."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.url = "https://example.com"
        mock_head.return_value = mock_response

        with patch("time.time", side_effect=[0, 2.5]):  # 2500ms response
            result = check_health("https://example.com")

        assert result["health_passed"] is True
        assert result["health_score"] == 50
        assert "Slow response" in result["health_issues"]

    @patch("requests.head")
    @patch("requests.get")
    def test_head_blocked_fallback_to_get(self, mock_get, mock_head):
        """Should fallback to GET when HEAD returns 405."""
        mock_head_response = Mock()
        mock_head_response.status_code = 405
        mock_head.return_value = mock_head_response

        mock_get_response = Mock()
        mock_get_response.status_code = 200
        mock_get_response.url = "https://example.com"
        mock_get.return_value = mock_get_response

        with patch("time.time", side_effect=[0, 0.5]):
            result = check_health("example.com")

        assert result["health_passed"] is True
        mock_get.assert_called_once()

    @patch("requests.head")
    def test_http_error(self, mock_head):
        """Should fail for HTTP errors."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.url = "https://example.com"
        mock_head.return_value = mock_response

        with patch("time.time", side_effect=[0, 0.5]):
            result = check_health("example.com")

        assert result["health_passed"] is False
        assert result["health_score"] == 0
        assert "HTTP 404" in result["health_issues"]

    @patch("requests.head")
    def test_timeout(self, mock_head):
        """Should handle timeout exception."""
        mock_head.side_effect = requests.exceptions.Timeout()

        result = check_health("example.com")

        assert result["health_passed"] is False
        assert "Timeout" in result["health_issues"]

    @patch("requests.head")
    def test_ssl_error(self, mock_head):
        """Should handle SSL error."""
        mock_head.side_effect = requests.exceptions.SSLError()

        result = check_health("example.com")

        assert result["health_passed"] is False
        assert "SSL Error" in result["health_issues"]

    @patch("requests.head")
    def test_connection_error(self, mock_head):
        """Should handle connection error."""
        mock_head.side_effect = requests.exceptions.ConnectionError()

        result = check_health("example.com")

        assert result["health_passed"] is False
        assert "Connection Failed" in result["health_issues"]

    def test_url_normalization(self):
        """Should add https:// to URLs without scheme."""
        with patch("requests.head") as mock_head:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.url = "https://example.com"
            mock_head.return_value = mock_response

            with patch("time.time", side_effect=[0, 0.5]):
                result = check_health("example.com")

            assert result["url_checked"] == "https://example.com"

    def test_preserves_http_scheme(self):
        """Should preserve http:// if explicitly provided."""
        with patch("requests.head") as mock_head:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.url = "http://example.com"
            mock_head.return_value = mock_response

            with patch("time.time", side_effect=[0, 0.5]):
                result = check_health("http://example.com")

            assert result["url_checked"] == "http://example.com"
