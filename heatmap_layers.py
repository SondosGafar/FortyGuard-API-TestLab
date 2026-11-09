"""Prepare a full-polygon GeoJSON preview, without estimating absent temperatures."""
from __future__ import annotations

from typing import Any
from heatmap_preview import center_from_geometry, temperature_property


def prepare_polygon_layer(map_data: dict[str, Any], maximum: int = 1500) -> dict:
    features = map_data.get("features") if isinstance(map_data, dict) else None
    if not isinstance(features, list):
        features = []
    clean = []
    rows = []
    points = []
    for idx, feature in enumerate(features[:maximum]):
        if not isinstance(feature, dict):
            continue
        geometry = feature.get("geometry")
        center = center_from_geometry(geometry)
        if center is None:
            continue
        if geometry.get("type") not in ("Polygon", "MultiPolygon"):
            continue
        props = feature.get("properties") if isinstance(feature.get("properties"), dict) else {}
        field, value = temperature_property(props)
        fid = str(idx)
        clean.append({"type": "Feature", "id": fid,
                      "properties": {"tile_number": idx + 1}, "geometry": geometry})
        rows.append({"id": fid, "Tile": idx + 1, "value": value, "path": field})
        points.append(center)
    center = {
        "lat": sum(p[0] for p in points) / len(points),
        "lon": sum(p[1] for p in points) / len(points),
    } if points else {"lat": 0.0, "lon": 0.0}
    # Consistency: only use the single dominant field path across all tiles.
    histogram = {}
    for row in rows:
        if row["path"] and row["value"] is not None:
            histogram[row["path"]] = histogram.get(row["path"], 0) + 1
    most_common = max(histogram, key=histogram.get) if histogram else None
    for row in rows:
        if row["path"] != most_common:
            row["value"] = None
    return {
        "geojson": {"type": "FeatureCollection", "features": clean},
        "rows": rows, "center": center, "total": len(features),
        "mapped": len(clean), "temperature_field": most_common,
        "measured": sum(r["value"] is not None for r in rows),
        "truncated": len(features) > maximum,
    }
