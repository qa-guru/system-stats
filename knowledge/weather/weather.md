# weather reference

Run from the project root; args go as JSON in `TOOL_ARGS`, result prints
to stdout as JSON:

```bash
TOOL_ARGS='{"location":"Berlin","language":"en"}' python3 tools/weather/weather.py
```

Omit `location` for the machine running the tool:

```bash
TOOL_ARGS='{"language":"ru"}' python3 tools/weather/weather.py
```

The tool is the only caller. Do not request Open-Meteo, the geocoding
API, or an IP-location API yourself.

## Arguments

- `location` — place name, optional. A comma and a region or country
  narrow the search (`Paris, France`), and only when the user supplied
  that qualifier. Empty or omitted means the machine's current location.
  At most 200 characters.
- `language` — two-letter code for geocoding place names, default `en`.
  Use the user's language (`ru`, not `ru-RU`). It does not translate the
  IP lookup; those labels stay as the lookup returns them.

## Where coordinates come from

- Named place — [Open-Meteo Geocoding](https://open-meteo.com/en/docs/geocoding-api).
  The first result is used. Further hits are `alternatives`.
- No place — city of the machine's public IP via `https://ipwho.is/`,
  then the forecast for those coordinates. This is the network egress,
  not GPS. A remote runner reports that runner's city. VPN egress is
  the VPN's city. The IP address is not included in the result.

Forecast data is the Open-Meteo [Forecast API](https://open-meteo.com/en/docs)
(`best_match` model, Celsius, km/h, mm). Non-commercial use needs no API
key. Attribution is required (CC BY 4.0).

## Output

- `location` — `name`, `admin1`, `country`, `country_code`, `latitude`,
  `longitude`, `source` (`geocoding` or `ip`). Named searches also include
  `query` and, when the geocoder sent it, `population`.
- `alternatives` — other geocoding hits (`name`, `admin1`, `country`,
  `country_code`, and `population` when present). Absent when there is
  nothing to disambiguate.
- `timezone` — IANA name of the forecast clock.
- `current` — conditions at `time` (local to `timezone`):
  `temperature_c`, `apparent_temperature_c`, `relative_humidity_pct`,
  `precipitation_mm`, `precipitation_interval_seconds`, `weather_code`,
  `cloud_cover_pct`, `wind_speed_kmh`, `wind_direction_deg` (0 is north,
  90 is east), `is_day`.
- `today` — local calendar day: `temperature_min_c`, `temperature_max_c`,
  `precipitation_mm` (day sum), `weather_code` (most severe code of the
  day, not the current code).
- `attribution` — credit line to keep in the answer.

`current.precipitation_mm` is the sum over
`precipitation_interval_seconds`, not the day total.

## Output and error format

- Invalid arguments — `{"error": "invalid arguments: ..."}`, exit 1.
  No lookup is performed.
- A failed lookup — `{"error": "..."}`, exit 0. Prefixes: `location not
  found`, `geocoding failed`, `ip location failed`, `forecast failed`.
  Inspect the error. If the sandbox blocks network access, request
  permission through the environment's approval mechanism and rerun this
  same tool. Never replace it with another weather command. If the
  approved run still fails, report the error. For a failed IP lookup,
  ask which place to use; do not try a different geolocation service.

## Interpretation

- Describe `current` as now, and `today` as the day's range and total
  precipitation. Translate `weather_code` with the table below. An
  unknown code stays numeric.
- Clear sky at night (`is_day` false, code 0) is clear, not sunny.
- `source: ip` — say the place is approximate, from the network, and
  name the city. Do not present it as the user's GPS position.
- Non-empty `alternatives` whose countries or regions differ — name the
  chosen place (city, region, country). A first hit with a much larger
  `population` is the obvious one; name it and do not ask. Ask only when
  the plausible hits are similarly likely.
- Mention Open-Meteo in the answer (`attribution`).
- Wind: nearest of N NE E SE S SW W NW.

### WMO weather codes

| Code | Conditions |
| --- | --- |
| 0 | Clear sky |
| 1 | Mainly clear |
| 2 | Partly cloudy |
| 3 | Overcast |
| 45 | Fog |
| 48 | Depositing rime fog |
| 51, 53, 55 | Light, moderate, dense drizzle |
| 56, 57 | Light, dense freezing drizzle |
| 61, 63, 65 | Slight, moderate, heavy rain |
| 66, 67 | Light, heavy freezing rain |
| 71, 73, 75 | Slight, moderate, heavy snowfall |
| 77 | Snow grains |
| 80, 81, 82 | Slight, moderate, violent rain showers |
| 85, 86 | Slight, heavy snow showers |
| 95 | Thunderstorm |
| 96, 99 | Thunderstorm with slight, heavy hail |
| 97 | Heavy thunderstorm |
