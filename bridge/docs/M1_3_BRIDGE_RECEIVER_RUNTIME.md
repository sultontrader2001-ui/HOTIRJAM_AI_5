# Sprint M1.3 — Bridge Receiver Runtime

**Result: PASS (unit / harness)**  
**Scope:** `bridge/` only — no `hotirjam_ai5` AI changes  
**Network:** OFF (local `--inbox` envelope feed)

---

## CLI

```bash
cd HOTIRJAM_AI_5/bridge
pip install -e .

bridge_receiver \
  --out-dir ./HOTIRJAM \
  --inbox ./envelopes.ndjson \
  --from-start \
  --log-file logs/bridge_receiver_runtime.log
```

Aliases: `bridge_receiver`, `hotirjam-bridge-receiver`

| Flag | Meaning |
|------|---------|
| `--out-dir` | Writes `mnq_ticks.ndjson` / `mnq_dom.ndjson` |
| `--inbox` | Local NDJSON of Bridge envelopes (Sender stand-in) |
| `--from-start` | Read inbox from byte 0 (default EOF) |
| `--max-messages N` | Stop after N processed inbox lines |
| Ctrl+C | Clean shutdown |

---

## Runtime log format

```text
[BRIDGE_RECEIVER] start out_dir=... inbox=... network=OFF
[BRIDGE_RECEIVER] write ch=tick seq=1 file=mnq_ticks.ndjson sha256=... sent_at=...
[BRIDGE_RECEIVER] DUPLICATE ch=tick seq=1
[BRIDGE_RECEIVER] MALFORMED_ENVELOPE ...
[BRIDGE_RECEIVER] stop ticks=... dom=... duplicates=... malformed=...
```

---

## Integrity

After each write, Receiver:

1. Encodes payload with canonical NDJSON (`separators=(',', ':')` + `\n`)
2. Appends to journal
3. Reads back last line and asserts **byte equality** + semantic `json.loads` equality
4. Logs SHA-256 of the written line

---

## Tests

```bash
cd HOTIRJAM_AI_5/bridge
PYTHONPATH=src python3 -m pytest tests/ -q
```

Coverage:

- 1000 ticks → 1000 lines, seq order preserved, checksum match  
- Duplicates skipped  
- Malformed envelope rejected  
- DOM → `mnq_dom.ndjson`  
- Clean stop  
- CLI inbox path  
