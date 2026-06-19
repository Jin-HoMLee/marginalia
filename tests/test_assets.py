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
