"""Command line interface for Elgato lights."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from collections.abc import Mapping, Sequence
from typing import Any

from aiohttp import ClientError, ClientSession, ClientTimeout
from elgato import Elgato, ElgatoConnectionError, ElgatoError, ElgatoNoBatteryError

from .const import (
    DEFAULT_PORT,
    DEFAULT_TIMEOUT_SECONDS,
    MAX_BRIGHTNESS_PCT,
    MAX_HUE_DEG,
    MAX_PORT,
    MAX_SATURATION_PCT,
    MAX_TEMPERATURE_KELVIN,
    MAX_TEMPERATURE_MIRED,
    MIN_BRIGHTNESS_PCT,
    MIN_HUE_DEG,
    MIN_PORT,
    MIN_SATURATION_PCT,
    MIN_TEMPERATURE_KELVIN,
    MIN_TEMPERATURE_MIRED,
)
from .transform import (
    build_summary,
    transform_battery,
    transform_info,
    transform_settings,
    transform_state,
)


class CliInputError(ValueError):
    """Raised for invalid CLI argument combinations."""


def _env_port() -> int:
    raw_port = os.getenv("ELGATO_PORT")
    if raw_port is None:
        return DEFAULT_PORT

    try:
        return int(raw_port)
    except ValueError:
        return DEFAULT_PORT


def _enum_to_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _kelvin_to_mired(kelvin: int | None) -> int | None:
    if kelvin is None:
        return None
    return round(1_000_000 / kelvin)


def _render_value(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, list):
        return ", ".join(str(item) for item in value) if value else "-"
    return str(value)


def _render_table(headers: list[str], rows: list[list[Any]]) -> str:
    """Render rows as a plain text table."""
    normalized_rows = [
        ["-" if value is None else str(value) for value in row] for row in rows
    ]
    widths = [len(h) for h in headers]

    for row in normalized_rows:
        for index, value in enumerate(row):
            widths[index] = max(widths[index], len(value))

    header_line = " | ".join(
        header.ljust(widths[i]) for i, header in enumerate(headers)
    )
    separator = "-+-".join("-" * width for width in widths)
    body = [
        " | ".join(value.ljust(widths[i]) for i, value in enumerate(row))
        for row in normalized_rows
    ]

    return "\n".join([header_line, separator, *body])


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser."""
    parser = argparse.ArgumentParser(
        prog="elgato",
        description=(
            "Control and inspect Elgato lights from the terminal "
            "with human and JSON output"
        ),
    )
    parser.add_argument(
        "--host",
        default=os.getenv("ELGATO_HOST"),
        help="Device host/IP (or env ELGATO_HOST)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=_env_port(),
        help=f"Device port (default: {DEFAULT_PORT}, env ELGATO_PORT)",
    )
    parser.add_argument(
        "--api-key",
        default=os.getenv("ELGATO_API_KEY"),
        help="Optional key placeholder (or env ELGATO_API_KEY)",
    )
    parser.add_argument(
        "--language",
        default="en",
        help="Language code placeholder for CLI consistency",
    )
    parser.add_argument(
        "--json", dest="json_output", action="store_true", help="Output as JSON"
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("info", help="Show device info")
    subparsers.add_parser("state", help="Show current light state")
    subparsers.add_parser("settings", help="Show current device settings")
    subparsers.add_parser("battery", help="Show battery information")
    subparsers.add_parser("identify", help="Trigger identify blink")
    subparsers.add_parser("restart", help="Restart the device")

    light_parser = subparsers.add_parser("light", help="Change light state")
    light_power_group = light_parser.add_mutually_exclusive_group()
    light_power_group.add_argument("--on", action="store_true", help="Turn light on")
    light_power_group.add_argument(
        "--off", action="store_true", help="Turn light off"
    )
    light_parser.add_argument(
        "--brightness-pct",
        type=int,
        help="Brightness in percent (0-100)",
    )
    light_parser.add_argument(
        "--temperature-kelvin",
        type=int,
        help="Color temperature in kelvin",
    )
    light_parser.add_argument("--hue", type=float, help="Hue in degrees (0-360)")
    light_parser.add_argument(
        "--saturation-pct",
        type=float,
        help="Saturation in percent (0-100)",
    )

    bypass_parser = subparsers.add_parser(
        "bypass",
        help="Set battery bypass (studio mode)",
    )
    bypass_group = bypass_parser.add_mutually_exclusive_group(required=True)
    bypass_group.add_argument("--on", action="store_true", help="Enable bypass")
    bypass_group.add_argument("--off", action="store_true", help="Disable bypass")

    energy_parser = subparsers.add_parser(
        "energy-saving",
        help="Enable or disable energy saving",
    )
    energy_group = energy_parser.add_mutually_exclusive_group(required=True)
    energy_group.add_argument(
        "--on", action="store_true", help="Enable energy saving"
    )
    energy_group.add_argument(
        "--off", action="store_true", help="Disable energy saving"
    )

    subparsers.add_parser("summary", help="Show info + settings + state + battery")

    return parser


def validate_args(args: argparse.Namespace) -> None:
    """Validate argument combinations."""
    if not args.host:
        raise CliInputError("Host missing. Use --host or ELGATO_HOST.")

    if not MIN_PORT <= args.port <= MAX_PORT:
        raise CliInputError(f"--port must be between {MIN_PORT} and {MAX_PORT}.")

    if args.command != "light":
        return

    has_light_change = any(
        value is not None
        for value in (
            True if args.on else None,
            True if args.off else None,
            args.brightness_pct,
            args.temperature_kelvin,
            args.hue,
            args.saturation_pct,
        )
    )
    if not has_light_change:
        raise CliInputError(
            "`light` needs at least one change flag "
            "(--on/--off/--brightness-pct/--temperature-kelvin/--hue/--saturation-pct)."
        )

    if args.brightness_pct is not None and not (
        MIN_BRIGHTNESS_PCT <= args.brightness_pct <= MAX_BRIGHTNESS_PCT
    ):
        raise CliInputError(
            f"--brightness-pct must be between {MIN_BRIGHTNESS_PCT} and {MAX_BRIGHTNESS_PCT}."
        )

    if args.hue is not None and not (MIN_HUE_DEG <= args.hue <= MAX_HUE_DEG):
        raise CliInputError(f"--hue must be between {MIN_HUE_DEG} and {MAX_HUE_DEG}.")

    if args.saturation_pct is not None and not (
        MIN_SATURATION_PCT <= args.saturation_pct <= MAX_SATURATION_PCT
    ):
        raise CliInputError(
            "--saturation-pct must be between "
            f"{MIN_SATURATION_PCT} and {MAX_SATURATION_PCT}."
        )

    if args.temperature_kelvin is not None and not (
        MIN_TEMPERATURE_KELVIN <= args.temperature_kelvin <= MAX_TEMPERATURE_KELVIN
    ):
        raise CliInputError(
            "--temperature-kelvin must be between "
            f"{MIN_TEMPERATURE_KELVIN} and {MAX_TEMPERATURE_KELVIN}."
        )

    if args.temperature_kelvin is not None and (
        args.hue is not None or args.saturation_pct is not None
    ):
        raise CliInputError("Do not mix --temperature-kelvin with --hue/--saturation-pct.")



def _location_from_info(
    host: str,
    port: int,
    info_payload: Mapping[str, Any] | None,
) -> dict[str, Any]:
    if info_payload is None:
        return {
            "host": host,
            "port": port,
            "display_name": None,
            "product_name": None,
            "serial_number": None,
        }

    return {
        "host": host,
        "port": port,
        "display_name": info_payload.get("display_name"),
        "product_name": info_payload.get("product_name"),
        "serial_number": info_payload.get("serial_number"),
    }



def _raw_info(info: Any) -> dict[str, Any]:
    wifi = getattr(info, "wifi", None)
    return {
        "display_name": getattr(info, "display_name", None),
        "product_name": getattr(info, "product_name", None),
        "serial_number": getattr(info, "serial_number", None),
        "firmware_version": getattr(info, "firmware_version", None),
        "firmware_build_number": getattr(info, "firmware_build_number", None),
        "hardware_board_type": getattr(info, "hardware_board_type", None),
        "features": getattr(info, "features", None),
        "mac_address": getattr(info, "mac_address", None),
        "wifi": (
            None
            if wifi is None
            else {
                "ssid": getattr(wifi, "ssid", None),
                "rssi": getattr(wifi, "rssi", None),
                "frequency_mhz": getattr(wifi, "frequency", None),
            }
        ),
    }



def _raw_settings(settings: Any) -> dict[str, Any]:
    battery = getattr(settings, "battery", None)
    energy_saving = getattr(battery, "energy_saving", None) if battery else None
    adjust_brightness = (
        getattr(energy_saving, "adjust_brightness", None) if energy_saving else None
    )

    return {
        "color_change_duration": getattr(settings, "color_change_duration", None),
        "power_on_behavior": _enum_to_int(getattr(settings, "power_on_behavior", None)),
        "power_on_brightness": getattr(settings, "power_on_brightness", None),
        "switch_off_duration": getattr(settings, "switch_off_duration", None),
        "switch_on_duration": getattr(settings, "switch_on_duration", None),
        "power_on_hue": getattr(settings, "power_on_hue", None),
        "power_on_saturation": getattr(settings, "power_on_saturation", None),
        "power_on_temperature": getattr(settings, "power_on_temperature", None),
        "battery": (
            None
            if battery is None
            else {
                "bypass": getattr(battery, "bypass", None),
                "energy_saving": (
                    None
                    if energy_saving is None
                    else {
                        "enabled": getattr(energy_saving, "enabled", None),
                        "disable_wifi": getattr(energy_saving, "disable_wifi", None),
                        "minimum_battery_level": getattr(
                            energy_saving,
                            "minimum_battery_level",
                            None,
                        ),
                        "adjust_brightness": (
                            None
                            if adjust_brightness is None
                            else {
                                "enabled": getattr(adjust_brightness, "enabled", None),
                                "brightness": getattr(adjust_brightness, "brightness", None),
                            }
                        ),
                    }
                ),
            }
        ),
    }



def _raw_state(state: Any) -> dict[str, Any]:
    return {
        "on": getattr(state, "on", None),
        "brightness": getattr(state, "brightness", None),
        "hue": getattr(state, "hue", None),
        "saturation": getattr(state, "saturation", None),
        "temperature": getattr(state, "temperature", None),
    }



def _raw_battery(battery: Any) -> dict[str, Any]:
    return {
        "power_source": _enum_to_int(getattr(battery, "power_source", None)),
        "status": _enum_to_int(getattr(battery, "status", None)),
        "level": getattr(battery, "level", None),
        "voltage_mv": getattr(battery, "voltage", None),
        "input_charge_voltage_mv": getattr(battery, "input_charge_voltage", None),
        "input_charge_current_ma": getattr(battery, "input_charge_current", None),
        "charge_voltage_v": getattr(battery, "charge_voltage", None),
        "charge_current_a": getattr(battery, "charge_current", None),
        "charge_power_w": getattr(battery, "charge_power", None),
    }



def print_human(command: str, payload: dict[str, Any]) -> None:
    """Print result in human-readable format."""
    location = payload["location"]
    loc_name = location.get("display_name") or location.get("host")
    serial = location.get("serial_number")
    endpoint = f"{location.get('host')}:{location.get('port')}"

    if serial:
        print(f"Location: {loc_name} ({serial}) @ {endpoint}")
    else:
        print(f"Location: {loc_name} @ {endpoint}")

    if command == "info":
        info = payload["info"]
        for label, key in (
            ("Display name", "display_name"),
            ("Product", "product_name"),
            ("Serial", "serial_number"),
            ("Firmware", "firmware_version"),
            ("Firmware build", "firmware_build_number"),
            ("Hardware board", "hardware_board_type"),
            ("MAC", "mac_address"),
            ("Features", "features"),
            ("WiFi SSID", "wifi_ssid"),
            ("WiFi RSSI (dBm)", "wifi_rssi_dbm"),
            ("WiFi frequency (MHz)", "wifi_frequency_mhz"),
        ):
            print(f"{label}: {_render_value(info.get(key))}")
        return

    if command in {"state", "light"}:
        state = payload["state"]
        for label, key in (
            ("On", "on"),
            ("Brightness (%)", "brightness_pct"),
            ("Brightness (1-255)", "brightness_255"),
            ("Color mode", "color_mode"),
            ("Hue (deg)", "hue_deg"),
            ("Saturation (%)", "saturation_pct"),
            ("Temperature (K)", "temperature_kelvin"),
            ("Temperature (mired)", "temperature_mired"),
        ):
            print(f"{label}: {_render_value(state.get(key))}")

        if command == "light":
            applied = payload["applied"]
            print("\nApplied:")
            rows = [
                [
                    applied.get("on"),
                    applied.get("brightness_pct"),
                    applied.get("hue_deg"),
                    applied.get("saturation_pct"),
                    applied.get("temperature_kelvin"),
                ]
            ]
            print(
                _render_table(
                    [
                        "on",
                        "brightness_pct",
                        "hue_deg",
                        "saturation_pct",
                        "temp_kelvin",
                    ],
                    rows,
                )
            )
        return

    if command == "settings":
        settings = payload["settings"]
        for label, key in (
            ("Power-on behavior", "power_on_behavior"),
            ("Power-on behavior code", "power_on_behavior_code"),
            ("Power-on brightness (%)", "power_on_brightness_pct"),
            ("Power-on hue (deg)", "power_on_hue_deg"),
            ("Power-on saturation (%)", "power_on_saturation_pct"),
            ("Power-on temperature (K)", "power_on_temperature_kelvin"),
            ("Color change duration (ms)", "color_change_duration_ms"),
            ("Switch-on duration (ms)", "switch_on_duration_ms"),
            ("Switch-off duration (ms)", "switch_off_duration_ms"),
            ("Battery present", "battery_present"),
            ("Battery bypass", "battery_bypass"),
            ("Energy saving", "energy_saving_enabled"),
            ("Energy saving disable WiFi", "energy_saving_disable_wifi"),
            (
                "Energy saving min battery (%)",
                "energy_saving_minimum_battery_level_pct",
            ),
            (
                "Energy saving adjust brightness",
                "energy_saving_adjust_brightness_enabled",
            ),
            (
                "Energy saving brightness (%)",
                "energy_saving_adjust_brightness_pct",
            ),
        ):
            print(f"{label}: {_render_value(settings.get(key))}")
        return

    if command == "battery":
        battery = payload["battery"]
        for label, key in (
            ("Power source", "power_source"),
            ("Status", "status"),
            ("Battery level (%)", "battery_level_pct"),
            ("Voltage (mV)", "voltage_mv"),
            ("Input charge voltage (mV)", "input_charge_voltage_mv"),
            ("Input charge current (mA)", "input_charge_current_ma"),
            ("Charge voltage (V)", "charge_voltage_v"),
            ("Charge current (A)", "charge_current_a"),
            ("Charge power (W)", "charge_power_w"),
        ):
            print(f"{label}: {_render_value(battery.get(key))}")
        return

    if command in {"bypass", "energy-saving"}:
        switch = payload["switch"]
        print(f"Switch: {_render_value(switch.get('name'))}")
        print(f"Enabled: {_render_value(switch.get('enabled'))}")
        print(
            f"Battery bypass: {_render_value(payload['settings'].get('battery_bypass'))}"
        )
        print(
            "Energy saving: "
            f"{_render_value(payload['settings'].get('energy_saving_enabled'))}"
        )
        return

    if command in {"identify", "restart"}:
        print(f"Result: {_render_value(payload.get('result'))}")
        return

    summary = payload
    print("\nState:")
    state = summary["state"]
    print(
        _render_table(
            ["on", "brightness_pct", "color_mode", "temp_k", "hue_deg", "sat_pct"],
            [
                [
                    state.get("on"),
                    state.get("brightness_pct"),
                    state.get("color_mode"),
                    state.get("temperature_kelvin"),
                    state.get("hue_deg"),
                    state.get("saturation_pct"),
                ]
            ],
        )
    )

    print("\nSettings:")
    settings = summary["settings"]
    print(
        _render_table(
            ["power_on", "brightness_pct", "bypass", "energy_saving"],
            [
                [
                    settings.get("power_on_behavior"),
                    settings.get("power_on_brightness_pct"),
                    settings.get("battery_bypass"),
                    settings.get("energy_saving_enabled"),
                ]
            ],
        )
    )

    if summary.get("battery") is not None:
        print("\nBattery:")
        battery = summary["battery"]
        print(
            _render_table(
                ["level_pct", "status", "source", "charge_power_w"],
                [
                    [
                        battery.get("battery_level_pct"),
                        battery.get("status"),
                        battery.get("power_source"),
                        battery.get("charge_power_w"),
                    ]
                ],
            )
        )


async def run_command(args: argparse.Namespace) -> dict[str, Any]:
    """Execute the selected command."""
    timeout = ClientTimeout(total=DEFAULT_TIMEOUT_SECONDS)

    async with ClientSession(timeout=timeout) as session:
        client = Elgato(args.host, port=args.port, session=session)

        if args.command == "info":
            info_payload = transform_info(_raw_info(await client.info()))
            return {
                "command": args.command,
                "location": _location_from_info(args.host, args.port, info_payload),
                "info": info_payload,
            }

        if args.command == "state":
            info_obj, state_obj = await asyncio.gather(client.info(), client.state())
            info_payload = transform_info(_raw_info(info_obj))
            return {
                "command": args.command,
                "location": _location_from_info(args.host, args.port, info_payload),
                "state": transform_state(_raw_state(state_obj)),
            }

        if args.command == "settings":
            info_obj, settings_obj = await asyncio.gather(client.info(), client.settings())
            info_payload = transform_info(_raw_info(info_obj))
            return {
                "command": args.command,
                "location": _location_from_info(args.host, args.port, info_payload),
                "settings": transform_settings(_raw_settings(settings_obj)),
            }

        if args.command == "battery":
            info_obj, battery_obj = await asyncio.gather(client.info(), client.battery())
            info_payload = transform_info(_raw_info(info_obj))
            return {
                "command": args.command,
                "location": _location_from_info(args.host, args.port, info_payload),
                "battery": transform_battery(_raw_battery(battery_obj)),
            }

        if args.command == "identify":
            info_payload = transform_info(_raw_info(await client.info()))
            await client.identify()
            return {
                "command": args.command,
                "location": _location_from_info(args.host, args.port, info_payload),
                "result": "identify_triggered",
            }

        if args.command == "restart":
            info_payload = transform_info(_raw_info(await client.info()))
            await client.restart()
            return {
                "command": args.command,
                "location": _location_from_info(args.host, args.port, info_payload),
                "result": "restart_requested",
            }

        if args.command == "light":
            on_value = True if args.on else False if args.off else None
            temperature_mired = _kelvin_to_mired(args.temperature_kelvin)
            if (
                temperature_mired is not None
                and not MIN_TEMPERATURE_MIRED <= temperature_mired <= MAX_TEMPERATURE_MIRED
            ):
                raise CliInputError(
                    "Converted mired temperature is out of range "
                    f"({MIN_TEMPERATURE_MIRED}-{MAX_TEMPERATURE_MIRED})."
                )

            await client.light(
                on=on_value,
                brightness=args.brightness_pct,
                hue=args.hue,
                saturation=args.saturation_pct,
                temperature=temperature_mired,
            )

            info_obj, state_obj = await asyncio.gather(client.info(), client.state())
            info_payload = transform_info(_raw_info(info_obj))

            return {
                "command": args.command,
                "location": _location_from_info(args.host, args.port, info_payload),
                "applied": {
                    "on": on_value,
                    "brightness_pct": args.brightness_pct,
                    "hue_deg": args.hue,
                    "saturation_pct": args.saturation_pct,
                    "temperature_kelvin": args.temperature_kelvin,
                    "temperature_mired": temperature_mired,
                },
                "state": transform_state(_raw_state(state_obj)),
            }

        if args.command == "bypass":
            await client.battery_bypass(on=args.on)
            info_obj, settings_obj = await asyncio.gather(client.info(), client.settings())
            info_payload = transform_info(_raw_info(info_obj))
            return {
                "command": args.command,
                "location": _location_from_info(args.host, args.port, info_payload),
                "switch": {"name": "bypass", "enabled": args.on},
                "settings": transform_settings(_raw_settings(settings_obj)),
            }

        if args.command == "energy-saving":
            await client.energy_saving(on=args.on)
            info_obj, settings_obj = await asyncio.gather(client.info(), client.settings())
            info_payload = transform_info(_raw_info(info_obj))
            return {
                "command": args.command,
                "location": _location_from_info(args.host, args.port, info_payload),
                "switch": {"name": "energy_saving", "enabled": args.on},
                "settings": transform_settings(_raw_settings(settings_obj)),
            }

        info_obj, settings_obj, state_obj = await asyncio.gather(
            client.info(),
            client.settings(),
            client.state(),
        )
        battery_raw = None
        if await client.has_battery():
            battery_raw = _raw_battery(await client.battery())

        info_payload = transform_info(_raw_info(info_obj))
        summary = build_summary(
            _raw_info(info_obj),
            _raw_settings(settings_obj),
            _raw_state(state_obj),
            battery_raw,
        )
        return {
            "command": args.command,
            "location": _location_from_info(args.host, args.port, info_payload),
            **summary,
        }


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point."""
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        validate_args(args)
        payload = asyncio.run(run_command(args))
    except CliInputError as error:
        print(f"Input error: {error}", file=sys.stderr)
        return 2
    except ElgatoNoBatteryError:
        print("Input error: Device has no battery.", file=sys.stderr)
        return 2
    except ElgatoError as error:
        print(f"Input error: {error}", file=sys.stderr)
        return 2
    except (ElgatoConnectionError, ClientError, TimeoutError) as error:
        print(f"Error while calling Elgato device: {error}", file=sys.stderr)
        return 1

    if args.json_output:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print_human(args.command, payload)

    return 0
