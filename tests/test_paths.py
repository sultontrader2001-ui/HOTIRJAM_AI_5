"""Tests for default tick path resolution."""

from __future__ import annotations

from pathlib import Path

import pytest

from hotirjam_ai5.live_data.paths import (
    default_dom_path,
    default_ninjatrader_user_data_dir,
    default_tick_path,
)


def test_default_tick_path_uses_user_data_dir(tmp_path: Path) -> None:
    path = default_tick_path(user_data_dir=tmp_path)
    assert path == (tmp_path / "HOTIRJAM" / "mnq_ticks.ndjson").resolve()


def test_default_dom_path_uses_user_data_dir(tmp_path: Path) -> None:
    path = default_dom_path(user_data_dir=tmp_path)
    assert path == (tmp_path / "HOTIRJAM" / "mnq_dom.ndjson").resolve()


def test_env_override(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HOTIRJAM_NINJATRADER_USER_DATA_DIR", str(tmp_path))
    assert default_ninjatrader_user_data_dir() == tmp_path.resolve()


def test_prefers_candidate_that_already_has_tick_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    home = tmp_path / "home"
    docs = home / "Documents" / "NinjaTrader 8"
    onedrive = home / "OneDrive" / "Documents" / "NinjaTrader 8"
    docs.mkdir(parents=True)
    onedrive.mkdir(parents=True)
    tick = onedrive / "HOTIRJAM" / "mnq_ticks.ndjson"
    tick.parent.mkdir(parents=True)
    tick.write_text("{}\n", encoding="utf-8")

    monkeypatch.setattr(
        "hotirjam_ai5.live_data.paths.Path.home",
        classmethod(lambda cls: home),
    )
    monkeypatch.delenv("HOTIRJAM_NINJATRADER_USER_DATA_DIR", raising=False)

    assert default_ninjatrader_user_data_dir() == onedrive.resolve()
    assert default_tick_path() == tick.resolve()


def test_falls_back_to_bridge_host_when_nt_has_no_tick(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Mac AI host: no NT Documents journal → use bridge/HOTIRJAM if present."""
    home = tmp_path / "empty_home"
    home.mkdir()
    bridge_root = tmp_path / "bridge_pkg"
    tick = bridge_root / "HOTIRJAM" / "mnq_ticks.ndjson"
    tick.parent.mkdir(parents=True)
    tick.write_text('{"symbol":"MNQ"}\n', encoding="utf-8")

    monkeypatch.setattr(
        "hotirjam_ai5.live_data.paths.Path.home",
        classmethod(lambda cls: home),
    )
    monkeypatch.setattr(
        "hotirjam_ai5.live_data.paths._bridge_host_user_data_dirs",
        lambda: (bridge_root,),
    )
    monkeypatch.delenv("HOTIRJAM_NINJATRADER_USER_DATA_DIR", raising=False)

    assert default_ninjatrader_user_data_dir() == bridge_root.resolve()
    assert default_tick_path() == tick.resolve()
