import test from "node:test";
import assert from "node:assert/strict";
import {
  visibleGroups, entryOwned, summarize, versionMarks, rowMatches, rowAvailability, elsewhereLabels,
} from "../logic.js";

const v = (code, mark) => ({code, label: code, mark});
const frlg = {id: "FRLG", label: "FireRed / LeafGreen", versions: [v("FR", "F"), v("LG", "L")]};
const swsh = {id: "SwSh", label: "Sword / Shield", versions: [v("SW", "Sw"), v("SH", "Sh")]};
const sv = {id: "SV", label: "Scarlet / Violet", versions: [v("SL", "S"), v("VL", "V")]};
const groups = [frlg, swsh, sv];
const e = (versions, extra = {}) => ({method: "Wild", place: "x", versions, ended: false, ...extra});
const pikachu = {id: "0025-0-m", dex: 25, name: "Pikachu", form: "", cells: {FRLG: [e(["FR", "LG"])]}, other: []};
const galarMeowth = {id: "0052-2", dex: 52, name: "Meowth", form: "Galarian", cells: {SwSh: [e(["SW", "SH"])]}, other: []};
const meowth = {id: "0052-0", dex: 52, name: "Meowth", form: "", cells: {}, other: []};
const gimmighoul = {id: "0999-1", dex: 999, name: "Gimmighoul", form: "Roaming", cells: {}, other: [e([], {method: "GO"})]};
const eventOnly = {id: "0001-0", dex: 1, name: "Bulbasaur", form: "", cells: {SwSh: [e(["SW"], {ended: true})]}, other: []};
const none = new Set();
const sw = new Set(["SW"]);

test("no owned versions shows every group", () => assert.equal(visibleGroups(groups, none).length, 3));
test("owning Sword shows only its group", () => assert.deepEqual(visibleGroups(groups, sw).map(g => g.id), ["SwSh"]));
test("entry for the other version is not owned", () => assert.equal(entryOwned({versions: ["SH"]}, sw), false));
test("entry with no versions or empty owned is owned", () => {
  assert.equal(entryOwned({versions: []}, sw), true);
  assert.equal(entryOwned({versions: ["SH"]}, none), true);
});
test("summarize keeps order and counts the rest", () => {
  const [a, b, c, d, f] = "abcde".split("").map(p => ({place: p}));
  const input = [a, b, c, d, f];
  assert.deepEqual(summarize(input, 3), {shown: [a, b, c], more: 2});
  assert.equal(input.length, 5);
  assert.deepEqual(summarize([a, b], 3), {shown: [a, b], more: 0});
});
test("no mark when entry covers all versions", () => assert.deepEqual(versionMarks({versions: ["SW", "SH"]}, swsh), []));
test("mark for a single version", () => assert.deepEqual(versionMarks({versions: ["SW"]}, swsh), ["Sw"]));
test("search by number ignores leading zeros", () => {
  assert.ok(rowMatches(pikachu, "025"));
  assert.ok(rowMatches(pikachu, "25"));
  assert.ok(!rowMatches(pikachu, "5"));
});
test("search by form name and multiple words", () => {
  assert.ok(rowMatches(galarMeowth, "galar"));
  assert.ok(rowMatches(galarMeowth, "galar meowth"));
  assert.ok(!rowMatches(meowth, "galar meowth"));
});
test("empty query matches everything", () => {
  assert.ok(rowMatches(pikachu, ""));
  assert.ok(rowMatches(meowth, "   "));
});
test("row only in GO is 'elsewhere' with a GO label", () => {
  assert.equal(rowAvailability(gimmighoul, groups, sw), "elsewhere");
  assert.deepEqual(elsewhereLabels(gimmighoul, groups, sw), ["Pokémon GO"]);
});
test("ended-only entry does not count as available", () => {
  assert.equal(rowAvailability(eventOnly, groups, sw), "none");
  assert.deepEqual(elsewhereLabels(eventOnly, groups, sw), []);
});
test("entry needing another game counts like ended for availability", () => {
  const mew = {id: "0151-0", dex: 151, name: "Mew", form: "",
    cells: {SwSh: [e(["SW", "SH"], {method: "Static", needs_other_game: true})]}, other: []};
  assert.equal(rowAvailability(mew, groups, sw), "none");
  assert.equal(rowAvailability(mew, groups, none), "none");
  assert.deepEqual(elsewhereLabels(mew, groups, sw), []);
});
test("a version exclusive names its version, not the pair", () => {
  const blaze = {id: "0128-2", dex: 128, name: "Tauros", form: "Paldea Blaze", cells: {SV: [e(["SL"])]}, other: []};
  assert.equal(rowAvailability(blaze, groups, new Set(["VL"])), "elsewhere");
  assert.deepEqual(elsewhereLabels(blaze, groups, new Set(["VL"])), ["SL"]);
});
test("availability owned vs elsewhere, empty owned counts all", () => {
  assert.equal(rowAvailability(galarMeowth, groups, sw), "owned");
  assert.equal(rowAvailability(pikachu, groups, sw), "elsewhere");
  assert.deepEqual(elsewhereLabels(pikachu, groups, sw), ["FireRed / LeafGreen"]);
  assert.equal(rowAvailability(pikachu, groups, none), "owned");
  assert.equal(rowAvailability(gimmighoul, groups, none), "elsewhere");
});

test("visibleRange picks the rows overlapping a band and the space around them", async () => {
  const {visibleRange} = await import("../logic.js");
  const h = [10, 10, 10, 10];
  assert.deepEqual(visibleRange(h, 15, 25), {start: 1, end: 3, before: 10, after: 10});
  assert.deepEqual(visibleRange(h, -100, 5), {start: 0, end: 1, before: 0, after: 30});
  assert.deepEqual(visibleRange(h, 10, 20), {start: 1, end: 2, before: 10, after: 20});
  assert.deepEqual(visibleRange(h, 500, 900), {start: 4, end: 4, before: 40, after: 0});
  assert.deepEqual(visibleRange([], 0, 100), {start: 0, end: 0, before: 0, after: 0});
});
