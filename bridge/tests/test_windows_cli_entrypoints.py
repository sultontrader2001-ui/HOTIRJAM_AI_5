"""Verify console entry points and python -m launchers (no network)."""

from __future__ import annotations

from pathlib import Path

import pytest


def test_pyproject_defines_console_scripts() -> None:
    root = Path(__file__).resolve().parents[1]
    text = (root / "pyproject.toml").read_text(encoding="utf-8")
    assert "[project.scripts]" in text
    assert 'bridge_sender = "hotirjam_bridge.sender.app:main"' in text
    assert 'hotirjam-bridge-sender = "hotirjam_bridge.sender.app:main"' in text
    assert 'bridge_receiver = "hotirjam_bridge.receiver.app:main"' in text
    assert 'hotirjam-bridge-receiver = "hotirjam_bridge.receiver.app:main"' in text


def test_windows_cmd_launchers_exist() -> None:
    root = Path(__file__).resolve().parents[1]
    assert (root / "bridge_sender.cmd").is_file()
    assert (root / "hotirjam-bridge-sender.cmd").is_file()
    assert (root / "bridge_receiver.cmd").is_file()
    assert (root / "install_windows.ps1").is_file()


def test_entry_points_registered_when_installed() -> None:
    import importlib.metadata as metadata

    dists = {d.metadata["Name"] for d in metadata.distributions() if d.metadata}
    if "hotirjam-bridge" not in dists:
        pytest.skip("hotirjam-bridge not installed in this environment")

    eps = metadata.entry_points()
    if hasattr(eps, "select"):
        scripts = list(eps.select(group="console_scripts"))
    else:  # pragma: no cover
        scripts = list(eps.get("console_scripts", []))  # type: ignore[arg-type]
    names = {ep.name for ep in scripts}
    assert "bridge_sender" in names
    assert "hotirjam-bridge-sender" in names
    assert "bridge_receiver" in names
    assert "hotirjam-bridge-receiver" in names


def test_sender_help_via_main() -> None:
    from hotirjam_bridge.sender.app import main as sender_main

    with pytest.raises(SystemExit) as excinfo:
        sender_main(["--help"])
    assert excinfo.value.code == 0


def test_package_main_help() -> None:
    from hotirjam_bridge.__main__ import main as package_main

    assert package_main(["--help"]) == 0


def test_module_path_importable() -> None:
    import hotirjam_bridge.sender.app as sender_app
    import hotirjam_bridge.receiver.app as receiver_app

    assert callable(sender_app.main)
    assert callable(receiver_app.main)
