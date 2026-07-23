# HOTIRJAM AI 5 Constitution v1.0

**Status:** OFFICIAL ARCHITECTURE LAW  
**Scope:** `HOTIRJAM_AI_5` (hotirjam-ai5 + hotirjam-bridge)  
**Authority:** Derived from Architecture Audit Phases 1–4 (inspect → decision → thinking → migration planning)  
**Version:** 1.1 (v1.0 + §6A Anti-Patterns)  
**Effective:** 2026-07-23  
**Rule:** Future code, refactors, and features MUST comply with this document. Behaviour, thresholds, and outputs MUST NOT change unless a later certified amendment explicitly authorizes them.

---

## 1. Vision

HOTIRJAM AI is a live MNQ market-judgment system that refuses by default, speaks only when evidence agrees, and never confuses observation with broker execution.

---

## 2. Mission

HOTIRJAM AI exists to continuously evaluate live MNQ conditions and, when justified, emit an **observation-only stance** (long, short, or none) together with a **virtual risk sketch** — without inventing market data and without placing orders until a separately certified Capital Risk and Execution layer exists.

---

## 3. Core Philosophy

### 3.1 Default to NO STANCE

The correct output under uncertainty, incomplete data, conflict, or instability is **no stance**. Activation is the exception. Silence is not failure; false stance is failure.

### 3.2 Never invent data

Missing, stale, malformed, or untrusted market truth MUST NOT be replaced with synthetic prices, fabricated depth, or guessed fills. Absence of truth yields NO STANCE (or observer silence), never fiction.

### 3.3 Observation before execution

Stance is an **observed judgment**, not a broker order. Execution is a future layer. Presenting or implying live order placement before that layer is certified is a constitutional violation.

### 3.4 Truth before confidence

Data trust and measurement validity are prior to scoring, confidence, and narrative explanation. No confidence number may excuse untrusted truth.

### 3.5 Refuse before predict

The system is optimized to **block bad conditions** before it is optimized to forecast opportunity. Filters and gates outrank speculative activation.

### 3.6 One mind, two products (where needed)

**Stance Decision** and **Structural Battlefield Observation** may coexist as parallel products. They MUST NOT silently merge. Using “decision” to mean both is forbidden in operator language without qualification.

### 3.7 Certification over intuition

Trading behaviour (weights, thresholds, stability rules, conflict rules, calibrated observer selection) changes only through the project certification methodology — never by migration convenience or UI preference.

---

## 4. Architecture Blueprint

```
Gateway
  ↓
Market Truth
  ↓
Measurement
  ↓
Decision  (+ Validation as an internal duty of Decision)
  ↓
Virtual Risk
  ↓
STANCE

Parallel (not inside Stance path):
  Structural Battlefield Observer

Future (empty until certified):
  Capital Risk
  Execution
```

**Presentation hosts** (terminal dashboards, ops shells, evidence CLIs) sit **beside** this blueprint. They may consume STANCE and Observer outputs; they MUST NOT redefine them.

**Transport** (Windows→Mac bridge) is part of **Gateway**. It MUST NOT contain Measurement, Decision, or Execution logic.

---

## 5. Layer Responsibilities

### 5.1 Gateway

| | |
|--|--|
| **Purpose** | Move and preserve market journals between venue host and AI host; operate process lifecycle. |
| **Allowed inputs** | Venue NDJSON (or equivalent), operator config, network envelopes. |
| **Allowed outputs** | Canonical journal files; transport health/metrics; ops status. |
| **Forbidden** | Stance scoring; physics; liquidity judgment; broker orders; inventing ticks/DOM; AI policy thresholds. |

### 5.2 Market Truth

| | |
|--|--|
| **Purpose** | Establish whether live market data is present, parseable, symbol-correct, and fresh enough to trust. |
| **Allowed inputs** | Journal lines / ticks / depth; clocks; symbol expectations. |
| **Allowed outputs** | Trusted market events; freshness/health signals; completeness flags. |
| **Forbidden** | Directional prediction; score weights; virtual plans; execution; fabricating missing fields. |

### 5.3 Measurement

| | |
|--|--|
| **Purpose** | Compute descriptive market quantities from trusted truth (motion, book, situation, optional structure). |
| **Allowed inputs** | Trusted events from Market Truth; bounded history for rates/windows. |
| **Allowed outputs** | Measurement snapshots (motion, liquidity/pressure, behavior/situation, structure where applicable). |
| **Forbidden** | Emitting STANCE; applying trade thresholds; broker actions; inventing series; “predicting” beyond describing state. |

### 5.4 Decision (includes Validation)

| | |
|--|--|
| **Purpose** | The **only** layer that may produce STANCE. Apply readiness, dual-side evidence, thresholds, stability, conflict rule, and explanation of refusal/activation. |
| **Allowed inputs** | Market Truth health/completeness; Measurement snapshots; optional bounded memory diagnostics; prior stability history. |
| **Allowed outputs** | STANCE (NO / LONG_OBSERVED / SHORT_OBSERVED or equivalent INTERNAL semantics); scores/confidence **as already defined**; explanations. |
| **Forbidden** | Changing weights/thresholds without certification; reading broker fills to justify stance; executing orders; importing Battlefield Observer as a hidden scorer; inventing measurements. |

**Validation** is not a separate product layer. It is Decision’s duty to enforce gates (readiness, thresholds, stability, conflict, authorization semantics) without duplicating Measurement.

### 5.5 Virtual Risk

| | |
|--|--|
| **Purpose** | After STANCE activation, attach a **virtual** invalidation/reward sketch and enforce single-stance discipline. |
| **Allowed inputs** | STANCE; price; motion context needed for plan geometry; lock state. |
| **Allowed outputs** | Virtual plan (entry/invalidation/reward); lock/block records. |
| **Forbidden** | Changing STANCE scores; broker orders; inventing market truth; stacking unlimited concurrent stances. |

### 5.6 STANCE

| | |
|--|--|
| **Purpose** | The constitutional **output concept** of Decision (+ attached Virtual Risk). |
| **Allowed inputs** | Only what Decision and Virtual Risk emit. |
| **Allowed outputs** | Observed stance artifact for UI, logs, audits. |
| **Forbidden** | Being produced by Gateway, Measurement, Observer, or Presentation. |

### 5.7 Structural Battlefield Observer (parallel)

| | |
|--|--|
| **Purpose** | Observe structural battlefield (objectives, initiative, response, continuation, break pressure) for certification and operator insight. |
| **Allowed inputs** | Trusted price/structure/candle evidence as defined for that product. |
| **Allowed outputs** | Observer frames/snapshots; evidence journals; UI pages. |
| **Forbidden** | Emitting STANCE; placing orders; silently feeding Stance Decision unless a **future certified amendment** redesigns that coupling. |

### 5.8 Capital Risk (future)

| | |
|--|--|
| **Purpose** | Capital, limits, flatten, and venue risk gates. |
| **Allowed** | Only after certification. |
| **Forbidden today** | Stubbing fake capital risk that alters STANCE or pretends execution safety. |

### 5.9 Execution (future)

| | |
|--|--|
| **Purpose** | Broker connectivity and order lifecycle. |
| **Allowed** | Only after certification; MUST consume Capital Risk and MUST NOT rewrite Decision. |
| **Forbidden today** | Any broker order path; any “execution” that mutates Decision outputs. |

---

## 6. Architecture Laws

These laws are **mandatory**. Violation requires a constitutional amendment, not a “quick fix.”

| ID | Law |
|----|-----|
| **L1** | **Gateway never contains AI.** No Measurement, Decision, Virtual Risk, or Execution logic in transport. |
| **L2** | **Decision is the only place where STANCE exists.** No other layer may invent stance. |
| **L3** | **Execution never changes Decision.** Future Execution consumes Decision/Capital Risk; it does not rewrite scores or stance. |
| **L4** | **Measurement never predicts stance.** It describes; Decision judges. |
| **L5** | **Observer never executes** and **never silently becomes Stance.** |
| **L6** | **Truth before confidence.** Untrusted truth ⇒ NO STANCE. |
| **L7** | **Default is NO STANCE.** Activation requires cleared gates. |
| **L8** | **No invented market data.** |
| **L9** | **Observation ≠ Execution** until Capital Risk + Execution are certified. |
| **L10** | **Single active virtual stance discipline.** No stance-stack spam. |
| **L11** | **Behaviour locks:** weights, thresholds, stability rules, and conflict rules do not change under migration or cleanup. |
| **L12** | **Journal payload integrity:** venue payload shapes consumed by Market Truth remain exact; transport metadata must not corrupt payload. |
| **L13** | **No circular domain coupling** as a design goal; temporary cycles require an explicit debt record and a removal plan. |
| **L14** | **Presentation hosts do not own business truth.** UI may display; it must not redefine Measurement or Decision semantics. |
| **L15** | **Certification methodology supersedes convenience.** Audited/LOCKED modules are not casually edited. |

---

## 6A. Architecture Anti-Patterns (STRICTLY FORBIDDEN)

The following patterns are **constitutionally banned**. They MUST NOT be introduced. Existing debt MUST be reduced under Phase 4 migration rules without changing trading behaviour. Creating new instances is a **constitutional violation**.

| ID | Anti-pattern | Ban |
|----|--------------|-----|
| **AP1** | **Circular dependencies** | Domain packages MUST NOT import each other in a cycle. Temporary legacy cycles are debt only — no new cycles; removal plan required. |
| **AP2** | **God classes / god modules** | A single class or module that orchestrates “everything” (guideline: **≥1000 lines** of orchestration, or unbounded fan-in of unrelated duties) is forbidden as a design target. Split by blueprint layer; Presentation hosts call layers — they do not *become* layers. |
| **AP3** | **Duplicated business logic** | The same business question MUST NOT be computed in two places (e.g. twin scorers, twin readiness chains, strategy matchers re-checking scorers). One owner per question. |
| **AP4** | **Mixing AI and Gateway** | Gateway/transport MUST remain AI-free. No Measurement, Decision, Virtual Risk, Observer judgment, or Execution inside Gateway. AI MUST NOT embed transport protocol policy as trading logic. |
| **AP5** | **STANCE outside Decision** | ONLY Decision may produce STANCE. Gateway, Market Truth, Measurement, Observer, Presentation, Evidence CLIs, and Virtual Risk MUST NOT invent stance (Virtual Risk may only *attach* plan/lock after Decision STANCE). |
| **AP6** | **Fake Execution or fake Risk layers** | Empty, stub, or decorative Capital Risk / Execution that imply safety or orders without certification are forbidden. Absence is honest; theatre is not. |
| **AP7** | **Multiple responsibilities in one module** | Each package/module MUST map to one blueprint duty (or one declared companion role: Presentation / Evidence / Ops). “Utility dumping grounds” that own unrelated business rules are forbidden. |

### Anti-pattern enforcement

1. Architecture / import-boundary tests SHOULD fail the build when AP1, AP4, AP5 are detectable.  
2. Code review MUST reject AP2–AP3, AP6–AP7 as design choices.  
3. Migration MAY relocate god orchestration only under Constitution refactoring rules (no behaviour change, goldens first).  
4. “Temporary” exceptions require a written debt entry and an expiry/removal wave — not silence.

---

## 7. Decision Philosophy (business questions only)

Before STANCE, the AI asks — in order:

1. **Can I trust the live data right now?**  
2. **Are required measurements complete?**  
3. **Is the market situation meaningful for a stance?**  
4. **Which side does motion favor?**  
5. **Does the book confirm or contradict that side?**  
6. **Do situation signals agree with that side?**  
7. **Has agreement persisted long enough to reject noise?**  
8. **Do evidence weights clear activation thresholds?**  
9. **If both sides clear, which conflict rule wins?**  
10. **Is a prior virtual stance still open (lock)?**  
11. **If activated: where is invalidation and reward?**  
12. **(Future) Does Capital Risk allow Execution?**

Any “no” on trust, completeness, stability, thresholds, or lock yields **NO STANCE** (or hold prior plan without new activation).

---

## 8. Measurement Principles

Measurement turns trusted truth into **descriptive quantities**. It does not emit STANCE.

| Concept | Meaning |
|---------|---------|
| **Motion** | How price is moving through time (e.g. velocity, acceleration, related mid/spread context). |
| **Liquidity** | How the book is distributed and shifting relative to tradeable sides. |
| **Pressure** | Directed force on price/book (book pressure on the Stance path; structural pressure may appear in Observer). |
| **Energy** | Intensity/effort of auction participation (Observer-oriented today; not a license to invent Stance Energy math in migration). |
| **Structure** | Levels and swings that define the battlefield (primarily Observer / structure measurement). |
| **Behavior** | How the market is behaving as a situation (regime, transitions, behavioral direction) — descriptive, not a trade ticket. |

**Principle:** Each measurement answers one descriptive question. Duplicating the same question under many names is unconstitutional once identified (collapse names; do not change formulas without certification).

---

## 9. Decision Principles

| Principle | Meaning |
|-----------|---------|
| **Readiness** | Permission to score: trusted truth + complete required inputs + allowed evaluation state. One concept — not a theater of renamed stages. |
| **Conflict** | Deterministic rule when both sides would otherwise activate. Must remain explicit and stable. |
| **Confidence** | Conviction measure used by Decision. Must not become a second copy of the same pass/fail checks without adding a distinct uncertainty question. |
| **Stability** | Persistence across successive evaluations so one-frame flicker cannot activate STANCE. |
| **Threshold** | Numeric (or equivalent) bars evidence must clear. Locked under L11. |
| **Single Stance Rule** | At most one active virtual stance/plan discipline at a time. |
| **Virtual Risk** | Invalidation and reward sketch attached after activation — observational risk geometry, not broker risk capital (until Capital Risk exists). |

---

## 10. Package Principles

Every package (or logical module) MUST:

1. **Single responsibility** — one clear job aligned to a blueprint layer.  
2. **Stable API** — public types/functions change by versioned amendment, not silent drift.  
3. **No circular dependency** as the end state; cycles are debt.  
4. **No duplicated business logic** — one owner per business question.  
5. **No hidden coupling** — especially Presentation→Domain and Observer→Stance.  
6. **Facade honesty** — if a shim exists for migration, it must not alter behaviour.  
7. **Docs match code** — e.g. “passive” modules must not secretly influence STANCE without documentation.

---

## 11. Refactoring Rules

1. **No behaviour changes** unless a certified amendment says so.  
2. **No threshold / weight / stability / conflict changes** in cleanup or migration.  
3. **No output schema changes** for STANCE or journals without explicit amendment.  
4. **Golden / characterisation tests first** before structural moves.  
5. **One migration wave at a time** (see Phase 4 order).  
6. **Move + re-export before rewrite.**  
7. **Never “fix” failing goldens by changing scores.**  
8. **Do not wire Observer into Stance** under the guise of refactor.  
9. **Do not create fake Capital Risk / Execution** to look complete.  
10. **LOCKED / CALIBRATED certified modules** follow certification methodology, not this constitution alone.

---

## 12. Testing Rules

| Class | Role |
|-------|------|
| **Characterisation tests** | Freeze current behaviour before structural moves. |
| **Golden outputs** | Fixed inputs → fixed STANCE scores/enums/plans. |
| **Regression suites** | Full Decision, Measurement, Virtual Risk, Gateway, Observer suites per touching wave. |
| **Architecture tests** | Import boundaries (Gateway↛AI engines; Stance↛Observer; Execution absent). |
| **Transport tests** | Envelope identity, dedupe, journal payload integrity. |
| **Forbidden “fixes”** | Changing thresholds to make tests pass. |

---

## 13. Future Roadmap (without changing current architecture)

Ordered possibilities — each requires its own certification track:

1. **Gateway hardening** (ops, multi-sender, session identity already in force).  
2. **Market Truth / Measurement cleanup** per Phase 4 waves (structure only).  
3. **Decision readiness consolidation** (structure only; shims; no math change).  
4. **Presentation thinning** (hosts call layers; do not own truth).  
5. **Capital Risk** (new layer; empty until certified).  
6. **Execution / Broker integration** (consumes Capital Risk + STANCE; never mutates Decision).  
7. **AI Learning** (offline or shadow only until certified; must not invent live truth).  

Roadmap items MUST NOT collapse Observer into Stance or invent Execution early.

---

## 14. Definition of Done — Architecture Compliance

HOTIRJAM AI 5 is **architecture compliant** when:

1. Every module is mappable to exactly one blueprint layer (or Presentation / Evidence / Ops companion).  
2. L1–L15 and Anti-Patterns AP1–AP7 hold under review and automated boundary tests where applicable.  
3. STANCE is produced only by Decision (+ Virtual Risk attachment).  
4. Gateway remains AI-free.  
5. Observer remains parallel and non-executing.  
6. Capital Risk and Execution are either absent or fully certified — never half-present.  
7. Characterisation goldens match the behaviour baseline except where a certified amendment changed them.  
8. Operators can name the blueprint layers without package archaeology.  
9. This Constitution is referenced by migration and certification docs as law.

---

## 15. Architecture Lock

### LOCKED — Permanent until constitutional amendment

- Vision, Mission, and Core Philosophy (§1–§3)  
- Blueprint topology (§4) and layer forbiddens (§5)  
- Architecture Laws L1–L15 (§6)  
- Architecture Anti-Patterns AP1–AP7 (§6A) — strictly forbidden  
- Decision question order (§7) — wording may clarify; meaning must not invert  
- Measurement concept meanings (§8) — formulas may only change via certification  
- Decision principles (§9) — numeric bars locked under L11  
- Package, refactor, and testing rules (§10–§12)  
- Separation of Stance vs Structural Battlefield Observer  
- Observation-before-execution boundary  
- Default NO STANCE  
- No invented market data  
- Empty Capital Risk / Execution until certified  

### Amendment procedure

1. Written proposal stating which section changes and why.  
2. Explicit statement of behaviour impact (none / certified change).  
3. Audit evidence if trading behaviour is affected.  
4. Version bump (v1.1, v2.0, …) and changelog entry.  
5. No silent amendment via code comment or PR description alone.

---

## Document control

| Field | Value |
|-------|--------|
| Title | HOTIRJAM AI 5 Constitution |
| Version | **1.1** |
| Kind | Architecture law (documentation) |
| Based on | Audit Phase 1–4; v1.1 adds §6A Architecture Anti-Patterns |
| Changelog | **v1.1** — Strict ban list AP1–AP7 (circular deps, god classes, duplicated logic, AI↔Gateway mix, STANCE outside Decision, fake Risk/Execution, multi-responsibility modules) |

**End of Constitution v1.1**
