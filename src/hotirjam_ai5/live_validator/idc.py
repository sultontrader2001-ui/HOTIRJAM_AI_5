"""Internal Diagnostics Console — framework rendering (H-6.6.1).

Read-only presentation. No engine data, no snapshots, no checkpoints.
Engine pages are placeholders until later sprints.
"""

from __future__ import annotations

from hotirjam_ai5.live_validator.presentation_mode import IdcPage

_PLACEHOLDER_TITLES: dict[IdcPage, str] = {
    IdcPage.OBJECTIVE: "OBJECTIVE ENGINE",
    IdcPage.INITIATIVE: "INITIATIVE ENGINE",
    IdcPage.RESPONSE: "RESPONSE ENGINE",
    IdcPage.CONTINUATION: "CONTINUATION ENGINE",
    IdcPage.BREAK_CAPABILITY: "BREAK CAPABILITY",
    IdcPage.MARKET_STATE: "MARKET STATE",
    IdcPage.PHYSICS: "PHYSICS",
    IdcPage.STRUCTURAL_MEMORY: "STRUCTURAL MEMORY",
    IdcPage.PERFORMANCE: "PERFORMANCE",
    IdcPage.LIVE_AUDIT: "LIVE AUDIT",
    IdcPage.CERTIFICATION: "CERTIFICATION",
    IdcPage.WARNINGS: "WARNINGS",
}

_MENU_KEY_TO_PAGE: dict[str, IdcPage] = {
    "1": IdcPage.OBJECTIVE,
    "2": IdcPage.INITIATIVE,
    "3": IdcPage.RESPONSE,
    "4": IdcPage.CONTINUATION,
    "5": IdcPage.BREAK_CAPABILITY,
    "6": IdcPage.MARKET_STATE,
    "7": IdcPage.PHYSICS,
    "8": IdcPage.STRUCTURAL_MEMORY,
    "9": IdcPage.PERFORMANCE,
    "a": IdcPage.LIVE_AUDIT,
    "A": IdcPage.LIVE_AUDIT,
    "b": IdcPage.CERTIFICATION,
    "B": IdcPage.CERTIFICATION,
    "w": IdcPage.WARNINGS,
    "W": IdcPage.WARNINGS,
}


def idc_page_for_key(ch: str) -> IdcPage | None:
    """Map a menu key to an IDC page, or None if not a page key."""
    return _MENU_KEY_TO_PAGE.get(ch)


def render_idc(page: IdcPage) -> str:
    """Render the IDC main menu or a placeholder page. No engine reads."""
    if page is IdcPage.MENU:
        return render_idc_main_menu()
    return render_idc_placeholder(page)


def render_idc_main_menu() -> str:
    """IDC main menu — navigation only."""
    lines = [
        "==============================",
        "HOTIRJAM AI 5",
        "Internal Diagnostics Console",
        "Read Only",
        "Engineering Console",
        "==============================",
        "",
        "1  Objective Engine",
        "2  Initiative Engine",
        "3  Response Engine",
        "4  Continuation Engine",
        "5  Break Capability",
        "6  Market State",
        "7  Physics",
        "8  Structural Memory",
        "9  Performance",
        "A  Live Audit",
        "B  Certification",
        "W  Warnings",
        "Q  Return Dashboard",
        "",
        "==============================",
    ]
    return "\n".join(lines)


def render_idc_placeholder(page: IdcPage) -> str:
    """Placeholder until the engine page is implemented."""
    title = _PLACEHOLDER_TITLES.get(page, page.value)
    lines = [
        "==============================",
        title,
        "IMPLEMENTATION PENDING",
        "==============================",
        "",
        "Press Q to return",
        "",
    ]
    return "\n".join(lines)
