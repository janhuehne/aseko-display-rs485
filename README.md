# Aseko Display RS485

[![hacs_badge](https://img.shields.io/badge/HACS-Default-41BDF5.svg)](https://github.com/hacs/integration)
[![GitHub release](https://img.shields.io/github/release/janhuehne/aseko-display-rs485.svg)](https://github.com/janhuehne/aseko-display-rs485/releases)
[![Validate](https://github.com/janhuehne/aseko-display-rs485/actions/workflows/validate.yml/badge.svg)](https://github.com/janhuehne/aseko-display-rs485/actions/workflows/validate.yml)

Home Assistant custom integration for **read-only** monitoring of Aseko ASIN Aqua
units via the **external Display RS485 bus**, typically bridged with a
Waveshare (or similar) RS485-to-Ethernet converter.

This does **not** talk to Aseko Cloud and does **not** change the unit’s Ethernet
remote-server settings. For the cloud TCP stream (port 47524), see
[aseko_local](https://github.com/hopkins-tk/home-assistant-aseko-local) instead.

> Protocol details are reverse-engineered from community captures. Decode quality
> varies by unit type; treat values as best-effort until verified against your display.

## Features

- Local TCP listener (default port **47525**)
- pH, chlorine / redox, water temperature, setpoints
- Filtration / electrolysis / dosing binary sensors (where mapped)
- Salt-oriented diagnostic error bits
- Peer allowlist, single-client limit, 60s freshness timeout

## Requirements

- Home Assistant 2024.12+
- ASIN Aqua with **RS485 Display** terminals (e.g. Salt)
- RS485 ↔ Ethernet bridge in **TCP Client** mode, **57600 8N1**, protocol None

## Install (HACS)

1. HACS → **Integrations** → search for **Aseko Display RS485**
2. Download, restart Home Assistant
3. Settings → Devices & services → **Add integration** → **Aseko Display RS485**

### Fallback: custom repository

If it does not appear in search yet (HACS cache not refreshed):

1. HACS → **Integrations** → ⋮ → **Custom repositories**
2. URL: `https://github.com/janhuehne/aseko-display-rs485` — category **Integration**
3. Download **Aseko Display RS485**, then continue from step 2 above

## Configuration

| Option | Default | Notes |
|--------|---------|--------|
| Bind address | `0.0.0.0` | Where HA listens |
| Port | `47525` | Must match the bridge destination port |
| Allowed host | *(empty)* | Set to your bridge’s LAN IP (recommended) |

Bridge example: TCP Client → `<home-assistant-ip>:47525`.

## Wiring

On the ASIN **RS485 Display** block, connect bridge **A / B / GND** (leave 12 V
unused if the bridge is PoE-powered). Do not use the Extender RS485 pair for
this integration.

## Optional dashboard

`examples/lovelace.dashboard_pool.json` is a sample storage-mode dashboard.
History charts need [apexcharts-card](https://github.com/RomRider/apexcharts-card).

## Protocol notes

- 27-byte frames, start `0x0A`, XOR CRC seed `0xAA`
- Status/telemetry only — **no write/control** (display command frames are undocumented)
- Chlorine vs redox setpoints use different scaling

## Development

```bash
python3 -m pytest tests/ -q
```

## License

MIT — see [LICENSE](LICENSE).

Not affiliated with Aseko.
