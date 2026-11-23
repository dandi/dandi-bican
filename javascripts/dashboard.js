// Dashboard page: loads data/dandisets.json and shows the totals, filters and cards.
(() => {
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`);
  const fmtInt = (n) => n.toLocaleString("en-US");
  const fmtDate = (iso) =>
    new Date(iso).toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric", timeZone: "UTC" });

  // Bytes to a short size, e.g. 1234567 -> ["1.2", "MB"]
  function fmtBytes(bytes) {
    const units = ["B", "KB", "MB", "GB", "TB", "PB"];
    let i = 0;
    while (bytes >= 1000 && i < units.length - 1) {
      bytes /= 1000;
      i += 1;
    }
    return [i === 0 || bytes >= 100 ? String(Math.round(bytes)) : bytes.toFixed(1), units[i]];
  }

  const SORTS = {
    newest: { label: "Newest", fn: (a, b) => (b.published || b.updated).localeCompare(a.published || a.updated) },
    largest: { label: "Largest", fn: (a, b) => b.bytes - a.bytes },
    subjects: { label: "Most subjects", fn: (a, b) => b.subjects - a.subjects },
    id: { label: "Dandiset ID", fn: (a, b) => a.id.localeCompare(b.id) },
  };

  const speciesOf = (d) => d.species.map((s) => s.name);

  // Options for a filter menu: "All", then each value with its count.
  function countedOptions(values, allLabel) {
    const counts = {};
    values.forEach((v) => (counts[v] = (counts[v] || 0) + 1));
    const sorted = Object.entries(counts).sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
    return [["", allLabel], ...sorted.map(([v, n]) => [v, `${v} (${n})`])];
  }

  function statTiles(items) {
    const sum = (key) => items.reduce((total, d) => total + d[key], 0);
    const [size, unit] = fmtBytes(sum("bytes"));
    return [
      ["Dandisets", fmtInt(items.length)],
      ["Subjects", fmtInt(sum("subjects"))],
      ["Files", fmtInt(sum("files"))],
      ["Data", size, unit],
      ["Species", fmtInt(new Set(items.flatMap(speciesOf)).size)],
    ]
      .map(
        ([label, value, unit]) => `
        <div class="bd-stat">
          <div class="bd-stat__label">${label}</div>
          <div class="bd-stat__value">${value}${unit ? `<span class="bd-stat__unit">${unit}</span>` : ""}</div>
        </div>`
      )
      .join("");
  }

  function card(d) {
    const [size, unit] = fmtBytes(d.bytes);
    const status =
      d.published
        ? `<span class="bd-status bd-status--published" title="Version ${esc(d.version)}">Published</span>`
        : `<span class="bd-status bd-status--draft" title="Not yet published on DANDI">Draft</span>`;
    const chips = [
      ...d.species.map((s) => `<span class="bd-chip"${s.scientific ? ` title="${esc(s.scientific)}"` : ""}>${esc(s.name)}</span>`),
      ...d.approaches.map((a) => `<span class="bd-chip">${esc(a)}</span>`),
    ].join("");
    const count = (n, word) => `<strong>${fmtInt(n)}</strong> ${word}${n === 1 ? "" : "s"}`;

    return `
      <article class="bd-card">
        <div class="bd-card__top">
          <span class="bd-id">DANDI:${esc(d.id)}</span>
          ${status}
        </div>
        <h3 class="bd-card__title"><a href="${esc(d.url)}">${esc(d.title).replace(/_/g, "_<wbr>")}</a></h3>
        ${chips ? `<div class="bd-chips">${chips}</div>` : ""}
        <div class="bd-card__footer">
          <p class="bd-card__stats">${count(d.subjects, "subject")} · ${count(d.files, "file")} · <strong>${size} ${unit}</strong></p>
          <div class="bd-card__actions">
            <a class="bd-btn" href="${esc(d.url)}">View on DANDI
              <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12h14M13 6l6 6-6 6"/></svg></a>
            <span class="bd-card__date" title="${d.published ? "Published" : "Last updated"} on DANDI">${fmtDate(d.published || d.updated)}</span>
          </div>
        </div>
      </article>`;
  }

  function render(root, data) {
    const all = data.dandisets;
    // Read filters from the URL, so a filtered view can be shared.
    const params = new URLSearchParams(location.search);
    const state = { q: "", species: "", type: "", sort: "newest" };
    Object.keys(state).forEach((key) => (state[key] = params.get(key) || state[key]));
    if (!Object.hasOwn(SORTS, state.sort)) state.sort = "newest";

    const select = (key, label, opts) => `
        <label><span class="md-visually-hidden">${label}</span>
          <select data-key="${key}">${opts
            .map(([value, text]) => `<option value="${esc(value)}"${value && value === state[key] ? " selected" : ""}>${esc(text)}</option>`)
            .join("")}</select></label>`;

    root.innerHTML = `
      <section class="bd-stats" aria-label="Totals">${statTiles(all)}</section>
      <div class="bd-controls" role="search">
        <label class="bd-search">
          <span class="md-visually-hidden">Search dandisets</span>
          <input type="search" placeholder="Search titles, people, keywords, IDs…" value="${esc(state.q)}" data-key="q">
        </label>
        ${select("species", "Species", countedOptions(all.flatMap(speciesOf), "All species"))}
        ${select("type", "Data type", countedOptions(all.flatMap((d) => d.approaches), "All data types"))}
        ${select("sort", "Sort by", Object.entries(SORTS).map(([key, s]) => [key, `Sort: ${s.label}`]))}
      </div>
      <div class="bd-summary" aria-live="polite"></div>
      <div class="bd-grid"></div>
      <p class="bd-footnote">Details from the <a href="https://dandiarchive.org/">DANDI Archive</a>, last updated ${esc(
        data.generated.replace("T", " at ").replace("Z", " UTC")
      )}.</p>`;

    const grid = root.querySelector(".bd-grid");
    const summary = root.querySelector(".bd-summary");

    function update() {
      const words = state.q.toLowerCase().split(/\s+/).filter(Boolean);
      const shown = all
        .filter(
          (d) =>
            (!state.species || speciesOf(d).includes(state.species)) &&
            (!state.type || d.approaches.includes(state.type)) &&
            words.every((word) => d.search.includes(word))
        )
        .sort(SORTS[state.sort].fn);

      summary.innerHTML =
        `Showing <strong>${shown.length}</strong> of ${all.length} dandisets` +
        (state.q || state.species || state.type ? ` <button type="button" class="bd-clear">Clear filters</button>` : "");
      grid.innerHTML = shown.length ? shown.map(card).join("") : `<p class="bd-empty">No dandisets match these filters.</p>`;

      const next = new URLSearchParams(Object.entries(state).filter(([key, v]) => v && !(key === "sort" && v === "newest")));
      const qs = next.toString();
      history.replaceState(history.state, "", `${location.pathname}${qs ? `?${qs}` : ""}${location.hash}`);
    }

    // Update when the search box or a menu changes.
    root.addEventListener("input", (e) => {
      const key = e.target.dataset.key;
      if (!key) return;
      state[key] = e.target.value;
      update();
    });
    root.addEventListener("click", (e) => {
      if (!e.target.closest(".bd-clear")) return;
      root.querySelectorAll("[data-key]:not([data-key=sort])").forEach((el) => {
        el.value = "";
        state[el.dataset.key] = "";
      });
      update();
    });
    update();
  }

  async function init() {
    const root = document.getElementById("bican-dashboard");
    if (!root) return;
    try {
      const res = await fetch("data/dandisets.json");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      render(root, await res.json());
    } catch (err) {
      root.innerHTML = `<p class="bd-empty">Couldn't load the dandiset list (${esc(err.message)}).
        If you're previewing locally, run <code>python scripts/fetch_dandisets.py</code> first.</p>`;
    }
  }

  // Start when the page loads.
  if (window.document$) document$.subscribe(init);
  else init();
})();
