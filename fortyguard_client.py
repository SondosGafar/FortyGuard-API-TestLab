"""Small, deliberate FortyGuard API test client.

No requests are made on import. API keys are never written to disk.
Specifications are based on the developer documentation supplied for Nov 2026.
"""
from __future__ import annotations

import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import requests

BASE_URL = "https://api.fortyguard.com"
EVIDENCE_DIR = Path(__file__).resolve().parent / "evidence"

ENDPOINTS = {
    "heatmap": {"title": "Create Heatmap", "path": "/v1/heatmap", "credits": 4220, "plan": "Premium"},
    "env_params": {"title": "Environmental Parameters", "path": "/v1/env_params", "credits": 2900, "plan": "Premium"},
    "satellite": {"title": "Satellite Segmentation", "path": "/v1/satellite", "credits": 14400, "plan": "Premium"},
    "streetview": {"title": "Street View Segmentation", "path": "/v1/streetview", "credits": 8600, "plan": "Premium"},
    "heat_intelligence": {"title": "Heat Intelligence", "path": "/v1/heat_intelligence", "credits": 8600, "plan": "Premium"},
    "routing": {"title": "Temperature-Aware Routing", "path": "/v1/routing", "credits": 3500, "plan": "Premium"},
}

TOTAL_ESTIMATED_CREDITS = sum(v["credits"] for v in ENDPOINTS.values())


def default_payload(name: str) -> dict[str, Any]:
    """Reasonable U.S.-based test examples; availability is NOT guaranteed."""
    moment = {"start_date": "2026-11-08", "start_time": "14:00", "filter_type": 1}
    defaults = {
        "heatmap": {
            "polygon_aoi": {"type": "FeatureCollection", "features": [
                {"type": "Feature", "properties": {}, "geometry": {
                    "type": "Polygon", "coordinates": [[
                        [-112.063, 33.460], [-112.052, 33.460],
                        [-112.052, 33.468], [-112.063, 33.468],
                        [-112.063, 33.460]
                    ]]}}
            ]},
            "date_time": moment, "granularity": 100
        },
        "env_params": {
            "latitude": 33.463837, "longitude": -112.057830,
            "temperature": 27.7,  # Celsius (approx 81.86 Fahrenheit)
            "date_time": moment,
            "analysis": ["heat_index_celsius", "relative_humidity_percent", "precipitation_mm"]
        },
        "satellite": {
            "sat": {"latitude": 33.463837, "longitude": -112.057830},
            "date_time": moment, "granularity": 80
        },
        "streetview": {
            "latitude": 33.463837, "longitude": -112.057830,
            "vertical_angle": 10.0, "horizontal_angle": 90.0, "back_view": False
        },
        "heat_intelligence": {
            "latitude": 33.463837, "longitude": -112.057830,
            "temperature": 81.86,  # Fahrenheit, per the required fields
            "date": "2026-11-08", "analysis": ["geographic", "environmental"]
        },
        "routing": {
            "origin": {"lat": 33.463837, "lon": -112.057830},
            "destination": {"lat": 33.469500, "lon": -112.043500},
            "departure_time": "2026-11-08T14:00:00-07:00"
        },
    }
    if name not in defaults:
        raise ValueError(f"Unknown endpoint name: {name}")
    # Safe to mutate the returned payload; defaults are rebuilt each call.
    return defaults[name]


def api_call(method: str, path: str, *, api_key: str | None = None,
             payload: Any = None, params: dict | None = None,
             timeout: int = 35) -> tuple[int | None, dict[str, Any]]:
    """Returns (HTTP status, parsed JSON). Handles transport failures as errors."""
    if not path.startswith("/v1/"):
        raise ValueError("Only the documented /v1/ endpoints can be called")
    headers: dict[str, str] = {"Accept": "application/json"}
    if api_key:
        headers["api-key"] = api_key
    if method.upper() == "POST":
        headers["Content-Type"] = "application/json"
    try:
        response = requests.request(method.upper(), BASE_URL + path,
                                    headers=headers, json=payload, params=params,
                                    timeout=timeout)
        try:
            body = response.json()
        except ValueError:
            body = {"error": True, "message": "Non-JSON server response", "body_excerpt": response.text[:600]}
        if not isinstance(body, dict):
            body = {"data": body}
        return response.status_code, body
    except requests.RequestException as error:
        return None, {"error": True, "transport_error": type(error).__name__,
                      "message": str(error)[:500]}


def submit(name: str, key: str, payload: dict[str, Any]) -> tuple[int | None, dict]:
    if name not in ENDPOINTS:
        raise ValueError(f"Unknown endpoint: {name}")
    return api_call("POST", ENDPOINTS[name]["path"], api_key=key, payload=payload)


def check_status(key: str, activity_id: str, *, links: bool = False) -> tuple[int | None, dict]:
    activity_id = activity_id.strip()
    if not re.fullmatch(r"[a-zA-Z0-9-]{1,128}", activity_id):
        raise ValueError("Activity ID must contain only letters, digits and hyphens")
    params = {"result_delivery": "links"} if links else None
    return api_call("GET", f"/v1/status/{activity_id}", api_key=key, params=params)


def activity_id_from(body: dict) -> str | None:
    data = body.get("data")
    return data.get("activity_id") if isinstance(data, dict) else None


def activity_state(body: dict) -> str | None:
    data = body.get("data")
    return data.get("status") if isinstance(data, dict) else None


SECRET_PARTS = ("api_key", "api-key", "authorization", "password", "secret", "token",
                "download_link", "download_url", "signed_url", "presigned", "signature")
IMAGE_KEYS = {"original_image", "orignal_image", "segmented_image", "image_content"}


def _brief(value: Any, key: str = "", depth: int = 0) -> Any:
    """Generate a bounded, safe evidence summary rather than storing raw signed URLs / imagery."""
    lowered = key.lower()
    if any(s in lowered for s in SECRET_PARTS):
        return "[REDACTED]"
    if lowered in IMAGE_KEYS:
        if isinstance(value, str):
            return f"[Base64/image data omitted; {len(value)} characters]"
        return f"[Image data omitted; {len(value) if isinstance(value, list) else '?'} items]"
    if lowered == "map_data" and isinstance(value, dict):
        features = value.get("features", [])
        return {"type": value.get("type"), "feature_count": len(features) if isinstance(features, list) else None,
                "geometry_types_sample": list(dict.fromkeys(
                    str(f.get("geometry", {}).get("type")) for f in features[:8] if isinstance(f, dict)
                )) if isinstance(features, list) else []}
    if depth > 5:
        return "[additional nesting omitted]"
    if isinstance(value, dict):
        return {str(k): _brief(v, str(k), depth + 1) for k, v in list(value.items())[:45]}
    if isinstance(value, list):
        sample = [_brief(v, key, depth + 1) for v in value[:6]]
        return {"item_count": len(value), "sample": sample} if len(value) > 6 else sample
    if isinstance(value, str):
        if value.startswith("http") and ("X-Amz-" in value or "Signature=" in value or "token=" in value):
            return "[Signed URL omitted]"
        return value[:350] + ("... [truncated]" if len(value) > 350 else "")
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return str(type(value).__name__)


def sanitized_result(body: dict) -> dict:
    return _brief(body)


def record_evidence(test_name: str, method: str, endpoint: str,
                    payload: Any, http_code: int | None, response_body: dict,
                    *, estimate: int = 0, notes: str = "") -> Path:
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc)
    entry = {
        "recorded_at_utc": timestamp.isoformat(timespec="seconds"),
        "test": test_name, "method": method, "endpoint": endpoint,
        "request_payload_without_authentication": _brief(payload),
        "http_status": http_code,
        "activity_id": activity_id_from(response_body),
        "task_status": activity_state(response_body),
        "response_summary": sanitized_result(response_body),
        "published_premium_credit_estimate_if_completed": estimate,
        "notes": notes,
    }
    safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", test_name).strip("_")[:55]
    path = EVIDENCE_DIR / (f"{timestamp.strftime('%Y%m%dT%H%M%S')}_{safe_name}_{uuid4().hex[:5]}.json")
    path.write_text(json.dumps(entry, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def evidence_records() -> list[dict]:
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    entries = []
    for path in sorted(EVIDENCE_DIR.glob("*.json"), reverse=True):
        try:
            d = json.loads(path.read_text(encoding="utf-8"))
            if "test" in d:
                d["file"] = path.name
                entries.append(d)
        except (json.JSONDecodeError, OSError):
            pass
    return entries


def evidence_csv_bytes() -> bytes:
    import io
    rows = evidence_records()
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=["recorded_at_utc", "test", "method", "endpoint",
                                               "http_status", "task_status", "activity_id", "file"])
    writer.writeheader()
    for entry in rows:
        writer.writerow({key: entry.get(key, "") for key in writer.fieldnames})
    return out.getvalue().encode("utf-8-sig")


def summarize_result_data(body: dict) -> dict:
    data = body.get("data") or {}
    if not isinstance(data, dict):
        return {}
    result = data.get("result") or {}
    return result if isinstance(result, dict) else {}
