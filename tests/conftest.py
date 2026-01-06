"""
Pytest fixtures and configuration for snippet tests.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import sys
from pathlib import Path
import builtins

# Add snippets directory to path for imports
SNIPPETS_DIR = Path(__file__).parent.parent / "snippets"
sys.path.insert(0, str(SNIPPETS_DIR))


def load_snippet_function(snippet_name: str, function_name: str):
    """
    Load a specific function from a snippet file without executing the n8n entry point.
    """
    snippet_path = SNIPPETS_DIR / f"{snippet_name}.py"
    with open(snippet_path) as f:
        code = f.read()

    # Remove the n8n entry point (everything after "# --- n8n Code Node Entry Point ---")
    if "# --- n8n Code Node Entry Point ---" in code:
        code = code.split("# --- n8n Code Node Entry Point ---")[0]

    # Create a namespace and exec the code
    namespace = {"__builtins__": builtins}

    # Add required imports to namespace
    import re
    import time
    import socket
    import ssl
    import requests
    from datetime import datetime, timezone
    from urllib.parse import urlparse, urljoin

    namespace.update({
        "re": re,
        "time": time,
        "socket": socket,
        "ssl": ssl,
        "requests": requests,
        "datetime": datetime,
        "timezone": timezone,
        "urlparse": urlparse,
        "urljoin": urljoin,
    })

    exec(code, namespace)
    return namespace.get(function_name)


@pytest.fixture
def mock_response():
    """Factory fixture to create mock HTTP responses."""
    def _create_response(
        status_code=200,
        text="",
        content=b"",
        url="https://example.com",
        headers=None
    ):
        response = Mock()
        response.status_code = status_code
        response.text = text
        response.content = content or text.encode()
        response.url = url
        response.headers = headers or {}
        return response
    return _create_response


@pytest.fixture
def sample_html():
    """Sample HTML for testing."""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Example Company - Leading Solutions</title>
        <meta name="description" content="We provide leading solutions for your business needs.">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <meta property="og:title" content="Example Company">
        <link rel="canonical" href="https://example.com">
    </head>
    <body>
        <h1>Welcome to Example Company</h1>
        <p>We are a leading provider of business solutions. Our team of experts
        is dedicated to helping you succeed. Contact us today to learn more about
        how we can help your business grow and thrive in the modern marketplace.</p>
        <p>Email: contact@example-company.com</p>
        <p>Phone: (555) 123-4567</p>
        <a href="https://linkedin.com/company/example-company">LinkedIn</a>
        <a href="https://twitter.com/exampleco">Twitter</a>
        <img src="logo.png" alt="Company Logo">
        <script src="https://www.google-analytics.com/analytics.js"></script>
    </body>
    </html>
    """


@pytest.fixture
def parked_domain_html():
    """HTML for a parked domain."""
    return """
    <!DOCTYPE html>
    <html>
    <head><title>Domain For Sale</title></head>
    <body>
        <h1>This domain is for sale!</h1>
        <p>Buy this domain at GoDaddy.com</p>
    </body>
    </html>
    """


@pytest.fixture
def under_construction_html():
    """HTML for an under construction page."""
    return """
    <!DOCTYPE html>
    <html>
    <head><title>Coming Soon</title></head>
    <body>
        <h1>Under Construction</h1>
        <p>We're working on something great. Check back soon!</p>
    </body>
    </html>
    """


@pytest.fixture
def minimal_html():
    """Minimal HTML with very little content."""
    return """
    <!DOCTYPE html>
    <html>
    <head><title>Test</title></head>
    <body><p>Hello</p></body>
    </html>
    """


@pytest.fixture
def no_contact_html():
    """HTML with no contact information."""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Privacy First Company</title>
        <meta name="viewport" content="width=device-width">
    </head>
    <body>
        <h1>Welcome</h1>
        <p>We value your privacy. Our company provides excellent services
        to customers worldwide. We have been in business for many years
        and continue to grow and expand our offerings to meet the needs
        of our diverse customer base.</p>
    </body>
    </html>
    """
