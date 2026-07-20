"""Tests for default tick path resolution."""

from __future__ import annotations

from pathlib import Path

import pytest

from hotirjam_ai5.live_data.paths import (
    default_ninjatrader_user_data_dir,
    default_tick_path,
)


def test_default_tick_path_uses_user_data_dir(tmp_path: Path) -> None:
    path = default_tick_path(user_data_dir=tmp_path)
    assert path == tmp_path / "HOTIRJAM" / "mnq_ticks.ndjson"


def test_env_override(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HOTIRJAM_NINJATRADER_USER_DATA_DIR", str(tmp_path))
    assert default_ninjatrader_user_data_dir() == tmp_path
