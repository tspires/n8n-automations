# snippet: url_health_check
"""
n8n Python Code Node: URL Health Check
Quick validation to filter out low-quality company prospects by checking if their website is accessible.

Input: Expects items with a 'url' or 'website' field
Output: Adds 'url_valid', 'url_status_code', and 'url_error' fields
"""

import requests
from urllib.parse import urlparse

def check_url(url: str, timeout: int = 5) -> dict:
    """
    Quick health check on a URL using HEAD request.
    Returns status info for filtering prospects.
    """
    result = {
        "url_valid": False,
        "url_status_code": None,
        "url_error": None,
        "url_checked": url
    }

    if not url:
        result["url_error"] = "No URL provided"
        return result

    # Normalize URL - add https:// if no scheme
    if not url.startswith(('http://', 'https://')):
        url = f"https://{url}"

    try:
        # HEAD request is faster than GET - just checks if server responds
        response = requests.head(
            url,
            timeout=timeout,
            allow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (compatible; ProspectValidator/1.0)"}
        )
        result["url_status_code"] = response.status_code
        result["url_valid"] = response.status_code < 400

    except requests.exceptions.Timeout:
        result["url_error"] = "Timeout"
    except requests.exceptions.SSLError:
        result["url_error"] = "SSL Error"
    except requests.exceptions.ConnectionError:
        result["url_error"] = "Connection Failed"
    except requests.exceptions.TooManyRedirects:
        result["url_error"] = "Too Many Redirects"
    except Exception as e:
        result["url_error"] = str(e)[:100]

    return result


# --- n8n Code Node Entry Point ---
# This runs when executed in n8n's Python Code node

output = []

for item in _input.all():
    data = item.json

    # Look for URL in common field names
    url = data.get("url") or data.get("website") or data.get("company_url") or data.get("domain")

    # Run the health check
    check_result = check_url(url)

    # Merge results with original data
    output.append({**data, **check_result})

return output
