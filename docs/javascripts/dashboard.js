/*
 * BICAN dashboard: reads data/dandisets.json (made by scripts/fetch_dandisets.py)
 * and shows summary numbers plus a searchable, filterable grid of dandisets.
 */
(function () {
  "use strict";

  const esc = (s) =>
    String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
  const safeUrl = (u) => (/^https?:\/\//i.test(u || "") ? u : "#");
  const fmtInt = (n) => Number(n || 0).toLocaleString("en-US");

  function fmtBytes(bytes) {
    const units = ["B", "KB", "MB", "GB", "TB", "PB"];
    let v = Number(bytes || 0);
    let i = 0;
    while (v >= 1000 && i < units.length - 1) {
      v /= 1000;
      i += 1;
    }
    const num = i === 0 || v >= 100 ? Math.round(v) : v.toFixed(1);
    return { num: String(num), unit: units[i], text: `${num} ${units[i]}` };
  }

  function fmtDate(iso) {
    if (!iso) return "";
    const d = new Date(`${iso}T00:00:00Z`);
    return d.toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric", timeZone: "UTC" });
  }

  const SORTS = {
    newest: { label: "Newest", fn: (a, b) => (b.published || b.created).localeCompare(a.published || a.created) },
    largest: { label: "Largest", fn: (a, b) => b.bytes - a.bytes },
    subjects: { label: "Most subjects", fn: (a, b) => b.subjects - a.subjects },
    id: { label: "Dandiset ID", fn: (a, b) => a.id.localeCompare(b.id) },
  };

  // Count how many dandisets have each value, for the filter menus.
  function tally(items, pick) {
    const counts = new Map();
    items.forEach((d) => pick(d).forEach((v) => counts.set(v, (counts.get(v) || 0) + 1)));
    return [...counts.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
  }

  const speciesOf = (d) => d.species.map((s) => s.name);
  const typesOf = (d) => d.approaches;

  function statTiles(items) {
    const size = fmtBytes(items.reduce((t, d) => t + d.bytes, 0));
    const species = new Set(items.flatMap(speciesOf));
    const tiles = [
      ["Dandisets", fmtInt(items.length), ""],
      ["Subjects", fmtInt(items.reduce((t, d) => t + d.subjects, 0)), ""],
      ["Files", fmtInt(items.reduce((t, d) => t + d.files, 0)), ""],
      ["Data", size.num, size.unit],
      ["Species", fmtInt(species.size), ""],
    ];
    return tiles
      .map(
        ([label, value, unit]) => `
        <div class="bd-stat">
          <div class="bd-stat__label">${label}</div>
          <div class="bd-stat__value">${value}${unit ? `<span class="bd-stat__unit">${unit}</span>` : ""}</div>
        </div>`
      )
      .join("");
  }

  function options(entries, allLabel, selected) {
    return [`<option value="">${allLabel}</option>`]
      .concat(
        entries.map(
          ([v, n]) => `<option value="${esc(v)}"${v === selected ? " selected" : ""}>${esc(v)} (${n})</option>`
        )
      )
      .join("");
  }

  function card(d) {
    const status =
      d.status === "published"
        ? `<span class="bd-status bd-status--published" title="Version ${esc(d.version)}">Published</span>`
        : `<span class="bd-status bd-status--draft" title="Not yet published on DANDI">Draft</span>`;
    const chips = d.species
      .map((s) => `<span class="bd-chip bd-chip--species"${s.scientific ? ` title="${esc(s.scientific)}"` : ""}>${esc(s.name)}</span>`)
      .concat(d.approaches.map((a) => `<span class="bd-chip">${esc(a)}</span>`))
      .join("");
    const size = fmtBytes(d.bytes);
    const people = d.contacts.slice(0, 2).join(", ");
    const org = d.organizations[0] || "";
    const who = [people, org].filter(Boolean).map(esc).join(" · ");
    const date = d.published ? `Published ${fmtDate(d.published)}` : `Created ${fmtDate(d.created)}`;
    const links = [`<a class="bd-btn bd-btn--primary" href="${safeUrl(d.url)}">View on DANDI</a>`];
    if (d.doi_url) links.push(`<a class="bd-btn" href="${safeUrl(d.doi_url)}" title="${esc(d.doi)}">DOI</a>`);
    d.papers.slice(0, 2).forEach((p) => links.push(`<a class="bd-btn" href="${safeUrl(p.url)}">${esc(p.label)}</a>`));

    return `
      <article class="bd-card">
        <div class="bd-card__top">
          <span class="bd-id">DANDI:${esc(d.id)}</span>
          ${status}
        </div>
        <h3 class="bd-card__title"><a href="${safeUrl(d.url)}">${esc(d.title)}</a></h3>
        ${d.note ? `<p class="bd-card__note">${esc(d.note)}</p>` : ""}
        ${d.description ? `<p class="bd-card__desc" title="${esc(d.description)}">${esc(d.description)}</p>` : ""}
        ${chips ? `<div class="bd-chips">${chips}</div>` : ""}
        <dl class="bd-facts">
          <div><dt>Subjects</dt><dd>${fmtInt(d.subjects)}</dd></div>
          <div><dt>Files</dt><dd>${fmtInt(d.files)}</dd></div>
          <div><dt>Size</dt><dd>${size.text}</dd></div>
        </dl>
        <p class="bd-card__meta">${who ? `${who}<br>` : ""}${date}</p>
        <div class="bd-links">${links.join("")}</div>
      </article>`;
  }

  function render(root, data) {
    const all = data.dandisets;
    const params = new URLSearchParams(window.location.search);
    const state = {
      q: params.get("q") || "",
      species: params.get("species") || "",
      type: params.get("type") || "",
      status: params.get("status") || "",
      sort: SORTS[params.get("sort")] ? params.get("sort") : "newest",
    };

    root.innerHTML = `
      <section class="bd-stats" aria-label="Totals">${statTiles(all)}</section>
      <div class="bd-controls" role="search">
        <label class="bd-search">
          <span class="bd-visually-hidden">Search dandisets</span>
          <input type="search" placeholder="Search titles, people, keywords, IDs…" value="${esc(state.q)}" data-key="q">
        </label>
        <label><span class="bd-visually-hidden">Species</span>
          <select data-key="species">${options(tally(all, speciesOf), "All species", state.species)}</select></label>
        <label><span class="bd-visually-hidden">Data type</span>
          <select data-key="type">${options(tally(all, typesOf), "All data types", state.type)}</select></label>
        <label><span class="bd-visually-hidden">Status</span>
          <select data-key="status">${options(tally(all, (d) => [d.status === "published" ? "Published" : "Draft"]), "Any status", state.status)}</select></label>
        <label><span class="bd-visually-hidden">Sort by</span>
          <select data-key="sort">${Object.entries(SORTS)
            .map(([k, s]) => `<option value="${k}"${k === state.sort ? " selected" : ""}>Sort: ${s.label}</option>`)
            .join("")}</select></label>
      </div>
      <div class="bd-summary" aria-live="polite"></div>
      <div class="bd-grid"></div>
      <p class="bd-footnote">Details from the <a href="https://dandiarchive.org/">DANDI Archive</a>, last updated ${esc(
        data.generated.replace("T", " at ").replace("Z", " UTC")
      )}.</p>`;

    const grid = root.querySelector(".bd-grid");
    const summary = root.querySelector(".bd-summary");

    function update() {
      const q = state.q.trim().toLowerCase();
      const shown = all
        .filter((d) => !state.species || speciesOf(d).includes(state.species))
        .filter((d) => !state.type || typesOf(d).includes(state.type))
        .filter((d) => !state.status || (state.status === "Published") === (d.status === "published"))
        .filter((d) => {
          if (!q) return true;
          const hay = [d.id, d.title, d.description, d.note, ...d.contacts, ...d.organizations, ...d.keywords, ...speciesOf(d), ...d.species.map((s) => s.scientific)]
            .join(" ")
            .toLowerCase();
          return q.split(/\s+/).every((word) => hay.includes(word));
        })
        .sort(SORTS[state.sort].fn);

      const filtered = state.q || state.species || state.type || state.status;
      summary.innerHTML =
        `Showing <strong>${shown.length}</strong> of ${all.length} dandisets` +
        (filtered ? ` <button type="button" class="bd-clear">Clear filters</button>` : "");
      grid.innerHTML = shown.length
        ? shown.map(card).join("")
        : `<p class="bd-empty">No dandisets match these filters.</p>`;

      const next = new URLSearchParams();
      Object.entries(state).forEach(([k, v]) => v && !(k === "sort" && v === "newest") && next.set(k, v));
      const qs = next.toString();
      history.replaceState(history.state, "", `${window.location.pathname}${qs ? `?${qs}` : ""}${window.location.hash}`);
    }

    root.querySelectorAll("[data-key]").forEach((el) => {
      el.addEventListener(el.tagName === "INPUT" ? "input" : "change", () => {
        state[el.dataset.key] = el.value;
        update();
      });
    });
    summary.addEventListener("click", (e) => {
      if (!e.target.closest(".bd-clear")) return;
      Object.assign(state, { q: "", species: "", type: "", status: "" });
      root.querySelectorAll("[data-key]").forEach((el) => {
        if (el.dataset.key !== "sort") el.value = "";
      });
      update();
    });
    update();
  }

  async function init() {
    const root = document.getElementById("bican-dashboard");
    if (!root || root.dataset.ready) return;
    root.dataset.ready = "1";
    try {
      const res = await fetch(new URL(root.dataset.src || "data/dandisets.json", window.location.href));
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      render(root, await res.json());
    } catch (err) {
      root.innerHTML = `<p class="bd-empty">Couldn't load the dandiset list (${esc(err.message)}).
        If you're previewing locally, run <code>python scripts/fetch_dandisets.py</code> first.</p>`;
    }
  }

  // Run on first load, and again after each in-site page change.
  if (window.document$ && typeof window.document$.subscribe === "function") {
    window.document$.subscribe(init);
  } else if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
