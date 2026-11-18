import test from "node:test";
import assert from "node:assert/strict";
import {
  STATE_KEY, emptyState, parseState, serializeState, toggleTick, orphanTicks, tickedCount,
  setTick, setOwned, latestState,
} from "../logic.js";

const rows = [{id: "0025-0-m"}, {id: "0052-2"}];

test("key and empty state", () => {
  assert.equal(STATE_KEY, "lfd-state-v1");
  assert.deepEqual(emptyState(), {version: 1, ticks: [], owned: []});
});
test("round trip", () => {
  const s = {version: 1, ticks: ["0025-0-m", "0052-2"], owned: ["SW"]};
  assert.deepEqual(parseState(serializeState(s)).state, s);
});
test("serialize sorts and de-duplicates", () => {
  const s = {version: 1, ticks: ["b", "a", "b"], owned: ["SW", "FR", "SW"]};
  assert.deepEqual(JSON.parse(serializeState(s)), {version: 1, ticks: ["a", "b"], owned: ["FR", "SW"]});
  assert.deepEqual(s.ticks, ["b", "a", "b"]);
});
test("orphan ticks are kept and reported", () => {
  const s = {version: 1, ticks: ["0025-0-m", "9999-9"], owned: []};
  assert.deepEqual(orphanTicks(s, rows), ["9999-9"]);
  assert.ok(parseState(serializeState(s)).state.ticks.includes("9999-9"));
  assert.equal(tickedCount(s, rows), 1);
});
test("garbage is rejected, not thrown", () => {
  for (const bad of ["", "not json", "[]", "null", '{"version":2,"ticks":[],"owned":[]}',
    '{"version":1,"ticks":"x","owned":[]}', '{"version":1,"ticks":[1],"owned":[]}',
    '{"version":1,"ticks":[],"owned":[2]}', undefined, null, 5, {}, []]) {
    const r = parseState(bad);
    assert.equal(r.ok, false);
    assert.equal(typeof r.error, "string");
  }
});
test("toggle adds then removes without mutating", () => {
  const s = {version: 1, ticks: ["a"], owned: ["SW"]};
  const added = toggleTick(s, "b");
  assert.deepEqual(added.ticks.sort(), ["a", "b"]);
  const removed = toggleTick(added, "b");
  assert.deepEqual(removed.ticks, ["a"]);
  assert.deepEqual(s, {version: 1, ticks: ["a"], owned: ["SW"]});
  assert.deepEqual(added.ticks.sort(), ["a", "b"]);
  assert.deepEqual(removed.owned, ["SW"]);
});
test("a tick made in another tab survives this tab's change", () => {
  const mine = {version: 1, ticks: ["a"], owned: []};
  const stored = serializeState({version: 1, ticks: ["a", "b"], owned: ["SW"]});   // other tab added b and Sword
  const {state, error} = latestState(stored, mine);
  assert.equal(error, "");
  const next = setTick(state, "c", true);
  assert.deepEqual([...next.ticks].sort(), ["a", "b", "c"]);
  assert.deepEqual(next.owned, ["SW"]);
  assert.deepEqual(setTick(next, "b", false).ticks.sort(), ["a", "c"]);
  assert.deepEqual(setTick(next, "a", true).ticks.sort(), ["a", "b", "c"]);   // idempotent
  assert.deepEqual(mine.ticks, ["a"]);
});
test("owned change merges with stored state", () => {
  const s = {version: 1, ticks: ["x"], owned: ["SW"]};
  assert.deepEqual(setOwned(s, "VL", true).owned.sort(), ["SW", "VL"]);
  assert.deepEqual(setOwned(s, "SW", false).owned, []);
  assert.deepEqual(setOwned(s, "SW", false).ticks, ["x"]);
});
test("unreadable or missing stored state falls back to this tab's state", () => {
  const mine = {version: 1, ticks: ["a"], owned: []};
  assert.deepEqual(latestState(null, mine), {state: mine, error: ""});
  const bad = latestState("not json", mine);
  assert.equal(bad.state, mine);
  assert.notEqual(bad.error, "");
});
