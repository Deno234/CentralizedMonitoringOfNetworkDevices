"""
API utilities with retry logic and better error handling
"""

import requests
import time
from typing import Optional, Any

API_BASE = "http://localhost:5000"
MAX_RETRIES = 3
RETRY_DELAY = 1  # seconds
TIMEOUT = 5  # seconds


def api_get(path: str, retries: int = MAX_RETRIES) -> Optional[Any]:
    """
    Make GET request to API with automatic retry on failure

    Args:
        path: API endpoint path (e.g., "/api/devices")
        retries: Number of retry attempts (default: 3)

    Returns:
        JSON response or None if all retries failed
    """
    url = f"{API_BASE}{path}"

    for attempt in range(retries):
        try:
            response = requests.get(url, timeout=TIMEOUT)

            # Check if response is successful
            if response.status_code == 200:
                return response.json()

            # Handle different status codes
            elif response.status_code == 404:
                print(f"⚠️  Endpoint not found: {path}")
                return None

            elif response.status_code >= 500:
                # Server error - retry
                if attempt < retries - 1:
                    print(f"⚠️  Server error {response.status_code}, retrying... ({attempt + 1}/{retries})")
                    time.sleep(RETRY_DELAY)
                    continue
                else:
                    print(f"❌ Server error {response.status_code} after {retries} attempts")
                    return None

            else:
                print(f"⚠️  Unexpected status code {response.status_code} for {path}")
                return None

        except requests.exceptions.ConnectionError:
            if attempt < retries - 1:
                print(f"⚠️  Connection failed, retrying... ({attempt + 1}/{retries})")
                time.sleep(RETRY_DELAY)
            else:
                print(f"❌ Cannot connect to API at {API_BASE}")
                return None

        except requests.exceptions.Timeout:
            if attempt < retries - 1:
                print(f"⚠️  Request timeout, retrying... ({attempt + 1}/{retries})")
                time.sleep(RETRY_DELAY)
            else:
                print(f"❌ Request timeout after {retries} attempts")
                return None

        except requests.exceptions.RequestException as e:
            print(f"❌ Request error: {str(e)}")
            return None

        except Exception as e:
            print(f"❌ Unexpected error: {str(e)}")
            return None

    return None


def api_post(path: str, data: dict, retries: int = MAX_RETRIES) -> Optional[Any]:
    """
    Make POST request to API with automatic retry on failure

    Args:
        path: API endpoint path
        data: JSON data to send
        retries: Number of retry attempts

    Returns:
        JSON response or None if failed
    """
    url = f"{API_BASE}{path}"

    for attempt in range(retries):
        try:
            response = requests.post(url, json=data, timeout=TIMEOUT)

            if response.status_code in [200, 201]:
                return response.json()

            elif response.status_code >= 500:
                if attempt < retries - 1:
                    time.sleep(RETRY_DELAY)
                    continue
                else:
                    return None

            else:
                print(f"⚠️  POST failed with status {response.status_code}")
                return None

        except Exception as e:
            if attempt < retries - 1:
                time.sleep(RETRY_DELAY)
            else:
                print(f"❌ POST error: {str(e)}")
                return None

    return None


def check_api_health() -> bool:
    """
    Check if API server is reachable and healthy

    Returns:
        True if healthy, False otherwise
    """
    try:
        response = requests.get(f"{API_BASE}/api/health", timeout=3)
        return response.status_code == 200
    except:
        return False


def get_api_stats() -> Optional[dict]:
    """
    Get API statistics and database info

    Returns:
        Dictionary with stats or None if failed
    """
    return api_get("/api/statistics")