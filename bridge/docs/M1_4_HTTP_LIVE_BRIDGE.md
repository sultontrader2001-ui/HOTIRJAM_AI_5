# Sprint M1.4 — HTTP Live Bridge

**Result: PASS (harness)**  
**Scope:** `bridge/` only — AI modules LOCKED  
**Transport:** Async HTTP (aiohttp)

---

## Architecture

```
Windows                         Mac
NT01/NT03 NDJSON
  → bridge_sender --url http://MAC:8765
       HTTP POST /tick|/dom|/heartbeat
  → bridge_receiver --http --port 8765
       → mnq_ticks.ndjson / mnq_dom.ndjson
```

---

## CLI

### Receiver (Mac)

```bash
bridge_receiver --http --out-dir ./HOTIRJAM --host 0.0.0.0 --port 8765 \
  --log-file logs/bridge_receiver_http.log
```

### Sender (Windows)

```bash
bridge_sender --tick-file .../mnq_ticks.ndjson --dom-file .../mnq_dom.ndjson \
  --url http://MAC_IP:8765 --from-start \
  --log-file logs/bridge_sender_http.log
```

---

## Terminal Bridge Status

Both sides refresh a live board:

```
Bridge Status
Connected: YES
Tick Sent: 125432
Tick Received: 125432
Dropped: 0
Duplicate: 0
Latency Avg: 12.34 ms
Heartbeat: OK
```

Also: `GET /status` (text), `GET /metrics` (JSON), `GET /health`.

---

## Endpoints

| Method | Path | Body |
|--------|------|------|
| POST | `/tick` | Envelope JSON |
| POST | `/dom` | Envelope JSON |
| POST | `/envelope` | Envelope JSON |
| POST | `/heartbeat` | `{tick_sent,dom_sent}` |
| GET | `/metrics` | counters |
| GET | `/status` | status board text |
| GET | `/health` | liveness |

Features: async HTTP, retry, timeout, heartbeat, seq gap → Dropped, dedupe, logging, metrics.

---

## PASS criteria (test)

- 1000 ticks sent → 1000 received  
- 0 lost (dropped gaps)  
- 0 duplicated  
- Order preserved  
- DOM preserved (10 snapshots in harness)

```bash
cd HOTIRJAM_AI_5/bridge
pip install -e ".[dev]"
PYTHONPATH=src python3 -m pytest tests/ -q
```
