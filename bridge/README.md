# HOTIRJAM Bridge (Phase M1)

**Status:** Design module — transport only  
**Scope:** Windows → Mac market-data bridge  
**Non-goals:** Objective Engine, Physics, Intent, Decision, Validation, Live Validator, Dashboard

This package is **intentionally outside** `src/hotirjam_ai5/`.  
It must not import AI engines. AI host continues to consume **NT01/NT03 NDJSON** files written by the Mac receiver.

```
Windows                         Mac
NT01 / NT03 (unchanged)
     ↓
Bridge Sender  ──WSS/HTTP──►  Bridge Receiver
     ↓                              ↓
local NDJSON journal          local NDJSON for Data Engine
                              (existing ingress — untouched)
```

## Documents

| Doc | Content |
|-----|---------|
| [`docs/M1_BRIDGE_ARCHITECTURE.md`](docs/M1_BRIDGE_ARCHITECTURE.md) | End-to-end architecture |
| [`docs/BRIDGE_SENDER_WINDOWS.md`](docs/BRIDGE_SENDER_WINDOWS.md) | Windows Sender design |
| [`docs/BRIDGE_RECEIVER_MAC.md`](docs/BRIDGE_RECEIVER_MAC.md) | Mac Receiver design |

## Package layout

```
bridge/
  README.md
  docs/
  src/hotirjam_bridge/
    __init__.py
    contracts.py
    sender/           # M1.2 runtime: bridge_sender CLI (network OFF)
    receiver/         # Mac design surface (runtime later)
```

## Windows PowerShell — CLI not found?

`bridge_sender` / `hotirjam-bridge-sender` come from package **`hotirjam-bridge`**
in this folder only. Installing `HOTIRJAM_AI_5` (hotirjam-ai5) does **not** create them.

```powershell
cd HOTIRJAM_AI_5\bridge
.\install_windows.ps1
python -m hotirjam_bridge.sender --help
hotirjam-bridge-sender --help   # requires Scripts on PATH / venv activated
.\hotirjam-bridge-sender.cmd --help
```

Full guide: [`docs/WINDOWS_CLI_INSTALL.md`](docs/WINDOWS_CLI_INSTALL.md)

## M1.4 — HTTP live bridge

```bash
# Mac
bridge_receiver --http --out-dir ./HOTIRJAM --port 8765

# Windows
bridge_sender --tick-file .../mnq_ticks.ndjson --url http://MAC:8765
```

Live terminal **Bridge Status** board (Connected / Sent / Received / Dropped / Duplicate / Latency / Heartbeat).  
See [`docs/M1_4_HTTP_LIVE_BRIDGE.md`](docs/M1_4_HTTP_LIVE_BRIDGE.md).

## Implementation rule (locked for this sprint)

1. Design and contracts first (this module).  
2. Do **not** modify `hotirjam_ai5` AI packages.  
3. Sender/Receiver runtime code may be added later **inside this tree only**.  
4. Cutover = Receiver writes `mnq_ticks.ndjson` / `mnq_dom.ndjson`; AI reads files as today.
