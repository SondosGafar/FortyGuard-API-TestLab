
import requests
import getpass
import json

api_key = getpass.getpass("Enter your FortyGuard API key: ")

# Syntactically valid UUID, but not an existing task
activity_id = "00000000-0000-4000-8000-000000000000"

url = f"https://api.fortyguard.com/v1/status/{activity_id}"

try:
    response = requests.get(
        url,
        headers={"api-key": api_key},
        timeout=30
    )

    print("=== INVALID ACTIVITY ID TEST ===")
    print("HTTP Status:", response.status_code)

    try:
        print(json.dumps(response.json(), indent=2))
    except ValueError:
        print(response.text[:1000])

except requests.RequestException as e:
    print("Connection Error:", e)
