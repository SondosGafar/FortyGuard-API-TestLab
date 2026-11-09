"""Pure schema-tolerant parsing of GeoJSON for an optional map preview.

Never fabricates temperature values. When numeric temperature values cannot be
identified, only spatial coverage (geometry-derived tile centers) is shown.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any

KNOWN_VALUES = {
    "temperature", "temperature_celsius", "temperature_fahrenheit", "temp",
    "temp_c", "temp_f", "tcm", "value", "air_temperature",
    "mean_temperature", "average_temperature", "temperature_mean", "temperature_avg",
    "temp_mean", "temp_avg", "temperature_2m", "t2m",
}


def _number(raw: Any) -> float | None:
    if isinstance(raw, bool):
        return None
    if isinstance(raw, (int, float)):
        v = float(raw)
    elif isinstance(raw, str):
        try:
            v = float(raw.strip())
        except ValueError:
            return None
    else:
        return None
    return v if math.isfinite(v) else None


def _normalize(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")


def temperature_property(props: dict[str, Any]) -> tuple[str | None, float | None]:
    """Find an explicitly temperature-like numeric property, including nested objects.

    The generic `value` key is supported for compatibility but has lowest priority.
    """
    candidates = []
    def walk(mapping: dict, prefix: str = "", depth: int = 0):
        if depth > 2:
            return
        for key, raw in mapping.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            normalized = _normalize(str(key))
            if isinstance(raw, dict):
                walk(raw, path, depth + 1)
                continue
            number = _number(raw)
            if number is None:
                continue
            if normalized in KNOWN_VALUES:
                priority = 3 if normalized == 'value' else 0
            elif 'temperature' in normalized or normalized.startswith('temp_') or normalized.endswith('_temp'):
                priority = 1
            else:
                continue
            candidates.append((priority, depth, path, number))
    walk(props)
    if not candidates:
        return None, None
    candidates.sort(key=lambda item: (item[0],item[1],item[2]))
    _,_,path,number = candidates[0]
    return path, number


def _flatten_coords(value: Any):
    if isinstance(value, (tuple, list)):
        if len(value) >= 2 and all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in value[:2]):
            lon, lat = value[0],value[1]
            if math.isfinite(lon) and math.isfinite(lat) and -180 <= lon <= 180 and -90 <= lat <= 90:
                yield (float(lon), float(lat))
        else:
            for sub in value:
                yield from _flatten_coords(sub)


def center_from_geometry(geometry: Any) -> tuple[float, float] | None:
    if not isinstance(geometry, dict):
        return None
    if geometry.get('type') not in ('Point','MultiPoint','Polygon','MultiPolygon'):
        return None
    pts = list(_flatten_coords(geometry.get('coordinates')))
    if not pts:
        return None
    # Bounding-box midpoint: a robust visual marker, not a mathematical centroid.
    lons, lats = zip(*pts)
    return ((min(lats)+max(lats))/2, (min(lons)+max(lons))/2)


def inspect_geojson(map_data: dict, limit: int = 1200) -> dict[str, Any]:
    features = map_data.get('features', [])
    if not isinstance(features, list):
        features = []
    rows = []
    paths = Counter()
    sample_keys = []
    for index, feature in enumerate(features[:limit],start=1):
        if not isinstance(feature,dict):
            continue
        props = feature.get('properties') or {}
        if not isinstance(props,dict):
            props = {}
        if not sample_keys and props:
            sample_keys = sorted(str(k) for k in props.keys())[:30]
        center = center_from_geometry(feature.get('geometry'))
        if center is None:
            continue
        path, numeric = temperature_property(props)
        if path is not None:
            paths[path]+=1
        rows.append({'Tile': index, 'lat': center[0], 'lon': center[1], 'value': numeric})
    return {
        'count': len(features),
        'rows': rows,
        'numeric_count': sum(x['value'] is not None for x in rows),
        'numeric_paths': dict(paths),
        'sample_property_keys': sample_keys,
    }
