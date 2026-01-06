"""Tests for company_maturity snippet."""

import pytest
from unittest.mock import patch, Mock, MagicMock
import requests
import socket

from conftest import load_snippet_function

check_maturity = load_snippet_function("company_maturity", "check_maturity")


class TestCheckMaturity:
    """Tests for the check_maturity function."""

    def test_empty_url(self):
        """Should return failure for empty URL."""
        result = check_maturity("")
        assert result["maturity_passed"] is False
        assert "No URL provided" in result["maturity_issues"]

    @patch("requests.get")
    @patch("socket.create_connection")
    def test_has_ssl(self, mock_socket, mock_get):
        """Should detect SSL certificate."""
        # Mock SSL connection
        mock_ssl_socket = MagicMock()
        mock_ssl_socket.getpeercert.return_value = {
            "issuer": [[("organizationName", "DigiCert")]],
            "notAfter": "Jan 01 00:00:00 2026 GMT"
        }

        mock_context = MagicMock()
        mock_context.wrap_socket.return_value.__enter__ = Mock(return_value=mock_ssl_socket)
        mock_context.wrap_socket.return_value.__exit__ = Mock(return_value=False)

        mock_conn = MagicMock()
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)
        mock_socket.return_value = mock_conn

        with patch("ssl.create_default_context", return_value=mock_context):
            with patch.object(mock_context, "wrap_socket") as mock_wrap:
                mock_wrap.return_value.__enter__ = Mock(return_value=mock_ssl_socket)
                mock_wrap.return_value.__exit__ = Mock(return_value=False)

                mock_get.return_value = Mock(
                    status_code=200,
                    text="<html></html>",
                    headers={}
                )

                result = check_maturity("example.com")

        assert result["maturity_data"]["has_ssl"] is True

    @patch("requests.get")
    @patch("socket.create_connection")
    def test_no_ssl(self, mock_socket, mock_get):
        """Should handle missing SSL."""
        mock_socket.side_effect = socket.error("Connection refused")
        mock_get.return_value = Mock(
            status_code=200,
            text="<html></html>",
            headers={}
        )

        result = check_maturity("example.com")

        assert result["maturity_data"]["has_ssl"] is False
        assert "No SSL certificate" in result["maturity_issues"]

    @patch("requests.get")
    @patch("socket.create_connection")
    def test_detects_tech_stack(self, mock_socket, mock_get):
        """Should detect technology stack from page content."""
        html = """
        <html>
        <head>
            <script src="https://www.google-analytics.com/analytics.js"></script>
        </head>
        <body>
            <div class="wp-content">WordPress site</div>
            <script src="https://js.stripe.com/v3/"></script>
        </body>
        </html>
        """
        mock_socket.side_effect = socket.error()
        mock_get.return_value = Mock(
            status_code=200,
            text=html,
            headers={"Server": "nginx"}
        )

        result = check_maturity("example.com")

        tech = result["maturity_data"]["tech_stack"]
        assert "wordpress" in tech
        assert "google_analytics" in tech
        assert "stripe" in tech
        assert "nginx" in tech

    @patch("requests.get")
    @patch("socket.create_connection")
    def test_business_tools_bonus(self, mock_socket, mock_get):
        """Should give bonus for business tools."""
        html = """
        <html>
        <script src="https://js.hubspot.com/"></script>
        <script src="https://widget.intercom.io/"></script>
        </html>
        """
        mock_socket.side_effect = socket.error()
        mock_get.return_value = Mock(
            status_code=200,
            text=html,
            headers={}
        )

        result = check_maturity("example.com")

        assert result["maturity_data"]["has_business_tools"] is True
        # Should get tech stack bonus + business tools bonus
        assert result["maturity_score"] > 0

    @patch("requests.get")
    @patch("socket.create_connection")
    def test_mx_records_with_dns(self, mock_socket, mock_get):
        """Should check MX records using dns.resolver."""
        mock_socket.side_effect = socket.error()
        mock_get.return_value = Mock(
            status_code=200,
            text="<html></html>",
            headers={}
        )

        # Mock dns.resolver
        mock_resolver = MagicMock()
        mock_resolver.resolve.return_value = [Mock()]

        with patch.dict("sys.modules", {"dns.resolver": mock_resolver}):
            with patch("dns.resolver.resolve", return_value=[Mock()]):
                result = check_maturity("example.com")

        assert result["maturity_data"]["has_mx_records"] is True

    @patch("requests.get")
    @patch("socket.create_connection")
    def test_score_calculation(self, mock_socket, mock_get):
        """Should calculate score based on signals."""
        html = """
        <html>
        <script src="https://www.google-analytics.com/analytics.js"></script>
        <script src="https://js.hubspot.com/"></script>
        </html>
        """

        # Mock SSL success
        mock_ssl_socket = MagicMock()
        mock_ssl_socket.getpeercert.return_value = {
            "issuer": [[("organizationName", "DigiCert")]],
            "notAfter": "Jan 01 00:00:00 2026 GMT"
        }

        mock_conn = MagicMock()
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)
        mock_socket.return_value = mock_conn

        mock_context = MagicMock()

        with patch("ssl.create_default_context", return_value=mock_context):
            mock_context.wrap_socket.return_value.__enter__ = Mock(return_value=mock_ssl_socket)
            mock_context.wrap_socket.return_value.__exit__ = Mock(return_value=False)

            mock_get.return_value = Mock(
                status_code=200,
                text=html,
                headers={}
            )

            result = check_maturity("example.com")

        # Should have SSL (20) + tech stack + business tools
        assert result["maturity_score"] >= 20
        assert result["maturity_data"]["has_ssl"] is True

    @patch("requests.get")
    @patch("socket.create_connection")
    def test_passed_requires_ssl(self, mock_socket, mock_get):
        """Should require SSL for passed status."""
        html = "<script src='https://js.hubspot.com/'></script>" * 10
        mock_socket.side_effect = socket.error()
        mock_get.return_value = Mock(
            status_code=200,
            text=html,
            headers={}
        )

        result = check_maturity("example.com")

        # Even with high tech stack score, should fail without SSL
        assert result["maturity_passed"] is False

    @patch("requests.get")
    def test_fetch_error(self, mock_get):
        """Should handle page fetch errors."""
        mock_get.side_effect = requests.exceptions.Timeout()

        with patch("socket.create_connection", side_effect=socket.error()):
            result = check_maturity("example.com")

        assert "Could not fetch page" in result["maturity_issues"]
