# HOTIRJAM Control Center v1

Mac-side ops menu for the **Bridge Receiver** and **Live Validator**.  
Does **not** modify bridge or AI Python code. Does **not** start the Windows sender.

## Quick start

```bash
cd HOTIRJAM_AI_5/control
chmod +x *.sh
./control_center.sh
```

Or run actions directly:

```bash
./start_hotirjam.sh
./status_hotirjam.sh
./stop_hotirjam.sh
./restart_hotirjam.sh
```

## What it starts

| Component | Detected command (in order) | Default args |
|-----------|----------------------------|--------------|
| Bridge Receiver | `hotirjam-bridge-receiver` → `bridge_receiver` → `python -m hotirjam_bridge.receiver` | `--http --out-dir {bridge}/HOTIRJAM --port 8765 --log-file {AI5}/logs/bridge_receiver.log` |
| Live Validator | `hotirjam-ai5-live-validator` → `python -m hotirjam_ai5.live_validator.app` | `--tick-file {bridge}/HOTIRJAM/mnq_ticks.ndjson` |

On macOS, Live Validator opens in a **new Terminal** window by default (`HOTIRJAM_VALIDATOR_MODE=terminal`). Set `HOTIRJAM_VALIDATOR_MODE=background` to nohup into `logs/live_validator.log`.

## Ports

| Port | Role |
|------|------|
| **8765** | M1.4 HTTP receiver (tick + dom + heartbeat) |
| **8766** | Compat / reserved DOM port — status reports LISTEN vs FREE (often free with single-port M1.4) |

## Environment overrides

| Variable | Purpose |
|----------|---------|
| `HOTIRJAM_AI5_ROOT` | Force AI5 root |
| `HOTIRJAM_OUT_DIR` | Receiver journal directory |
| `HOTIRJAM_RECEIVER_PORT` | Default `8765` |
| `HOTIRJAM_DOM_PORT` | Default `8766` (status only) |
| `HOTIRJAM_START_VALIDATOR` | `0` = receiver only |
| `HOTIRJAM_VALIDATOR_MODE` | `terminal` \| `background` |
| `HOTIRJAM_SYMBOL` | Default `MNQ` |
| `NO_COLOR` | Disable ANSI colors |

## Logs

All under `{HOTIRJAM_AI5_ROOT}/logs/`:

- `bridge_receiver.log`
- `live_validator.log`
- `control_center.log`
- `control/*.pid`
