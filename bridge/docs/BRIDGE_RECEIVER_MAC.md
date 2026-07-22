# Bridge Receiver — Mac Design

**Component:** `hotirjam_bridge.receiver`  
**Runs on:** Mac (AI host)  
**Status:** Design (no production runtime in this sprint)  
**Does not:** import or invoke AI engines; only writes NT-compatible NDJSON for existing ingress

---

## 1. Purpose

Accept Bridge envelopes (or raw NT02/NT04 compat bodies) from the Windows Sender and append **payload-only** lines to local journals that the existing Mac Data Engine already knows how to read:

- `mnq_ticks.ndjson` — NT01 shape  
- `mnq_dom.ndjson` — NT03 shape  

AI processes (`hotirjam-ai5-live-validator`, dashboard, etc.) keep using **file ingress**. Receiver never calls Objective, Physics, Intent, Decision, or Validation.

---

## 2. Responsibilities

| Must | Must not |
|------|----------|
| Listen on VPN/private bind address | Bind unnecessarily to public WAN without VPN |
| Accept WSS (primary) and HTTP compat | Execute trades or hold broker sessions |
| Validate envelope `v` / `ch` / `seq` | Mutate payload field names/types |
| Dedupe `(ch, seq)` | Import `hotirjam_ai5.objective` or engines |
| Append one NDJSON line per accepted payload | Recompute DOM imbalance “to fix” data |
| Heartbeat timeout → drop session | Crash AI if Sender disconnects |
| Rotate/flush files safely | Delete Windows journals |

---

## 3. Process model

```
[Bridge Sender / Windows]
        ↓ WSS or HTTP
[Bridge Receiver / Mac]  →  append local NDJSON
        ↓
[LiveTickIngress / DomIngress]  ← existing AI5 (untouched)
        ↓
[Data Engine → AI modules]
```

Receiver is a **standalone process**. Starting/stopping it must not require restarting AI, and vice versa (AI will show FEED_IDLE/WAITING if files stall).

---

## 4. Network surface

### 4.1 Primary — WSS server

| Item | Design value |
|------|----------------|
| Bind | `0.0.0.0` or VPN IP only |
| Port | `9443` (suggested) |
| Path | `/bridge` |
| Clients | Prefer **single** active Sender session |
| Auth | Optional shared token on `ctrl/hello` |

On `hello`: record peer; reset session dedupe window as needed; reply `ctrl` ack:

```json
{
  "v": 1,
  "ch": "ctrl",
  "seq": 0,
  "src": "BRIDGE_RECEIVER",
  "sent_at": 1710000000.1,
  "payload": { "type": "hello_ack", "protocol": 1 }
}
```

### 4.2 Compat — HTTP

| Endpoint | Body | Action |
|----------|------|--------|
| `POST /tick` | NT01 JSON or envelope | Append tick line |
| `POST /dom` | NT03 JSON or envelope | Append DOM line |
| `GET /health` | — | `{ "ok": true, "tick_lines": N, "dom_lines": M }` |

Ports (compat with NT02/NT04 docs): tick `8765`, dom `8766`, or single process serving both paths on one port.

---

## 5. Outputs (local files)

| File | Content | Consumer |
|------|---------|----------|
| `{out_dir}/mnq_ticks.ndjson` | One NT01 object per line | `LiveTickIngress` |
| `{out_dir}/mnq_dom.ndjson` | One NT03 object per line | DOM ingress |

### Path strategy (cutover-friendly)

| Mode | `out_dir` | AI config |
|------|-----------|-----------|
| Shadow | `~/HOTIRJAM_BRIDGE/` | AI **not** pointed here yet |
| Cutover | Same layout AI expects, e.g. `~/Documents/NinjaTrader 8/HOTIRJAM/` **or** env `HOTIRJAM_NINJATRADER_USER_DATA_DIR` parent | Point AI env at this UserDataDir |

Design rule: Receiver creates `HOTIRJAM` subdir and files if missing. Flush after each line (or batched ≤ 5–10 ms) so tailers see data promptly.

**Write format:** `json.dumps(payload, separators=(",", ":")) + "\n"` — payload only, no envelope keys on the line.

---

## 6. Acceptance / validation pipeline

For each inbound message:

1. Parse JSON.  
2. If envelope (`v` + `ch` + `payload`): use `payload`; else treat entire body as payload (compat).  
3. Channel checks:
   - `tick` → require NT01 fields; `symbol == expected`.  
   - `dom` → require NT03 `schema_version`, `instrument` / symbol rules.  
   - `hb` → update liveness; **do not** write journals.  
   - `ctrl` → session handling only.  
4. Dedupe: if `(ch, seq)` seen → ignore (count `duplicates`).  
5. Append payload line; fsync/flush per policy.  
6. Update metrics.

Reject malformed with log + counter; do not write partial garbage lines.

---

## 7. Reconnection & session lifecycle

| Event | Receiver behavior |
|-------|-------------------|
| Client disconnect | Clear session; keep files; ready for next `hello` |
| Second Sender connects | Reject or supersede by policy (M1: **reject** second; log) |
| Gap in `seq` | Log `GAP`; continue (Sender file resume is source of truth); optional later `ctrl/gap` |
| No `hb` / ping for **5 s** | Close WS; await reconnect |
| AI not running | Continue writing files normally |

Receiver **does not** retransmit to AI; AI tails files independently.

---

## 8. Heartbeat

| Signal | Action |
|--------|--------|
| WS ping/pong | Keepalive |
| App `hb` from Sender | Refresh `last_hb_at`; expose in `/health` |
| Missing hb | Drop session after 5 s |
| `/health` | Distinguish `bridge_connected` vs `feed_idle` (no recent tick/dom lines) |

---

## 9. Configuration surface (design)

| Key | Example | Notes |
|-----|---------|-------|
| `bind_host` | `0.0.0.0` | Prefer VPN IP in production notes |
| `wss_port` | `9443` | Primary |
| `http_port` | `8765` | Compat (tick+dom paths) |
| `out_dir` | `~/Documents/NinjaTrader 8/HOTIRJAM` | Or shadow dir |
| `expected_symbol` | `MNQ` | |
| `token` | optional | hello auth |
| `dedupe_window` | last N seqs per channel | Bounded memory |
| `flush_each_line` | `true` | Default for live tail |

---

## 10. Metrics / logging

- `ticks_accepted` / `dom_accepted`  
- `duplicates` / `malformed` / `gaps`  
- `reconnects_seen`  
- `last_tick_at` / `last_dom_at` / `last_hb_at`  
- `connected: bool`  

Stderr highlight for gaps/auth failures (ops), not for every tick.

---

## 11. Failure modes

| Failure | Receiver behavior |
|---------|-------------------|
| Disk full | Error log; stop accepts or pause writes; surface unhealthy |
| Bad payload | Reject line; keep session |
| Envelope version unsupported | Reject with ctrl error; log |
| Sender flood | Apply max queue; prefer blocking read over drop (align with Sender M1 no-silent-drop) |
| Accidental AI import | **Forbidden by package layout** — review gate |

---

## 12. Security (M1 design)

- Listen on Tailscale IP when possible.  
- Token on `hello`.  
- No execution surface.  
- Do not expose Receiver on public Wi-Fi without VPN + TLS.

---

## 13. Implementation outline (future — not this sprint)

```
hotirjam_bridge/receiver/
  __init__.py
  app.py               # CLI entry (future)
  server_wss.py
  server_http.py       # compat
  validate_tick.py     # NT01 field checks (local copy of rules — no AI import)
  validate_dom.py      # NT03 field checks
  writer.py            # NDJSON append
  dedupe.py
  health.py
  metrics.py
```

**Dependency rule:** `hotirjam_bridge.receiver` must **not** depend on `hotirjam_ai5`.  
Tick/DOM field validation is duplicated as **contract asserts** in the bridge package (or shared pure schema module under `bridge/` only).

---

## 14. Cutover checklist (ops — when runtime exists)

1. Start Receiver with **shadow** `out_dir`.  
2. Start Sender; verify line counts.  
3. Point AI `HOTIRJAM_NINJATRADER_USER_DATA_DIR` at cutover dir **or** switch Receiver `out_dir`.  
4. Confirm Live Validator price updates.  
5. Confirm `git diff` on `src/hotirjam_ai5/objective` etc. remains empty.

---

## 15. Acceptance criteria (design complete when)

- [x] Responsibilities and non-goals documented  
- [x] WSS + HTTP surfaces specified  
- [x] File handoff to existing ingress specified  
- [x] Dedupe, heartbeat, gap, security noted  
- [x] No AI package coupling  
- [ ] Runtime CLI (next sprint)  
- [ ] Live session with Windows Sender
