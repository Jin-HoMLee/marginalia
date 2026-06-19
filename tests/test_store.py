# tests/test_store.py
from marginalia.store import ThreadStore


def test_set_render_records_html_and_elements():
    s = ThreadStore(title="T")
    s.set_render("<html>x</html>", {"c1": "Hello world"})
    assert s.html == "<html>x</html>"
    assert s.elements["c1"] == "Hello world"


def test_add_and_drain_comment_uses_known_label():
    s = ThreadStore()
    s.set_render("", {"c1": "First para"})
    s.add_comment("c1", "my note")  # label omitted -> looked up from elements
    item = s.next_comment_nowait()
    assert item == {"element_id": "c1", "label": "First para", "comment": "my note"}
    assert s.next_comment_nowait() is None  # drained


def test_add_comment_prefers_explicit_label():
    s = ThreadStore()
    s.set_render("", {})  # element not in render map (e.g. a reply-card element)
    s.add_comment("r1-c2", "note", label="card text")
    item = s.next_comment_nowait()
    assert item["label"] == "card text"


def test_replies_roundtrip_for_polling():
    s = ThreadStore()
    s.set_render("", {"c1": "First para"})
    s.add_reply("c1", "**bold**", "<p><b>bold</b></p>")
    replies = s.get_replies()
    assert replies == [{"element_id": "c1", "html": "<p><b>bold</b></p>"}]


def test_done_flag():
    s = ThreadStore()
    assert s.done.is_set() is False
    s.mark_done()
    assert s.done.is_set() is True


def test_events_log_is_ordered_with_labels():
    s = ThreadStore()
    s.set_render("", {"c1": "Para one"})
    s.add_comment("c1", "q1")
    s.add_reply("c1", "a1", "<p>a1</p>")
    kinds = [(e["type"], e["label"]) for e in s.events]
    assert kinds == [("comment", "Para one"), ("reply", "Para one")]
