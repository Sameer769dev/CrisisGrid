"""Live USGS Earthquake & Hazard Feed service (AGENTS.md §2 permitted data source).

Fetches real-time global seismic events from the official, free, unauthenticated
USGS GeoJSON Summary Feed (https://earthquake.usgs.gov/earthquakes/feed/v1.0/geojson.php)
and normalizes them into deterministic CrisisGrid triage inputs (coordinates for
OpenStreetMap Overpass facility lookup + structured telemetry field report).

Strict compliance (AGENTS.md §2 & §4):
- Zero AI model calls inside this module.
- Never fabricates seismic events, magnitudes, or coordinates.
- If the upstream USGS feed is unreachable, raises UsgsUpstreamError so the API
  can report an honest 502 status rather than returning synthetic earthquakes.
"""
from __future__ import annotations

import datetime as dt
import time
from typing import Any

import httpx

USGS_FEEDS: dict[str, str] = {
    "4.5_day": "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/4.5_day.geojson",
    "4.5_week": "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/4.5_week.geojson",
    "significant_month": "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/significant_month.geojson",
    "2.5_day": "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/2.5_day.geojson",
}
DEFAULT_USGS_FEED = "4.5_day"
USGS_TIMEOUT_SECONDS = 12.0


class UsgsUpstreamError(RuntimeError):
    """Raised when the upstream USGS GeoJSON feed fails or returns invalid data."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


def _classify_seismic_severity(
    magnitude: float | None,
    alert: str | None,
    tsunami: bool,
) -> tuple[str, int]:
    """Deterministic severity label and baseline urgency score (0-100) from USGS telemetry."""
    mag = float(magnitude) if magnitude is not None else 0.0
    alert_norm = (alert or "").strip().lower()

    if alert_norm in ("red", "orange") or mag >= 6.5 or (tsunami and mag >= 5.5):
        urgency = min(100, int(round(75 + max(0.0, mag - 6.0) * 10)))
        return "critical", max(80, urgency)
    if alert_norm == "yellow" or mag >= 5.5 or tsunami:
        urgency = min(89, int(round(60 + max(0.0, mag - 5.0) * 12)))
        return "high", max(62, urgency)
    if mag >= 4.5:
        urgency = min(69, int(round(42 + max(0.0, mag - 4.5) * 15)))
        return "moderate", max(42, urgency)
    return "low", max(20, int(round(mag * 8)))


def _build_telemetry_field_report(event: dict[str, Any]) -> str:
    """Build a deterministic, facts-only field report from USGS sensor parameters."""
    mag_str = f"M{event['magnitude']:.1f}" if event.get("magnitude") is not None else "Unrated magnitude"
    place = event.get("place") or "unspecified epicenter"
    depth = event.get("depth_km")
    depth_str = f" at {depth:.1f} km depth" if isinstance(depth, (int, float)) else ""
    lat = event.get("latitude")
    lon = event.get("longitude")
    coord_str = f" ({lat:.4f}, {lon:.4f})" if isinstance(lat, (int, float)) and isinstance(lon, (int, float)) else ""
    alert = (event.get("alert_level") or "none").upper()
    tsunami_note = (
        " USGS TSUNAMI ADVISORY FLAGGED — prioritize coastal/low-lying evacuation corridors and elevated landing zones."
        if event.get("tsunami_warning")
        else " Verify bridge integrity, rubble blockage on primary road corridors, and flat ground clearance for rotary-wing medevac."
    )
    return (
        f"USGS Seismic Telemetry ({event['event_id']}): {mag_str} earthquake recorded near {place}{depth_str}{coord_str}. "
        f"PAGER alert level: {alert}.{tsunami_note}"
    )


def normalize_usgs_feature(feature: dict[str, Any]) -> dict[str, Any] | None:
    """Normalize a single USGS GeoJSON Feature into a CrisisGrid seismic event record."""
    if not isinstance(feature, dict):
        return None
    props = feature.get("properties")
    geom = feature.get("geometry")
    if not isinstance(props, dict) or not isinstance(geom, dict):
        return None
    coords = geom.get("coordinates")
    if not isinstance(coords, (list, tuple)) or len(coords) < 2:
        return None
    try:
        lon = float(coords[0])
        lat = float(coords[1])
        depth_km = round(float(coords[2]), 2) if len(coords) >= 3 and coords[2] is not None else None
    except (TypeError, ValueError):
        return None
    if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
        return None

    raw_mag = props.get("mag")
    try:
        magnitude = round(float(raw_mag), 2) if raw_mag is not None else None
    except (TypeError, ValueError):
        magnitude = None

    time_ms = props.get("time")
    time_iso: str | None = None
    if isinstance(time_ms, (int, float)):
        try:
            time_iso = dt.datetime.fromtimestamp(time_ms / 1000.0, tz=dt.timezone.utc).isoformat()
        except (OverflowError, OSError, ValueError):
            time_iso = None

    alert_raw = props.get("alert")
    alert_level = str(alert_raw).strip().lower() if alert_raw else None
    tsunami_warning = bool(props.get("tsunami") == 1 or props.get("tsunami") is True)
    severity_estimate, urgency_estimate = _classify_seismic_severity(magnitude, alert_level, tsunami_warning)

    event_id = str(feature.get("id") or props.get("code") or f"usgs-{int(lat*100)}_{int(lon*100)}")
    place = str(props.get("place") or "Global seismic zone").strip()
    title = str(props.get("title") or f"M{magnitude if magnitude is not None else '?'} - {place}").strip()

    record: dict[str, Any] = {
        "event_id": event_id,
        "title": title,
        "place": place,
        "magnitude": magnitude,
        "depth_km": depth_km,
        "latitude": round(lat, 4),
        "longitude": round(lon, 4),
        "time_epoch_ms": int(time_ms) if isinstance(time_ms, (int, float)) else None,
        "time_iso": time_iso,
        "alert_level": alert_level,
        "tsunami_warning": tsunami_warning,
        "felt_reports": int(props["felt"]) if isinstance(props.get("felt"), (int, float)) else None,
        "mmi_intensity": round(float(props["mmi"]), 2) if isinstance(props.get("mmi"), (int, float)) else None,
        "usgs_url": str(props["url"]) if props.get("url") else None,
        "severity_estimate": severity_estimate,
        "urgency_estimate": urgency_estimate,
        "recommended_preset_id": "earthquake-bridge",
    }
    record["field_report"] = _build_telemetry_field_report(record)
    return record


async def fetch_usgs_live_events(
    *,
    feed: str = DEFAULT_USGS_FEED,
    min_magnitude: float = 4.5,
    limit: int = 6,
    http_client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    """Fetch and deterministically normalize real-time USGS earthquake events."""
    feed_key = (feed or DEFAULT_USGS_FEED).strip().lower()
    if feed_key not in USGS_FEEDS:
        raise ValueError(f"Unsupported USGS feed '{feed}'. Choose from: {', '.join(sorted(USGS_FEEDS))}.")
    if limit < 1 or limit > 25:
        raise ValueError("limit must be between 1 and 25.")

    url = USGS_FEEDS[feed_key]
    started = time.perf_counter()

    owns_client = http_client is None
    client = http_client or httpx.AsyncClient(timeout=USGS_TIMEOUT_SECONDS)
    try:
        try:
            resp = await client.get(url, headers={"Accept": "application/geo+json, application/json"})
        except Exception as exc:
            raise UsgsUpstreamError(f"USGS GeoJSON feed request failed: {type(exc).__name__}: {exc}") from exc
    finally:
        if owns_client:
            await client.aclose()

    if resp.status_code != 200:
        raise UsgsUpstreamError(
            f"USGS GeoJSON feed returned HTTP {resp.status_code} for {url}.",
            status_code=resp.status_code,
        )

    try:
        payload = resp.json()
    except Exception as exc:
        raise UsgsUpstreamError(f"USGS feed returned non-JSON payload: {exc}") from exc

    if not isinstance(payload, dict) or not isinstance(payload.get("features"), list):
        raise UsgsUpstreamError("USGS feed payload is missing the GeoJSON 'features' array.")

    events: list[dict[str, Any]] = []
    for raw_feature in payload["features"]:
        norm = normalize_usgs_feature(raw_feature)
        if norm is None:
            continue
        if norm["magnitude"] is not None and norm["magnitude"] < min_magnitude:
            continue
        events.append(norm)

    events.sort(
        key=lambda e: (
            e["magnitude"] if e["magnitude"] is not None else -1.0,
            e["time_epoch_ms"] if e["time_epoch_ms"] is not None else 0,
        ),
        reverse=True,
    )
    selected = events[:limit]
    latency_ms = round((time.perf_counter() - started) * 1000, 1)

    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    return {
        "status": "ok",
        "provider": "USGS Earthquake Hazards Program (earthquake.usgs.gov)",
        "feed": feed_key,
        "feed_url": url,
        "feed_title": metadata.get("title") or f"USGS {feed_key} GeoJSON feed",
        "model_calls": 0,
        "min_magnitude": min_magnitude,
        "total_matching": len(events),
        "count": len(selected),
        "events": selected,
        "latency_ms": latency_ms,
        "trace": [
            {
                "step": "usgs",
                "event": "seismic_feed_loaded",
                "detail": (
                    f"Loaded {len(selected)} live USGS seismic event(s) (M>={min_magnitude}) from '{feed_key}' "
                    f"in {latency_ms} ms (0 model calls). Coordinates ready for OpenStreetMap Overpass facility lookup."
                ),
                "state": "info",
                "latency_ms": latency_ms,
            }
        ],
        "next_step": (
            "Select an earthquake to populate Mission Control with its real epicenter coordinates "
            "(for OpenStreetMap Overpass hospital/shelter lookup) and telemetry field report."
        ),
    }

