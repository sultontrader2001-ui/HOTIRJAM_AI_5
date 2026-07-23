# HOTIRJAM Gateway — NinjaTrader 8 AddOn

Standalone NinjaTrader AddOn that opens a TCP link to the Python Gateway transport.

**Hard rules:** no Tick subscriptions, no DOM subscriptions, no heartbeat payloads, no orders, no broker API, no trading logic.

This folder is **not** part of the Python `hotirjam_gateway` package. The Python transport never imports NinjaTrader.

## Files

| File | Role |
|------|------|
| `AddOns/HotirjamGatewayAddOn.cs` | `AddOnBase` — auto-loads with NT; starts/stops client |
| `AddOns/GatewayClient.cs` | TCP Connect / Disconnect / auto-reconnect |

## Defaults

| Setting | Value |
|---------|-------|
| Host | `127.0.0.1` |
| Port | `8765` (`GatewayClient.DefaultPort`) |
| Reconnect delay | 2000 ms |

## Install (Windows + NinjaTrader 8)

1. Quit NinjaTrader completely.
2. Copy both `.cs` files into:
   ```
   Documents\NinjaTrader 8\bin\Custom\AddOns\
   ```
3. Start the Python Gateway transport on the same host/port, for example:
   ```bash
   cd gateway
   .venv/bin/python -c "from hotirjam_gateway.transport import TransportServer; import time; s=TransportServer(host='0.0.0.0', port=8765); s.start(); print('listening', s.port); 
   try:
    while True: time.sleep(1)
   finally: s.stop()"
   ```
4. Start NinjaTrader 8 and compile in NinjaScript Editor if needed.
5. Open the **Output** window.

## Expected Output logs

```
HOTIRJAM AddOn Loaded
HOTIRJAM AddOn Started
HOTIRJAM GatewayClient Start host=127.0.0.1 port=8765
HOTIRJAM GatewayClient Connect ok host=127.0.0.1 port=8765
```

On drop (Python stopped): reconnect attempts. On NT shutdown:

```
HOTIRJAM GatewayClient Disconnect
HOTIRJAM GatewayClient Stop
HOTIRJAM AddOn Stopped
```

## API (GatewayClient)

- `Start()` — background supervisor: connect + auto-reconnect
- `Stop()` — stop supervisor + disconnect
- `Connect()` — single connect attempt
- `Disconnect()` — close socket (supervisor will reconnect if still started)
- `IsConnected` / `IsStarted`
