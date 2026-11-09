
import requests
import getpass
import json

api_key = getpass.getpass("Enter your FortyGuard API key: ")

url = "https://api.fortyguard.com/v1/heatmap"

headers = {
    "api-key": api_key,
    "Content-Type": "application/json"
}

# Intentionally invalid request:
# Required heatmap parameters are missing
invalid_payload = {}

try:
    response = requests.post(
        url,
        headers=headers,
        json=invalid_payload,
        timeout=30
    )

    print("=== INVALID PAYLOAD TEST ===")
    print("HTTP Status:", response.status_code)

    try:
        print(json.dumps(response.json(), indent=2))
    except ValueError:
        print(response.text[:1000])

except requests.RequestException as e:
    print("Connection Error:", e)
