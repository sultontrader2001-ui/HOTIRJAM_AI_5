"""ReplayValidator — deterministic replay over H-8.0 observations (H-8.1)."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence

from hotirjam_ai5.observation.models import ObservationCycle
from hotirjam_ai5.replay.checks import (
    label_confidence,
    subsequent_window,
    validate_break_capability,
    validate_continuation,
    validate_initiative,
    validate_objective,
    validate_response,
)
from hotirjam_ai5.replay.models import (
    MarketPoint,
    ModuleVerdict,
    ObservationReplayResult,
    ReplayReport,
)
from hotirjam_ai5.replay.parse import parse_observation


class ReplayValidator:
    """Validate observation consistency against subsequent market data.

    Read-only. Never mutates observations or market inputs.
    """

    def replay(
        self,
        observations: Sequence[ObservationCycle],
        market: Sequence[MarketPoint],
    ) -> ReplayReport:
        """Replay every observation against the shared market series."""
        # Defensive copy of references only — never mutate caller lists.
        obs = tuple(observations)
        mkt = tuple(market)
        results: list[ObservationReplayResult] = []

        for cycle in obs:
            parsed = parse_observation(
                objective=cycle.objective,
                initiative=cycle.initiative,
                response=cycle.response,
                continuation=cycle.continuation,
                break_capability=cycle.break_capability,
                confidence=cycle.confidence,
                price=cycle.price,
            )
            path = subsequent_window(mkt, after_time=cycle.time)
            notes: list[str] = []

            obj_v, obj_n = validate_objective(parsed, path)
            notes.append(f"objective: {obj_n}")
            ini_v, ini_n = validate_initiative(parsed, path)
            notes.append(f"initiative: {ini_n}")
            rsp_v, rsp_n = validate_response(parsed, path)
            notes.append(f"response: {rsp_n}")
            cont_v, cont_n = validate_continuation(parsed, path)
            notes.append(f"continuation: {cont_n}")
            brk_v, brk_n = validate_break_capability(parsed, path)
            notes.append(f"break: {brk_n}")

            module_verdicts = (obj_v, ini_v, rsp_v, cont_v, brk_v)
            passes = sum(1 for v in module_verdicts if v is ModuleVerdict.PASS)
            conf_l, conf_n = label_confidence(
                parsed, module_passes=passes, module_total=len(module_verdicts)
            )
            notes.append(f"confidence: {conf_n}")

            results.append(
                ObservationReplayResult(
                    cycle_id=cycle.cycle_id,
                    observation_time=cycle.time,
                    objective=obj_v,
                    initiative=ini_v,
                    response=rsp_v,
                    continuation=cont_v,
                    break_capability=brk_v,
                    confidence=conf_l,
                    notes=tuple(notes),
                    subsequent_points=len(path),
                )
            )

        fingerprint = _fingerprint(obs, mkt, tuple(results))
        summary = _session_summary(tuple(results))
        # Session PASS when every module PASS and confidence Calibrated for all,
        # OR when we have results and determinism holds (always). Soften:
        # Session pass = all observations have no FAIL modules (confidence label OK either way)
        session_pass = bool(results) and all(
            r.objective is ModuleVerdict.PASS
            and r.initiative is ModuleVerdict.PASS
            and r.response is ModuleVerdict.PASS
            and r.continuation is ModuleVerdict.PASS
            and r.break_capability is ModuleVerdict.PASS
            for r in results
        )
        return ReplayReport(
            results=tuple(results),
            session_pass=session_pass,
            summary_lines=tuple(summary),
            deterministic_fingerprint=fingerprint,
        )


def _fingerprint(
    observations: tuple[ObservationCycle, ...],
    market: tuple[MarketPoint, ...],
    results: tuple[ObservationReplayResult, ...],
) -> str:
    payload = {
        "observations": [
            {
                "cycle_id": o.cycle_id,
                "time": o.time,
                "objective": o.objective,
                "initiative": o.initiative,
                "response": o.response,
                "continuation": o.continuation,
                "break_capability": o.break_capability,
                "confidence": o.confidence,
                "price": o.price,
            }
            for o in observations
        ],
        "market": [{"time": p.time, "price": p.price} for p in market],
        "results": [
            {
                "cycle_id": r.cycle_id,
                "objective": r.objective.value,
                "initiative": r.initiative.value,
                "response": r.response.value,
                "continuation": r.continuation.value,
                "break_capability": r.break_capability.value,
                "confidence": r.confidence.value,
            }
            for r in results
        ],
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _session_summary(results: tuple[ObservationReplayResult, ...]) -> list[str]:
    if not results:
        return ["No observations replayed"]
    total = len(results)
    obj_p = sum(1 for r in results if r.objective is ModuleVerdict.PASS)
    ini_p = sum(1 for r in results if r.initiative is ModuleVerdict.PASS)
    rsp_p = sum(1 for r in results if r.response is ModuleVerdict.PASS)
    cont_p = sum(1 for r in results if r.continuation is ModuleVerdict.PASS)
    brk_p = sum(1 for r in results if r.break_capability is ModuleVerdict.PASS)
    cal = sum(1 for r in results if r.confidence.value == "Calibrated")
    return [
        f"Observations replayed: {total}",
        f"Objective PASS: {obj_p}/{total}",
        f"Initiative PASS: {ini_p}/{total}",
        f"Response PASS: {rsp_p}/{total}",
        f"Continuation PASS: {cont_p}/{total}",
        f"Break Capability PASS: {brk_p}/{total}",
        f"Confidence Calibrated: {cal}/{total}",
    ]
