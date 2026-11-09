
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
                    [-74.0170, 40.7050],
                    [-74.0030, 40.7050],
                    [-74.0030, 40.7180],
                    [-74.0170, 40.7180],
                    [-74.0170, 40.7050]
                ]]
            }
        }]
    },
    "date_time": {
        "start_date": "2024-07-15",
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
