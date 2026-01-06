"""Tests for prospect_validator (all-in-one) snippet."""

import pytest
from unittest.mock import patch, Mock, MagicMock
import requests
import socket

from conftest import load_snippet_function

validate_prospect = load_snippet_function("prospect_validator", "validate_prospect")


class TestValidateProspect:
    """Tests for the validate_prospect function."""

    def test_empty_url(self):
        """Should return failure for empty URL."""
        result = validate_prospect("")
        assert result["overall_passed"] is False
        assert result["health_passed"] is False
        assert "No URL provided" in result["health_issues"]

    @patch("requests.get")
    @patch("socket.create_connection")
    def test_full_validation_pass(self, mock_socket, mock_get, sample_html):
        """Should pass all checks for good site."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = sample_html
        mock_response.url = "https://example.com"
        mock_response.headers = {"Server": "nginx"}
        mock_get.return_value = mock_response

        # Mock SSL
        mock_ssl_socket = MagicMock()
        mock_ssl_socket.getpeercert.return_value = {
            "issuer": [[("organizationName", "DigiCert")]],
        }
        mock_conn = MagicMock()
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)
        mock_socket.return_value = mock_conn

        with patch("ssl.create_default_context") as mock_ctx:
            mock_ctx.return_value.wrap_socket.return_value.__enter__ = Mock(return_value=mock_ssl_socket)
            mock_ctx.return_value.wrap_socket.return_value.__exit__ = Mock(return_value=False)

            with patch("time.time", side_effect=[0, 0.5]):
                result = validate_prospect("example.com")

        assert result["health_passed"] is True
        assert result["legitimacy_passed"] is True
        assert result["contactability_passed"] is True
        assert result["overall_score"] >= 50

    @patch("requests.get")
    def test_http_error_stops_early(self, mock_get):
        """Should stop early on HTTP error."""
        mock_response = Mock()
        mock_response.status_code = 500

        with patch("time.time", side_effect=[0, 0.5]):
            mock_get.return_value = mock_response
            result = validate_prospect("example.com")

        assert result["health_passed"] is False
        assert "HTTP 500" in result["health_issues"]
        # Other checks should have default values
        assert result["legitimacy_passed"] is False
        assert result["seo_passed"] is False

    @patch("requests.get")
    @patch("socket.create_connection")
    def test_parked_domain_fails_legitimacy(self, mock_socket, mock_get, parked_domain_html):
        """Should fail legitimacy for parked domain."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = parked_domain_html
        mock_response.url = "https://example.com"
        mock_response.headers = {}
        mock_get.return_value = mock_response
        mock_socket.side_effect = socket.error()

        with patch("time.time", side_effect=[0, 0.5]):
            result = validate_prospect("example.com")

        assert result["health_passed"] is True
        assert result["legitimacy_passed"] is False
        assert "Parked domain" in result["legitimacy_issues"]

    @patch("requests.get")
    @patch("socket.create_connection")
    def test_extracts_contact_info(self, mock_socket, mock_get):
        """Should extract emails and phones."""
        html = """
        <html>
        <head><title>Test Company</title></head>
        <body>
            <p>Email: sales@testcompany.com</p>
            <p>Phone: (555) 123-4567</p>
            <a href="https://linkedin.com/company/testco">LinkedIn</a>
        </body>
        </html>
        """ + ("word " * 60)

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = html
        mock_response.url = "https://example.com"
        mock_response.headers = {}
        mock_get.return_value = mock_response
        mock_socket.side_effect = socket.error()

        with patch("time.time", side_effect=[0, 0.5]):
            result = validate_prospect("example.com")

        assert result["contactability_passed"] is True
        assert "sales@testcompany.com" in result["contactability_data"]["emails"]
        assert len(result["contactability_data"]["phones"]) > 0
        assert "linkedin" in result["contactability_data"]["social_links"]

    @patch("requests.get")
    @patch("socket.create_connection")
    def test_detects_tech_stack(self, mock_socket, mock_get):
        """Should detect technology stack."""
        html = """
        <html>
        <head><title>Test</title></head>
        <body>
            <div class="wp-content">WordPress</div>
            <script src="https://www.google-analytics.com/analytics.js"></script>
        </body>
        </html>
        """ + ("word " * 60)

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = html
        mock_response.url = "https://example.com"
        mock_response.headers = {"Server": "cloudflare"}
        mock_get.return_value = mock_response
        mock_socket.side_effect = socket.error()

        with patch("time.time", side_effect=[0, 0.5]):
            result = validate_prospect("example.com")

        tech = result["maturity_data"]["tech_stack"]
        assert "wordpress" in tech
        assert "google_analytics" in tech
        assert "cloudflare" in tech

    @patch("requests.get")
    @patch("socket.create_connection")
    def test_seo_checks(self, mock_socket, mock_get):
        """Should perform SEO checks."""
        html = """
        <html>
        <head>
            <title>Great Company Title</title>
            <meta name="viewport" content="width=device-width">
        </head>
        <body><h1>Welcome</h1></body>
        </html>
        """ + ("word " * 60)

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = html
        mock_response.url = "https://example.com"
        mock_response.headers = {}
        mock_get.return_value = mock_response
        mock_socket.side_effect = socket.error()

        with patch("time.time", side_effect=[0, 0.5]):
            result = validate_prospect("example.com")

        assert result["seo_data"]["title"] == "Great Company Title"
        assert result["seo_data"]["has_https"] is True
        assert result["seo_data"]["has_viewport"] is True

    @patch("requests.get")
    def test_timeout_handling(self, mock_get):
        """Should handle timeout gracefully."""
        mock_get.side_effect = requests.exceptions.Timeout()

        result = validate_prospect("example.com")

        assert result["health_passed"] is False
        assert "Timeout" in result["health_issues"]
        assert result["overall_passed"] is False

    @patch("requests.get")
    def test_ssl_error_handling(self, mock_get):
        """Should handle SSL errors."""
        mock_get.side_effect = requests.exceptions.SSLError()

        result = validate_prospect("example.com")

        assert result["health_passed"] is False
        assert "SSL Error" in result["health_issues"]

    @patch("requests.get")
    @patch("socket.create_connection")
    def test_overall_score_calculation(self, mock_socket, mock_get, sample_html):
        """Should calculate weighted overall score."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = sample_html
        mock_response.url = "https://example.com"
        mock_response.headers = {}
        mock_get.return_value = mock_response

        # Mock SSL success
        mock_ssl_socket = MagicMock()
        mock_conn = MagicMock()
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)
        mock_socket.return_value = mock_conn

        with patch("ssl.create_default_context") as mock_ctx:
            mock_ctx.return_value.wrap_socket.return_value.__enter__ = Mock(return_value=mock_ssl_socket)
            mock_ctx.return_value.wrap_socket.return_value.__exit__ = Mock(return_value=False)

            with patch("time.time", side_effect=[0, 0.5]):
                result = validate_prospect("example.com")

        # Check that overall score is a weighted average
        expected = (
            result["health_score"] * 0.10 +
            result["legitimacy_score"] * 0.25 +
            result["seo_score"] * 0.15 +
            result["contactability_score"] * 0.30 +
            result["maturity_score"] * 0.20
        )
        assert result["overall_score"] == round(expected)

    @patch("requests.get")
    @patch("socket.create_connection")
    def test_url_normalization(self, mock_socket, mock_get):
        """Should normalize URL with https://."""
        html = "<html><body>" + ("word " * 60) + "</body></html>"
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = html
        mock_response.url = "https://example.com"
        mock_response.headers = {}
        mock_get.return_value = mock_response
        mock_socket.side_effect = socket.error()

        with patch("time.time", side_effect=[0, 0.5]):
            result = validate_prospect("example.com")

        assert result["url_checked"] == "https://example.com"

    @patch("requests.get")
    @patch("socket.create_connection")
    def test_schema_consistency(self, mock_socket, mock_get, sample_html):
        """Should have consistent schema structure."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = sample_html
        mock_response.url = "https://example.com"
        mock_response.headers = {}
        mock_get.return_value = mock_response
        mock_socket.side_effect = socket.error()

        with patch("time.time", side_effect=[0, 0.5]):
            result = validate_prospect("example.com")

        # Check all expected fields exist
        for prefix in ["health", "legitimacy", "seo", "contactability", "maturity"]:
            assert f"{prefix}_passed" in result
            assert f"{prefix}_score" in result
            assert f"{prefix}_issues" in result
            assert f"{prefix}_data" in result

        assert "overall_passed" in result
        assert "overall_score" in result
        assert "url_checked" in result
