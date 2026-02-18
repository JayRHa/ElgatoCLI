"""Transform raw Elgato responses into normalized CLI payloads."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .const import BATTERY_STATUS_MAP, POWER_ON_BEHAVIOR_MAP, POWER_SOURCE_MAP


def _dig(data: Mapping[str, Any], *path: str, default: Any = None) -> Any:
    """Read nested dict fields safely."""
    current: Any = data
    for key in path:
        if not isinstance(current, Mapping) or key not in current:
            return default
        current = current[key]
    return current


def _mired_to_kelvin(mired: int | None) -> int | None:
    if mired is None or mired <= 0:
        return None
    return round(1_000_000 / mired)


def _brightness_pct_to_255(brightness_pct: int | None) -> int | None:
    if brightness_pct is None:
        return None
    return round((brightness_pct * 255) / 100)


def transform_info(data: Mapping[str, Any]) -> dict[str, Any]:
    """Transform accessory info payload."""
    return {
        "display_name": data.get("display_name"),
        "product_name": data.get("product_name"),
        "serial_number": data.get("serial_number"),
        "firmware_version": data.get("firmware_version"),
        "firmware_build_number": data.get("firmware_build_number"),
        "hardware_board_type": data.get("hardware_board_type"),
        "features": data.get("features") or None,
        "mac_address": data.get("mac_address"),
        "wifi_ssid": _dig(data, "wifi", "ssid"),
        "wifi_rssi_dbm": _dig(data, "wifi", "rssi"),
        "wifi_frequency_mhz": _dig(data, "wifi", "frequency_mhz"),
    }


def transform_state(data: Mapping[str, Any]) -> dict[str, Any]:
    """Transform light state payload."""
    hue = data.get("hue")
    temperature_mired = data.get("temperature")
    brightness_pct = data.get("brightness")

    return {
        "on": data.get("on"),
        "brightness_pct": brightness_pct,
        "brightness_255": _brightness_pct_to_255(brightness_pct),
        "color_mode": "hs" if hue is not None else "color_temp",
        "hue_deg": hue,
        "saturation_pct": data.get("saturation"),
        "temperature_mired": temperature_mired,
        "temperature_kelvin": _mired_to_kelvin(temperature_mired),
    }


def transform_settings(data: Mapping[str, Any]) -> dict[str, Any]:
    """Transform settings payload."""
    power_on_temperature_mired = data.get("power_on_temperature")
    power_on_behavior_code = data.get("power_on_behavior")

    return {
        "color_change_duration_ms": data.get("color_change_duration"),
        "switch_on_duration_ms": data.get("switch_on_duration"),
        "switch_off_duration_ms": data.get("switch_off_duration"),
        "power_on_behavior": POWER_ON_BEHAVIOR_MAP.get(power_on_behavior_code),
        "power_on_behavior_code": power_on_behavior_code,
        "power_on_brightness_pct": data.get("power_on_brightness"),
        "power_on_hue_deg": data.get("power_on_hue"),
        "power_on_saturation_pct": data.get("power_on_saturation"),
        "power_on_temperature_mired": power_on_temperature_mired,
        "power_on_temperature_kelvin": _mired_to_kelvin(power_on_temperature_mired),
        "battery_present": data.get("battery") is not None,
        "battery_bypass": _dig(data, "battery", "bypass"),
        "energy_saving_enabled": _dig(data, "battery", "energy_saving", "enabled"),
        "energy_saving_disable_wifi": _dig(
            data,
            "battery",
            "energy_saving",
            "disable_wifi",
        ),
        "energy_saving_minimum_battery_level_pct": _dig(
            data,
            "battery",
            "energy_saving",
            "minimum_battery_level",
        ),
        "energy_saving_adjust_brightness_enabled": _dig(
            data,
            "battery",
            "energy_saving",
            "adjust_brightness",
            "enabled",
        ),
        "energy_saving_adjust_brightness_pct": _dig(
            data,
            "battery",
            "energy_saving",
            "adjust_brightness",
            "brightness",
        ),
    }


def transform_battery(data: Mapping[str, Any]) -> dict[str, Any]:
    """Transform battery payload."""
    power_source_code = data.get("power_source")
    status_code = data.get("status")
    input_charge_voltage_mv = data.get("input_charge_voltage_mv")
    input_charge_current_ma = data.get("input_charge_current_ma")

    charge_voltage_v = data.get("charge_voltage_v")
    if charge_voltage_v is None and input_charge_voltage_mv is not None:
        charge_voltage_v = round(input_charge_voltage_mv / 1000, 2)

    charge_current_a = data.get("charge_current_a")
    if charge_current_a is None and input_charge_current_ma is not None:
        charge_current_a = round(input_charge_current_ma / 1000, 2)

    charge_power_w = data.get("charge_power_w")
    if (
        charge_power_w is None
        and input_charge_voltage_mv is not None
        and input_charge_current_ma is not None
    ):
        charge_power_w = round(
            (input_charge_voltage_mv * input_charge_current_ma) / 1_000_000,
            2,
        )

    return {
        "power_source": POWER_SOURCE_MAP.get(power_source_code),
        "power_source_code": power_source_code,
        "status": BATTERY_STATUS_MAP.get(status_code),
        "status_code": status_code,
        "battery_level_pct": data.get("level"),
        "voltage_mv": data.get("voltage_mv"),
        "input_charge_voltage_mv": input_charge_voltage_mv,
        "input_charge_current_ma": input_charge_current_ma,
        "charge_voltage_v": charge_voltage_v,
        "charge_current_a": charge_current_a,
        "charge_power_w": charge_power_w,
    }


def build_summary(
    info_data: Mapping[str, Any],
    settings_data: Mapping[str, Any],
    state_data: Mapping[str, Any],
    battery_data: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Build a combined summary payload."""
    return {
        "info": transform_info(info_data),
        "settings": transform_settings(settings_data),
        "state": transform_state(state_data),
        "battery": None if battery_data is None else transform_battery(battery_data),
    }
