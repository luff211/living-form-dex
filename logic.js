// Pure page logic: no DOM access, no Node-only imports.

export const visibleGroups = (groups, owned) =>
  owned.size === 0 ? groups : groups.filter(g => g.versions.some(v => owned.has(v.code)));

export const entryOwned = (entry, owned) =>
  owned.size === 0 || entry.versions.length === 0 || entry.versions.some(c => owned.has(c));

export const summarize = (entries, max = 3) => ({
  shown: entries.slice(0, max),
  more: Math.max(0, entries.length - max),
});

export function versionMarks(entry, group) {
  const covered = group.versions.filter(v => entry.versions.includes(v.code));
  return covered.length === group.versions.length ? [] : covered.map(v => v.mark);
}

// lower case without accents, so "poke" finds "Poké"
const fold = s => s.normalize("NFD").replace(/\p{M}/gu, "").toLowerCase();

export function rowMatches(row, query) {
  const q = fold(String(query ?? "").trim());
  if (!q) return true;
  if (/^\d+$/.test(q)) return row.dex === Number(q);
  const hay = fold(`${row.name} ${row.form}`);
  return q.split(/\s+/).every(w => hay.includes(w));
}

// Usable by a player starting that game alone: not ended and not needing another game's save data.
export const isLive = e => !e.ended && !e.needs_other_game;
const live = list => (list ?? []).filter(isLive);

export function rowAvailability(row, groups, owned) {
  let elsewhere = live(row.other).length > 0;
  for (const g of groups) {
    const entries = live(row.cells[g.id]);
    if (entries.some(e => entryOwned(e, owned))) return "owned";
    if (entries.length) elsewhere = true;
  }
  return elsewhere ? "elsewhere" : "none";
}

export function elsewhereLabels(row, groups, owned) {
  // a group counts by name only when every version has it; otherwise name the versions that do
  const labels = groups.flatMap(g => {
    const has = g.versions.filter(v => live(row.cells[g.id]).some(e => e.versions.includes(v.code)));
    return has.length === g.versions.length ? [g.label] : has.map(v => v.label);
  });
  const other = live(row.other);
  if (other.some(e => e.method === "GO")) labels.push("Pokémon GO");
  if (other.some(e => e.method === "HOME gift")) labels.push("HOME gift");
  return labels;
}

export const STATE_KEY = "lfd-state-v1";

export const emptyState = () => ({version: 1, ticks: [], owned: []});

const isStrings = a => Array.isArray(a) && a.every(x => typeof x === "string");

export function parseState(text) {
  let data;
  try { data = JSON.parse(text); } catch { return {ok: false, error: "That is not a valid saved-state file."}; }
  if (!data || typeof data !== "object" || Array.isArray(data) || data.version !== 1)
    return {ok: false, error: "That file is not a saved state from this page (version 1)."};
  if (!isStrings(data.ticks) || !isStrings(data.owned))
    return {ok: false, error: "The ticks and owned games in that file must be lists of text."};
  return {ok: true, state: {version: 1, ticks: [...data.ticks], owned: [...data.owned]}};
}

const sortedUnique = a => [...new Set(a)].sort();

export const serializeState = state => JSON.stringify({
  version: 1, ticks: sortedUnique(state.ticks), owned: sortedUnique(state.owned),
});

export const toggleTick = (state, rowId) => ({
  ...state,
  ticks: state.ticks.includes(rowId) ? state.ticks.filter(t => t !== rowId) : [...state.ticks, rowId],
});

const setIn = (list, x, on) => [...list.filter(y => y !== x), ...(on ? [x] : [])];

export const setTick = (state, rowId, on) => ({...state, ticks: setIn(state.ticks, rowId, on)});

export const setOwned = (state, code, on) => ({...state, owned: setIn(state.owned, code, on)});

// The state to change before a save: what is stored now (another tab may have written it), else this tab's own.
export function latestState(storedText, current) {
  if (storedText === null || storedText === undefined) return {state: current, error: ""};
  const parsed = parseState(storedText);
  return parsed.ok ? {state: parsed.state, error: ""} : {state: current, error: parsed.error};
}

const ids = rows => new Set(rows.map(r => r.id));

export const orphanTicks = (state, rows) => {
  const known = ids(rows);
  return state.ticks.filter(t => !known.has(t));
};

export const tickedCount = (state, rows) => {
  const ticked = new Set(state.ticks);
  return rows.filter(r => ticked.has(r.id)).length;
};

// Rows [start, end) that overlap the band [from, to) (px from the top of the first row), with the height above and below them.
export function visibleRange(heights, from, to) {
  let y = 0, i = 0;
  while (i < heights.length && y + heights[i] <= from) y += heights[i++];
  const start = i, before = y;
  while (i < heights.length && y < to) y += heights[i++];
  let after = 0;
  for (let j = i; j < heights.length; j++) after += heights[j];
  return {start, end: i, before, after};
}

// Serebii PokéEarth page for an entry's place; Evolve and Breed places are Pokémon, not locations.
export function placeLink(entry, group) {
  if (!group?.links || entry.method === "Evolve" || entry.method === "Breed") return null;
  return Object.hasOwn(group.links, entry.place) ? group.links[entry.place] : null;
}
