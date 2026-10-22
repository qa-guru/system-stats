# AGENTS.md

## System diagnostics

Machine state (CPU, memory, disk, uptime, processes, ports, benchmark) is
collected only via the `system-stats` skill. Never gather these metrics
with ad-hoc shell commands; read-only: never kill processes or change
system settings.

## Weather

Weather for the machine's current location, or for a place the user
named, is reported only via the `weather` skill. Never call weather,
geocoding, or IP-location APIs directly, and never invent conditions.
