
import json
from pathlib import Path

file_path = Path("evidence/phoenix_status.json")

with open(file_path, "r", encoding="utf-8") as file:
    response = json.load(file)

print("=== FORTYGUARD API RESPONSE ANALYSIS ===")

print("\n1. Response fields:")
print(list(response.keys()))

data = response.get("data", {})

if isinstance(data, dict):
    print("\n2. Data fields:")
    print(list(data.keys()))

    print("\n3. Task status:")
    print(data.get("status", "Not provided"))

    print("\n4. Result structure:")
    for key, value in data.items():
        if isinstance(value, dict):
            print(f"{key}: Object with fields {list(value.keys())}")
        elif isinstance(value, list):
            print(f"{key}: List with {len(value)} items")
        else:
            print(f"{key}: {type(value).__name__}")
else:
    print("\nData type:", type(data).__name__)

print("\nAnalysis completed.")
