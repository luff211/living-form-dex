import {
  visibleGroups, entryOwned, summarize, versionMarks, rowAvailability, elsewhereLabels, rowMatches,
  STATE_KEY, emptyState, parseState, serializeState, orphanTicks, tickedCount, setTick, setOwned, latestState,
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
let view = null;          // {groups, sharedDex, tbody, end, rows (filtered), shown}
let observer = null;
let importError = "";
const CHUNK = 50;

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
  node.append(el("span", {class: "what", text: entry.place ? `${entry.method}: ${entry.place}` : entry.method}));
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
    });
  }
  return td;
}

function flagCell(text, unverified) {
  const td = el("td", {class: text === "–" ? "flag" : ""}, text);
  if (unverified) td.append(" ", el("span", {class: "tag unv", title: UNVERIFIED_TITLE, text: "unverified"}));
  return td;
}

function rowNode(row, groups, sharedDex, ticked) {
  const label = row.form || (sharedDex.has(row.dex) ? "Base form" : "");
  const box = el("input", {type: "checkbox", "aria-label": `${row.name}${label ? ` (${label})` : ""} caught`});
  box.checked = ticked.has(row.id);
  box.dataset.id = row.id;

  const name = el("th", {scope: "row", class: "p2"}, row.name);
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
    th("#", "p1"), th("Name", "p2"), th("Form", "p3"), th("Mega", ""), th("Gmax", ""),
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
    const tr = ev.target.closest("tr");
    tr.classList.toggle("ticked", ev.target.checked);
    if (hideTicked && ev.target.checked) tr.hidden = true;
    showCount();
    showMessages();
  });
  const end = el("div", {class: "rows-end"});
  $("main").replaceChildren(el("table", {}, el("thead", {}, headerRow(groups)), tbody), end);
  view = {groups, sharedDex, tbody, end, rows: [], shown: 0};
  observer?.disconnect();
  observer = new IntersectionObserver(es => { if (es.some(e => e.isIntersecting)) renderMore(); },
    {root: $("main"), rootMargin: "0px 0px 1500px 0px"});
  applyFilter();
  showCount();
  showMessages();
}

function applyFilter() {
  const ticked = new Set(state.ticks);
  view.rows = data.rows.filter(row => !(hideTicked && ticked.has(row.id)) && rowMatches(row, query));
  view.shown = 0;
  view.tbody.replaceChildren();
  $("main").scrollTop = 0;
  renderMore();
}

// Rows are built as the reader scrolls near the end: building all of them at once (115k nodes) made the page lag.
function renderMore() {
  const ticked = new Set(state.ticks);
  const next = view.rows.slice(view.shown, view.shown + CHUNK);
  view.tbody.append(...next.map(row => rowNode(row, view.groups, view.sharedDex, ticked)));
  view.shown += next.length;
  // observing again fires the callback again if the end marker is still in range after this chunk
  observer.unobserve(view.end);
  if (view.shown < view.rows.length) observer.observe(view.end);
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
    const res = await fetch("data/dex.json.gz");
    if (!res.ok) throw new Error(`HTTP ${res.status} ${res.statusText} for data/dex.json.gz`);
    data = await new Response(res.body.pipeThrough(new DecompressionStream("gzip"))).json();
    if (!data || !Array.isArray(data.rows) || !Array.isArray(data.groups)) throw new Error("The data file has no rows.");
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
