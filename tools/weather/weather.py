#!/usr/bin/env python3
"""weather tool: current conditions as a JSON report.

Arguments arrive as JSON in TOOL_ARGS, stdout is the tool result.
Read-only, stdlib only. A named place is geocoded with Open-Meteo; an
omitted place uses the machine's public IP, then Open-Meteo for the
forecast. Invalid arguments print {"error": ...} and exit 1; a failed
lookup prints {"error": ...} and exits 0.
"""

import json
import os
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
IP_URL = "https://ipwho.is/"
TIMEOUT = 15
MAX_LOCATION_LEN = 200
USER_AGENT = "system-stats-weather/1.0"

CURRENT_VARS = ",".join(
    [
        "temperature_2m",
        "apparent_temperature",
        "relative_humidity_2m",
        "precipitation",
        "weather_code",
        "cloud_cover",
        "wind_speed_10m",
        "wind_direction_10m",
        "is_day",
    ]
)
DAILY_VARS = ",".join(
    [
        "weather_code",
        "temperature_2m_max",
        "temperature_2m_min",
        "precipitation_sum",
    ]
)


def _api_reason(body):
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return body[:300] if body else ""
    if isinstance(data, dict):
        reason = data.get("reason") or data.get("message")
        if isinstance(reason, str):
            return reason
    return body[:300]


def _ssl_context():
    """Default trust store, or the OS bundle when the Python install has none.

    python.org builds on macOS ship without cert.pem until Install
    Certificates.command is run. Verification stays on.
    """
    ctx = ssl.create_default_context()
    if ctx.cert_store_stats().get("x509", 0) > 0:
        return ctx
    for path in (
        "/etc/ssl/cert.pem",
        "/etc/ssl/certs/ca-certificates.crt",
        "/etc/pki/tls/certs/ca-bundle.crt",
    ):
        if os.path.isfile(path):
            ctx.load_verify_locations(path)
            return ctx
    return ctx


SSL_CONTEXT = _ssl_context()


def _get_json(url):
    req = urllib.request.Request(
        url, headers={"Accept": "application/json", "User-Agent": USER_AGENT}
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT, context=SSL_CONTEXT) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")
        reason = _api_reason(detail) or e.reason
        raise RuntimeError(f"HTTP {e.code}: {reason}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(str(e.reason)) from e
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"response was not JSON: {e}") from e
    if isinstance(data, dict) and data.get("error") is True:
        raise RuntimeError(data.get("reason") or "request failed")
    if not isinstance(data, dict):
        raise RuntimeError("response was not a JSON object")
    return data


def _round(value, digits=1):
    if value is None:
        return None
    return round(float(value), digits)


def _int_or_none(value):
    if value is None:
        return None
    return int(value)


def _place(row):
    place = {
        "name": row.get("name") or "",
        "admin1": row.get("admin1") or "",
        "country": row.get("country") or "",
        "country_code": row.get("country_code") or "",
    }
    population = row.get("population")
    if isinstance(population, int) and not isinstance(population, bool):
        place["population"] = population
    return place


def _coord(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RuntimeError(f"missing {name}")
    return float(value)


def resolve_named(location, language):
    url = GEOCODING_URL + "?" + urllib.parse.urlencode(
        {"name": location, "count": 5, "language": language, "format": "json"}
    )
    try:
        data = _get_json(url)
    except RuntimeError as e:
        raise RuntimeError(f"geocoding failed: {e}") from e
    results = data.get("results") or []
    if not results:
        raise RuntimeError(f"location not found: {location}")
    top = results[0]
    try:
        latitude = _coord(top.get("latitude"), "latitude")
        longitude = _coord(top.get("longitude"), "longitude")
    except RuntimeError as e:
        raise RuntimeError(f"geocoding failed: {e}") from e
    place = _place(top)
    place.update(
        {
            "query": location,
            "latitude": latitude,
            "longitude": longitude,
            "source": "geocoding",
        }
    )
    alternatives = [_place(row) for row in results[1:] if isinstance(row, dict)]
    return place, alternatives


def resolve_ip():
    url = IP_URL + "?" + urllib.parse.urlencode(
        {
            "fields": "success,message,city,region,country,country_code,latitude,longitude",
        }
    )
    try:
        data = _get_json(url)
    except RuntimeError as e:
        raise RuntimeError(f"ip location failed: {e}") from e
    if data.get("success") is False:
        raise RuntimeError(
            "ip location failed: " + (data.get("message") or "lookup unsuccessful")
        )
    name = data.get("city") or data.get("region") or data.get("country") or ""
    if not name:
        raise RuntimeError("ip location failed: no place name")
    try:
        latitude = _coord(data.get("latitude"), "latitude")
        longitude = _coord(data.get("longitude"), "longitude")
    except RuntimeError as e:
        raise RuntimeError(f"ip location failed: {e}") from e
    place = {
        "name": name,
        "admin1": data.get("region") or "",
        "country": data.get("country") or "",
        "country_code": data.get("country_code") or "",
        "latitude": latitude,
        "longitude": longitude,
        "source": "ip",
    }
    return place, []


def fetch_forecast(place):
    url = FORECAST_URL + "?" + urllib.parse.urlencode(
        {
            "latitude": place["latitude"],
            "longitude": place["longitude"],
            "current": CURRENT_VARS,
            "daily": DAILY_VARS,
            "timezone": "auto",
            "forecast_days": 1,
            "temperature_unit": "celsius",
            "wind_speed_unit": "kmh",
            "precipitation_unit": "mm",
        }
    )
    try:
        data = _get_json(url)
    except RuntimeError as e:
        raise RuntimeError(f"forecast failed: {e}") from e
    current = data.get("current")
    daily = data.get("daily")
    if not isinstance(current, dict) or not isinstance(daily, dict):
        raise RuntimeError("forecast failed: response missing current or daily")

    def daily_at(key):
        values = daily.get(key)
        if not isinstance(values, list) or not values:
            raise RuntimeError(f"forecast failed: response missing daily.{key}")
        return values[0]

    for key in (
        "time",
        "temperature_2m",
        "apparent_temperature",
        "relative_humidity_2m",
        "precipitation",
        "weather_code",
        "cloud_cover",
        "wind_speed_10m",
        "wind_direction_10m",
        "is_day",
    ):
        if key not in current:
            raise RuntimeError(f"forecast failed: response missing current.{key}")

    is_day = current["is_day"]
    return {
        "latitude": data.get("latitude"),
        "longitude": data.get("longitude"),
        "timezone": data.get("timezone") or "",
        "current": {
            "time": current["time"],
            "precipitation_interval_seconds": _int_or_none(current.get("interval")),
            "temperature_c": _round(current["temperature_2m"]),
            "apparent_temperature_c": _round(current["apparent_temperature"]),
            "relative_humidity_pct": _int_or_none(current["relative_humidity_2m"]),
            "precipitation_mm": _round(current["precipitation"]),
            "weather_code": _int_or_none(current["weather_code"]),
            "cloud_cover_pct": _int_or_none(current["cloud_cover"]),
            "wind_speed_kmh": _round(current["wind_speed_10m"]),
            "wind_direction_deg": _int_or_none(current["wind_direction_10m"]),
            "is_day": None if is_day is None else bool(is_day),
        },
        "today": {
            "date": daily_at("time"),
            "temperature_max_c": _round(daily_at("temperature_2m_max")),
            "temperature_min_c": _round(daily_at("temperature_2m_min")),
            "precipitation_mm": _round(daily_at("precipitation_sum")),
            "weather_code": _int_or_none(daily_at("weather_code")),
        },
    }


def collect(location, language):
    if location:
        place, alternatives = resolve_named(location, language)
    else:
        place, alternatives = resolve_ip()
    forecast = fetch_forecast(place)
    report = {
        "location": place,
        "current": forecast["current"],
        "today": forecast["today"],
        "timezone": forecast["timezone"],
        "attribution": "Weather data by Open-Meteo.com, CC BY 4.0",
    }
    if alternatives:
        report["alternatives"] = alternatives
    return report


def main() -> int:
    try:
        args = json.loads(os.environ.get("TOOL_ARGS", "{}"))
        if not isinstance(args, dict):
            raise ValueError("TOOL_ARGS must be a JSON object")
        location = args.get("location", "")
        if location is None:
            location = ""
        if not isinstance(location, str):
            raise ValueError(f"location must be a string, got {location!r}")
        location = location.strip()
        if len(location) > MAX_LOCATION_LEN:
            raise ValueError(f"location must be at most {MAX_LOCATION_LEN} characters")
        language = args.get("language", "en")
        if not isinstance(language, str) or len(language) != 2 or not language.isalpha():
            raise ValueError(f"language must be a 2-letter code, got {language!r}")
        language = language.lower()
    except (ValueError, TypeError) as e:
        print(json.dumps({"error": f"invalid arguments: {e}"}))
        return 1

    try:
        report = collect(location, language)
    except Exception as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False, indent=2))
        return 0

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
