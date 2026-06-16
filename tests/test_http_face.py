# tests/test_http_face.py
import json
import urllib.request
import urllib.error

import pytest

from store import ThreadStore
from http_face import HttpFace


@pytest.fixture
def running():
    store = ThreadStore(title="T")
    store.set_render("<html><body>hello</body></html>", {"c1": "First para"})
    face = HttpFace(store, preferred_port=0)  # 0 -> ephemeral
    face.start()
    yield store, face, f"http://127.0.0.1:{face.port}"
    face.stop()


def _get(url):
    with urllib.request.urlopen(url, timeout=3) as r:
        return r.status, r.read().decode()


def _post(url, payload):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data,
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=3) as r:
        return r.status, r.read().decode()


def test_get_root_serves_page(running):
    _store, _face, base = running
    status, body = _get(base + "/")
    assert status == 200
    assert "hello" in body


def test_post_comment_lands_in_store(running):
    store, _face, base = running
    status, body = _post(base + "/comment",
                         {"element_id": "c1", "label": "First para", "comment": "hi"})
    assert status == 200
    assert json.loads(body)["ok"] is True
    item = store.next_comment_nowait()
    assert item == {"element_id": "c1", "label": "First para", "comment": "hi"}


def test_get_replies_returns_store_replies(running):
    store, _face, base = running
    store.add_reply("c1", "**b**", "<p><b>b</b></p>")
    status, body = _get(base + "/replies")
    assert status == 200
    assert json.loads(body) == [{"element_id": "c1", "html": "<p><b>b</b></p>"}]


def test_post_done_sets_flag(running):
    store, _face, base = running
    status, _ = _post(base + "/done", {})
    assert status == 200
    assert store.done.is_set()


def test_unknown_path_404(running):
    _store, _face, base = running
    with pytest.raises(urllib.error.HTTPError) as e:
        _get(base + "/nope")
    assert e.value.code == 404
