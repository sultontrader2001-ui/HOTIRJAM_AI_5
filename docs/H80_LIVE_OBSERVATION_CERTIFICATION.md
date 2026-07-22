# Sprint H-8.0 — Live Observation & Certification

**Status: PASS**  
**Suite:** 649 passed · observation demo session PASS  
**Scope:** Observation layer only  
**Forbidden:** RuntimeHub mutation · AI edits · Decision Engine edits · orders / trades

---

## Package

`src/hotirjam_ai5/observation/`

| Module | Role |
|--------|------|
| `models.py` | `ObservationCycle` |
| `recorder.py` | Extract fields from published `ValidatorFrame` (+ optional Dashboard) |
| `session.py` | `ObservationSession` — live / hub / tick-driven |
| `report.py` | End-of-session `CertificationReport` |
| `app.py` | CLI `hotirjam-ai5-observe` |

---

## Per-cycle fields

Time · Objective · Initiative · Response · Continuation · Break Capability · Confidence · Market State · Evidence · No Trade Reason · Decision

---

## Modes

| Mode | Behavior |
|------|----------|
| `live` | Poll tick NDJSON via existing ingress + LiveValidatorController (unchanged) |
| `hub` | Read RuntimeHub frames only (no publish) |
| `demo` | Synthetic ticks for offline certification |

---

## Certification gates

- No orders attempted  
- RuntimeHub not mutated by observation layer  
- `min_cycles` satisfied  
- All required fields present  
- No forbidden live trading decisions (`BUY`/`SELL`/…)  

---

## CLI

```bash
hotirjam-ai5-observe --mode demo --max-cycles 5 --min-cycles 5
hotirjam-ai5-observe --mode live --tick-file PATH --max-cycles 50
hotirjam-ai5-observe --mode hub --max-seconds 30
```

**Verdict:** see runner / CLI output for the session under test.
