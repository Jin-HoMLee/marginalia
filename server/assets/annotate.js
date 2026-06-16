(function () {
  "use strict";
  var seenReplies = 0;        // how many reply records we've already rendered
  var replyCidCounter = 0;    // unique ids for elements inside reply cards
  var popup = null;

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
    if (popup && popup.parentNode) popup.parentNode.removeChild(popup);
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
    popup.innerHTML =
      '<div class="mg-popup-label">' + escapeHtml(label) + "</div>" +
      '<textarea class="mg-popup-ta" rows="3" placeholder="Comment on this…"></textarea>' +
      '<div class="mg-popup-row">' +
      '<button class="mg-cancel">Cancel</button>' +
      '<button class="mg-send">Send ⌘⏎</button></div>';
    document.body.appendChild(popup);
    positionPopup(popup, el);
    var ta = popup.querySelector(".mg-popup-ta");
    ta.focus();
    popup.querySelector(".mg-cancel").onclick = closePopup;
    popup.querySelector(".mg-send").onclick = function () { send(el, cid, label, ta.value); };
    ta.addEventListener("keydown", function (ev) {
      if (ev.key === "Enter" && (ev.metaKey || ev.ctrlKey)) send(el, cid, label, ta.value);
      else if (ev.key === "Escape") closePopup();
    });
  }

  function send(el, cid, label, text) {
    text = (text || "").trim();
    if (!text) { closePopup(); return; }
    fetch("/comment", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ element_id: cid, label: label, comment: text })
    }).then(function () {
      el.classList.add("mg-has");
      toast("Comment sent → Claude");
      closePopup();
    }).catch(function () { toast("Send failed — your text is kept"); });
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

  // Render a reply card under the element it answers, and make the card annotatable.
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
    if (anchor && anchor.parentNode) {
      anchor.parentNode.insertBefore(card, anchor.nextSibling);
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
