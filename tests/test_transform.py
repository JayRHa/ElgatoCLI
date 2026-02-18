"""Tests for transformation helpers."""

from __future__ import annotations

from elgato_cli.transform import (
    build_summary,
    transform_battery,
    transform_info,
    transform_settings,
    transform_state,
)


def test_transform_info() -> None:
    raw = {
        "display_name": "Desk Light",
        "product_name": "Elgato Key Light",
        "serial_number": "ABC123",
        "firmware_version": "1.2.3",
        "firmware_build_number": 456,
        "hardware_board_type": 2,
        "features": ["lights", "identify"],
        "mac_address": "aa:bb:cc:dd:ee:ff",
        "wifi": {"ssid": "Studio", "rssi": -52, "frequency_mhz": 5200},
    }

    transformed = transform_info(raw)

    assert transformed["display_name"] == "Desk Light"
    assert transformed["serial_number"] == "ABC123"
    assert transformed["wifi_ssid"] == "Studio"
    assert transformed["wifi_rssi_dbm"] == -52


def test_transform_state_color_temp() -> None:
    raw = {
        "on": True,
        "brightness": 42,
        "hue": None,
        "saturation": None,
        "temperature": 200,
    }

    transformed = transform_state(raw)

    assert transformed["color_mode"] == "color_temp"
    assert transformed["brightness_255"] == 107
    assert transformed["temperature_kelvin"] == 5000


def test_transform_state_hs_mode() -> None:
    raw = {
        "on": True,
        "brightness": 100,
        "hue": 210.0,
        "saturation": 50.0,
        "temperature": None,
    }

    transformed = transform_state(raw)

    assert transformed["color_mode"] == "hs"
    assert transformed["hue_deg"] == 210.0
    assert transformed["saturation_pct"] == 50.0
    assert transformed["temperature_kelvin"] is None


def test_transform_settings_with_battery() -> None:
    raw = {
        "color_change_duration": 250,
        "power_on_behavior": 1,
        "power_on_brightness": 75,
        "switch_off_duration": 100,
        "switch_on_duration": 120,
        "power_on_hue": 180.0,
        "power_on_saturation": 40.0,
        "power_on_temperature": 220,
        "battery": {
            "bypass": True,
            "energy_saving": {
                "enabled": True,
                "disable_wifi": False,
                "minimum_battery_level": 30,
                "adjust_brightness": {"enabled": True, "brightness": 20},
            },
        },
    }

    transformed = transform_settings(raw)

    assert transformed["power_on_behavior"] == "restore_last"
    assert transformed["power_on_temperature_kelvin"] == 4545
    assert transformed["battery_present"] is True
    assert transformed["battery_bypass"] is True
    assert transformed["energy_saving_adjust_brightness_pct"] == 20


def test_transform_settings_without_battery() -> None:
    raw = {
        "color_change_duration": 250,
        "power_on_behavior": 2,
        "power_on_brightness": 50,
        "switch_off_duration": 100,
        "switch_on_duration": 120,
        "power_on_hue": None,
        "power_on_saturation": None,
        "power_on_temperature": None,
        "battery": None,
    }

    transformed = transform_settings(raw)

    assert transformed["power_on_behavior"] == "use_defaults"
    assert transformed["battery_present"] is False
    assert transformed["battery_bypass"] is None


def test_transform_battery_computed_values() -> None:
    raw = {
        "power_source": 2,
        "status": 2,
        "level": 64.0,
        "voltage_mv": 3690,
        "input_charge_voltage_mv": 5200,
        "input_charge_current_ma": 1100,
        "charge_voltage_v": None,
        "charge_current_a": None,
        "charge_power_w": None,
    }

    transformed = transform_battery(raw)

    assert transformed["power_source"] == "battery"
    assert transformed["status"] == "charging"
    assert transformed["battery_level_pct"] == 64.0
    assert transformed["charge_voltage_v"] == 5.2
    assert transformed["charge_current_a"] == 1.1
    assert transformed["charge_power_w"] == 5.72


def test_build_summary_without_battery() -> None:
    info_raw = {"display_name": "Desk", "product_name": "Key Light", "serial_number": "1"}
    settings_raw = {
        "color_change_duration": 100,
        "power_on_behavior": 0,
        "power_on_brightness": 50,
        "switch_off_duration": 100,
        "switch_on_duration": 100,
        "power_on_hue": None,
        "power_on_saturation": None,
        "power_on_temperature": None,
        "battery": None,
    }
    state_raw = {
        "on": False,
        "brightness": 0,
        "hue": None,
        "saturation": None,
        "temperature": 300,
    }

    summary = build_summary(info_raw, settings_raw, state_raw, None)

    assert summary["info"]["display_name"] == "Desk"
    assert summary["state"]["temperature_kelvin"] == 3333
    assert summary["battery"] is None
