
import requests
import getpass

api_key = getpass.getpass("FortyGuard API key: ")

activity_id = "46858e5d-ec93-4c16-8347-1391835e9732"

url = f"https://api.fortyguard.com/v1/status/{activity_id}"

response = requests.get(
    url,
    headers={"api-key": api_key},
    timeout=30
)

response.raise_for_status()

data = response.json()["data"]
print("Activity status:", data["status"])

locations = data["result"]["locations"]
parameters = locations[0]["parameters"]

requested = [
    "heat_index_celsius",
    "relative_humidity_percent",
    "precipitation_mm"
]

print("\n=== REQUESTED ENVIRONMENTAL PARAMETERS ===")

for field in requested:
    print(f"{field}: {parameters.get(field, 'MISSING')}")

print("\nAdditional parameter fields:",
      len(set(parameters) - set(requested)))
