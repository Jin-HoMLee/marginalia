"""Shared, thread-safe state for a single marginalia thread.

Written by the HTTP face (comments, done) and read/written by the MCP
async handlers (drain comments, add replies). No rendering, no IO.
"""
import queue
import threading
import time


class ThreadStore:
    def __init__(self, title=""):
        self.title = title
        self.html = ""                      # the served page
        self.elements = {}                  # cid -> label (first ~140 chars)
        self.events = []                    # ordered log: comments + replies (for export)
        self.done = threading.Event()
        self._lock = threading.Lock()       # guards events + _replies
        self._comments = queue.Queue()      # signaling channel drained by next_comment_nowait
        self._replies = []                  # reply records for the browser poller

    def set_render(self, html, elements):
        # Called once before the server starts accepting requests; html/elements are
        # intentionally not lock-guarded (no concurrent writer exists yet).
        self.html = html
        self.elements = dict(elements)

    def add_comment(self, element_id, comment, label=""):
        label = label or self.elements.get(element_id, element_id)
        item = {"element_id": element_id, "label": label, "comment": comment}
        with self._lock:
            self.events.append({"type": "comment", "ts": time.time(), **item})
        self._comments.put(item)

    def next_comment_nowait(self):
        try:
            return self._comments.get_nowait()
        except queue.Empty:
            return None

    def add_reply(self, element_id, markdown_text, html, label=""):
        label = label or self.elements.get(element_id, element_id)
        rec = {"element_id": element_id, "label": label,
               "markdown": markdown_text, "html": html}
        with self._lock:
            self._replies.append(rec)
            self.events.append({"type": "reply", "ts": time.time(), **rec})

    def get_replies(self):
        with self._lock:
            return [{"element_id": r["element_id"], "html": r["html"]}
                    for r in self._replies]

    def mark_done(self):
        self.done.set()
