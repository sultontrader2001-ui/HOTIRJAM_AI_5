"""Tests for default tick path resolution."""

from __future__ import annotations

from pathlib import Path

import pytest

from hotirjam_ai5.live_data.paths import (
    default_dom_path,
    default_ninjatrader_user_data_dir,
    default_tick_path,
    sibling_dom_path,
)


def test_default_tick_path_uses_user_data_dir(tmp_path: Path) -> None:
    path = default_tick_path(user_data_dir=tmp_path)
    assert path == (tmp_path / "HOTIRJAM" / "mnq_ticks.ndjson").resolve()


def test_default_dom_path_uses_user_data_dir(tmp_path: Path) -> None:
    path = default_dom_path(user_data_dir=tmp_path)
    assert path == (tmp_path / "HOTIRJAM" / "mnq_dom.ndjson").resolve()


def test_sibling_dom_path_matches_tick_folder(tmp_path: Path) -> None:
    tick = tmp_path / "HOTIRJAM" / "mnq_ticks.ndjson"
    tick.parent.mkdir(parents=True)
    tick.write_text("{}\n", encoding="utf-8")
    assert sibling_dom_path(tick) == (tmp_path / "HOTIRJAM" / "mnq_dom.ndjson").resolve()


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
    monkeypatch.setattr(
        "hotirjam_ai5.live_data.paths._bridge_host_user_data_dirs",
        lambda: (),
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


def test_prefers_live_bridge_over_decoy_dom_only(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """cwd/HOTIRJAM with only a stale DOM must not beat bridge/HOTIRJAM with ticks."""
    home = tmp_path / "empty_home"
    home.mkdir()
    cwd = tmp_path / "ai5"
    bridge = cwd / "bridge"
    decoy_dom = cwd / "HOTIRJAM" / "mnq_dom.ndjson"
    live_tick = bridge / "HOTIRJAM" / "mnq_ticks.ndjson"
    live_dom = bridge / "HOTIRJAM" / "mnq_dom.ndjson"
    decoy_dom.parent.mkdir(parents=True)
    live_tick.parent.mkdir(parents=True)
    decoy_dom.write_text('{"source":"NT03"}\n', encoding="utf-8")
    live_tick.write_text('{"symbol":"MNQ"}\n' * 20, encoding="utf-8")
    live_dom.write_text('{"source":"NT03"}\n' * 50, encoding="utf-8")

    monkeypatch.setattr(
        "hotirjam_ai5.live_data.paths.Path.home",
        classmethod(lambda cls: home),
    )
    monkeypatch.setattr(
        "hotirjam_ai5.live_data.paths.Path.cwd",
        classmethod(lambda cls: cwd),
    )
    monkeypatch.setattr(
        "hotirjam_ai5.live_data.paths._bridge_host_user_data_dirs",
        lambda: (cwd / "bridge", cwd),
    )
    monkeypatch.delenv("HOTIRJAM_NINJATRADER_USER_DATA_DIR", raising=False)

    assert default_ninjatrader_user_data_dir() == bridge.resolve()
    assert default_tick_path() == live_tick.resolve()
    assert default_dom_path() == live_dom.resolve()
