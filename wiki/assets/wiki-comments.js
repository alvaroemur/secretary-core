(function () {
  "use strict";

  var SLUG = window.WIKI_SLUG;
  if (!SLUG) return;

  var IS_LOCAL = location.hostname === "localhost" || location.hostname === "127.0.0.1";
  var API_BASE = IS_LOCAL ? "" : (window.WIKI_COMMENTS_API || "");
  var API = API_BASE + "/api/comments/" + SLUG;
  var REMOTE_API = (window.WIKI_COMMENTS_API || "") + "/api/comments/" + SLUG;
  var API_SECRET = window.WIKI_COMMENTS_SECRET || "";
  var INDEX = window.WIKI_INDEX || [];
  var comments = [];
  var sidebar = null;
  var selPopover = null;
  var newForm = null;
  var pendingSelection = null;
  var pendingHighlight = null;
  var activeFilter = "all";
  var actionModal = null;

  // ── Helpers ──

  function esc(s) {
    var d = document.createElement("div");
    d.textContent = s || "";
    return d.innerHTML;
  }

  function genId() {
    var now = new Date();
    var d = now.toISOString().slice(0, 10).replace(/-/g, "");
    var n = String(Math.floor(Math.random() * 900) + 100);
    return "c-" + d + "-" + n;
  }

  function fmtDate(iso) {
    if (!iso) return "";
    try {
      var d = new Date(iso);
      var day = d.getDate();
      var months = ["ene","feb","mar","abr","may","jun","jul","ago","sep","oct","nov","dic"];
      return day + " " + months[d.getMonth()];
    } catch (e) { return iso.slice(0, 10); }
  }

  function findSection(node) {
    var el = node;
    while (el && el !== document.body) {
      if (el.previousElementSibling) {
        var prev = el.previousElementSibling;
        if (/^H[23]$/.test(prev.tagName) && prev.id) return prev.id;
      }
      el = el.parentElement;
    }
    var headings = document.querySelectorAll("h2[id], h3[id]");
    if (headings.length) return headings[0].id;
    return "";
  }

  function removePendingHighlight() {
    if (pendingHighlight && pendingHighlight.parentNode) {
      var parent = pendingHighlight.parentNode;
      while (pendingHighlight.firstChild) {
        parent.insertBefore(pendingHighlight.firstChild, pendingHighlight);
      }
      parent.removeChild(pendingHighlight);
    }
    pendingHighlight = null;
  }

  function statusOf(c) {
    if (c.status === "archived") return "archived";
    if (c.status === "resolved") return "resolved";
    if (c.type === "merge" || c.type === "move") return c.type;
    if (c.replies && c.replies.length > 0) {
      var last = c.replies[c.replies.length - 1];
      if (last.type === "question") return "question";
      return "replied";
    }
    return "open";
  }

  function typeLabel(c) {
    if (c.type === "merge") return "🔀 fusionar";
    if (c.type === "move") return "📂 mover";
    return null;
  }

  // ── Article autocomplete ──

  function createAutocomplete(input, onSelect) {
    var list = document.createElement("ul");
    list.className = "ac-results";
    input.parentNode.style.position = "relative";
    input.parentNode.appendChild(list);

    input.addEventListener("input", function () {
      var q = input.value.toLowerCase().trim();
      list.innerHTML = "";
      if (q.length < 2) { list.style.display = "none"; return; }
      var matches = INDEX.filter(function (e) {
        return e.titulo.toLowerCase().indexOf(q) !== -1 || e.href.toLowerCase().indexOf(q) !== -1;
      }).slice(0, 8);
      if (!matches.length) { list.style.display = "none"; return; }
      matches.forEach(function (m) {
        var li = document.createElement("li");
        li.innerHTML = '<span class="ac-title">' + esc(m.titulo) + '</span> <span class="ac-cat">' + esc(m.cat) + '</span>';
        li.addEventListener("mousedown", function (e) {
          e.preventDefault();
          input.value = m.titulo;
          input.dataset.slug = m.href.replace(".html", "");
          list.style.display = "none";
          if (onSelect) onSelect(m);
        });
        list.appendChild(li);
      });
      list.style.display = "block";
    });

    input.addEventListener("blur", function () {
      setTimeout(function () { list.style.display = "none"; }, 150);
    });
  }

  // ── API ──

  function authHeaders(xhr) {
    if (!IS_LOCAL && API_SECRET) {
      xhr.setRequestHeader("Authorization", "Bearer " + API_SECRET);
    }
  }

  function loadComments(cb) {
    var xhr = new XMLHttpRequest();
    xhr.open("GET", API);
    xhr.onload = function () {
      if (xhr.status === 200) {
        try { comments = JSON.parse(xhr.responseText); } catch (e) { comments = []; }
      } else { comments = []; }
      cb();
    };
    xhr.onerror = function () { comments = []; cb(); };
    xhr.send();
  }

  function saveComment(comment, cb) {
    var xhr = new XMLHttpRequest();
    xhr.open("POST", API);
    xhr.setRequestHeader("Content-Type", "application/json");
    authHeaders(xhr);
    xhr.onload = function () {
      loadComments(cb);
    };
    xhr.onerror = function () { cb(); };
    xhr.send(JSON.stringify(comment));
  }

  function updateComment(id, data, cb) {
    var xhr = new XMLHttpRequest();
    xhr.open("PUT", API + "/@" + id);
    xhr.setRequestHeader("Content-Type", "application/json");
    authHeaders(xhr);
    xhr.onload = function () { loadComments(cb); };
    xhr.onerror = function () { cb(); };
    xhr.send(JSON.stringify(data));
  }

  function deleteComment(id, cb) {
    var xhr = new XMLHttpRequest();
    xhr.open("DELETE", API + "/@" + id);
    authHeaders(xhr);
    xhr.onload = function () { loadComments(cb); };
    xhr.onerror = function () { cb(); };
    xhr.send();
  }

  // ── Sync ──

  function mergeComments(local, remote) {
    var byId = {};
    var changed = false;
    local.forEach(function (c) { byId[c.id] = c; });
    remote.forEach(function (c) {
      if (!byId[c.id]) {
        byId[c.id] = c;
        changed = true;
      } else {
        var ex = byId[c.id];
        var lr = (ex.replies || []).length;
        var rr = (c.replies || []).length;
        var lRes = ex.status === "resolved" || ex.status === "archived";
        var rRes = c.status === "resolved" || c.status === "archived";
        if (rr > lr || (rRes && !lRes)) {
          byId[c.id] = c;
          changed = true;
        }
      }
    });
    local.forEach(function (c) {
      if (!byId[c.id] || byId[c.id] === c) return;
    });
    var merged = Object.keys(byId).map(function (k) { return byId[k]; });
    merged.sort(function (a, b) { return (a.created || "").localeCompare(b.created || ""); });
    return { comments: merged, changed: changed };
  }

  function fetchRemote(cb) {
    var xhr = new XMLHttpRequest();
    xhr.open("GET", REMOTE_API);
    if (API_SECRET) xhr.setRequestHeader("Authorization", "Bearer " + API_SECRET);
    xhr.onload = function () {
      if (xhr.status === 200) {
        try { cb(JSON.parse(xhr.responseText)); } catch (e) { cb(null); }
      } else { cb(null); }
    };
    xhr.onerror = function () { cb(null); };
    xhr.send();
  }

  function pushTo(url, data, useAuth) {
    var xhr = new XMLHttpRequest();
    xhr.open("PUT", url);
    xhr.setRequestHeader("Content-Type", "application/json");
    if (useAuth && API_SECRET) xhr.setRequestHeader("Authorization", "Bearer " + API_SECRET);
    xhr.send(JSON.stringify(data));
  }

  function syncComments(cb) {
    var localCopy = comments.slice();
    fetchRemote(function (remote) {
      if (!remote) { if (cb) cb(); return; }
      var result = mergeComments(localCopy, remote);
      if (!result.changed && localCopy.length === remote.length) { if (cb) cb(); return; }
      comments = result.comments;
      if (IS_LOCAL) {
        // push merged to local server
        var xhr = new XMLHttpRequest();
        xhr.open("PUT", "/api/sync-page/" + SLUG);
        xhr.setRequestHeader("Content-Type", "application/json");
        xhr.send(JSON.stringify(comments));
      }
      // push merged to remote
      var payload = {};
      payload[SLUG] = comments;
      pushTo(REMOTE_API.replace("/api/comments/" + SLUG, "/api/sync"), payload, true);
      if (cb) cb();
    });
  }

  // ── Inline highlights ──

  function renderHighlights() {
    document.querySelectorAll(".commented-text").forEach(function (el) {
      el.outerHTML = el.textContent;
    });

    var body = document.querySelector(".body");
    if (!body) return;

    var inlineComments = comments.filter(function (c) {
      return c.anchor && c.anchor.text && c.status !== "resolved";
    });

    inlineComments.forEach(function (c, i) {
      var walker = document.createTreeWalker(body, NodeFilter.SHOW_TEXT);
      var searchText = c.anchor.text;
      while (walker.nextNode()) {
        var node = walker.currentNode;
        var idx = node.textContent.indexOf(searchText);
        if (idx === -1) continue;

        var range = document.createRange();
        range.setStart(node, idx);
        range.setEnd(node, idx + searchText.length);

        var span = document.createElement("span");
        span.className = "commented-text";
        span.dataset.commentId = c.id;

        var indicator = document.createElement("span");
        indicator.className = "comment-indicator";
        indicator.textContent = String(i + 1);

        range.surroundContents(span);
        span.appendChild(indicator);

        span.addEventListener("click", function () {
          openSidebar();
          highlightCard(c.id);
        });
        break;
      }
    });
  }

  // ── Section comment buttons ──

  function initSectionButtons() {
    var body = document.querySelector(".body");
    if (!body) return;

    body.querySelectorAll("h2[id], h3[id]").forEach(function (heading) {
      var btn = document.createElement("a");
      btn.className = "section-comment-btn";
      btn.title = "Comentar esta sección";
      btn.innerHTML = '<svg viewBox="0 0 24 24" width="14" height="14" fill="currentColor"><path d="M20 2H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h14l4 4V4c0-1.1-.9-2-2-2zm0 15.17L18.83 16H4V4h16v13.17z"/></svg>';
      btn.addEventListener("click", function (e) {
        e.preventDefault();
        e.stopPropagation();
        openSectionCommentForm(heading);
      });
      heading.appendChild(btn);
    });
  }

  function openSectionCommentForm(heading) {
    if (newForm) newForm.style.display = "none";
    removePendingHighlight();

    var sectionForm = document.createElement("div");
    sectionForm.className = "new-comment-form section-form";
    sectionForm.innerHTML =
      '<div class="selected-quote">§ ' + esc(heading.textContent.replace("¶", "").trim()) + '</div>' +
      '<textarea placeholder="Escribe tu comentario…"></textarea>' +
      '<div class="form-actions">' +
      '<button class="btn-cancel">Cancelar</button>' +
      '<button class="btn-save">Guardar</button></div>';

    var rect = heading.getBoundingClientRect();
    sectionForm.style.position = "absolute";
    sectionForm.style.display = "block";
    sectionForm.style.left = (rect.right + 12 + window.scrollX) + "px";
    sectionForm.style.top = (rect.top + window.scrollY) + "px";

    document.body.appendChild(sectionForm);

    var formRect = sectionForm.getBoundingClientRect();
    if (formRect.right > window.innerWidth) {
      sectionForm.style.left = (rect.left - formRect.width - 12 + window.scrollX) + "px";
    }
    if (formRect.right > window.innerWidth) {
      sectionForm.style.left = "8px";
      sectionForm.style.right = "8px";
      sectionForm.style.width = "auto";
    }

    sectionForm.querySelector("textarea").focus();

    sectionForm.querySelector(".btn-cancel").addEventListener("click", function () {
      sectionForm.remove();
    });

    sectionForm.querySelector(".btn-save").addEventListener("click", function () {
      var text = sectionForm.querySelector("textarea").value.trim();
      if (!text) return;
      var comment = {
        id: genId(),
        anchor: { text: "", section: heading.id },
        comment: text,
        author: "alvaro",
        created: new Date().toISOString(),
        status: "open",
        replies: []
      };
      sectionForm.remove();
      saveComment(comment, function () {
        renderHighlights();
        renderSidebar();
        openSidebar();
        highlightCard(comment.id);
      });
    });
  }

  // ── Selection popover ──

  function initSelectionPopover() {
    selPopover = document.createElement("div");
    selPopover.className = "selection-popover";
    selPopover.innerHTML = '<svg viewBox="0 0 24 24"><path d="M20 2H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h14l4 4V4c0-1.1-.9-2-2-2zm0 15.17L18.83 16H4V4h16v13.17z"/></svg> Comentar';
    document.body.appendChild(selPopover);

    newForm = document.createElement("div");
    newForm.className = "new-comment-form";
    newForm.innerHTML =
      '<div class="selected-quote"></div>' +
      '<textarea placeholder="Escribe tu comentario…"></textarea>' +
      '<div class="form-actions">' +
      '<button class="btn-cancel">Cancelar</button>' +
      '<button class="btn-save">Guardar</button></div>';
    document.body.appendChild(newForm);

    var body = document.querySelector(".body");
    if (!body) return;

    document.addEventListener("mouseup", function (e) {
      if (selPopover.contains(e.target) || newForm.contains(e.target)) return;
      if (e.target.closest(".section-form")) return;

      var sel = window.getSelection();
      if (!sel || sel.isCollapsed || !sel.toString().trim()) {
        selPopover.style.display = "none";
        return;
      }

      var range = sel.getRangeAt(0);
      if (!body.contains(range.commonAncestorContainer)) {
        selPopover.style.display = "none";
        return;
      }

      var rect = range.getBoundingClientRect();
      pendingSelection = {
        text: sel.toString().trim().slice(0, 200),
        section: findSection(range.startContainer),
        range: range.cloneRange(),
        rect: { top: rect.top, left: rect.left, right: rect.right, bottom: rect.bottom }
      };

      selPopover.style.display = "flex";
      selPopover.style.left = (rect.left + rect.width / 2 - 50 + window.scrollX) + "px";
      selPopover.style.top = (rect.top - 36 + window.scrollY) + "px";
    });

    selPopover.addEventListener("click", function () {
      selPopover.style.display = "none";
      if (!pendingSelection) return;

      window.getSelection().removeAllRanges();

      try {
        pendingHighlight = document.createElement("span");
        pendingHighlight.className = "pending-highlight";
        pendingSelection.range.surroundContents(pendingHighlight);
      } catch (e) {
        pendingHighlight = null;
      }

      var quote = newForm.querySelector(".selected-quote");
      quote.textContent = '"' + pendingSelection.text + '"';

      var savedRect = pendingSelection.rect;
      var anchorRect = pendingHighlight
        ? pendingHighlight.getBoundingClientRect()
        : savedRect;

      newForm.style.display = "block";
      newForm.style.left = (anchorRect.right + 12 + window.scrollX) + "px";
      newForm.style.top = (anchorRect.top + window.scrollY) + "px";

      var formRect = newForm.getBoundingClientRect();
      if (formRect.right > window.innerWidth) {
        newForm.style.left = (anchorRect.left - formRect.width - 12 + window.scrollX) + "px";
      }

      newForm.querySelector("textarea").value = "";
      newForm.querySelector("textarea").focus();
    });

    newForm.querySelector(".btn-cancel").addEventListener("click", function () {
      newForm.style.display = "none";
      removePendingHighlight();
      pendingSelection = null;
    });

    newForm.querySelector(".btn-save").addEventListener("click", function () {
      var text = newForm.querySelector("textarea").value.trim();
      if (!text || !pendingSelection) return;

      var comment = {
        id: genId(),
        anchor: { text: pendingSelection.text, section: pendingSelection.section },
        comment: text,
        author: "alvaro",
        created: new Date().toISOString(),
        status: "open",
        replies: []
      };

      newForm.style.display = "none";
      removePendingHighlight();
      pendingSelection = null;

      saveComment(comment, function () {
        renderHighlights();
        renderSidebar();
        openSidebar();
        highlightCard(comment.id);
      });
    });
  }

  // ── Action modal (merge / move) ──

  function showActionModal(type) {
    if (actionModal) actionModal.remove();

    var currentTitle = document.querySelector(".page-title")
      ? document.querySelector(".page-title").textContent.trim()
      : SLUG;

    var html = "";
    if (type === "merge") {
      html =
        '<div class="modal-overlay">' +
        '<div class="modal-box">' +
        '<div class="modal-header">🔀 Fusionar artículos<button class="modal-close">×</button></div>' +
        '<div class="modal-body">' +
        '<label>Absorber en (el que sobrevive)</label>' +
        '<div class="ac-wrap"><input class="ac-input" id="merge-target" value="' + esc(currentTitle) + '" data-slug="' + esc(SLUG) + '"></div>' +
        '<div class="merge-swap"><button class="btn-swap" title="Intercambiar">⇅</button></div>' +
        '<label>Fusionar desde (se absorbe)</label>' +
        '<div class="ac-wrap"><input class="ac-input" id="merge-source" placeholder="Buscar artículo…"></div>' +
        '<div class="merge-explain"></div>' +
        '<label>Nota (opcional)</label>' +
        '<textarea id="merge-note" placeholder="Razón de la fusión…"></textarea>' +
        '</div>' +
        '<div class="modal-footer"><button class="btn-cancel">Cancelar</button><button class="btn-action">Crear propuesta</button></div>' +
        '</div></div>';
    } else if (type === "move") {
      html =
        '<div class="modal-overlay">' +
        '<div class="modal-box">' +
        '<div class="modal-header">📂 Mover artículo<button class="modal-close">×</button></div>' +
        '<div class="modal-body">' +
        '<label>Artículo</label>' +
        '<input class="modal-input" value="' + esc(currentTitle) + '" disabled>' +
        '<label>Mover a categoría</label>' +
        '<input class="modal-input" id="move-dest" placeholder="ej: organizaciones/">' +
        '<label>Nota (opcional)</label>' +
        '<textarea id="move-note" placeholder="Razón del movimiento…"></textarea>' +
        '</div>' +
        '<div class="modal-footer"><button class="btn-cancel">Cancelar</button><button class="btn-action">Crear propuesta</button></div>' +
        '</div></div>';
    }

    actionModal = document.createElement("div");
    actionModal.innerHTML = html;
    actionModal = actionModal.firstChild;
    document.body.appendChild(actionModal);

    if (type === "merge") {
      var targetInput = actionModal.querySelector("#merge-target");
      var sourceInput = actionModal.querySelector("#merge-source");
      var explainEl = actionModal.querySelector(".merge-explain");

      createAutocomplete(targetInput, updateMergeExplain);
      createAutocomplete(sourceInput, updateMergeExplain);

      function updateMergeExplain() {
        var t = targetInput.value || "?";
        var s = sourceInput.value || "?";
        if (s && s !== "?") {
          explainEl.textContent = "\"" + s + "\" se fusionará dentro de \"" + t + "\"";
        } else {
          explainEl.textContent = "";
        }
      }

      actionModal.querySelector(".btn-swap").addEventListener("click", function () {
        var tv = targetInput.value;
        var ts = targetInput.dataset.slug || "";
        targetInput.value = sourceInput.value;
        targetInput.dataset.slug = sourceInput.dataset.slug || "";
        sourceInput.value = tv;
        sourceInput.dataset.slug = ts;
        updateMergeExplain();
      });

      sourceInput.addEventListener("input", updateMergeExplain);
      targetInput.addEventListener("input", updateMergeExplain);
    }

    actionModal.querySelector(".modal-close").addEventListener("click", closeModal);
    actionModal.querySelector(".btn-cancel").addEventListener("click", closeModal);
    actionModal.addEventListener("click", function (e) {
      if (e.target === actionModal) closeModal();
    });

    actionModal.querySelector(".btn-action").addEventListener("click", function () {
      var comment;
      if (type === "merge") {
        var target = actionModal.querySelector("#merge-target");
        var source = actionModal.querySelector("#merge-source");
        if (!source.value.trim()) return;
        comment = {
          id: genId(),
          type: "merge",
          anchor: null,
          comment: actionModal.querySelector("#merge-note").value.trim() || "Propuesta de fusión",
          author: "alvaro",
          created: new Date().toISOString(),
          status: "open",
          replies: [],
          merge: {
            target: { slug: target.dataset.slug || "", title: target.value },
            source: { slug: source.dataset.slug || "", title: source.value }
          }
        };
      } else if (type === "move") {
        var dest = actionModal.querySelector("#move-dest").value.trim();
        if (!dest) return;
        comment = {
          id: genId(),
          type: "move",
          anchor: null,
          comment: actionModal.querySelector("#move-note").value.trim() || "Propuesta de movimiento",
          author: "alvaro",
          created: new Date().toISOString(),
          status: "open",
          replies: [],
          move: { destination: dest }
        };
      }
      closeModal();
      saveComment(comment, function () {
        renderHighlights();
        renderSidebar();
        openSidebar();
        highlightCard(comment.id);
      });
    });
  }

  function closeModal() {
    if (actionModal) {
      actionModal.remove();
      actionModal = null;
    }
  }

  // ── Sidebar ──

  function initSidebar() {
    sidebar = document.createElement("aside");
    sidebar.className = "comment-sidebar";
    sidebar.innerHTML =
      '<div class="sidebar-header"><h3>Comentarios</h3><button class="sidebar-close">×</button></div>' +
      '<div class="sidebar-filters"></div>' +
      '<div class="sidebar-list"></div>' +
      '<div class="sidebar-bottom-actions">' +
      '<button class="sidebar-add-btn">' +
      '<svg viewBox="0 0 24 24"><path d="M20 2H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h14l4 4V4c0-1.1-.9-2-2-2zm0 15.17L18.83 16H4V4h16v13.17z"/></svg>' +
      'Comentario</button>' +
      '<button class="sidebar-action-btn" data-type="merge">🔀 Fusionar</button>' +
      '<button class="sidebar-action-btn" data-type="move">📂 Mover</button>' +
      '<button class="sidebar-action-btn sidebar-sync-btn" data-type="sync">🔄 Sync</button>' +
      '</div>';

    var wrap = document.querySelector(".page-wrap");
    if (wrap) {
      wrap.appendChild(sidebar);
    } else {
      var main = document.querySelector("main.content");
      if (!main) return;
      var w = document.createElement("div");
      w.className = "page-wrap";
      main.parentNode.insertBefore(w, main);
      var pm = document.createElement("div");
      pm.className = "page-main";
      w.appendChild(pm);
      pm.appendChild(main);
      w.appendChild(sidebar);
    }

    sidebar.querySelector(".sidebar-close").addEventListener("click", closeSidebar);

    sidebar.querySelector(".sidebar-add-btn").addEventListener("click", function () {
      var text = prompt("Comentario general:");
      if (!text || !text.trim()) return;
      var comment = {
        id: genId(),
        anchor: null,
        comment: text.trim(),
        author: "alvaro",
        created: new Date().toISOString(),
        status: "open",
        replies: []
      };
      saveComment(comment, function () {
        renderHighlights();
        renderSidebar();
        highlightCard(comment.id);
      });
    });

    sidebar.querySelectorAll(".sidebar-action-btn").forEach(function (btn) {
      btn.addEventListener("click", function () {
        if (btn.dataset.type === "sync") {
          btn.textContent = "⏳ Sync...";
          syncComments(function () {
            renderHighlights();
            renderSidebar();
            btn.textContent = "🔄 Sync";
          });
          return;
        }
        showActionModal(btn.dataset.type);
      });
    });
  }

  function renderSidebar() {
    if (!sidebar) return;

    var counts = { all: 0, open: 0, question: 0, replied: 0, resolved: 0, archived: 0, merge: 0, move: 0 };
    comments.forEach(function (c) {
      var st = statusOf(c);
      if (st !== "archived") counts.all++;
      counts[st]++;
    });

    var filtersEl = sidebar.querySelector(".sidebar-filters");
    var filterButtons =
      '<button class="sidebar-filter' + (activeFilter === "all" ? " active" : "") + '" data-f="all">Todos (' + counts.all + ')</button>' +
      '<button class="sidebar-filter' + (activeFilter === "open" ? " active" : "") + '" data-f="open">Abiertos (' + counts.open + ')</button>' +
      '<button class="sidebar-filter' + (activeFilter === "question" ? " active" : "") + '" data-f="question">Pregunta (' + counts.question + ')</button>' +
      '<button class="sidebar-filter' + (activeFilter === "replied" ? " active" : "") + '" data-f="replied">Respondidos (' + counts.replied + ')</button>';
    if (counts.merge > 0) {
      filterButtons += '<button class="sidebar-filter' + (activeFilter === "merge" ? " active" : "") + '" data-f="merge">🔀 Fusionar (' + counts.merge + ')</button>';
    }
    if (counts.move > 0) {
      filterButtons += '<button class="sidebar-filter' + (activeFilter === "move" ? " active" : "") + '" data-f="move">📂 Mover (' + counts.move + ')</button>';
    }
    filterButtons += '<button class="sidebar-filter' + (activeFilter === "resolved" ? " active" : "") + '" data-f="resolved">Resueltos (' + counts.resolved + ')</button>';
    if (counts.archived > 0) {
      filterButtons += '<button class="sidebar-filter' + (activeFilter === "archived" ? " active" : "") + '" data-f="archived">Archivo (' + counts.archived + ')</button>';
    }

    filtersEl.innerHTML = filterButtons;

    filtersEl.querySelectorAll(".sidebar-filter").forEach(function (btn) {
      btn.addEventListener("click", function () {
        activeFilter = btn.dataset.f;
        renderSidebar();
      });
    });

    var listEl = sidebar.querySelector(".sidebar-list");
    var filtered = comments.filter(function (c) {
      var st = statusOf(c);
      if (activeFilter === "all") return st !== "archived";
      return st === activeFilter;
    });

    if (!filtered.length) {
      listEl.innerHTML = '<div class="sidebar-empty">No hay comentarios' +
        (activeFilter !== "all" ? " con este filtro" : "") + '</div>';
      return;
    }

    listEl.innerHTML = filtered.map(function (c) {
      var st = statusOf(c);
      var tl = typeLabel(c);
      var badgeClass = st;
      var badgeLabel = tl || (st === "open" ? "abierto" : st === "question" ? "pregunta" : st === "replied" ? "respondido" : st === "archived" ? "archivado" : "resuelto");

      var quoteHtml = "";
      if (c.type === "merge" && c.merge) {
        quoteHtml = '<div class="sc-typed-card merge-card">' +
          '<span class="sc-typed-label">Absorber</span> ' + esc(c.merge.source.title) +
          ' <span class="sc-typed-arrow">→</span> <span class="sc-typed-label">en</span> ' + esc(c.merge.target.title) +
          '</div>';
      } else if (c.type === "move" && c.move) {
        quoteHtml = '<div class="sc-typed-card move-card">' +
          '<span class="sc-typed-label">Mover a:</span> ' + esc(c.move.destination) +
          '</div>';
      } else if (c.anchor && c.anchor.text) {
        quoteHtml = '<div class="sc-quote">"' + esc(c.anchor.text) + '"</div>';
        if (c.anchor.section) {
          quoteHtml += '<div class="sc-section">§ ' + esc(c.anchor.section.replace(/-/g, " ")) + '</div>';
        }
      } else if (c.anchor && c.anchor.section) {
        quoteHtml = '<div class="sc-section">§ ' + esc(c.anchor.section.replace(/-/g, " ")) + '</div>';
      } else {
        quoteHtml = '<div class="sc-general-tag">Comentario general</div>';
      }

      var repliesHtml = "";
      if (c.replies) {
        repliesHtml = c.replies.map(function (r) {
          return '<div class="sc-reply"><div class="sc-reply-author">' +
            esc(r.author) + ' · ' + fmtDate(r.created) + '</div>' +
            esc(r.text) + '</div>';
        }).join("");
      }

      var actionsHtml = "";
      if (st !== "archived") {
        actionsHtml += '<button class="sc-reply-btn" data-id="' + c.id + '">Responder</button>';
      }
      if (st !== "resolved" && st !== "archived") {
        actionsHtml += '<button class="resolve" data-id="' + c.id + '">✓ Resolver</button>';
      }
      if (st === "resolved") {
        actionsHtml += '<button class="archive" data-id="' + c.id + '">📦 Archivar</button>';
      }
      if (st !== "resolved" && st !== "archived") {
        actionsHtml += '<button class="discard" data-id="' + c.id + '" title="Eliminar">🗑</button>';
      }

      return '<div class="sidebar-card" data-id="' + c.id + '">' +
        '<div class="sc-header"><div><span class="sc-author">' + esc(c.author) +
        '</span> · <span class="status-badge ' + badgeClass + '">' + badgeLabel + '</span></div>' +
        '<span class="sc-time">' + fmtDate(c.created) + '</span></div>' +
        quoteHtml +
        '<div class="sc-body">' + esc(c.comment) + '</div>' +
        repliesHtml +
        '<div class="sc-actions">' + actionsHtml + '</div></div>';
    }).join("");

    listEl.querySelectorAll(".sc-reply-btn").forEach(function (btn) {
      btn.addEventListener("click", function (e) {
        e.stopPropagation();
        var id = btn.dataset.id;
        var text = prompt("Respuesta:");
        if (!text || !text.trim()) return;
        var reply = { author: "alvaro", text: text.trim(), created: new Date().toISOString() };
        var c = comments.find(function (x) { return x.id === id; });
        if (!c) return;
        if (!c.replies) c.replies = [];
        c.replies.push(reply);
        updateComment(id, c, function () { renderSidebar(); });
      });
    });

    listEl.querySelectorAll(".resolve").forEach(function (btn) {
      btn.addEventListener("click", function (e) {
        e.stopPropagation();
        var id = btn.dataset.id;
        var c = comments.find(function (x) { return x.id === id; });
        if (!c) return;
        c.status = "resolved";
        updateComment(id, c, function () {
          renderHighlights();
          renderSidebar();
        });
      });
    });

    listEl.querySelectorAll(".archive").forEach(function (btn) {
      btn.addEventListener("click", function (e) {
        e.stopPropagation();
        var id = btn.dataset.id;
        var c = comments.find(function (x) { return x.id === id; });
        if (!c) return;
        c.status = "archived";
        updateComment(id, c, function () {
          renderHighlights();
          renderSidebar();
        });
      });
    });

    listEl.querySelectorAll(".discard").forEach(function (btn) {
      btn.addEventListener("click", function (e) {
        e.stopPropagation();
        var id = btn.dataset.id;
        deleteComment(id, function () {
          renderHighlights();
          renderSidebar();
        });
      });
    });

    listEl.querySelectorAll(".sidebar-card").forEach(function (card) {
      card.addEventListener("click", function () {
        var id = card.dataset.id;
        var el = document.querySelector('.commented-text[data-comment-id="' + id + '"]');
        if (el) el.scrollIntoView({ behavior: "smooth", block: "center" });
        highlightCard(id);
      });
    });

    updateToggleCount();
  }

  function highlightCard(id) {
    if (!sidebar) return;
    sidebar.querySelectorAll(".sidebar-card").forEach(function (c) {
      c.classList.toggle("active", c.dataset.id === id);
    });
  }

  function openSidebar() {
    if (!sidebar) return;
    sidebar.classList.add("open");
  }

  function closeSidebar() {
    if (!sidebar) return;
    sidebar.classList.remove("open");
  }

  function updateToggleCount() {
    var btn = document.querySelector(".comment-toggle");
    if (!btn) return;
    var open = comments.filter(function (c) { return statusOf(c) !== "resolved"; }).length;
    var countEl = btn.querySelector(".count");
    if (countEl) countEl.textContent = String(open);
    btn.classList.toggle("empty", open === 0);
  }

  // ── Toggle button ──

  function initToggle() {
    var topbar = document.querySelector(".topbar");
    if (!topbar) return;

    var search = topbar.querySelector("#search");
    var btn = document.createElement("button");
    btn.className = "comment-toggle";
    btn.title = "Ver comentarios";
    btn.innerHTML =
      '<svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor"><path d="M20 2H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h14l4 4V4c0-1.1-.9-2-2-2zm0 15.17L18.83 16H4V4h16v13.17z"/></svg> ' +
      '<span class="toggle-label">Comentarios</span> <span class="count">0</span>';
    topbar.insertBefore(btn, search);

    btn.addEventListener("click", function () {
      if (sidebar && sidebar.classList.contains("open")) {
        closeSidebar();
      } else {
        openSidebar();
      }
    });
  }

  // ── Init ──

  if (document.querySelector(".page-title")) {
    initToggle();
    initSidebar();
    initSelectionPopover();
    initSectionButtons();
    loadComments(function () {
      renderHighlights();
      renderSidebar();
      syncComments(function () {
        renderHighlights();
        renderSidebar();
      });
    });
  }
})();
