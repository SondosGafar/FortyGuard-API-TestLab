
import requests
import getpass
import json
from pathlib import Path

api_key = getpass.getpass("Enter your FortyGuard API key: ")

url = "https://api.fortyguard.com/v1/env_params"

headers = {
    "api-key": api_key,
    "Content-Type": "application/json"
}

payload = {
    "latitude": 33.463837,
    "longitude": -112.057830,
    "temperature": 27.7,  # Approx. 81.86°F
    "date_time": {
        "start_date": "2026-11-08",
        "start_time": "14:00",
        "filter_type": 1
    },
    "analysis": [
        "heat_index_celsius",
        "relative_humidity_percent",
        "precipitation_mm"
    ]
}

try:
    response = requests.post(
        url,
        headers=headers,
        json=payload,
        timeout=30
    )

    print("=== ENVIRONMENTAL PARAMETERS TEST ===")
    print("HTTP Status:", response.status_code)

    result = response.json()

    evidence_dir = Path("evidence")
    evidence_dir.mkdir(exist_ok=True)

    (evidence_dir / "environmental_submission.json").write_text(
        json.dumps(result, indent=2),
        encoding="utf-8"
    )

    if response.ok:
        data = result.get("data", {})
        print("Activity ID:", data.get("activity_id"))
        print("Submission successful!")
    else:
        print("Error Response:")
        print(json.dumps(result, indent=2))

except requests.RequestException as e:
    print("Connection Error:", e)
except ValueError:
    print("Response was not valid JSON")
