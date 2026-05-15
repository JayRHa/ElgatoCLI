<!-- unified-readme:start -->
<div align="center">

# Elgato CLI

**CLI tool for controlling Elgato devices from the terminal.**

Build. Automate. Share.

[![GitHub stars](https://img.shields.io/github/stars/JayRHa/ElgatoCLI?style=for-the-badge&logo=github&color=f4c542)](https://github.com/JayRHa/ElgatoCLI/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/JayRHa/ElgatoCLI?style=for-the-badge&logo=github&color=4078c0)](https://github.com/JayRHa/ElgatoCLI/network/members)
[![GitHub issues](https://img.shields.io/github/issues/JayRHa/ElgatoCLI?style=for-the-badge&logo=github&color=d73a4a)](https://github.com/JayRHa/ElgatoCLI/issues)
[![Contributors](https://img.shields.io/github/contributors/JayRHa/ElgatoCLI?style=for-the-badge&logo=github&color=28a745)](https://github.com/JayRHa/ElgatoCLI/graphs/contributors)

---

`CLI Tool` | `Python` | `Public` | `Maintained`

</div>

## What is this?

This repository provides cLI tool for controlling Elgato devices from the terminal.

> Browse the documentation below for setup notes, usage details, and project-specific context.

---

## Quick Start

1. Review the project documentation below.
2. Clone the repository:

   ```bash
   git clone https://github.com/JayRHa/ElgatoCLI.git
   ```

3. Follow the setup, deployment, or usage notes in the preserved documentation section.

---
<!-- unified-readme:end -->

## Existing Documentation

<div align="center">
  <h1>Elgato CLI</h1>
  <p><strong>Fast local control for Elgato lights with operator-friendly output and clean JSON.</strong></p>
  <p>
    <img src="https://img.shields.io/badge/python-3.11%2B-2d7ff9?style=for-the-badge" alt="Python 3.11+">
    <img src="https://img.shields.io/badge/interface-CLI-0f172a?style=for-the-badge" alt="CLI">
    <img src="https://img.shields.io/badge/output-text%20%7C%20json-0ea5e9?style=for-the-badge" alt="Text and JSON output">
    <img src="https://img.shields.io/badge/automation-ready-16a34a?style=for-the-badge" alt="Automation ready">
  </p>
</div>

## Overview

`elgato` is a high-signal command line tool for:

- device info, state, settings, and battery diagnostics
- direct light control (on/off, brightness, color temperature, hue/saturation)
- clean machine-readable JSON for pipelines
- fast terminal-first human output

## 60-Second Quickstart

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -e .

export ELGATO_HOST="192.168.1.40"

elgato info
elgato state
elgato light --on --brightness-pct 45 --temperature-kelvin 5000
elgato summary --json
```

## Why It Feels Great To Use

- Single command surface: `elgato`
- Strict argument validation with clear errors
- Human view for operators, JSON view for automation
- Built-in device actions (`identify`, `restart`, battery switch controls)
- Predictable exit codes for CI and scripts

## Install

```bash
python3 -m pip install -e .
```

If your Python is externally managed, use a virtualenv (recommended).

## Authentication

No authentication is required for direct local device access.

`--api-key` and `ELGATO_API_KEY` are accepted only for CLI interface consistency in shared automation.

```bash
elgato --api-key "<OPTIONAL_PLACEHOLDER>" --host 192.168.1.40 info
```

```bash
export ELGATO_API_KEY="<OPTIONAL_PLACEHOLDER>"
elgato --host 192.168.1.40 state
```

## Command Matrix

| Command | Purpose | Common flags |
| --- | --- | --- |
| `info` | Device metadata and Wi-Fi details | `--host`, `--json` |
| `state` | Current power/brightness/color state | `--host`, `--json` |
| `settings` | Persistent device settings | `--host`, `--json` |
| `battery` | Battery and charging metrics | `--host`, `--json` |
| `light` | Change light output | `--on/--off`, `--brightness-pct`, `--temperature-kelvin`, `--hue`, `--saturation-pct` |
| `bypass` | Toggle battery bypass (studio mode) | `--on/--off`, `--json` |
| `energy-saving` | Toggle energy-saving mode | `--on/--off`, `--json` |
| `identify` | Trigger identify blink | `--host`, `--json` |
| `restart` | Restart device | `--host`, `--json` |
| `summary` | Combined info + settings + state + battery | `--host`, `--json` |

## Usage Examples

### `info`

```bash
elgato --host 192.168.1.40 info
elgato --host 192.168.1.40 info --json
```

### `state`

```bash
elgato --host 192.168.1.40 state
elgato state --json
```

### `settings`

```bash
elgato --host 192.168.1.40 settings
elgato settings --json
```

### `battery`

```bash
elgato --host 192.168.1.40 battery
elgato battery --json
```

### `light`

```bash
elgato --host 192.168.1.40 light --on --brightness-pct 60
elgato --host 192.168.1.40 light --hue 210 --saturation-pct 55 --json
```

### `bypass`

```bash
elgato --host 192.168.1.40 bypass --on
elgato --host 192.168.1.40 bypass --off --json
```

### `energy-saving`

```bash
elgato --host 192.168.1.40 energy-saving --on
elgato --host 192.168.1.40 energy-saving --off --json
```

### `identify`

```bash
elgato --host 192.168.1.40 identify
elgato identify --json
```

### `restart`

```bash
elgato --host 192.168.1.40 restart
elgato restart --json
```

### `summary`

```bash
elgato --host 192.168.1.40 summary
elgato summary --json
```

## Automation Recipes

Read current temperature (Kelvin):

```bash
elgato summary --json | jq -r '.state.temperature_kelvin'
```

Read battery level safely (devices without battery return `null`):

```bash
elgato summary --json | jq -r '.battery.battery_level_pct // "n/a"'
```

Wait until light is on:

```bash
until [ "$(elgato state --json | jq -r '.state.on')" = "true" ]; do sleep 1; done
```

## Exit Codes

| Code | Meaning |
| --- | --- |
| `0` | Success |
| `1` | API/network/runtime error |
| `2` | Input/auth/rate-limit error |

## Troubleshooting

`Input error: Host missing. Use --host or ELGATO_HOST.`
Set `--host` explicitly or export `ELGATO_HOST`.

`Input error: Device has no battery.`
Your model does not expose battery endpoints; skip `battery`, `bypass`, and `energy-saving`.

`Input error: Do not mix --temperature-kelvin with --hue/--saturation-pct.`
Choose either color temperature mode or HS mode per command.

`Error while calling Elgato device`
Check IP/port reachability and that the device is online in the local network.

## Developer Notes

Run from source:

```bash
PYTHONPATH=src python3 -m elgato_cli --help
```

Compile check:

```bash
python3 -m compileall -q src tests
```

Tests:

```bash
PYTHONPATH=src python3 -m pytest -q
```

## Project Structure

```text
src/elgato_cli/
  cli.py           # parsing, command execution, output rendering
  transform.py     # normalization layer
  const.py         # constants and mappings
  __main__.py      # python -m entrypoint
tests/
  test_transform.py
```

## Security

- Never commit API keys.
- Prefer environment variables in CI/CD.
- Restrict network access to trusted LAN segments when automating device control.
