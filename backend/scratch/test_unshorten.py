
import requests

url = "https://lnkd.in/gerC6Frs" # PagerDuty
try:
    # Use a real browser user agent
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    response = requests.get(url, allow_redirects=True, timeout=10, headers=headers)
    print(f"Final URL: {response.url}")
    print(f"Status Code: {response.status_code}")
except Exception as e:
    print(f"Error: {e}")
