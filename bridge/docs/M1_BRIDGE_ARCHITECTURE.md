# M1 — Bridge Architecture

**Module:** `HOTIRJAM_AI_5/bridge` (`hotirjam_bridge`)  
**Phase:** Design only (no AI code changes)  
**Payload contracts:** NT01 tick JSON, NT03 DOM JSON (frozen)

---

## 1. Role split

| Host | Role | Process |
|------|------|---------|
| **Windows VPS** | Pure collector | NinjaTrader + Rithmic + NT01 + NT03 + **Bridge Sender** |
| **Mac** | AI host | **Bridge Receiver** + existing Data Engine ingress (file tail) + AI (untouched) |

---

## 2. Data flow

```
Rithmic
  → NinjaTrader Desktop (Windows)
      → NT01 → {UserDataDir}/HOTIRJAM/mnq_ticks.ndjson
      → NT03 → {UserDataDir}/HOTIRJAM/mnq_dom.ndjson
          → Bridge Sender (tail, read-only)
              → WSS (primary) / HTTP POST (compat)
                  → Bridge Receiver (Mac)
                      → {Mac HOTIRJAM}/mnq_ticks.ndjson
                      → {Mac HOTIRJAM}/mnq_dom.ndjson
                          → LiveTickIngress / DomIngress
                              → Data Engine → AI modules (NO bridge imports)
```

**Invariant:** AI never speaks to NinjaTrader or the Sender. Receiver never imports Objective/Physics/Decision.

---

## 3. Transport decision (design)

| Priority | Transport | Use |
|----------|-----------|-----|
| Primary | **WSS** over VPN (Tailscale/WireGuard) | Multiplexed `tick` + `dom` + `hb` |
| Compat | HTTP POST `/tick`, `/dom` (NT02/NT04 style) | Shadow / fallback |
| Rejected | UDP | Lossy — unsuitable for certification feeds |

**Dial direction:** Windows Sender connects **outbound** to Mac Receiver (or VPN IP).

---

## 4. Wire envelope (shared contract)

Defined in code as constants/dataclasses: `hotirjam_bridge.contracts`.

```json
{
  "v": 1,
  "ch": "tick",
  "seq": 1849201,
  "src": "NT01",
  "sent_at": 1710000000.456,
  "payload": { "...": "exact NT01 or NT03 object" }
}
```

| `ch` | Meaning | Payload |
|------|---------|---------|
| `tick` | Last trade tick | NT01 fields only |
| `dom` | DOM snapshot | NT03 schema 1.0 |
| `hb` | Application heartbeat | `{ "tick_seq", "dom_seq", "role" }` |
| `ctrl` | Session control | `hello` / `goodbye` / `gap` |

- **`seq` is per-channel** (independent tick vs dom counters).  
- Envelope fields must **not** be merged into NT01/NT03 payload keys.  
- Receiver strips envelope and appends **payload only** as one NDJSON line.

---

## 5. Reliability (summary)

| Concern | Design |
|---------|--------|
| Source of truth while offline | Windows NDJSON journals (NT01/NT03) |
| Reconnect | Sender exponential backoff; resume file byte offset |
| Delivery | At-least-once; Receiver dedupe by `(ch, seq)` |
| Heartbeat | WS ping/pong + app `hb` every 1–2 s; dead after ~5 s |
| Backpressure | Prefer lag over silent drop (M1 default) |
| Latency SLO | Transport add-on p50 &lt; 50 ms, p95 &lt; 150 ms (soft) |

Details: Sender and Receiver design docs.

---

## 6. Safety boundary

Bridge **may**:

- Tail NDJSON read-only (Windows)
- Send/receive envelope frames
- Write NDJSON on Mac
- Log metrics (rates, gaps, lag, reconnects)

Bridge **must not**:

- Place/cancel orders or touch broker APIs
- Import or call Objective, Physics, Intent, Decision, Validation
- Mutate NT01/NT03 schemas
- Fabricate ticks or DOM levels
- Modify AI package source under `src/hotirjam_ai5/`

---

## 7. Relation to existing NT02 / NT04

| Existing | Bridge M1 |
|----------|-----------|
| `tools/nt02_tick_sender.py` | Conceptual ancestor of Sender tick path |
| `tools/nt02_tick_receiver.py` | Conceptual ancestor of Receiver tick path |
| `tools/nt04_dom_transport.py` | Conceptual ancestor of Sender DOM path |
| HTTP-only, separate ports | Evolve to one module + WSS multiplex |

NT02/NT04 remain valid **compat** references until Bridge runtime replaces them. No requirement to delete them in the design phase.

---

## 8. Out of scope for this module creation

- Runtime WSS/HTTP implementation (next sprint)  
- Wiring Receiver output into AI process memory  
- Changing default paths inside `hotirjam_ai5.live_data`  
- Formal Objective validation
