# HOTIRJAM Gateway — NinjaTrader 8 AddOn (Sprint NT-1)

Standalone NinjaTrader AddOn that hosts the HOTIRJAM Gateway connection lifecycle.

**Hard rules for this sprint:** no Tick subscriptions, no DOM subscriptions, no orders, no broker API, no trading logic.

This folder is **not** part of the Python `hotirjam_gateway` package. The Python transport never imports NinjaTrader.

## Files

| File | Role |
|------|------|
| `AddOns/HotirjamGatewayAddOn.cs` | `AddOnBase` — auto-loads with NT; clean start/stop |
| `AddOns/GatewayClient.cs` | Gateway connection host skeleton (no sockets yet) |

## Install (Windows + NinjaTrader 8)

1. Quit NinjaTrader completely.
2. Copy both `.cs` files into:
   ```
   Documents\NinjaTrader 8\bin\Custom\AddOns\
   ```
3. Start NinjaTrader 8.
4. Open **New → NinjaScript Editor**, then **Compile** (F5) if NT did not auto-compile.
5. Open the **Output** window.

## Expected Output logs

On load / Control Center up:

```
HOTIRJAM AddOn Loaded
HOTIRJAM AddOn Started
```

On Control Center close / NT shutdown:

```
HOTIRJAM AddOn Stopped
```

## Definition of Done (NT-1)

- [ ] AddOn compiles in NinjaScript Editor with no errors
- [ ] NinjaTrader starts normally
- [ ] Output shows Loaded / Started on startup
- [ ] Output shows Stopped on shutdown
