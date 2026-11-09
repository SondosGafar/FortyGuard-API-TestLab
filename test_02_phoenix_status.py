
import requests
import getpass
import json
from pathlib import Path

api_key = getpass.getpass("Enter your FortyGuard API key: ")

activity_id = "606d1f79-6b1d-4567-8d78-10f16317a8b3"

url = f"https://api.fortyguard.com/v1/status/{activity_id}"

try:
    response = requests.get(
        url,
        headers={"api-key": api_key},
        timeout=30
    )

    print("HTTP Status Code:", response.status_code)

    result = response.json()
    data = result.get("data", {})
    status = data.get("status", "Unknown")

    print("Task Status:", status)

    # Save locally for testing evidence
    evidence_dir = Path("evidence")
    evidence_dir.mkdir(exist_ok=True)

    evidence_file = evidence_dir / "phoenix_status.json"
    evidence_file.write_text(
        json.dumps(result, indent=2),
        encoding="utf-8"
    )

    print("Response saved to:", evidence_file)

except requests.RequestException as e:
    print("Connection Error:", e)
except ValueError:
    print("Response was not valid JSON")
