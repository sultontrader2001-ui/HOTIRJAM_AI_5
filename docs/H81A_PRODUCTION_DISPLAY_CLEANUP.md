# Sprint H-8.1A — Production Display Cleanup

**Status: PASS**  
**Scope:** Gate `[INGRESS_POLL]` stderr (default OFF). Keep `IngressPollSnapshot`.  
**Forbidden:** RuntimeHub · AI · Observation · Replay · DisplayAdapter redesign

---

## Change

| Before | After |
|--------|-------|
| Every `poll()` → `sys.stderr.write([INGRESS_POLL]…)` | stderr only when debug enabled |
| Always-on scroll beside TerminalDisplay | Production TTY: snapshot only, no scroll stream |

**Enable stderr:** `HOTIRJAM_INGRESS_POLL_STDERR=1` or `HOTIRJAM_INGRESS_DEBUG=1`  
**Canonical diagnostic:** `LiveTickIngress.last_poll` → `IngressPollSnapshot` (unchanged)  
**UI binding:** IDC / Developer paths continue to read the snapshot (read-only)  
**DisplayAdapter:** untouched (paint-only)

---

## Files modified

- `src/hotirjam_ai5/live_data/diagnostics.py` — `ingress_poll_stderr_enabled()`
- `src/hotirjam_ai5/live_data/ingress.py` — gate `_emit_poll_snapshot`

## Files created

- `tests/test_h81a_ingress_poll_stderr.py`
- `docs/H81A_PRODUCTION_DISPLAY_CLEANUP.md`

---

## Certification

| Check | Result |
|-------|--------|
| Production default: no `[INGRESS_POLL]` on stderr | **PASS** |
| Snapshot still populated | **PASS** |
| Debug flag exposes `[INGRESS_POLL]` | **PASS** |
| DisplayAdapter unchanged | **PASS** |
| Full suite | **661 passed** |

**Verdict: PASS**
