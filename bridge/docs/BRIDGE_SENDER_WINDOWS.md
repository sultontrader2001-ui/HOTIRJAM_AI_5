# Bridge Sender — Windows Design

**Component:** `hotirjam_bridge.sender`  
**Runs on:** Windows VPS (with NinjaTrader + Rithmic)  
**Status:** Design (no production runtime in this sprint)  
**Does not:** import AI modules, talk to broker, modify NDJSON journals

---

## 1. Purpose

Read NT01 / NT03 NDJSON journals **read-only**, wrap each line in the Bridge envelope, and deliver to the Mac Bridge Receiver over **WSS (primary)** or **HTTP POST (compat)**.

Windows remains a **pure market-data collector**. Sender is the only process that opens the network path to Mac.

---

## 2. Responsibilities

| Must | Must not |
|------|----------|
| Tail `mnq_ticks.ndjson` and `mnq_dom.ndjson` | Truncate, rewrite, or delete journal files |
| Validate JSON parse + symbol filter | Recalculate DOM or invent ticks |
| Assign per-channel monotonic `seq` | Call Objective / Decision / Validation |
| Connect outbound to Mac Receiver | Accept inbound trading commands |
| Heartbeat + reconnect + offset resume | Block NinjaTrader UI thread (run as separate Python process) |
| Emit metrics (sent, fail, lag, reconnect) | Require Mac AI to be running for local journal health |

---

## 3. Process model

```
Recommended (M1):
  [NinjaTrader]  → files →  [Bridge Sender.py]  → network → Mac

Not recommended:
  NinjaScript directly opening sockets (keeps NT01/NT03 file-only safety boundary)
```

- **One Sender process** multiplexes tick + DOM on one WSS (preferred).  
- Optional: two HTTP senders (NT02/NT04 style) during shadow phase only.  
- Run via Task Scheduler / NSSM / manual console under the same user that can read `Documents\NinjaTrader 8\HOTIRJAM\`.

---

## 4. Inputs

| Input | Default path | Producer |
|-------|--------------|----------|
| Tick journal | `{UserDataDir}\HOTIRJAM\mnq_ticks.ndjson` | NT01 |
| DOM journal | `{UserDataDir}\HOTIRJAM\mnq_dom.ndjson` | NT03 |
| Config | CLI / env / local yaml (future) | Operator |

### Tail semantics

- Open files **read-only**.  
- Track **byte offset** per file (persist to `bridge_sender_offsets.json` next to journals or under `%LOCALAPPDATA%\HOTIRJAM\bridge\`).  
- On start: optional `--from-eof` (live only) vs `--from-offset` (resume).  
- Skip empty / malformed lines; increment `malformed_lines`; never crash the loop.  
- Poll interval: **50–200 ms** (match NT02/NT04 practice); do not sleep between bursts when backlog exists.

---

## 5. Outputs (wire)

### 5.1 Primary — WSS client

- URL example: `wss://100.x.y.z:9443/bridge` (VPN IP) or `ws://` on private mesh only.  
- After TCP/WS open → send `ctrl/hello`:

```json
{
  "v": 1,
  "ch": "ctrl",
  "seq": 0,
  "src": "BRIDGE_SENDER",
  "sent_at": 1710000000.0,
  "payload": {
    "type": "hello",
    "role": "sender",
    "symbol": "MNQ",
    "tick_seq_next": 1,
    "dom_seq_next": 1,
    "protocol": 1
  }
}
```

- Then stream `tick` / `dom` frames; interleave `hb` every **1–2 s**.  
- Honor Receiver `ctrl` acks if implemented later; M1 minimum = fire-and-forget + local offset advance after successful send.

### 5.2 Compat — HTTP POST

| Channel | Method | Path | Body |
|---------|--------|------|------|
| Tick | POST | `/tick` | Raw NT01 JSON **or** full envelope (Receiver accepts both in compat mode) |
| DOM | POST | `/dom` | Raw NT03 JSON **or** full envelope |

Compat mode exists for shadow migration with existing NT02/NT04 receivers. Design target remains WSS.

---

## 6. Sequencing and reasons

| Channel | `src` | `seq` |
|---------|-------|-------|
| tick | `NT01` | `tick_seq` += 1 per successfully queued/sent line |
| dom | `NT03` | `dom_seq` += 1 per successfully queued/sent line |

`sent_at` = sender wall clock (UTC unix seconds, float).  
Do not alter payload `timestamp` / `timestamp_utc`.

---

## 7. Reconnection strategy

1. On send/connect failure: close socket; mark session dead.  
2. Backoff: **0.5 → 1 → 2 → 5 → 10 s** (cap 10), ±20% jitter.  
3. Reconnect → `hello` again.  
4. **Do not reset** file offsets on transient disconnect (avoid re-flood unless operator sets `--retransmit-unacked`).  
5. M1 default after successful WS send: advance offset (at-least-once if Receiver crashed before write — Receiver dedupes by seq).  
6. If Mac unreachable for extended time: keep tailing locally (offsets freeze at last successful send); journals continue to grow — catch-up when link returns (backpressure: send as fast as possible until caught up).

---

## 8. Heartbeat

| Layer | Behavior |
|-------|----------|
| WebSocket | Rely on ping/pong if available in client library |
| App `ch=hb` | Every 1–2 s with `{ "role":"sender", "tick_seq", "dom_seq", "queue_depth" }` |
| Local stale feed | If no new file bytes for T seconds but WS up → still send `hb` (distinguishes idle market from dead bridge) |

Sender does **not** declare feed health for AI; it only reports bridge liveness.

---

## 9. Configuration surface (design)

| Key | Example | Notes |
|-----|---------|-------|
| `tick_file` | `...\HOTIRJAM\mnq_ticks.ndjson` | Required |
| `dom_file` | `...\HOTIRJAM\mnq_dom.ndjson` | Required |
| `receiver_url` | `wss://mac-vpn:9443/bridge` | Primary |
| `http_tick_url` | `http://mac:8765/tick` | Compat |
| `http_dom_url` | `http://mac:8766/dom` | Compat |
| `symbol` | `MNQ` | Filter |
| `mode` | `wss` \| `http` \| `shadow-both` | Shadow = dual send |
| `poll_interval` | `0.05` | Seconds |
| `offset_store` | path | Persist byte offsets + last seq |
| `expected_symbol` | `MNQ` | Reject other roots |

---

## 10. Metrics / logging

Log counters (stdout + optional NDJSON metrics file):

- `lines_read_tick` / `lines_read_dom`  
- `frames_sent_tick` / `frames_sent_dom`  
- `send_failures` / `reconnects`  
- `malformed_lines`  
- `last_sent_at` / `backlog_bytes`  
- `transport_lag_estimate` = `sent_at - payload.timestamp` (ticks only; clock-skew aware)

Never log full DOM books at high rate in info mode (debug only).

---

## 11. Failure modes

| Failure | Sender behavior |
|---------|-----------------|
| NT file missing | Wait/retry open; warn |
| Malformed line | Skip + count |
| Receiver down | Backoff reconnect; hold offset |
| Partial write / timeout | Retry frame; do not advance offset until success (WSS) |
| Symbol mismatch | Skip line |
| Disk full on Windows | NT01/NT03 fail independently; Sender logs and idles |

---

## 12. Security (M1 design)

- Prefer **VPN mesh**; no public internet exposure.  
- Optional shared token in `hello` (`payload.token`).  
- TLS (`wss://`) when certificates available; on private Tailscale, `ws://` acceptable for M1 lab only.  
- No broker credentials in Sender config.

---

## 13. Implementation outline (future — not this sprint)

```
hotirjam_bridge/sender/
  __init__.py
  app.py              # CLI entry (future)
  tail.py             # byte-offset NDJSON tail
  envelope.py         # wrap payload
  transport_wss.py    # client
  transport_http.py   # compat POST
  offsets.py          # persistence
  metrics.py
```

**Dependency rule:** `hotirjam_bridge.sender` may use stdlib + optional `websockets`/`httpx`.  
It must **not** depend on `hotirjam_ai5`.

---

## 14. Acceptance criteria (design complete when)

- [x] Responsibilities and non-goals documented  
- [x] Inputs/outputs and envelope mapping specified  
- [x] Reconnect, heartbeat, offset resume specified  
- [x] No AI package coupling  
- [ ] Runtime CLI (next sprint)  
- [ ] Live shadow session against Mac Receiver
