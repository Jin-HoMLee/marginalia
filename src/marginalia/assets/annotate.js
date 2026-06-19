(function () {
  "use strict";
  var seenReplies = 0;        // how many reply records we've already rendered
  var replyCidCounter = 0;    // unique ids for elements inside reply cards
  var popup = null;
  var drafts = {};            // cid -> unsent draft text, so an accidental close never loses typing

  function escapeHtml(s) {
    return s.replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  // Attach click-to-comment to every [data-cid] inside `root` not yet wired.
  function makeClickable(root) {
    var els = root.querySelectorAll("[data-cid]");
    for (var i = 0; i < els.length; i++) {
      var el = els[i];
      if (el.__mg) continue;
      el.__mg = true;
      el.classList.add("mg-anno");
      el.addEventListener("click", onClick);
    }
  }

  function onClick(e) {
    e.stopPropagation();
    openPopup(e.currentTarget);
  }

  function closePopup() {
    if (popup && popup.parentNode) {
      var ta = popup.querySelector(".mg-popup-ta");
      var cid = popup.getAttribute("data-cid");
      if (ta && cid && ta.value.trim()) drafts[cid] = ta.value;  // preserve unsent draft
      popup.parentNode.removeChild(popup);
    }
    popup = null;
  }

  function positionPopup(p, el) {
    var r = el.getBoundingClientRect();
    var top = window.scrollY + r.bottom + 6;
    var left = window.scrollX + r.left;
    left = Math.min(left, window.scrollX + document.documentElement.clientWidth - 320);
    p.style.top = top + "px";
    p.style.left = Math.max(8, left) + "px";
  }

  function openPopup(el) {
    closePopup();
    var cid = el.getAttribute("data-cid");
    var label = el.textContent.trim().slice(0, 140);
    popup = document.createElement("div");
    popup.className = "mg-popup";
    popup.setAttribute("data-cid", cid);
    popup.innerHTML =
      '<div class="mg-popup-label">' + escapeHtml(label) + "</div>" +
      '<textarea class="mg-popup-ta" rows="3" placeholder="Comment on this…"></textarea>' +
      '<div class="mg-popup-row">' +
      '<button class="mg-cancel">Cancel</button>' +
      '<button class="mg-send">Send ⌘⏎</button></div>';
    document.body.appendChild(popup);
    positionPopup(popup, el);
    var ta = popup.querySelector(".mg-popup-ta");
    ta.value = drafts[cid] || "";   // restore any preserved draft
    ta.focus();
    popup.querySelector(".mg-cancel").onclick = closePopup;
    popup.querySelector(".mg-send").onclick = function () { send(el, cid, label, ta.value); };
    ta.addEventListener("keydown", function (ev) {
      if (ev.key === "Enter" && (ev.metaKey || ev.ctrlKey)) send(el, cid, label, ta.value);
      else if (ev.key === "Escape") closePopup();
    });
  }

  // POST a comment to the server and render the user's "You" card under anchorEl.
  // Returns the fetch promise so callers can handle success/failure.
  function submitComment(element_id, label, text, anchorEl) {
    return fetch("/comment", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ element_id: element_id, label: label, comment: text })
    }).then(function () {
      if (anchorEl) renderComment(anchorEl, text);
      toast("Comment sent → Claude");
    });
  }

  function send(el, cid, label, text) {
    text = (text || "").trim();
    if (!text) { closePopup(); return; }
    submitComment(cid, label, text, el).then(function () {
      delete drafts[cid];                       // sent successfully -> drop the draft
      if (popup && popup.parentNode) { popup.parentNode.removeChild(popup); popup = null; }
      el.classList.add("mg-has");
    }).catch(function () { toast("Send failed — your text is kept"); });  // popup stays open
  }

  function toast(msg) {
    var t = document.createElement("div");
    t.className = "mg-toast";
    t.textContent = msg;
    document.body.appendChild(t);
    requestAnimationFrame(function () { t.classList.add("show"); });
    setTimeout(function () {
      t.classList.remove("show");
      setTimeout(function () { if (t.parentNode) t.parentNode.removeChild(t); }, 250);
    }, 1600);
  }

  // Insert `card` into the thread block under anchorEl, AFTER any comment/reply
  // cards already attached, so a thread reads top-to-bottom in chronological order.
  function insertIntoThread(anchorEl, card) {
    var ref = anchorEl;
    while (ref.nextSibling && ref.nextSibling.nodeType === 1 &&
           (ref.nextSibling.classList.contains("mg-reply") ||
            ref.nextSibling.classList.contains("mg-comment"))) {
      ref = ref.nextSibling;
    }
    if (ref.parentNode) ref.parentNode.insertBefore(card, ref.nextSibling);
  }

  // Render the user's own comment as a card so the thread is legible.
  function renderComment(anchorEl, text) {
    var card = document.createElement("div");
    card.className = "mg-comment";
    card.innerHTML = '<span class="mg-comment-tag">You</span>' +
                     '<span class="mg-comment-body">' + escapeHtml(text) + "</span>";
    insertIntoThread(anchorEl, card);
  }

  // Render a reply card under the element it answers, make it annotatable, and
  // wire any [label](#reply:answer) links as clickable answer options.
  function renderReply(rec) {
    var anchor = document.querySelector('[data-cid="' + CSS.escape(rec.element_id) + '"]');
    var card = document.createElement("details");
    card.className = "mg-reply";
    card.open = true;
    var body = document.createElement("div");
    body.className = "mg-reply-body";
    body.innerHTML = rec.html;
    // give every block inside the reply a unique data-cid so it is threadable
    var blocks = body.querySelectorAll("p,li,blockquote,h1,h2,h3,h4,h5,h6,td");
    for (var i = 0; i < blocks.length; i++) {
      if (!blocks[i].getAttribute("data-cid")) {
        replyCidCounter += 1;
        blocks[i].setAttribute("data-cid", "r" + replyCidCounter);
      }
    }
    var summary = document.createElement("summary");
    summary.textContent = "Claude replied";
    card.appendChild(summary);
    card.appendChild(body);

    // Clickable answer options: [Label](#reply:Answer) -> a button that sends "Answer".
    var cardLabel = body.textContent.trim().slice(0, 140);
    var opts = body.querySelectorAll('a[href^="#reply:"]');
    for (var j = 0; j < opts.length; j++) {
      (function (a) {
        var answer = decodeURIComponent(a.getAttribute("href").slice("#reply:".length));
        a.classList.add("mg-opt");
        a.setAttribute("role", "button");
        a.addEventListener("click", function (ev) {
          ev.preventDefault();
          ev.stopPropagation();
          if (a.classList.contains("mg-opt-chosen")) return;
          a.classList.add("mg-opt-chosen");
          submitComment(rec.element_id, cardLabel, answer, card)
            .catch(function () { toast("Send failed"); a.classList.remove("mg-opt-chosen"); });
        });
      })(opts[j]);
    }

    if (anchor && anchor.parentNode) {
      insertIntoThread(anchor, card);
    } else {
      document.getElementById("mg-doc").appendChild(card);
    }
    makeClickable(card);
  }

  function pollReplies() {
    fetch("/replies").then(function (r) { return r.json(); }).then(function (list) {
      for (var i = seenReplies; i < list.length; i++) renderReply(list[i]);
      seenReplies = list.length;
    }).catch(function () { /* server gone / transient */ });
  }

  function init() {
    makeClickable(document.getElementById("mg-doc"));
    document.addEventListener("click", function (e) {
      if (popup && !popup.contains(e.target) && !e.target.closest("[data-cid]")) closePopup();
    });
    var doneBtn = document.getElementById("mg-done");
    if (doneBtn) doneBtn.onclick = function () {
      fetch("/done", { method: "POST" })
        .then(function () { toast("Thread closed"); })
        .catch(function () { toast("Could not close — is the server up?"); });
    };
    setInterval(pollReplies, 1500);
    pollReplies();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
