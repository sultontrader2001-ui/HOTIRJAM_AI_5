"""Trade Planning Engine — builds plans after INTERNAL approvals (Sprint 49).

Does not place orders, connect to a broker, or invent BUY/SELL decisions.
Only plans trades already approved as BUY_INTERNAL / SELL_INTERNAL.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Callable, Sequence
import json
import time
import uuid
from pathlib import Path

from hotirjam_ai5.trade_decision.models import TradeDecision, TradeDecisionSnapshot
from hotirjam_ai5.trade_planning.models import (
    TradeDirection,
    TradePlan,
    TradePlanResult,
    TradePlanStatus,
    TradePlanningConfig,
)

DEFAULT_TRADE_PLANS_PATH = Path("logs") / "trade_plans.json"
_INTERNAL = frozenset(
    {TradeDecision.BUY_INTERNAL.value, TradeDecision.SELL_INTERNAL.value}
)


class TradePlanningEngine:
    """Observes approved INTERNAL decisions and maintains TP/SL plans."""

    def __init__(
        self,
        *,
        config: TradePlanningConfig | None = None,
        clock: Callable[[], float] | None = None,
        id_factory: Callable[[], str] | None = None,
        path: Path | str | None = None,
    ) -> None:
        self._config = config or TradePlanningConfig()
        self._clock = clock or time.time
        self._id_factory = id_factory or (lambda: uuid.uuid4().hex)
        self._path = Path(path) if path is not None else DEFAULT_TRADE_PLANS_PATH
        self._prices: deque[float] = deque(maxlen=self._config.price_history_size)
        self._momentum: deque[float] = deque(maxlen=self._config.price_history_size)
        self._plans: list[TradePlan] = []
        self._active: TradePlan | None = None
        self._last_decision: str | None = None
        self._load()

    @property
    def config(self) -> TradePlanningConfig:
        return self._config

    @property
    def active_plan(self) -> TradePlan | None:
        return self._active

    @property
    def plans(self) -> tuple[TradePlan, ...]:
        return tuple(self._plans)

    @property
    def closed_plans(self) -> tuple[TradePlan, ...]:
        return tuple(p for p in self._plans if p.status is TradePlanStatus.CLOSED)

    def record_price(self, price: float, *, velocity: float | None = None) -> None:
        """Append a live price sample for swing / momentum-origin stops."""
        self._prices.append(float(price))
        if velocity is not None:
            self._moments_push(float(velocity))

    def _moments_push(self, velocity: float) -> None:
        self._momentum.append(velocity)

    def observe(
        self,
        decision: TradeDecisionSnapshot,
        *,
        current_price: float | None,
        timestamp: float | None = None,
        velocity: float | None = None,
        allow_new: bool = True,
    ) -> TradePlan | None:
        """Create a plan on BUY_INTERNAL / SELL_INTERNAL edge; update active plan.

        When ``allow_new`` is False (Position Lock ACTIVE), price updates still
        run but no new Trade Plan is created.
        """
        now = timestamp if timestamp is not None else self._clock()
        if current_price is not None:
            self.record_price(current_price, velocity=velocity)

        closed = self.update_price(current_price=current_price, timestamp=now)
        del closed  # closes are consumed via closed_plans / update_price callers

        decision_value = decision.decision.value
        created: TradePlan | None = None
        if (
            allow_new
            and decision_value in _INTERNAL
            and decision_value != self._last_decision
            and current_price is not None
            and self._active is None
        ):
            direction = (
                TradeDirection.BUY
                if decision.decision is TradeDecision.BUY_INTERNAL
                else TradeDirection.SELL
            )
            created = self._build_plan(
                direction=direction,
                entry=current_price,
                now=now,
            )
            # Activate immediately — entry is the approved current price.
            created = TradePlan(
                plan_id=created.plan_id,
                direction=created.direction,
                entry_price=created.entry_price,
                stop_loss=created.stop_loss,
                take_profit=created.take_profit,
                risk_points=created.risk_points,
                reward_points=created.reward_points,
                risk_reward=created.risk_reward,
                status=TradePlanStatus.ACTIVE,
                created_at=created.created_at,
                activated_at=now,
                stop_source=created.stop_source,
            )
            self._plans.append(created)
            self._active = created
            self._save()

        self._last_decision = decision_value
        return created

    def update_price(
        self,
        *,
        current_price: float | None,
        timestamp: float | None = None,
    ) -> list[TradePlan]:
        """Advance ACTIVE plan against live price; close on TP or SL."""
        if current_price is None or self._active is None:
            return []
        now = timestamp if timestamp is not None else self._clock()
        plan = self._active
        hit = self._check_exit(plan, current_price)
        if hit is None:
            return []
        result, exit_price, points = hit
        closed = TradePlan(
            plan_id=plan.plan_id,
            direction=plan.direction,
            entry_price=plan.entry_price,
            stop_loss=plan.stop_loss,
            take_profit=plan.take_profit,
            risk_points=plan.risk_points,
            reward_points=plan.reward_points,
            risk_reward=plan.risk_reward,
            status=TradePlanStatus.CLOSED,
            created_at=plan.created_at,
            activated_at=plan.activated_at,
            closed_at=now,
            exit_price=exit_price,
            result=result,
            points=points,
            stop_source=plan.stop_source,
        )
        self._replace_plan(closed)
        self._active = None
        self._save()
        return [closed]

    def current_view_plan(self) -> TradePlan | None:
        """Plan shown on the dashboard — active, else latest."""
        if self._active is not None:
            return self._active
        if self._plans:
            return self._plans[-1]
        return None

    def _build_plan(
        self,
        *,
        direction: TradeDirection,
        entry: float,
        now: float,
    ) -> TradePlan:
        if direction is TradeDirection.BUY:
            stop, source = self._buy_stop(entry)
            risk = entry - stop
            reward = risk * self._config.default_rr
            tp = entry + reward
        else:
            stop, source = self._sell_stop(entry)
            risk = stop - entry
            reward = risk * self._config.default_rr
            tp = entry - reward
        rr = reward / risk if risk > 0 else self._config.default_rr
        return TradePlan(
            plan_id=self._id_factory(),
            direction=direction,
            entry_price=entry,
            stop_loss=stop,
            take_profit=tp,
            risk_points=risk,
            reward_points=reward,
            risk_reward=rr,
            status=TradePlanStatus.PLANNED,
            created_at=now,
            stop_source=source,
        )

    def _buy_stop(self, entry: float) -> tuple[float, str]:
        prices = list(self._prices)
        origin_low = self._momentum_origin_low(prices)
        if origin_low is not None and origin_low < entry:
            return origin_low, "momentum_origin"
        swing_low = min(prices) if prices else None
        if swing_low is not None and swing_low < entry:
            return swing_low, "swing"
        return entry - self._config.min_stop_points, "fallback"

    def _sell_stop(self, entry: float) -> tuple[float, str]:
        prices = list(self._prices)
        origin_high = self._momentum_origin_high(prices)
        if origin_high is not None and origin_high > entry:
            return origin_high, "momentum_origin"
        swing_high = max(prices) if prices else None
        if swing_high is not None and swing_high > entry:
            return swing_high, "swing"
        return entry + self._config.min_stop_points, "fallback"

    def _momentum_origin_low(self, prices: Sequence[float]) -> float | None:
        """Lowest price since velocity last turned non-positive → positive."""
        if len(prices) < 2 or len(self._momentum) < 2:
            return min(prices) if prices else None
        # Walk back while recent velocity samples are positive.
        moms = list(self._momentum)
        start = len(prices) - 1
        for i in range(len(moms) - 1, -1, -1):
            if moms[i] <= 0:
                start = min(i + 1, len(prices) - 1)
                break
            start = i
        window = prices[start:]
        return min(window) if window else None

    def _momentum_origin_high(self, prices: Sequence[float]) -> float | None:
        """Highest price since velocity last turned non-negative → negative."""
        if len(prices) < 2 or len(self._momentum) < 2:
            return max(prices) if prices else None
        moms = list(self._momentum)
        start = len(prices) - 1
        for i in range(len(moms) - 1, -1, -1):
            if moms[i] >= 0:
                start = min(i + 1, len(prices) - 1)
                break
            start = i
        window = prices[start:]
        return max(window) if window else None

    @staticmethod
    def _check_exit(
        plan: TradePlan,
        price: float,
    ) -> tuple[TradePlanResult, float, float] | None:
        if plan.direction is TradeDirection.BUY:
            if price <= plan.stop_loss:
                return TradePlanResult.LOSS, plan.stop_loss, -plan.risk_points
            if price >= plan.take_profit:
                return TradePlanResult.WIN, plan.take_profit, plan.reward_points
        else:
            if price >= plan.stop_loss:
                return TradePlanResult.LOSS, plan.stop_loss, -plan.risk_points
            if price <= plan.take_profit:
                return TradePlanResult.WIN, plan.take_profit, plan.reward_points
        return None

    def _replace_plan(self, plan: TradePlan) -> None:
        for index, existing in enumerate(self._plans):
            if existing.plan_id == plan.plan_id:
                self._plans[index] = plan
                return
        self._plans.append(plan)

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        self._plans = [TradePlan.from_dict(item) for item in raw.get("plans", [])]
        active_id = raw.get("active_plan_id")
        self._active = None
        if active_id:
            for plan in self._plans:
                if plan.plan_id == active_id and plan.status is TradePlanStatus.ACTIVE:
                    self._active = plan
                    break
        self._last_decision = raw.get("last_decision")

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "plans": [p.to_dict() for p in self._plans],
            "active_plan_id": self._active.plan_id if self._active else None,
            "last_decision": self._last_decision,
        }
        tmp = self._path.with_suffix(self._path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        tmp.replace(self._path)
