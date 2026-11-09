"""Pure transformations for the Environmental Parameters API response.

No network calls; no fabricated measurements. None and the documented legacy
-999 sentinel are treated as unavailable rather than real numeric readings.
"""
from __future__ import annotations

import math
from typing import Any

PARAMETER_INFO = {
    "heat_index_celsius": ("Heat index", "°C"),
    "apparent_temperature_celsius": ("Apparent temperature", "°C"),
    "wet_bulb_temperature_celsius": ("Wet-bulb temperature", "°C"),
    "relative_humidity_percent": ("Relative humidity", "%"),
    "precipitation_mm": ("Precipitation", "mm"),
    "cloud_cover_octas": ("Cloud cover", "octas"),
    "elevation": ("Elevation", "m"),
    "air_quality:idx": ("Air quality index (US)", "AQI"),
    "air_quality_pm2p5:idx": ("PM2.5 index (US)", "AQI"),
    "air_quality_pm10:idx": ("PM10 index (US)", "AQI"),
    "air_quality_no2:idx": ("NO₂ index (US)", "AQI"),
    "aqi_us_co": ("CO index (US)", "AQI"),
    "air_quality_o3:idx": ("O₃ index (US)", "AQI"),
    "air_quality_so2:idx": ("SO₂ index (US)", "AQI"),
    "methane_ppb": ("Methane", "ppb"),
    "co2_ppm": ("Carbon dioxide", "ppm"),
}


def valid_measurement(value: Any) -> float | None:
    """Return a finite numeric measurement, excluding missing-value encodings."""
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) and number != -999 else None


def normalize_series(raw: Any) -> list[float | None]:
    """Normalize either a scalar or a time-aligned array; preserve missing positions."""
    values = raw if isinstance(raw, list) else [raw]
    return [valid_measurement(value) for value in values]


def _locations(result: dict) -> list[dict]:
    raw = result.get("locations")
    if isinstance(raw, dict):
        return [raw]
    if isinstance(raw, list):
        return [item for item in raw if isinstance(item, dict)]
    return []


def environmental_view(result: dict) -> dict:
    """Build a view-model from the actual locations[].parameters response schema."""
    metadata = result.get("metadata") if isinstance(result.get("metadata"), dict) else {}
    locs = _locations(result)
    loc = locs[0] if locs else {}
    params = loc.get("parameters") if isinstance(loc.get("parameters"), dict) else {}
    if not params and isinstance(result.get("parameters"), dict):
        params = result["parameters"]  # compatibility with another documented response variant
    rows = []
    for key, raw in params.items():
        values = normalize_series(raw)
        good = [v for v in values if v is not None]
        title, unit = PARAMETER_INFO.get(key, (key.replace("_", " "), ""))
        rows.append({
            "key": key, "label": title, "unit": unit,
            "values": values, "first": values[0] if values else None,
            "available": len(good), "count": len(values),
        })
    time_range = metadata.get("time_range") if isinstance(metadata.get("time_range"), dict) else {}
    return {
        "metadata": metadata, "timezone": metadata.get("timezone"),
        "timestamps": metadata.get("timestamps") if isinstance(metadata.get("timestamps"), list) else [],
        "time_range": time_range,
        "latitude": loc.get("lat", loc.get("latitude")),
        "longitude": loc.get("lon", loc.get("longitude")),
        "elevation": loc.get("elevation"),
        "input_temperature": loc.get("temperature"),
        "location_count": len(locs),
        "rows": rows,
        "solar_irradiance": loc.get("solar_irradiance") or result.get("solar_irradiance"),
    }


def requested_parameter_coverage(rows: list[dict], requested: list[str] | None) -> dict:
    """Check field presence (not just non-nullness) for requested parameters."""
    if not isinstance(requested, list) or not requested:
        return {"requested": [], "present": [], "absent": [], "additional": []}
    found = {row["key"] for row in rows}
    return {
        "requested": requested,
        "present": [p for p in requested if p in found],
        "absent": [p for p in requested if p not in found],
        "additional": sorted(found - set(requested)),
    }
