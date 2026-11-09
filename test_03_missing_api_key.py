
import requests

url = "https://api.fortyguard.com/v1/heatmap"

# Intentionally omit API key
headers = {
    "Content-Type": "application/json"
}

response = requests.post(
    url,
    headers=headers,
    json={},
    timeout=30
)

print("=== MISSING API KEY TEST ===")
print("HTTP Status:", response.status_code)

try:
    print("Response:", response.json())
except ValueError:
    print("Response:", response.text[:1000])
