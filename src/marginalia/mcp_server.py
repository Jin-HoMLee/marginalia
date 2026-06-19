"""marginalia MCP server: stdio JSON-RPC tools + bundled localhost HTTP face.

Run as a script:  python3 /abs/path/server/mcp_server.py
Registered via:   claude mcp add --scope user marginalia -- python3 <abs path>
"""
import asyncio
import os
import re
import sys
import time
import webbrowser
from pathlib import Path

import markdown as _md
from mcp.server.fastmcp import FastMCP

from .store import ThreadStore
from .render import render
from .http_face import HttpFace
from .export import export_markdown

mcp = FastMCP("marginalia")

_STATE = {"store": None, "http": None}
_DEFAULT_PORT = int(os.environ.get("MARGINALIA_PORT", "8787"))


def _teardown():
    if _STATE.get("http") is not None:
        try:
            _STATE["http"].stop()
        except Exception:
            pass
    _STATE["http"] = None
    _STATE["store"] = None


def _do_start(markdown, title="marginalia", open_browser=True):
    _teardown()
    store = ThreadStore(title=title)
    page, elements = render(markdown, title)
    store.set_render(page, elements)
    http = HttpFace(store, preferred_port=_DEFAULT_PORT)
    http.start()
    url = "http://127.0.0.1:%d/" % http.port
    _STATE["store"] = store
    _STATE["http"] = http
    if open_browser:
        try:
            webbrowser.open(url)
        except Exception:
            pass
    print("[marginalia] serving thread at %s" % url, file=sys.stderr, flush=True)
    return {"url": url, "n_elements": len(elements)}


async def _do_await(timeout_s=540):
    # Capture a local ref: it keeps the store alive even if _teardown() nulls _STATE mid-loop.
    store = _STATE["store"]
    if store is None:
        return {"status": "error", "message": "no active thread; call start_thread first"}
    end = time.monotonic() + max(1, timeout_s)
    while time.monotonic() < end:
        if store.done.is_set():
            return {"status": "done"}
        item = store.next_comment_nowait()
        if item is not None:
            return {"status": "comment", **item}
        await asyncio.sleep(0.2)  # yield so the JSON-RPC loop stays responsive
    return {"status": "pending"}


def _do_reply(element_id, markdown):
    store = _STATE["store"]
    if store is None:
        return {"ok": False, "error": "no active thread"}
    html = _md.markdown(markdown, extensions=["tables", "fenced_code"])
    store.add_reply(element_id, markdown, html)
    return {"ok": True}


def _do_end(export=True, path=""):
    store = _STATE["store"]
    if store is None:
        return {"saved_path": None}
    saved = None
    error = None
    if export:
        text = export_markdown(store)
        out = Path(path) if path else (Path.cwd() / "marginalia-thread.md")
        try:
            out.parent.mkdir(parents=True, exist_ok=True)  # ensure the target dir exists
            out.write_text(text, encoding="utf-8")
            saved = str(out)
        except OSError as exc:
            error = str(exc)
    _teardown()
    if error is not None:
        return {"saved_path": None, "error": error}
    return {"saved_path": saved}


@mcp.tool()
def start_thread(markdown: str, title: str = "marginalia") -> dict:
    """Render Markdown into a clickable browser page and start the thread.

    Returns {url, n_elements}. Open the url; comments arrive via await_comment.
    """
    return _do_start(markdown, title=title, open_browser=True)


@mcp.tool()
async def await_comment(timeout_s: int = 540) -> dict:
    """Block until the next browser comment, a Done click, or the timeout.

    Returns {status:"comment", element_id, label, comment} for a real comment,
    {status:"done"} when the user clicks Done, or {status:"pending"} on timeout
    (just call await_comment again — this only exists to stay under the MCP
    tool-timeout cliff).
    """
    return await _do_await(timeout_s=timeout_s)


@mcp.tool()
def post_reply(element_id: str, markdown: str) -> dict:
    """Render Claude's reply as an in-page card anchored to element_id."""
    return _do_reply(element_id, markdown)


@mcp.tool()
def end_thread(export: bool = True, path: str = "") -> dict:
    """Close the thread; optionally export it to a standalone Markdown file."""
    return _do_end(export=export, path=path)


def main():
    mcp.run()


if __name__ == "__main__":
    main()
