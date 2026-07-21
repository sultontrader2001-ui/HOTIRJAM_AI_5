"""Trade Planning models — plan only, never places orders (Sprint 49)."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any, Mapping


class TradeDirection(StrEnum):
    """Planned trade direction (from approved INTERNAL decisions only)."""

    BUY = "BUY"
    SELL = "SELL"


class TradePlanStatus(StrEnum):
    """Lifecycle of a virtual trade plan."""

    PLANNED = "PLANNED"
    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"


class TradePlanResult(StrEnum):
    """Outcome when a plan closes on TP or SL."""

    WIN = "WIN"
    LOSS = "LOSS"
    NONE = "NONE"


@dataclass(frozen=True, slots=True)
class TradePlan:
    """Complete execution plan for one approved INTERNAL signal."""

    plan_id: str
    direction: TradeDirection
    entry_price: float
    stop_loss: float
    take_profit: float
    risk_points: float
    reward_points: float
    risk_reward: float
    status: TradePlanStatus
    created_at: float
    activated_at: float | None = None
    closed_at: float | None = None
    exit_price: float | None = None
    result: TradePlanResult = TradePlanResult.NONE
    points: float | None = None
    stop_source: str = "swing"  # swing | momentum_origin | fallback

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["direction"] = self.direction.value
        payload["status"] = self.status.value
        payload["result"] = self.result.value
        return payload

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> TradePlan:
        return cls(
            plan_id=str(raw["plan_id"]),
            direction=TradeDirection(str(raw["direction"])),
            entry_price=float(raw["entry_price"]),
            stop_loss=float(raw["stop_loss"]),
            take_profit=float(raw["take_profit"]),
            risk_points=float(raw["risk_points"]),
            reward_points=float(raw["reward_points"]),
            risk_reward=float(raw["risk_reward"]),
            status=TradePlanStatus(str(raw["status"])),
            created_at=float(raw["created_at"]),
            activated_at=(
                float(raw["activated_at"]) if raw.get("activated_at") is not None else None
            ),
            closed_at=(
                float(raw["closed_at"]) if raw.get("closed_at") is not None else None
            ),
            exit_price=(
                float(raw["exit_price"]) if raw.get("exit_price") is not None else None
            ),
            result=TradePlanResult(str(raw.get("result", TradePlanResult.NONE.value))),
            points=float(raw["points"]) if raw.get("points") is not None else None,
            stop_source=str(raw.get("stop_source", "swing")),
        )


@dataclass(frozen=True, slots=True)
class TradePlanningConfig:
    """Configurable planning parameters (not Decision thresholds)."""

    default_rr: float = 2.0
    min_stop_points: float = 2.0
    price_history_size: int = 50

    def __post_init__(self) -> None:
        if self.default_rr <= 0:
            raise ValueError("default_rr must be positive")
        if self.min_stop_points <= 0:
            raise ValueError("min_stop_points must be positive")
        if self.price_history_size < 2:
            raise ValueError("price_history_size must be >= 2")
