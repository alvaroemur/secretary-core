(function () {
  const input = document.getElementById("search");
  if (!input || !window.WIKI_INDEX) return;

  const index = window.WIKI_INDEX;
  const topbar = input.parentElement;

  // Detectar prefix relativo mirando el href del logo.
  const home = topbar.querySelector(".home");
  const prefix = home ? home.getAttribute("href").replace(/index\.html$/, "") : "";

  let results;

  function ensureResultsEl() {
    if (results) return results;
    results = document.createElement("ul");
    results.className = "search-results";
    results.hidden = true;
    topbar.style.position = "relative";
    topbar.appendChild(results);
    return results;
  }

  function normalize(s) {
    return (s || "")
      .toLowerCase()
      .normalize("NFD")
      .replace(/[̀-ͯ]/g, "");
  }

  // Pre-normalizar índice una sola vez.
  const norm = index.map((e) => ({
    titulo: normalize(e.titulo),
    cat: normalize(e.cat),
    body: normalize(e.body || ""),
  }));

  function snippet(bodyOrig, bodyN, nq) {
    if (!bodyOrig) return "";
    const idx = bodyN.indexOf(nq);
    if (idx < 0) return "";
    const start = Math.max(0, idx - 40);
    const end = Math.min(bodyOrig.length, idx + nq.length + 80);
    let s = bodyOrig.slice(start, end);
    if (start > 0) s = "…" + s;
    if (end < bodyOrig.length) s = s + "…";
    return s;
  }

  function search(q) {
    const nq = normalize(q);
    if (!nq) return [];
    const titleHits = [];
    const bodyHits = [];
    for (let i = 0; i < index.length; i++) {
      const e = index[i];
      const n = norm[i];
      if (n.titulo.includes(nq) || n.cat.includes(nq)) {
        titleHits.push({ entry: e, snip: "" });
      } else if (n.body && n.body.includes(nq)) {
        bodyHits.push({ entry: e, snip: snippet(e.body, n.body, nq) });
      }
    }
    return titleHits.concat(bodyHits).slice(0, 15);
  }

  function escapeHtml(s) {
    return (s || "").replace(
      /[&<>"']/g,
      (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]
    );
  }

  function highlight(text, q) {
    const escaped = escapeHtml(text);
    if (!text || !q) return escaped;
    const nText = normalize(text);
    const nQ = normalize(q);
    const idx = nText.indexOf(nQ);
    if (idx < 0) return escaped;
    // Re-mapear índice al texto original (asumiendo que normalize no cambia longitud
    // significativamente — sólo case + acentos, ambos preservan posición de caracteres).
    return (
      escapeHtml(text.slice(0, idx)) +
      "<mark>" +
      escapeHtml(text.slice(idx, idx + nQ.length)) +
      "</mark>" +
      escapeHtml(text.slice(idx + nQ.length))
    );
  }

  function render(items, q) {
    const el = ensureResultsEl();
    if (!items.length) {
      el.hidden = true;
      el.innerHTML = "";
      return;
    }
    el.innerHTML = items
      .map(({ entry, snip }) => {
        const snippetHtml = snip
          ? `<div class="search-snippet">${highlight(snip, q)}</div>`
          : "";
        return (
          `<li><a href="${prefix}${entry.href}">` +
          `<strong>${highlight(entry.titulo, q)}</strong>` +
          ` <span class="search-cat">· ${escapeHtml(entry.cat)}</span>` +
          snippetHtml +
          `</a></li>`
        );
      })
      .join("");
    el.hidden = false;
  }

  input.addEventListener("input", () => render(search(input.value), input.value));
  input.addEventListener("blur", () =>
    setTimeout(() => {
      if (results) results.hidden = true;
    }, 150)
  );
  input.addEventListener("focus", () => {
    if (input.value) render(search(input.value), input.value);
  });
})();

(function () {
  var btn = document.getElementById("theme-toggle");
  if (!btn) return;
  var t = document.documentElement.getAttribute("data-theme") || "light";
  btn.textContent = t === "dark" ? "☀️" : "🌙";
  btn.addEventListener("click", function () {
    t = t === "dark" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", t);
    localStorage.setItem("wiki-theme", t);
    btn.textContent = t === "dark" ? "☀️" : "🌙";
  });
})();
