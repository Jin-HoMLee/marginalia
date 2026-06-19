# tests/test_mcp_tools.py
import asyncio
from pathlib import Path

import marginalia.mcp_server as m


def setup_function(_fn):
    m._teardown()  # clean state between tests


def test_start_thread_renders_and_serves():
    res = m._do_start("# Hi\n\nA paragraph.", title="Doc", open_browser=False)
    assert res["url"].startswith("http://127.0.0.1:")
    assert res["n_elements"] == 2
    assert m._STATE["store"] is not None
    m._teardown()


def test_await_comment_returns_clean_comment():
    m._do_start("# Hi\n\nA paragraph.", open_browser=False)
    store = m._STATE["store"]
    store.add_comment("c1", "my note")
    res = asyncio.run(m._do_await(timeout_s=2))
    assert res == {"status": "comment", "element_id": "c1",
                   "label": "Hi", "comment": "my note"}
    m._teardown()


def test_await_comment_times_out_to_pending():
    m._do_start("# Hi", open_browser=False)
    res = asyncio.run(m._do_await(timeout_s=1))
    assert res == {"status": "pending"}
    m._teardown()


def test_await_comment_reports_done():
    m._do_start("# Hi", open_browser=False)
    m._STATE["store"].mark_done()
    res = asyncio.run(m._do_await(timeout_s=2))
    assert res == {"status": "done"}
    m._teardown()


def test_post_reply_adds_rendered_card():
    m._do_start("# Hi\n\nPara.", open_browser=False)
    res = m._do_reply("c1", "**bold** reply")
    assert res["ok"] is True
    replies = m._STATE["store"].get_replies()
    assert replies[0]["element_id"] == "c1"
    assert "<strong>bold</strong>" in replies[0]["html"]
    m._teardown()


def test_end_thread_exports_and_teardown(tmp_path):
    m._do_start("# Hi\n\nPara.", title="Doc", open_browser=False)
    m._STATE["store"].add_comment("c1", "q")
    out = tmp_path / "thread.md"
    res = m._do_end(export=True, path=str(out))
    assert res["saved_path"] == str(out)
    assert out.read_text().startswith("# Doc")
    assert m._STATE["store"] is None  # torn down


def test_reply_without_active_thread_is_safe():
    m._teardown()
    res = m._do_reply("c1", "hi")
    assert res["ok"] is False
    assert "error" in res


def test_end_without_active_thread_is_safe():
    m._teardown()
    res = m._do_end()
    assert res == {"saved_path": None}


def test_end_without_export_skips_file(tmp_path):
    m._do_start("# Hi", open_browser=False)
    res = m._do_end(export=False)
    assert res == {"saved_path": None}
    assert m._STATE["store"] is None  # still tears down


def test_resolve_poll_timeout_prefers_explicit(monkeypatch):
    monkeypatch.setenv("MARGINALIA_POLL_S", "20")
    assert m._resolve_poll_timeout(5) == 5


def test_resolve_poll_timeout_reads_env_when_none(monkeypatch):
    monkeypatch.setenv("MARGINALIA_POLL_S", "20")
    assert m._resolve_poll_timeout(None) == 20


def test_resolve_poll_timeout_defaults_when_unset(monkeypatch):
    monkeypatch.delenv("MARGINALIA_POLL_S", raising=False)
    assert m._resolve_poll_timeout(None) == 540


def test_export_default_uses_threads_dir_env(tmp_path, monkeypatch):
    monkeypatch.setenv("MARGINALIA_THREADS_DIR", str(tmp_path))
    m._do_start("# Hi\n\nPara.", title="My Doc", open_browser=False)
    m._STATE["store"].add_comment("c1", "q")
    res = m._do_end(export=True)  # no explicit path
    saved = Path(res["saved_path"])
    assert saved.parent == tmp_path
    assert saved.name == "my-doc.thread.md"
    assert saved.read_text().startswith("# My Doc")


def test_default_export_path_falls_back_to_home(monkeypatch):
    monkeypatch.delenv("MARGINALIA_THREADS_DIR", raising=False)
    m._do_start("# Hi", title="T", open_browser=False)
    p = m._default_export_path(m._STATE["store"])
    assert p == Path.home() / ".marginalia" / "threads" / "t.thread.md"
    m._teardown()


def test_slug_handles_punctuation_and_empty():
    assert m._slug("My Doc!") == "my-doc"
    assert m._slug("") == "marginalia-thread"
