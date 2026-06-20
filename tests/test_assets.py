# tests/test_assets.py
from pathlib import Path

ASSETS = Path(__file__).resolve().parents[1] / "src" / "marginalia" / "assets"


def test_theme_css_has_core_classes():
    css = (ASSETS / "theme.css").read_text(encoding="utf-8")
    for token in [".wrap", ".mg-anno", ".mg-popup", ".mg-reply", ".mg-bar", ".mg-comment", ".mg-opt"]:
        assert token in css, f"missing {token} in theme.css"


def test_theme_css_has_freeze_and_banner_classes():
    css = (ASSETS / "theme.css").read_text(encoding="utf-8")
    for token in [".mg-frozen", ".mg-banner", ".mg-undo", ".mg-close-now"]:
        assert token in css, f"missing {token} in theme.css"


def test_annotate_js_has_contract_hooks():
    js = (ASSETS / "annotate.js").read_text(encoding="utf-8")
    # HTTP contract endpoints the server implements
    assert "/comment" in js
    assert "/replies" in js
    assert "/done" in js
    # the data-cid anchor and the done button id from the page template
    assert "data-cid" in js
    assert "mg-done" in js
    # re-annotation of reply-card contents (threading)
    assert "makeClickable" in js
    # UX features: user comment cards, draft persistence, clickable answer options
    assert "renderComment" in js
    assert "drafts" in js
    assert "#reply:" in js
    assert "mg-opt" in js


def test_annotate_js_has_close_flow_hooks():
    js = (ASSETS / "annotate.js").read_text(encoding="utf-8")
    # state machine + grace-window UI
    assert "beginClosing" in js
    assert "commitClose" in js
    assert "undoClose" in js
    assert "mg-banner" in js
    assert "mg-frozen" in js
    assert "Undo" in js
    assert "Close now" in js
    # 6-second grace window — pin the real source of truth, not a substring of
    # "}, 1600)" (the toast timeout), which "6" would also match
    assert "var seconds = 6" in js


def test_annotate_js_freeze_guards_cover_all_post_paths():
    """The freeze state machine must gate every path that can POST /comment or
    strand /done — the silent-loss and hung-thread cases the feature targets."""
    js = (ASSETS / "annotate.js").read_text(encoding="utf-8")
    # #1: the live-only guard must cover three sites — onClick, beginClosing,
    # AND the mg-opt answer-button handler (CSS pointer-events doesn't block
    # keyboard / programmatic activation of the latter).
    assert js.count('state !== "live"') >= 3, "mg-opt handler missing the live-only guard"
    # #2: a tab-close during the grace window must still deliver /done.
    assert "pagehide" in js
    assert "sendBeacon" in js
    # #3: a late /replies render must not append under the closed banner —
    # commitClose already guards on "closed"; renderReply must too.
    assert js.count('state === "closed"') >= 2, "renderReply missing the closed guard"
