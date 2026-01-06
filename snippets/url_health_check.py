# snippet: url_health_check
"""
n8n Python Code Node: URL Health Check
Quick validation to filter out low-quality company prospects by checking if their website is accessible.

Input: Expects items with a 'url' or 'website' field
Output: health_passed, health_score, health_issues, health_data
"""

import requests

REQUEST_TIMEOUT = 5
USER_AGENT = "Mozilla/5.0 (compatible; ProspectValidator/1.0)"


def check_health(url: str) -> dict:
    """Quick health check on a URL."""
    result = {
        "url_checked": None,
        "health_passed": False,
        "health_score": 0,
        "health_issues": [],
        "health_data": {
            "status_code": None,
            "response_time_ms": None,
            "final_url": None,
        },
    }

    if not url:
        result["health_issues"].append("No URL provided")
        return result

    # Normalize URL
    if not url.startswith(('http://', 'https://')):
        url = f"https://{url}"
    result["url_checked"] = url

    headers = {"User-Agent": USER_AGENT}

    import time
    start_time = time.time()

    try:
        # HEAD is faster, but some servers block it - fallback to GET
        response = requests.head(url, timeout=REQUEST_TIMEOUT, allow_redirects=True, headers=headers)
        if response.status_code == 405:
            response = requests.get(url, timeout=REQUEST_TIMEOUT, allow_redirects=True, headers=headers)

        response_time_ms = int((time.time() - start_time) * 1000)

        result["health_data"]["status_code"] = response.status_code
        result["health_data"]["response_time_ms"] = response_time_ms
        result["health_data"]["final_url"] = response.url

        if response.status_code >= 400:
            result["health_issues"].append(f"HTTP {response.status_code}")
            result["health_score"] = 0
        else:
            result["health_passed"] = True
            # Score based on response time
            if response_time_ms < 500:
                result["health_score"] = 100
            elif response_time_ms < 1000:
                result["health_score"] = 90
            elif response_time_ms < 2000:
                result["health_score"] = 75
            elif response_time_ms < 3000:
                result["health_score"] = 50
            else:
                result["health_score"] = 25
                result["health_issues"].append("Slow response")

    except requests.exceptions.Timeout:
        result["health_issues"].append("Timeout")
    except requests.exceptions.SSLError:
        result["health_issues"].append("SSL Error")
    except requests.exceptions.ConnectionError:
        result["health_issues"].append("Connection Failed")
    except requests.exceptions.TooManyRedirects:
        result["health_issues"].append("Too Many Redirects")
    except Exception as e:
        result["health_issues"].append(f"Error: {str(e)[:50]}")

    return result


# --- n8n Code Node Entry Point ---
output = []

for item in _input.all():
    data = item.json
    url = data.get("url_checked") or data.get("url") or data.get("website") or data.get("company_url") or data.get("domain")

    check_result = check_health(url)
    output.append({**data, **check_result})

return output
