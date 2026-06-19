# tests/test_export.py
from marginalia.store import ThreadStore
from marginalia.export import export_markdown


def test_export_orders_comments_and_replies():
    s = ThreadStore(title="My Doc")
    s.set_render("", {"c1": "First paragraph"})
    s.add_comment("c1", "what about X?")
    s.add_reply("c1", "Good point about X.", "<p>Good point about X.</p>")
    out = export_markdown(s)
    assert out.splitlines()[0] == "# My Doc"
    assert "> **On:** First paragraph" in out
    assert "what about X?" in out
    assert "Good point about X." in out
    # comment appears before its reply
    assert out.index("what about X?") < out.index("Good point about X.")


def test_export_handles_empty_thread():
    s = ThreadStore(title="Empty")
    out = export_markdown(s)
    assert out.startswith("# Empty")


def test_export_default_title_when_blank():
    s = ThreadStore()
    s.add_comment("c1", "note", label="some label")
    out = export_markdown(s)
    assert out.startswith("# marginalia thread")
