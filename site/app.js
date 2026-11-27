import {
  visibleGroups, entryOwned, summarize, versionMarks, rowAvailability, elsewhereLabels, rowMatches,
  STATE_KEY, emptyState, parseState, serializeState, orphanTicks, tickedCount, setTick, setOwned, latestState,
  visibleRange, placeLink, expireEntries,
} from "./logic.js";

const $ = id => document.getElementById(id);
const UNVERIFIED_TITLE = "Not yet checked by hand against a game guide; treat as a guess.";

function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") node.className = v;
    else if (k === "text") node.textContent = v;
    else node.setAttribute(k, v);
  }
  node.append(...children);
  return node;
}

// --- state and storage ---------------------------------------------------

let state = emptyState();
let storageOk = true;
let storedUnreadable = "";

function loadState() {
  let text = null;
  try {
    text = window.localStorage.getItem(STATE_KEY);
  } catch {
    storageOk = false;
    return;
  }
  if (text === null) return;
  const parsed = parseState(text);
  if (parsed.ok) { state = parsed.state; storedUnreadable = ""; }
  // Leave the unreadable copy in storage; it is only replaced when the owner changes something.
  else storedUnreadable = parsed.error;
}

// Apply one change to the latest stored state, so a change made in another tab is not overwritten.
function commit(change) {
  let text = null;
  try { text = window.localStorage.getItem(STATE_KEY); } catch { storageOk = false; }
  const latest = latestState(text, state);
  state = change(latest.state);
  if (latest.error && !storedUnreadable) {
    // newly unreadable copy: say so and keep it; the next change replaces it, as at load
    storedUnreadable = latest.error;
    return;
  }
  saveState();
}

function saveState() {
  storedUnreadable = "";
  try {
    window.localStorage.setItem(STATE_KEY, serializeState(state));
    storageOk = true;
  } catch {
    storageOk = false;
  }
}

// --- page -----------------------------------------------------------------

let data;
let owned = new Set();
let hideTicked = false;
let query = "";
// Only the rows near the viewport are in the DOM; spacer rows stand in for the rest.
// view: {groups, sharedDex, thead, tbody, top, bottom, rows (filtered), trs: Map id→tr, heights: Map id→px}
let view = null;
let importError = "";
const OVERSCAN = 800;     // px rendered above and below the viewport
let measuredSum = 0, measuredCount = 0;

function showMessages() {
  const box = $("messages");
  const lines = [];
  if (!storageOk) lines.push("Ticks cannot be saved in this browser. Use Export to keep them.");
  if (storedUnreadable) lines.push(
    `Your saved ticks could not be read (${storedUnreadable}) Starting empty; the saved copy is left as it is until you change something.`);
  if (importError) lines.push(`Import refused: ${importError} Nothing was changed.`);
  if (data) {
    const n = orphanTicks(state, data.rows).length;
    if (n) lines.push(`${n} ticks refer to rows that are no longer listed. They are kept in your saved state.`);
  }
  box.replaceChildren(...lines.map(t => el("p", {text: t})));
}

function showCount() {
  $("count").textContent = `${tickedCount(state, data.rows)} / ${data.rows.length}`;
}

function entryNode(entry, group) {
  const node = el("div", {class: "entry"});
  if (entry.ended) node.classList.add("ended");
  if (entry.needs_other_game) node.classList.add("needs");
  if (!entryOwned(entry, owned)) node.classList.add("dim");
  const url = placeLink(entry, group);
  node.append(url
    ? el("span", {class: "what"}, `${entry.method}: `,
        el("a", {href: url, target: "_blank", rel: "noopener", title: "Open on Serebii PokéEarth", text: entry.place}))
    : el("span", {class: "what", text: entry.place ? `${entry.method}: ${entry.place}` : entry.method}));
  if (entry.dlc) node.append(" ", el("span", {class: "dlc", text: `(${entry.dlc})`}));
  const marks = group ? versionMarks(entry, group) : [];
  if (marks.length) node.append(" ", el("span", {class: "marks", text: `[${marks.join(", ")}]`}));
  if (entry.ended) node.append(" ", el("span", {class: "tag ended", text: "ended"}));
  if (entry.needs_other_game) node.append(" ", el("span", {class: "tag needs", text: "needs another game or player"}));
  if (entry.unverified) node.append(" ", el("span", {class: "tag unv", title: UNVERIFIED_TITLE, text: "unverified"}));
  if (entry.note) node.append(" ", el("span", {class: "note", text: entry.note}));
  return node;
}

function entriesCell(entries, group) {
  const td = el("td", {class: "game"});
  if (!entries || entries.length === 0) {
    td.append(el("span", {class: "empty", text: "–"}));
    return td;
  }
  const {shown, more} = summarize(entries, 3);
  const list = el("div", {}, ...shown.map(e => entryNode(e, group)));
  td.append(list);
  if (more > 0) {
    td.classList.add("expandable");
    const btn = el("button", {type: "button", class: "more", "aria-expanded": "false", text: `+${more}`});
    td.append(btn);
    td.addEventListener("click", ev => {
      if (ev.target.closest("a, input")) return;
      const open = btn.getAttribute("aria-expanded") !== "true";
      list.replaceChildren(...(open ? entries : shown).map(e => entryNode(e, group)));
      btn.setAttribute("aria-expanded", String(open));
      btn.textContent = open ? "Show fewer" : `+${more}`;
      schedule();
    });
  }
  return td;
}

function flagCell(text, unverified) {
  const td = el("td", {class: text === "–" ? "fl flag" : "fl"}, text);
  if (unverified) td.append(" ", el("span", {class: "tag unv", title: UNVERIFIED_TITLE, text: "unverified"}));
  return td;
}

function rowNode(row, groups, sharedDex, ticked) {
  const label = row.form || (sharedDex.has(row.dex) ? "Base form" : "");
  const box = el("input", {type: "checkbox", "aria-label": `${row.name}${label ? ` (${label})` : ""} caught`});
  box.checked = ticked.has(row.id);
  box.dataset.id = row.id;

  const name = el("th", {scope: "row", class: "p2"});
  // decorative: the name sits next to it; fixed size keeps row heights steady while images load
  if (row.sprite) name.append(el("img", {class: "sprite", src: data.meta.sprite_base + row.sprite, alt: "",
                                         width: 40, height: 40, loading: "lazy", decoding: "async"}));
  name.append(row.name);
  // narrow screens unpin the Form column, so the form also shows under the name
  if (label) name.append(el("span", {class: "formline", text: label}));
  const avail = rowAvailability(row, data.groups, owned);
  if (avail === "none") name.append(el("span", {class: "avail", text: "Not currently obtainable"}));
  else if (avail === "elsewhere" && owned.size > 0)
    name.append(el("span", {class: "avail",
      text: `Not in your games — available in: ${elsewhereLabels(row, data.groups, owned).join(", ")}`}));

  const tr = el("tr", {},
    el("td", {class: "p0"}, box),
    el("td", {class: "p1", text: String(row.dex).padStart(4, "0")}),
    name,
    el("td", {class: "p3", text: label}),
    flagCell(row.mega.length ? row.mega.join(", ") : "–", false),
    flagCell(row.gmax ? "Yes" : "–", row.gmax && row.gmax_unverified),
    ...groups.map(g => entriesCell(row.cells[g.id], g)),
    entriesCell(row.other, null),
  );
  if (box.checked) tr.classList.add("ticked");
  return tr;
}

function headerRow(groups) {
  const th = (text, cls, ...extra) => el("th", {scope: "col", class: cls, text}, ...extra);
  return el("tr", {},
    el("th", {scope: "col", class: "p0", "aria-label": "Caught"}, "✓"),
    th("#", "p1"), th("Name", "p2"), th("Form", "p3"), th("Mega", "fl"), th("Gmax", "fl"),
    ...groups.map(g => {
      const route = el("span", {class: "route", text: g.home_route});
      if (g.home_route_unverified) route.append(" ", el("span", {class: "tag unv", title: UNVERIFIED_TITLE, text: "unverified"}));
      return th(g.label, "game", route);
    }),
    th("Other", "game"),
  );
}

// Full rebuild: on load and when the owned versions change (columns and dimming both depend on them).
function render() {
  const groups = visibleGroups(data.groups, owned);
  const counts = new Map();
  for (const r of data.rows) counts.set(r.dex, (counts.get(r.dex) ?? 0) + 1);
  const sharedDex = new Set([...counts].filter(([, n]) => n > 1).map(([d]) => d));
  const tbody = el("tbody");
  tbody.addEventListener("change", ev => {
    const id = ev.target.dataset?.id;
    if (!id) return;
    commit(s => setTick(s, id, ev.target.checked));
    ev.target.closest("tr").classList.toggle("ticked", ev.target.checked);
    if (hideTicked && ev.target.checked) {
      view.rows = view.rows.filter(r => r.id !== id);
      view.trs.delete(id);
      ev.target.closest("tr").remove();
      update();
    }
    showCount();
    showMessages();
  });
  const spacer = () => el("tr", {class: "spacer", "aria-hidden": "true"}, el("td", {colspan: String(groups.length + 7)}));
  const thead = el("thead", {}, headerRow(groups));
  view = {groups, sharedDex, thead, tbody, top: spacer(), bottom: spacer(), rows: [], trs: new Map(), heights: new Map()};
  measuredSum = measuredCount = 0;
  $("main").replaceChildren(el("table", {}, thead, tbody));
  applyFilter();
  showCount();
  showMessages();
}

function applyFilter() {
  const ticked = new Set(state.ticks);
  view.rows = data.rows.filter(row => !(hideTicked && ticked.has(row.id)) && rowMatches(row, query));
  view.trs = new Map();
  view.tbody.replaceChildren(view.top, view.bottom);
  $("main").scrollTop = 0;
  update();
}

let pending = false;
function schedule() {
  if (pending) return;
  pending = true;
  requestAnimationFrame(() => { pending = false; update(); });
}

// Put the rows overlapping the viewport (plus OVERSCAN) in the DOM, size the spacers for the rest,
// then measure what was rendered. Unmeasured rows use the average measured height.
function update() {
  if (!view) return;
  const main = $("main");
  const est = measuredCount ? measuredSum / measuredCount : 60;
  const heights = view.rows.map(r => view.heights.get(r.id) ?? est);
  const top = main.scrollTop - view.thead.offsetHeight;
  const {start, end, before, after} = visibleRange(heights, top - OVERSCAN, top + main.clientHeight + OVERSCAN);
  const firstSeen = visibleRange(heights, top, top + 1).start;

  const ticked = new Set(state.ticks);
  const trs = new Map();
  for (let i = start; i < end; i++) {
    const row = view.rows[i];
    trs.set(row.id, view.trs.get(row.id) ?? rowNode(row, view.groups, view.sharedDex, ticked));
  }
  for (const [id, tr] of view.trs) if (!trs.has(id)) tr.remove();
  // rows kept from the last update are already in order; only new ones move (keeps focus on kept rows)
  let prev = view.top;
  for (const tr of trs.values()) {
    if (prev.nextSibling !== tr) prev.after(tr);
    prev = tr;
  }
  view.trs = trs;
  view.top.firstChild.style.height = `${before}px`;
  view.bottom.firstChild.style.height = `${after}px`;

  // measure; rows above the first visible one that changed size would move the content, so scroll by the same amount
  let shift = 0, changed = false, i = start;
  for (const [id, tr] of trs) {
    const h = tr.getBoundingClientRect().height;
    const old = view.heights.get(id);
    if (old === undefined) { measuredSum += h; measuredCount++; }
    if (h !== old) view.heights.set(id, h);
    if (h !== heights[i]) {
      changed = true;
      if (i < firstSeen) shift += h - heights[i];
    }
    i++;
  }
  if (shift) main.scrollTop += shift;
  // estimates were off, so the rendered rows may not fill the band: go again (stops once every row is measured)
  if (changed) schedule();
}

function buildOwnButtons() {
  const wrap = $("own-groups");
  wrap.replaceChildren(...data.groups.map(g => el("div", {class: "own-group"},
    el("span", {text: g.id}),
    ...g.versions.map(v => {
      const b = el("button", {type: "button", "aria-pressed": String(owned.has(v.code)), text: v.label});
      b.addEventListener("click", () => {
        const on = !owned.has(v.code);
        commit(s => setOwned(s, v.code, on));
        owned = new Set(state.owned);
        buildOwnButtons();
        render();
      });
      return b;
    }))));
  showOwnSummary();
}

function showOwnSummary() {
  const names = data.groups.flatMap(g => g.versions).filter(v => owned.has(v.code)).map(v => v.label);
  $("own-summary").textContent = names.length ? names.join(", ") : "nothing chosen, all games shown";
}

function wireBar() {
  let timer;
  $("search").addEventListener("input", ev => {
    clearTimeout(timer);
    timer = setTimeout(() => { query = ev.target.value; applyFilter(); }, 150);
  });
  $("hide-ticked").addEventListener("click", ev => {
    hideTicked = !hideTicked;
    ev.currentTarget.setAttribute("aria-pressed", String(hideTicked));
    applyFilter();
  });
  $("export").addEventListener("click", () => {
    const url = URL.createObjectURL(new Blob([serializeState(state)], {type: "application/json"}));
    const a = el("a", {href: url, download: "living-form-dex-state.json"});
    document.body.append(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  });
  $("import").addEventListener("click", () => $("import-file").click());
  $("import-file").addEventListener("change", async ev => {
    const file = ev.target.files[0];
    ev.target.value = "";
    if (!file) return;
    let parsed;
    try { parsed = parseState(await file.text()); } catch { parsed = {ok: false, error: "That file could not be read."}; }
    importError = parsed.ok ? "" : parsed.error;
    if (parsed.ok && window.confirm(
      `Replace your ${state.ticks.length} ticks with the ${parsed.state.ticks.length} ticks in this file? ` +
      "Your owned games will be replaced too.")) {
      state = parsed.state;
      owned = new Set(state.owned);
      saveState();
      buildOwnButtons();
      render();
    }
    showMessages();
  });
}

async function start() {
  loadState();
  owned = new Set(state.owned);
  showMessages();
  try {
    const meta = name => document.querySelector(`meta[name="${name}"]`)?.content || "dev";
    $("version").textContent = `v${meta("version")}`;
    // a new key per data build, so browsers never keep an old dex.json.gz
    const res = await fetch(`data/dex.json.gz?v=${encodeURIComponent(meta("data-key"))}`);
    if (!res.ok) throw new Error(`HTTP ${res.status} ${res.statusText} for data/dex.json.gz`);
    data = await new Response(res.body.pipeThrough(new DecompressionStream("gzip"))).json();
    if (!data || !Array.isArray(data.rows) || !Array.isArray(data.groups)) throw new Error("The data file has no rows.");
    expireEntries(data.rows);
  } catch (err) {
    data = undefined;
    $("main").replaceChildren(el("div", {class: "load-error"},
      el("p", {text: "Could not load the dex data. Run the build, then reload."}),
      el("code", {text: String(err && err.message || err)})));
    return;
  }
  buildOwnButtons();
  wireBar();
  render();
  $("main").addEventListener("scroll", schedule, {passive: true});
  // a new width rewraps the text, so measured heights are stale; height-only resizes (mobile address bar) are not
  let width = window.innerWidth;
  window.addEventListener("resize", () => {
    if (window.innerWidth !== width && view) { width = window.innerWidth; view.heights.clear(); measuredSum = measuredCount = 0; }
    schedule();
  });
  // another tab saved: show its ticks and owned games here too
  window.addEventListener("storage", ev => {
    if (ev.key !== STATE_KEY || ev.newValue === null) return;
    loadState();
    owned = new Set(state.owned);
    buildOwnButtons();
    render();
  });
}

start();
