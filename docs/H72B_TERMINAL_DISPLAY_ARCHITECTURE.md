# Sprint H-7.2B — Terminal Display Architecture

**Status: LOCKED (architecture)** · Implementation authorized by H-7.2C  
**Scope:** Next-generation terminal rendering backend for HOTIRJAM AI 5  

This document defines the single rendering contract for all terminal UIs.

---

## 0. Design principles (absolute)

| # | Principle | Meaning |
|---|-----------|---------|
| 1 | **Fixed viewport** | The operator surface occupies a stable rectangular region. History must not scroll under normal refresh. |
| 2 | **Frame-based only** | Every refresh is a complete logical frame. No append streams. No log-style emission. |
| 3 | **Single render pass** | Compose once → paint once (or skip). No multi-pass re-compose for the same refresh. |
| 4 | **Presentation ≠ terminal** | UI composers produce terminal-agnostic frames. Adapters own I/O and escape sequences. |
| 5 | **One backend, many UIs** | Dashboard, Mission Control, Developer Console, and future terminal UIs share one display stack. |
| 6 | **Capability ≠ contract** | ANSI vs non-ANSI changes *how* paint occurs, never *whether* paint is frame-based. |
| 7 | **No second runtime** | Display layer never evaluates engines, never owns market/decision state, never substitutes RuntimeHub. |
| 8 | **Honesty under constraint** | If a host cannot support fixed-viewport paint, the system must degrade to an explicit non-dashboard mode—not silent append-as-dashboard. |

---

## 1. Problem statement (from architecture review)

### Current model (as observed)

```
UI composer  →  full text string  →  TerminalDisplay.render_frame
                                      ├─ ANSI TTY     → in-place line paint (frame-like)
                                      └─ fallback     → Conditional Stream Flush (append / scroll)
```

| Layer | Status |
|-------|--------|
| Mission Control composition | Correct |
| RuntimeHub | Correct |
| Presentation binding | Correct |
| TerminalDisplay contract | **Broken under fallback** — Frame Composition + Conditional Stream Flush |

### Required model

```
UI composer  →  FrameBuffer  →  TerminalDisplay (orchestrator)  →  DisplayAdapter.paint(frame)
                                                                      └─ always fixed viewport
```

---

## 2. Architecture diagram

```
┌──────────────────────────────────────────────────────────────────────────┐
│  UI COMPOSERS (presentation only — no engines)                            │
│  DashboardView · MissionControlShell · DeveloperConsole · future UIs      │
└───────────────────────────────┬──────────────────────────────────────────┘
                                │  produce FrameBuffer (or FrameSpec → FrameBuffer)
                                ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  TERMINAL DISPLAY FACADE                                                  │
│  · Owns viewport lifecycle (prepare / resize / shutdown)                  │
│  · Owns last-painted frame identity                                       │
│  · Selects DisplayAdapter once (or on capability change)                  │
│  · Enforces: one paint per accepted frame; skip identical frames          │
└───────────────────────────────┬──────────────────────────────────────────┘
                                │  paint(FrameBuffer, PaintHints)
                                ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  DISPLAY ADAPTERS (mutually exclusive implementations of one contract)    │
│                                                                           │
│  ┌─────────────────────┐  ┌──────────────────────┐  ┌─────────────────┐ │
│  │ AnsiCursorAdapter   │  │ CompatibleHomeAdapter│  │ CaptureAdapter  │ │
│  │ (VT / ANSI TTY)     │  │ (interactive, no VT) │  │ (tests / pipes) │ │
│  │ row/col overwrite   │  │ home + overwrite     │  │ replace buffer  │ │
│  └─────────────────────┘  └──────────────────────┘  └─────────────────┘ │
│                                                                           │
│  FORBIDDEN: StreamAppendAdapter as a dashboard mode                       │
└──────────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
                     Host terminal / test capture
```

**Hard separation**

| Owns | Does not own |
|------|----------------|
| Viewport geometry, last frame, paint strategy | DashboardState, ValidatorFrame, RuntimeHub |
| Cursor / clear / resize I/O | Layout semantics of Cockpit / Lab |
| Frame identity / skip policy | Ages, provenance, engine evaluation |

---

## 3. Design answers

### 3.1 How should TerminalDisplay be architected?

**As a thin facade / orchestrator**, not as a monolith that mixes composition, capability detection, and I/O.

Responsibilities of `TerminalDisplay` (conceptual name may remain for API continuity):

1. **Lifecycle:** `prepare` → `paint` loop → `shutdown`
2. **Viewport:** track rows/cols; invalidate last frame on resize
3. **Adapter selection:** choose one `DisplayAdapter` from capability probe
4. **Frame gate:** accept `FrameBuffer`; skip if identical; otherwise single `adapter.paint`
5. **Public layout helper:** expose current viewport size to composers (width/height)

It must **not**:

- Split text and choose append vs overwrite as alternate *semantics*
- Print on RuntimeHub publish
- Re-compose UI content
- Clear the full screen on every refresh (startup/resize only)

### 3.2 Should FrameBuffer be a first-class object?

**Yes.**

`FrameBuffer` is the canonical unit of terminal presentation.

Conceptual contents:

| Field | Role |
|-------|------|
| `lines` | Ordered row strings (logical content; may be shorter than viewport height) |
| `width` | Column budget used when composing (or “unbounded then clamp at paint”) |
| `height` | Row budget / intended viewport rows (optional but recommended) |
| `identity` | Hash or structural equality key for skip-identical |
| `generation` | Monotonic compose id (optional diagnostics) |
| `meta` | Non-painted tags (e.g. UI name) — never affects engines |

Rules:

- Composers emit `FrameBuffer`, not ad-hoc multi-line strings as the long-term contract (string input may remain as a temporary adapter during migration).
- A frame is **immutable** after compose for a given refresh.
- Padding / truncation to viewport is either done at compose time (preferred for layout honesty) or as a pure clamp at paint time — but **never** by appending extra frames.

### 3.3 How should DisplayAdapter relate to FrameBuffer?

```
FrameBuffer  = WHAT to show (terminal-agnostic)
DisplayAdapter = HOW to paint that WHAT onto a fixed viewport
```

Contract (conceptual):

| Method | Meaning |
|--------|---------|
| `capabilities` | Reports fixed-viewport support, cursor model, max size |
| `prepare(viewport)` | One-time clear / cursor hide / reserve region |
| `paint(frame, previous, viewport)` | Replace viewport content; may use line diffs |
| `on_resize(viewport)` | Re-establish origin; force full paint next |
| `shutdown(viewport)` | Restore cursor; leave terminal usable |

Adapters **consume** FrameBuffer; they do not build UI.

Adapters **may** retain a copy of last painted lines for diff — that is paint-cache, not application state.

### 3.4 How should ANSI and non-ANSI share one rendering contract?

**One contract, multiple adapters.**

| Capability | Adapter | Paint semantics (identical) |
|------------|---------|-----------------------------|
| ANSI / VT cursor addressing | `AnsiCursorAdapter` | Move to viewport origin row; overwrite lines; clear tails |
| Interactive console without ANSI | `CompatibleHomeAdapter` | Home cursor by OS API or equivalent; overwrite fixed line count; blank surplus rows |
| Non-interactive capture (tests, CI) | `CaptureAdapter` | Replace an in-memory last-frame buffer; optional single snapshot export — **never** append successive frames to a growing log as “live dashboard” |

**Shared invariants (all adapters):**

1. Paint replaces the **entire** viewport region for the frame.
2. Paint does not emit “another copy below” the previous frame.
3. Identical frames → no I/O (facade-level skip before adapter call).
4. Shorter frames clear vacated rows inside the viewport.
5. Longer frames either clamp to viewport height or trigger scroll-*within*-viewport policy defined by the UI — not terminal history scroll.

**Degradation policy (honesty):**

If no fixed-viewport adapter can be selected:

- Do **not** pretend to be a live dashboard via stream append.
- Enter **Snapshot Mode**: paint at most one frame (or on explicit demand), or refuse interactive loop with a clear capability error message.
- Tests use `CaptureAdapter` and assert frame replacement, never growing line history across refreshes.

### 3.5 How should resize be handled?

Resize is a **display lifecycle event**, not a composer side-effect buried in paint.

```
SIGWINCH / poll size change
  → Viewport(rows, cols) updated
  → invalidate last-painted identity
  → optional: notify composer “geometry dirty”
  → next refresh: composer rebuilds FrameBuffer for new size
  → adapter.on_resize → full paint (no partial diff across geometries)
```

Rules:

| Rule | Rationale |
|------|-----------|
| Never paint old-width lines into new-width viewport without rebuild | Prevents wrap/corruption |
| Full paint after resize | Diff against previous geometry is unsafe |
| Composer owns reflow | Display does not invent layout |
| Detect size each refresh or via signal | Either is valid; must be deterministic |

### 3.6 How should partial redraw be designed?

Partial redraw is an **adapter optimization**, not a separate UI mode.

```
Facade receives FrameBuffer F_new
  if F_new identical to F_prev → skip
  else adapter.paint(F_new, F_prev, viewport)
         └─ line-diff: rewrite only changed rows
         └─ clear rows that existed in F_prev but not F_new
         └─ never scroll history
```

Constraints:

- Diff key is **line index within viewport**, not semantic widgets.
- Widget-level dirty regions are a future optional enhancement; v1 line-diff is sufficient.
- Partial redraw must preserve identical visual result to full paint.
- After resize or prepare, force **full** paint.

### 3.7 How should identical frames be skipped?

**Facade-level gate before any adapter I/O.**

Identity options (choose one primary; others optional):

| Strategy | Pros | Cons |
|----------|------|------|
| Exact `lines` equality | Simple, current behavior | Sensitive to any churn |
| Content hash of lines | Cheap compare after hash | Still churn-sensitive |
| Composer-supplied generation + content stamp | Lets UI suppress cosmetic churn | Requires composer discipline |

Recommended default:

1. Structural equality of `FrameBuffer.lines` (and effective width/height if they affect paint).
2. Composers remain responsible for not injecting unnecessary per-tick noise into the frame (already H-7.2A.1 intent).
3. Skip must happen even when adapter would have been a no-op — avoid flush/syscalls.

---

## 4. Responsibilities

### 4.1 UI Composer (Dashboard / Mission Control / Developer)

- Read RuntimeHub / runner-provided snapshots only.
- Layout into lines for current viewport size.
- Emit one `FrameBuffer` per refresh.
- Never call adapter I/O directly.
- Never evaluate engines for display.

### 4.2 TerminalDisplay (facade)

- Capability probe → adapter selection.
- Viewport tracking and resize invalidation.
- Identical-frame skip.
- Single `paint` delegation.
- `prepare` / `shutdown` orchestration.

### 4.3 FrameBuffer

- Immutable presentation unit.
- Equality / identity for skip.
- No I/O. No terminal knowledge.

### 4.4 DisplayAdapter

- Fixed-viewport paint only.
- Optional line-diff.
- Host-specific cursor / clear mechanics.
- Must not append frames.

### 4.5 Capability Probe

- Detect TTY, VT/ANSI, OS console home support, size.
- Input to adapter selection only.
- Must not change rendering *contract*.

### 4.6 Explicitly out of scope

- RuntimeHub
- Engines / Objective / R vs P
- Provenance binding
- Journal / logger semantics
- Network / broker I/O

---

## 5. Rendering lifecycle (single refresh)

```
1. Runner tick (or MC refresh)
2. Composer reads latest bound state (read-only)
3. Composer queries viewport size from TerminalDisplay
4. Composer builds FrameBuffer (single compose)
5. TerminalDisplay.accept(frame)
     a. If resize pending → on_resize; clear last identity
     b. If frame == last → return (skip)
     c. adapter.paint(frame, last, viewport)   // one pass
     d. last = frame
6. End refresh
```

**Invariant:** At most one compose and one paint attempt per refresh. Paint may no-op internally on empty diff, but facade skip is preferred when fully identical.

---

## 6. Frame lifecycle

```
CREATE   Composer allocates immutable FrameBuffer for this refresh
COMMIT   Frame handed to TerminalDisplay (ownership of identity transfers to facade cache)
PAINT    Adapter consumes frame (read-only)
RETIRE   Previous frame discarded after successful paint or replaced on skip-check
```

Frames are not pooled across UIs. One active “last painted” frame per TerminalDisplay instance.

---

## 7. Display lifecycle

```
CONSTRUCT   Bind stream; probe capabilities; select adapter
PREPARE     Clear once; hide cursor if supported; establish viewport origin; last=None
RUN         accept/paint loop
SHUTDOWN    Show cursor; move below viewport; detach last frame; mark unprepared
```

Rules:

- Full screen clear only in `PREPARE` (and optionally after catastrophic corruption) — never every frame.
- Multiple UI modes may share one display instance only if they serialize ownership of the viewport (one active composer at a time).

---

## 8. Resize lifecycle

```
DETECT   Size differs from Viewport
MARK     geometry_dirty = true; invalidate last frame identity
NOTIFY   Optional callback to composer / runner (“reflow required”)
NEXT     Composer rebuilds FrameBuffer at new size
PAINT    adapter.on_resize + full paint
CLEAR    geometry_dirty = false
```

If size oscillates rapidly: coalesce to one rebuild per refresh (last size wins).

---

## 9. Performance considerations

| Concern | Design stance |
|---------|----------------|
| Refresh rate | Bounded by runner interval; display must not amplify with extra paints |
| Identical skip | Mandatory; avoids syscall/flush storms |
| Line diff | Reduces bytes on ANSI path; optional on Compatible |
| Frame size | Clamp to viewport; do not paint off-screen history |
| Allocation | Prefer immutable line lists; avoid re-splitting strings in adapter |
| Capture/tests | In-memory replace is O(rows); assert non-growth across N refreshes |
| Capability probe | Once at construct (+ rare re-probe); not every paint |

Non-goals for H-7.2B era:

- GPU / alternate screen buffer mandatory (optional later enhancement for Ansi adapter)
- Widget dirty rectangles beyond line diff
- Async paint threads

---

## 10. Compatibility considerations

| Host | Expected adapter | Dashboard behavior |
|------|------------------|--------------------|
| macOS/Linux TTY with TERM≠dumb | AnsiCursorAdapter | Fixed viewport |
| Windows console with VT enabled | AnsiCursorAdapter | Fixed viewport |
| Windows console without VT but interactive | CompatibleHomeAdapter | Fixed viewport via cursor home |
| IDE integrated terminal (TTY + ANSI) | AnsiCursorAdapter | Fixed viewport |
| Redirected stdout / CI pipe | CaptureAdapter or Snapshot Mode | No scrolling “live dashboard” |
| TERM=dumb | Compatible or Snapshot | Honesty policy |
| Forced ANSI env override | Respect probe override | Still frame-paint only |

**Migration note (design, not patch):** Existing `render_frame(text: str)` can be defined as sugar that builds a transient FrameBuffer from `splitlines()`, preserving call sites while the contract hardens.

**Test contract:** Tests must verify that N refreshes with changing content leave capture size consistent with one frame (replacement), not N×frame append growth.

---

## 11. Risk analysis

| Risk | Severity | Mitigation (architectural) |
|------|----------|----------------------------|
| Keep stream-append fallback labeled “compatible” | High — recreates scrolling log | Forbid append as dashboard mode; Snapshot Mode instead |
| Dual semantics hidden behind `uses_ansi` | High | Adapter polymorphism; one paint contract |
| FrameBuffer becomes second state store | Medium | Frame holds lines only; no engine objects |
| Partial redraw bugs (stale lines) | Medium | Full paint on resize/prepare; clear vacated rows |
| Resize storms | Low | Coalesce per refresh |
| Multiple composers writing one display | Medium | Single viewport owner; serialize UI mode |
| CaptureAdapter used as live operator UI | Medium | Capability gate; interactive requires fixed-viewport adapter |
| Scope creep into MC/Dashboard layout | High | H-7.2B is display backend only; composers unchanged in this design sprint |

---

## 12. Recommended implementation order

*Order only — this sprint does not implement.*

| Step | Work | Why first |
|------|------|-----------|
| 1 | Freeze this architecture doc; add registry note “H-7.2B DESIGN” | Certification gate |
| 2 | Introduce FrameBuffer + DisplayAdapter contracts (types/interfaces only in a later code sprint) | Make contract testable |
| 3 | Implement CaptureAdapter + tests proving replace-not-append | Locks anti-scroll invariant |
| 4 | Implement AnsiCursorAdapter (lift from current ANSI path) | Primary operator path |
| 5 | Implement CompatibleHomeAdapter (POSIX + Windows home) | Close interactive non-ANSI gap |
| 6 | Wire TerminalDisplay facade: prepare / skip / paint / resize / shutdown | Unify lifecycle |
| 7 | Remove/disable stream-append dashboard path; add Snapshot Mode | Eliminate root cause |
| 8 | Point Dashboard, LV, Mission Control at facade without logic changes | Shared backend |
| 9 | Certification: scroll invariant, identical-skip, resize full-paint, no runtime ownership | Evidence before LOCK |

**Dependency rule:** No Mission Control feature work should depend on append rendering. H-7.2B implementation (future sprint) unblocks stable operator UX.

---

## 13. Relationship to prior sprints

| Sprint | Role |
|--------|------|
| H-7.0 | MC information architecture |
| H-7.1 | MC shell |
| H-7.2 / H-7.2A | Read-only bind + RuntimeHub |
| H-7.2A.1 | Compose/format stabilization |
| **H-7.2B** | **Terminal display contract (this doc)** |
| Future H-7.2B.x | Implementation of this design |

---

## 14. Acceptance criteria for a future implementation sprint

A future code sprint may claim H-7.2B complete only if:

1. Live interactive dashboard does not grow terminal scrollback solely due to refresh.
2. ANSI and non-ANSI interactive paths both obey fixed-viewport paint.
3. Non-interactive hosts do not silently append frames as a fake dashboard.
4. Identical frames produce zero paint I/O.
5. Resize forces composer rebuild + full paint.
6. Dashboard, Mission Control, and LV share the same facade.
7. No engine / RuntimeHub / evaluation changes are required for the display fix.
8. Tests prove replace-not-append for CaptureAdapter across many refreshes.

---

## 15. Explicit non-goals (this design)

- Rewriting Mission Control layout
- Changing RuntimeHub publish model
- Introducing a GUI framework
- Alternate-screen / full TUI library mandate (blessed/rich/textual) — may be evaluated later as an adapter implementation, not as a replacement for FrameBuffer
- Calibrating trading thresholds or AI behavior

---

**END H-7.2B DESIGN — FROZEN INTENT UNTIL IMPLEMENTATION SPRINT AUTHORIZED**
