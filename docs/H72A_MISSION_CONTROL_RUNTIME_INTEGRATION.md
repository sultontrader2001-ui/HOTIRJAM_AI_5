# Sprint H-7.2A — Mission Control Runtime Integration Certification

**Result: PASS**  
**Scope:** Attach Mission Control to the existing HOTIRJAM AI runner runtime as a passive observer

---

## Architecture path

```
HOTIRJAM AI runner (owns runtime)
  DashboardApp.poll_once → on_tick / on_dom          [runner]
  DashboardApp.render_once:
       state = controller.snapshot()                 [runner only]
       RuntimeHub.publish_dashboard(state)           [same object ref]
       MissionControlShell.render(bundle=state)      [passive view]
         OR classic DashboardRenderer.render(state)

Live Validator runner (owns architecture runtime)
  on_tick → pipeline.evaluate → ValidatorFrame       [runner]
  render_once:
       frame = controller.latest                     [existing]
       RuntimeHub.publish_frame(frame)               [same object ref]
       MissionControlShell.render(bundle=frame)      [passive view]
```

**CLI**

- `python -m hotirjam_ai5 --mission-control` — same Dashboard runtime + MC view  
- `hotirjam-ai5-live-validator --mission-control` — same LV runtime + MC view  
- Standalone `hotirjam-ai5-mission-control` without hub → remains UNWIRED (honest)

Mission Control **never** calls `snapshot()` / `evaluate()` / `on_tick()` / `calculate()`.

---

## Objects subscribed

| Publisher | Object | Hub slot |
|-----------|--------|----------|
| `DashboardApp` | `DashboardState` (post-runner snapshot) | `hub.dashboard` |
| `LiveValidatorApp` | `ValidatorFrame` (`controller.latest`) | `hub.frame` |
| `LiveValidatorApp` | `LoopTimingSnapshot` (if present) | `hub.loop_timing` |
| `LiveValidatorApp` | journal summaries | `hub.transition_summaries` |

Identity rule: published object **is** the runner object (`is` checks in tests).

---

## Remaining UNWIRED fields (by runner)

### On Dashboard runner (`--mission-control`)

| Field / module | Why |
|----------------|-----|
| Next Trigger | No trigger object in runtime |
| Grade | No grade field |
| Objective (cockpit) | No `ValidatorFrame` on Dashboard spine |
| Lab LIVE Objective/Response/Continuation/Break | No `ValidatorFrame` |
| Lab Force/Energy (INI) | No Initiative frame |
| Logger / Checkpoint (from LoopTiming) | Dashboard path does not publish LV loop timing |

Market, Decision, Account, Feed/System (dashboard health), Physics, Memory, Liquidity, Market State, Timeline, Events: **bound** when runner has produced state.

### On Live Validator runner (`--mission-control`)

| Field / module | Why |
|----------------|-----|
| Next Trigger / Grade | Absent |
| Bid/Ask/Spread/Tick Rate/Session | Not on `ValidatorFrame` |
| Account | No `DashboardState` |
| Physics / Memory / Market State (DASH) | Dashboard-only |
| Risk | N/A engine |
| Execution | DISABLED |

Objective / Response / Continuation / Break / Force / Energy / Logger / Checkpoint: **bound** from frame + timing.

---

## Performance impact

| Item | Impact |
|------|--------|
| Extra `snapshot()` calls | **None** — still one per refresh (runner) |
| Extra engines | **None** |
| Hub publish | Reference store only |
| MC render | String formatting of already-built state |

**No performance regression** vs prior runner refresh path.

---

## Certification gates

| Gate | Result |
|------|--------|
| MC attached to existing runtime | **PASS** |
| No duplicated runtime / engines | **PASS** |
| No MC `snapshot` / `evaluate` / `on_tick` | **PASS** |
| Published object identity preserved | **PASS** |
| No runtime ownership by MC | **PASS** |
| No performance regression (one snapshot/refresh) | **PASS** |

**Overall: PASS**
