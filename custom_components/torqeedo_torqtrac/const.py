"""Constants for Torqeedo TorqTrac."""

DOMAIN = "torqeedo_torqtrac"

SIGNAL_UPDATE = f"{DOMAIN}_update_{{address}}"

# Seconds without a valid frame before entities go unavailable (link still up)
STALE_AFTER = 30
RECONNECT_MIN = 5
RECONNECT_MAX = 120
