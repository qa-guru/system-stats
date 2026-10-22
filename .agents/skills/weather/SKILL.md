---
name: weather
description: >-
  Report current weather for the machine's location, or for a place named
  in the request, via the read-only tools/weather/weather.py (Open-Meteo).
  Use when asked about weather, forecast, temperature, rain, wind, or
  conditions here or in a named place — including погода, прогноз,
  температура, дождь.
---

# weather

1. A place named in the request goes in `location`. Add a region or
   country after a comma only when the user gave one. No place — omit
   `location`; the tool resolves the machine's current location.
2. Set `language` to the user's two-letter language code (for example
   `ru`) so place names come back translated when available.
3. Run only this tool. If the sandbox blocks the network, request
   permission and rerun the same tool. Do not call weather, geocoding,
   or IP APIs yourself, and do not invent conditions.
4. Answer in a few lines from the JSON. Name the resolved place and
   attribute Open-Meteo.

Interface (arguments, output, errors) and interpretation rules:
`knowledge/weather/weather.md`.
