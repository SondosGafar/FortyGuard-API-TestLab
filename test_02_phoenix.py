
import requests
import getpass

# Enter your API key securely
api_key = getpass.getpass("Enter your FortyGuard API key: ")

url = "https://api.fortyguard.com/v1/heatmap"

headers = {
    "api-key": api_key,
    "Content-Type": "application/json"
}

# Official Quickstart example

payload = {
    "polygon_aoi": {
        "type": "FeatureCollection",
        "features": [{
            "type": "Feature",
            "properties": {},
            "geometry": {
                "type": "Polygon",
                "coordinates": [[
                    [-112.063, 33.460],
                    [-112.052, 33.460],
                    [-112.052, 33.468],
                    [-112.063, 33.468],
                    [-112.063, 33.460]
                ]]
            }
        }]
    },
    "date_time": {
        "start_date": "2026-11-08",
        "start_time": "14:00",
        "filter_type": 1
    },
    "granularity": 100
}

try:
    response = requests.post(
        url,
        headers=headers,
        json=payload,
        timeout=30
    )

    print("HTTP Status Code:", response.status_code)

    result = response.json()

    if response.ok:
        activity_id = result.get("data", {}).get("activity_id")
        print("Activity ID:", activity_id)
    else:
        print("Error Response:", result)

except requests.RequestException as e:
    print("Connection Error:", e)
except ValueError:
    print("Response was not valid JSON")
