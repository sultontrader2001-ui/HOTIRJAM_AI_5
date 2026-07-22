# Sprint M1.2 — Bridge Sender Runtime

**Result: PASS (unit / harness)**  
**Scope:** `bridge/` only — no `hotirjam_ai5` AI changes  
**Network:** OFF (log-only)

---

## CLI

```bash
cd HOTIRJAM_AI_5/bridge
pip install -e .

bridge_sender \
  --tick-file "/path/to/HOTIRJAM/mnq_ticks.ndjson" \
  --symbol MNQ \
  --poll 0.05 \
  --log-file logs/bridge_sender_runtime.log
```

Aliases: `bridge_sender`, `hotirjam-bridge-sender`

| Flag | Meaning |
|------|---------|
| `--tick-file` | NT01 `mnq_ticks.ndjson` |
| `--from-start` | Read from byte 0 (default: EOF / live) |
| `--max-ticks N` | Stop after N accepted ticks |
| `--log-file` | Tee runtime log to file |
| Ctrl+C | Clean shutdown (`request_stop`) |

---

## Runtime log format

Each accepted tick:

```text
[BRIDGE_SENDER] seq=1 ch=tick symbol=MNQ last=18000.25 bid=... ask=... vol=1.0 sent_at=... payload_ts=... envelope={...}
```

Start / stop:

```text
[BRIDGE_SENDER] start file=... symbol=MNQ from_eof=True poll=0.05 network=OFF
[BRIDGE_SENDER] stop accepted=... malformed=... last_seq=... offset=...
```

Malformed lines: `[BRIDGE_SENDER] MALFORMED ...`

---

## Behavior (M1.2)

1. Real-time NDJSON tail (incomplete trailing line held back)  
2. JSON parse + NT01 validation  
3. Envelope: `v`, `ch=tick`, `seq`, `src=NT01`, `sent_at`, `payload`  
4. Console (+ optional file) log  
5. **No network send**

---

## Tests

```bash
cd HOTIRJAM_AI_5/bridge
PYTHONPATH=src python3 -m pytest tests/ -q
```

Expected coverage:

- New tick appended → caught on next poll  
- Stop signal / clean `run()` exit  
- 1000 ticks continuous read (`seq` 1..1000)  
- CLI `--max-ticks` + `--log-file`
