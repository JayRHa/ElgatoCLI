"""Constants and mappings for the Elgato CLI."""

from __future__ import annotations

from typing import Final

DEFAULT_PORT: Final = 9123
DEFAULT_TIMEOUT_SECONDS: Final = 20

MIN_PORT: Final = 1
MAX_PORT: Final = 65535

MIN_BRIGHTNESS_PCT: Final = 0
MAX_BRIGHTNESS_PCT: Final = 100

MIN_HUE_DEG: Final = 0.0
MAX_HUE_DEG: Final = 360.0

MIN_SATURATION_PCT: Final = 0.0
MAX_SATURATION_PCT: Final = 100.0

MIN_TEMPERATURE_MIRED: Final = 143
MAX_TEMPERATURE_MIRED: Final = 344
MIN_TEMPERATURE_KELVIN: Final = 2900
MAX_TEMPERATURE_KELVIN: Final = 7000

POWER_ON_BEHAVIOR_MAP: Final[dict[int, str]] = {
    0: "unknown",
    1: "restore_last",
    2: "use_defaults",
}

POWER_SOURCE_MAP: Final[dict[int, str]] = {
    0: "unknown",
    1: "mains",
    2: "battery",
}

BATTERY_STATUS_MAP: Final[dict[int, str]] = {
    0: "draining",
    2: "charging",
    3: "charged",
}
