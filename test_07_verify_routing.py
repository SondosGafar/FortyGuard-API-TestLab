
import requests
import getpass

api_key = getpass.getpass("FortyGuard API key: ")
activity_id = "1afe605c-eb01-4705-ba64-e6d8c5b1d621"

response = requests.get(
    f"https://api.fortyguard.com/v1/status/{activity_id}",
    headers={"api-key": api_key},
    timeout=30
)
response.raise_for_status()

data = response.json()["data"]
print("Activity status:", data["status"])

routing = data["result"]["result_routing"]
features = routing.get("features", [])

print("Returned routes:", len(features))
print("Distinct routes:", routing.get("dial", {}).get("distinct_routes"))

for i, feature in enumerate(features, 1):
    props = feature.get("properties") or {}
    geometry = feature.get("geometry") or {}

    print(f"\n=== ROUTE {i} ===")
    print("Distance (km):", props.get("distance_km"))
    print("Duration (min):", props.get("duration_min"))
    print("Label:", props.get("label"))
    print("Selected:", props.get("selected"))
    print("Geometry type:", geometry.get("type"))
    print("Coordinates available:", bool(geometry.get("coordinates")))

print("\nNo cooler route:",
      routing.get("dial", {}).get("no_cooling_available"))
