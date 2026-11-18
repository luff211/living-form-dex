# Living Form Dex Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A page, served from this machine on port 8507, listing every HOME-storable Pokémon form with where it is obtainable in each main series game, plus a personal tick list.

**Architecture:** A .NET console program dumps PKHeX's encounter, evolution and form data untouched to `build/raw.json`. A Python (stdlib only) build step combines that with hand-kept rule files and writes `site/data/dex.json`. A static vanilla-JS page renders the table from that file; `python3 -m http.server` under a systemd user unit serves `site/`.

**Tech Stack:** .NET 10 SDK (user-local in `~/.dotnet`), `PKHeX.Core` 26.10.18 (NuGet), Python 3.12 stdlib + `unittest`, Node 18 `node --test` for page logic, vanilla HTML/CSS/JS (ES modules, no bundler), systemd user unit.

**Spec:** `docs/superpowers/specs/2026-11-14-living-form-dex-design.md` — read it first; this plan argues from it.

## Global Constraints

- Project root: `~/living-form-dex/`. Licence: GPL-3.0-or-later (`LICENSE` file, `PKHeX.Core` is GPL).
- No text copied from Bulbapedia or Serebii. Nothing fetched automatically from either. Do not work around Bulbapedia's bot check.
- No Pokémon images.
- All user-visible text in English, sentence case.
- No third-party runtime dependencies: Python stdlib only, no npm packages, no CSS/JS libraries.
- Every hand-kept fact carries `"verified": false` when drafted and `"checked": ""`; only the owner flips them. A cell that depends on an unverified fact is marked unverified in the output.
- Any script that writes `site/data/dex.json` or a rule file is report-only by default and writes only with `--write`.
- "Obtainable" means a player starting that game alone can get the form. Legal-but-unreachable origins must not appear.
- Port 8507, bound to `<tailscale-ip>` only, plain HTTP, static files only.
- Row ids are stable: `"{species:04d}-{form}"` plus `"-m"` / `"-f"` for gender rows (for example `0025-0-f`). Never renumber.
- Commit after every task. Local git only; do not create a remote or push without asking the owner.

## Review Focus

Failure modes the spec implies that are most likely to bite the owner. Each has a test in the task named.

1. A rebuilt data file drops or renames a row the owner had ticked → the tick must be kept in saved state and reported, never silently deleted (Task 10).
2. Importing a wrong or damaged state file → rejected with a message, existing ticks untouched (Task 10).
3. Browser storage unavailable or throwing → page still renders and says ticks will not be saved (Task 11).
4. `dex.json` missing, half-written or unreadable → page shows a plain error instead of an empty table; the build writes atomically (Tasks 8 and 11).
5. A newer PKHeX returns an encounter type the build has no label for → the build check fails naming the type, instead of mislabelling it (Task 5).

## File Structure

```
LICENSE  README.md  .gitignore
exporter/Exporter.csproj  exporter/Program.cs        # PKHeX → build/raw.json, no interpretation
rules/games.json            # game groups, versions, marks, HOME routes (read by exporter AND builder)
rules/forms.json            # row exclusions + per-form method overrides + carry-to-HOME notes
rules/sv_exclusives.json    # Scarlet-only / Violet-only
rules/releases.json         # re-release differences and ended-ticket encounters
rules/dlc.json              # location name → DLC name
rules/gender_diff.json      # species with a visible gender difference
rules/gmax.json             # species that can Gigantamax
builder/dexbuild/model.py   # Entry, Row dataclasses
builder/dexbuild/rules.py   # load + validate rule files
builder/dexbuild/kinds.py   # PKHeX type name → method label
builder/dexbuild/rows.py    # which rows exist
builder/dexbuild/direct.py  # encounters → entries
builder/dexbuild/derive.py  # evolve and breed
builder/dexbuild/assemble.py# everything → Dex, ordering, Other column
builder/dexbuild/checks.py  # structural checks
builder/dexbuild/__main__.py# CLI
builder/tests/test_*.py     # unittest
tools/fetch_gender_diff.py  # one-off: PokéAPI CSV → rules/gender_diff.json
site/index.html  site/style.css  site/package.json   # {"type":"module"} so node can import logic.js
site/logic.js               # pure functions, no DOM
site/app.js                 # DOM, storage
site/tests/logic.test.js    # node --test
site/data/dex.json          # generated, git-ignored
deploy/living-form-dex.service
build/                      # git-ignored
```

Commands used throughout (put them in `README.md` in Task 1):

```bash
export DOTNET_ROOT=$HOME/.dotnet DOTNET_CLI_TELEMETRY_OPTOUT=1 DOTNET_NOLOGO=1
~/.dotnet/dotnet run -c Release --project exporter -- rules/games.json build/raw.json   # export
cd builder && python3 -m unittest discover -s tests -v                                  # python tests
python3 -m dexbuild --raw ../build/raw.json --rules ../rules --out ../site/data/dex.json          # check (run from builder/)
python3 -m dexbuild --raw ../build/raw.json --rules ../rules --out ../site/data/dex.json --write  # build
cd site && node --test tests/                                                           # page logic tests
```

---

### Task 1: Project skeleton, .NET, and species/forms export

**Files:**
- Create: `LICENSE` (GPL-3.0 text), `README.md`, `.gitignore` (`build/`, `site/data/dex.json`, `exporter/bin/`, `exporter/obj/`, `__pycache__/`)
- Create: `rules/games.json`, `exporter/Exporter.csproj`, `exporter/Program.cs`
- Test: `builder/tests/test_raw_species.py`

**Interfaces:**
- Produces: `rules/games.json`:

```json
{"groups": [
  {"id": "RBY", "label": "Red / Blue / Yellow", "blank": "PK1", "personal": "RB",
   "versions": [{"code": "RD", "label": "Red", "mark": "R"}, {"code": "GN", "label": "Blue", "mark": "B"}, {"code": "YW", "label": "Yellow", "mark": "Y"}],
   "home_route": {"text": "3DS Virtual Console → Poké Transporter → Pokémon Bank → HOME", "verified": false, "checked": ""}}
]}
```

  Remaining groups, in this order, same shape — `id | blank | personal | versions (code label mark)`:
  `GSC | PK2 | C | GD Gold G, SI Silver S, C Crystal C` ·
  `RSE | PK3 | E | R Ruby R, S Sapphire S, E Emerald E` ·
  `FRLG | PK3 | FR | FR FireRed FR, LG LeafGreen LG` ·
  `DPPt | PK4 | Pt | D Diamond D, P Pearl P, Pt Platinum Pt` ·
  `HGSS | PK4 | HGSS | HG HeartGold HG, SS SoulSilver SS` ·
  `BW | PK5 | BW | B Black B, W White W` ·
  `B2W2 | PK5 | B2W2 | B2 "Black 2" B2, W2 "White 2" W2` ·
  `XY | PK6 | XY | X X X, Y Y Y` ·
  `ORAS | PK6 | AO | OR "Omega Ruby" OR, AS "Alpha Sapphire" AS` ·
  `SM | PK7 | SM | SN Sun S, MN Moon M` ·
  `USUM | PK7 | USUM | US "Ultra Sun" US, UM "Ultra Moon" UM` ·
  `LGPE | PB7 | GG | GP "Let's Go Pikachu" P, GE "Let's Go Eevee" E` ·
  `SwSh | PK8 | SWSH | SW Sword Sw, SH Shield Sh` ·
  `BDSP | PB8 | BDSP | BD "Brilliant Diamond" BD, SP "Shining Pearl" SP` ·
  `PLA | PA8 | LA | PLA "Legends: Arceus" PLA` ·
  `SV | PK9 | SV | SL Scarlet S, VL Violet V` ·
  `ZA | PA9 | ZA | ZA "Legends: Z-A" ZA`.
  Then one pseudo-group `{"id": "GO", "label": "Pokémon GO", "blank": "PK8", "personal": "SWSH", "versions": [{"code": "GO", "label": "Pokémon GO", "mark": "GO"}], "other": true}`.
  `code` is a `PKHeX.Core.GameVersion` enum name; `blank` a PKM class name; `personal` a `PersonalTable` static property name. **Verify three things against PKHeX source before trusting them:** (a) `GN` is international Blue and `BU` is Japan-only Blue (comments in `GameVersion.cs`); (b) every `personal` name exists; (c) every `code` parses. Draft `home_route.text` for every group from general knowledge, all `verified: false`; FRLG's text must say the Switch → HOME link was announced for October 2026 and is unconfirmed.
- Produces: `build/raw.json` top level `{"pkhex": "26.10.18", "species": [...], "megas": {...}, "encounters": [], "evolutions": []}` where

```json
"species": [{"id": 52, "name": "Meowth", "forms": [
   {"form": 0, "name": "", "battle_only": false, "fused": false, "groups": ["RBY", "GSC"]},
   {"form": 1, "name": "Alola", "battle_only": false, "fused": false, "groups": ["SM", "USUM", "LGPE", "SwSh", "SV", "ZA"]}]}],
"megas": {"6": ["Mega X", "Mega Y"]}
```

  `groups` = groups whose personal table reports the species+form present. `megas` = form names starting with "Mega" seen in any context, keyed by species id as a string. Mega forms still appear in `forms` with `battle_only: true`.

- [ ] **Step 1: Install the .NET 10 SDK user-local.** Read `https://builds.dotnet.microsoft.com/dotnet/release-metadata/10.0/releases.json`, take the latest SDK's `dotnet-sdk-linux-x64.tar.gz` URL and SHA-512, download, verify with `sha512sum -c`, extract to `~/.dotnet`. Do not run Microsoft's install script.
  Run: `~/.dotnet/dotnet --version` — Expected: `10.0.x`

- [ ] **Step 2: `git init`, write `LICENSE`, `.gitignore`, `README.md` (the command block above), `rules/games.json`.**

- [ ] **Step 3: Write the failing test** `builder/tests/test_raw_species.py`. Tests that need `build/raw.json` call a shared helper `load_raw()` in `builder/tests/util.py` that raises `unittest.SkipTest` when the file is absent.

```python
def test_meowth_forms(self):
    m = species(raw, 52)
    self.assertEqual(m["name"], "Meowth")
    self.assertEqual({f["form"] for f in m["forms"]} >= {0, 1, 2}, True)
    self.assertNotIn("RBY", form(m, 1)["groups"])      # Alolan Meowth does not exist in Red
    self.assertIn("SwSh", form(m, 2)["groups"])        # Galarian Meowth exists in Sword/Shield
def test_megas_are_flagged_not_lost(self):
    self.assertEqual(sorted(raw["megas"]["6"]), ["Mega X", "Mega Y"])
    self.assertTrue(all(f["battle_only"] for f in species(raw, 6)["forms"] if f["name"].startswith("Mega")))
def test_every_species_present(self):
    ids = [s["id"] for s in raw["species"]]
    self.assertEqual(ids, list(range(1, len(ids) + 1)))
    self.assertGreaterEqual(len(ids), 1025)
```

- [ ] **Step 4: Run** `cd builder && python3 -m unittest discover -s tests -v` — Expected: skipped (no raw.json).

- [ ] **Step 5: Implement the exporter.** `Exporter.csproj`: `net10.0`, `OutputType Exe`, `InvariantGlobalization true`, `PackageReference PKHeX.Core 26.10.18`. `Program.cs` takes `args[0]` = games.json path, `args[1]` = output path. For names use `GameInfo.GetStrings("en").specieslist`; for form names `FormConverter.GetFormList(...)`; for presence `PersonalTable.<personal>.IsPresentInGame(species, form)`; for flags `FormInfo.IsBattleOnlyForm` / `FormInfo.IsFusedForm`. These member names are from memory of PKHeX — confirm each in the 26.10.18 source (`https://github.com/kwsch/PKHeX`) and adapt; the JSON shape above is what is fixed. Fail with a non-zero exit and a message naming the bad value if any `code`, `blank` or `personal` in games.json does not resolve.

- [ ] **Step 6: Run the exporter, then the tests** — Expected: 3 tests PASS.

- [ ] **Step 7: Commit** `chore: scaffold project, export species and forms from PKHeX`

---

### Task 2: Export encounters

**Files:**
- Modify: `exporter/Program.cs`
- Test: `builder/tests/test_raw_encounters.py`

**Interfaces:**
- Consumes: `rules/games.json` groups (Task 1).
- Produces: `raw["encounters"]`, one object per distinct encounter:

```json
{"group": "SwSh", "species": 52, "form": 1, "form_random": false,
 "type": "EncounterStatic8", "label": "Static Encounter",
 "versions": ["SW", "SH"], "location": "Fields of Honor (Isle of Armor)",
 "egg": false, "event_title": null, "gender": null}
```

  `type` = the encounter object's C# class name. `label` = its `Name`. `versions` = the group's version codes that the encounter's `Version` equals or contains; **drop the encounter when that list is empty**. `location` = `enc.GetEncounterLocation(enc.Generation, enc.Version)` or `""`. `form_random` = true when PKHeX uses a "form decided at encounter" marker (constants in `EncounterUtil.cs`; observed values 30 and 31), with `form` left as the marker. `event_title` = the gift's card title when the encounter is a `MysteryGift` and the title is non-empty. `gender` = `"m"`/`"f"` when the encounter fixes gender, else null.

- [ ] **Step 1: Write the failing tests** (helper `encs(raw, group, species, form=None)` returns matching encounters):

```python
def test_galarian_farfetchd_is_sword_only(self):
    wild = [e for e in encs(raw, "SwSh", 83, 1) if e["type"].startswith("EncounterSlot")]
    self.assertTrue(wild)
    self.assertTrue(all(e["versions"] == ["SW"] for e in wild))
def test_deoxys_forms_by_game(self):
    self.assertEqual({tuple(e["versions"]) for e in encs(raw, "FRLG", 386, 1)}, {("FR",)})
    self.assertEqual({tuple(e["versions"]) for e in encs(raw, "FRLG", 386, 2)}, {("LG",)})
    self.assertTrue(any(e["versions"] == ["E"] for e in encs(raw, "RSE", 386, 3)))
def test_no_alolan_meowth_before_it_existed(self):
    self.assertEqual(encs(raw, "RBY", 52, 1), [])
def test_no_cross_group_leak(self):
    self.assertTrue(all(set(e["versions"]) <= {"X", "Y"} for e in raw["encounters"] if e["group"] == "XY"))
def test_only_direct_encounters(self):
    # asking for Raichu must not return Pikachu's encounters under species 26
    self.assertTrue(all(e["species"] == 26 for e in encs(raw, "SM", 26)))
def test_roaming_gimmighoul_is_go_only(self):
    groups = {e["group"] for e in raw["encounters"] if e["species"] == 999 and e["form"] == 1}
    self.assertEqual(groups, {"GO"})
def test_unown_random_form_marked(self):
    self.assertTrue(any(e["form_random"] for e in encs(raw, "GSC", 201)))
```

- [ ] **Step 2: Run** — Expected: FAIL (`encounters` empty).

- [ ] **Step 3: Implement.** For each group and each species whose id fits the blank PKM's `MaxSpeciesID`, for each form listed for that group in Task 1 (form 0 only where the format has no form field): set `Species`/`Form` on a fresh blank and call, as proven in the spike:

```csharp
EncounterMovesetGenerator.GenerateEncounters(pk, ReadOnlyMemory<ushort>.Empty, versions)
```

  Keep only results whose `Species` equals the requested species (the generator also walks back to pre-evolutions) and whose `Form` equals the requested form or is a random marker. De-duplicate on every emitted field. Sort output by group order, species, form, type, location so re-runs diff cleanly.

- [ ] **Step 4: Run exporter + tests** — Expected: PASS. Note the run time in the commit message.

- [ ] **Step 5: Commit** `feat: export direct encounters per game group`

---

### Task 3: Export evolutions

**Files:**
- Modify: `exporter/Program.cs`
- Test: `builder/tests/test_raw_evolutions.py`

**Interfaces:**
- Produces: `raw["evolutions"]`: `{"group": "SM", "from": [25, 0], "to": [26, 1], "trade": false}` — one per evolution that can be performed **inside that group's games**, with the resulting form resolved. `trade` is true when the method needs a trade.

- [ ] **Step 1: Write the failing tests** (helper `evos(raw, group)` returns a set of `(from_species, from_form, to_species, to_form)`):

```python
def test_pikachu_becomes_alolan_raichu_in_alola(self):
    self.assertIn((25, 0, 26, 1), evos(raw, "SM"))
    self.assertNotIn((25, 0, 26, 0), evos(raw, "SM"))
def test_galarian_meowth_evolves_to_perrserker(self):
    self.assertIn((52, 2, 863, 0), evos(raw, "SwSh"))
def test_trade_evolution_flagged(self):
    self.assertTrue(any(e["trade"] for e in raw["evolutions"] if e["group"] == "RBY" and e["from"] == [64, 0]))
def test_no_evolution_into_absent_species(self):
    present = {(s["id"], f["form"]) for s in raw["species"] for f in s["forms"] if "RBY" in f["groups"]}
    self.assertTrue(all((t, tf) in present for (_, _, t, tf) in evos(raw, "RBY")))
```

- [ ] **Step 2: Run** — Expected: FAIL.

- [ ] **Step 3: Implement** using PKHeX's per-context evolution tree (`EvolutionTree.GetEvolutionTree(EntityContext)` and its forward lookup — confirm names in source). Emit an edge only when both ends are present in the group (Task 1 presence). If PKHeX does not model the Alola-only Raichu rule at this level, the first test tells you; then resolve it from the group's personal/evolution data rather than hard-coding species.

- [ ] **Step 4: Run exporter + tests** — Expected: PASS.

- [ ] **Step 5: Commit** `feat: export in-game evolutions per group`

---

### Task 4: Rule files and loader

**Files:**
- Create: `rules/forms.json`, `rules/sv_exclusives.json`, `rules/releases.json`, `rules/dlc.json`, `rules/gmax.json`, `rules/gender_diff.json`, `tools/fetch_gender_diff.py`
- Create: `builder/dexbuild/__init__.py`, `builder/dexbuild/rules.py`
- Test: `builder/tests/test_rules.py`

**Interfaces:**
- Produces: `load_rules(rules_dir: pathlib.Path) -> Rules`, raising `RulesError(str)` naming file and entry on any problem. `Rules` is a dataclass with fields `games: dict`, `forms: dict`, `sv_exclusives: list`, `releases: list`, `dlc: list`, `gmax: set[int]`, `gmax_unverified: set[int]`, `gender_diff: set[int]`.
- File shapes (every object in an `entries` list also has `"verified": false, "checked": ""`):

```json
// forms.json
{"exclude": {"entries": [{"species": 493, "forms": [1, 17], "reason": "type follows held plate; HOME strips items"}]},
 "methods": {"entries": [{"species": 869, "form": 3, "group": "SwSh", "method": "Form change",
                           "place": "Evolve Milcery holding a sweet; cream depends on spin", "versions": null}]},
 "annotate": {"entries": [{"species": 386, "form": null, "group": "RSE", "note": "Does not carry to HOME"}]}}
// sv_exclusives.json
{"entries": [{"species": 246, "form": null, "version": "SL"}]}
// releases.json
{"entries": [{"group": "FRLG", "species": 386, "location_contains": "Birth Island",
              "set": {"ended": false, "note": "Aurora Ticket is given after the Hall of Fame"}}]}
// dlc.json
{"entries": [{"group": "SV", "dlc": "The Teal Mask", "locations": ["Kitakami Road"]}]}
// gmax.json
{"entries": [{"species": 6}]}
// gender_diff.json
{"source": "PokéAPI pokemon_species.csv, column has_gender_differences", "species": [3, 12], "form_is_gender": [678]}
```

  `forms` in `exclude` is an inclusive `[first, last]` range. `form: null` means every form. `set` may contain `ended` (bool), `method` (str), `note` (str). A `methods` entry **replaces** that form's cell for that group (`versions: null` = every version of the group, otherwise a list of version codes). An `annotate` entry keeps the cell PKHeX produced and adds `note` to each entry in it; use it for forms that are obtainable but lost on transfer.

- [ ] **Step 1: Write the failing tests** using `tempfile` directories:

```python
def test_loads_real_rules(self):
    r = load_rules(REPO / "rules")
    self.assertIn("RBY", [g["id"] for g in r.games["groups"]])
def test_entry_without_verified_is_rejected(self):
    # write forms.json whose exclude entry lacks "verified"
    with self.assertRaisesRegex(RulesError, r"forms\.json.*verified"): load_rules(tmp)
def test_unknown_group_is_rejected(self):
    # releases.json entry with "group": "XX"
    with self.assertRaisesRegex(RulesError, r"releases\.json.*XX"): load_rules(tmp)
def test_unknown_version_is_rejected(self):
    # sv_exclusives.json entry with "version": "SW"
    with self.assertRaisesRegex(RulesError, r"sv_exclusives\.json.*SW"): load_rules(tmp)
def test_malformed_json_names_the_file(self):
    with self.assertRaisesRegex(RulesError, r"dlc\.json"): load_rules(tmp)
```

- [ ] **Step 2: Run** — Expected: FAIL (module missing).

- [ ] **Step 3: Implement `load_rules`.**

- [ ] **Step 4: Draft the rule content** (all `verified: false`), from PKHeX output and general knowledge only:
  - `forms.json` `exclude`: the item-held and reverting forms named in the spec's Rows section. `methods`: Alcremie, Rotom, Vivillon, Unown and similar cases found by listing species that have `form_random` encounters or forms with no encounter in a group where the species is obtainable. `annotate`: forms set by the game rather than carried by the Pokémon (for example Deoxys in generation 3), with note `"Does not carry to HOME"`.
  - `sv_exclusives.json`: Scarlet-only and Violet-only species and forms (include Paldean Tauros Blaze → `SL`, Aqua → `VL`, Larvitar line → `SL`, Bagon line → `VL`).
  - `releases.json`: the three known differences in the spec's "Re-releases" section, plus `set: {"ended": true, "method": "Event"}` for ticket-gated statics in original releases (Birth Island and Navel Rock in RSE; Faraway Island; and equivalents you can identify from PKHeX locations).
  - `dlc.json`: SV Kitakami and Blueberry Academy location names, Z-A "Hyperspace Lumiose". (SwSh needs none: its location names end in `(Isle of Armor)` / `(Crown Tundra)`.)
  - `gmax.json`: every species with a Gigantamax form.
  - `tools/fetch_gender_diff.py`: downloads `https://raw.githubusercontent.com/PokeAPI/pokeapi/master/data/v2/csv/pokemon_species.csv`, prints the ids with `has_gender_differences == 1`; with `--write` updates `rules/gender_diff.json` `species` and keeps `form_is_gender`. `form_is_gender` = species whose male/female looks are separate PKHeX forms already (find them from raw.json form names; Meowstic 678 is one).

- [ ] **Step 5: Run tests** — Expected: PASS.

- [ ] **Step 6: Commit** `feat: hand-kept rule files with verified flags and a validating loader`

---

### Task 5: Encounters → entries

**Files:**
- Create: `builder/dexbuild/model.py`, `builder/dexbuild/kinds.py`, `builder/dexbuild/direct.py`
- Test: `builder/tests/test_direct.py`

**Interfaces:**
- Consumes: `raw` (Tasks 1–3), `Rules` (Task 4).
- Produces, in `model.py`:

```python
@dataclass(frozen=True)
class Entry:
    method: str            # Wild, Static, Gift, In-game trade, Raid, Evolve, Breed, Form change, Event, GO, HOME gift
    place: str
    versions: tuple[str, ...]   # version codes this entry applies to; () for Other-column entries
    dlc: str | None = None
    ended: bool = False         # no longer obtainable by a new player
    unverified: bool = False    # depends on an unverified hand-kept fact
    note: str | None = None
    gender: str | None = None   # "m" / "f" when the source fixes gender
```

- Produces: `kinds.method_for(type_name: str, label: str) -> tuple[str, bool]` returning `(method, ended)`; raises `UnknownKind(type_name)` when nothing matches.
- Produces: `direct.direct_entries(raw: dict, rules: Rules) -> dict[tuple[str, int, int], list[Entry]]` keyed `(group_id, species, form)`. Eggs are **not** included here (Task 6 owns Breed). `form_random` encounters are attached to every form of that species present in the group, with `note="Form varies"` and `unverified=True` unless a `forms.json` method entry for that species+group replaces them.

- [ ] **Step 1: Write the failing tests** with small hand-built `raw` dicts (helper `enc(**kw)` fills defaults) plus one against real data:

```python
def test_wild_static_trade_gift_labels(self):
    self.assertEqual(method_for("EncounterSlot8", "Wild Encounter (SW)"), ("Wild", False))
    self.assertEqual(method_for("EncounterStatic8", "Static Encounter"), ("Static", False))
    self.assertEqual(method_for("EncounterTrade8", "In-game Trade"), ("In-game trade", False))
def test_events_and_distributions_are_ended(self):
    self.assertEqual(method_for("WC8", "Event Gift"), ("Event", True))
    self.assertEqual(method_for("EncounterStatic8ND", "Distribution Raid Den Encounter - 067")[1], True)
def test_unknown_type_raises(self):                       # Review Focus 5
    with self.assertRaises(UnknownKind): method_for("EncounterBrandNew12", "Something")
def test_every_real_type_is_mapped(self):                 # Review Focus 5, against build/raw.json
    for t, l in {(e["type"], e["label"]) for e in load_raw()["encounters"]}: method_for(t, l)
def test_sv_exclusive_narrows_versions(self):
    # Larvitar wild in SV with versions [SL, VL] + rule {246, None, "SL"}
    self.assertEqual(out[("SV", 246, 0)][0].versions, ("SL",))
    self.assertTrue(out[("SV", 246, 0)][0].unverified)
def test_sv_exclusive_does_not_touch_raids(self):
    self.assertEqual(raid_entry.versions, ("SL", "VL"))
def test_dlc_from_swsh_suffix_and_rule_file(self):
    self.assertEqual(e_ioa.dlc, "Isle of Armor"); self.assertEqual(e_ioa.place, "Fields of Honor")
    self.assertEqual(e_kitakami.dlc, "The Teal Mask")
def test_release_rule_overrides_ended(self):
    # FRLG Deoxys at Birth Island with the releases.json FRLG entry
    self.assertFalse(e.ended); self.assertIn("Aurora Ticket", e.note); self.assertTrue(e.unverified)
def test_event_title_used_when_present(self):
    self.assertEqual(e.place, "Pokémon 20th Anniversary")   # event_title wins over location
def test_event_without_title(self):
    self.assertEqual((e.method, e.place), ("Event", ""))
def test_home_gift_goes_to_other(self):
    # WC8 with location "Pokémon HOME" in group SwSh
    self.assertEqual(out[("GO", 801, 1)][0].method, "HOME gift")
def test_random_form_spreads_to_all_forms(self):
    self.assertEqual(out[("GSC", 201, 5)][0].note, "Form varies")
def test_eggs_excluded(self):
    self.assertNotIn(("SM", 52, 0), out)
```

- [ ] **Step 2: Run** — Expected: FAIL.

- [ ] **Step 3: Implement.** `kinds.py` is an ordered list of `(regex on type name, optional regex on label, method, ended)`; build it by listing the distinct `(type, label)` pairs in real `raw.json`. Events, distribution raids, distribution outbreaks and shut-down services (Dream World / Entree Forest) are `ended=True`; stock raids are `Raid, False`; Pokéwalker is `Gift, False` with the label kept as the place. Other-column entries (group `GO`, and events located at "Pokémon HOME") are stored under the key `("GO", species, form)` with `versions=()`.

- [ ] **Step 4: Run tests** — Expected: PASS.

- [ ] **Step 5: Commit** `feat: turn PKHeX encounters into labelled entries`

---

### Task 6: Evolve and Breed

**Files:**
- Create: `builder/dexbuild/derive.py`
- Test: `builder/tests/test_derive.py`

**Interfaces:**
- Consumes: `direct_entries` output (Task 5), `raw["evolutions"]`, `raw["encounters"]` (eggs).
- Produces: `derive.add_evolve_and_breed(direct: dict, raw: dict) -> dict` — same key shape, with `Evolve` and `Breed` entries added.

Rules, per group:
- **Evolve:** `(species, form)` gains `Entry("Evolve", "Evolve <pre-evolution name>", versions)` when an evolution edge leads to it from something obtainable in that group. `versions` = union of the versions in which the pre-evolution is obtainable. Trade evolutions use place `"Evolve <name> (trade)"`. Repeat until nothing changes, so three-stage lines resolve. `ended`/`unverified` are true only if **every** route to the pre-evolution is ended/unverified.
- **Breed:** `(species, form)` gains `Entry("Breed", "Breed <name>", versions)` only when PKHeX has an egg encounter for it in that group **and** some member of its evolution family in the same form line is obtainable in that group by a non-Breed method. Family = connected through that group's evolution edges.

- [ ] **Step 1: Write the failing tests:**

```python
def test_evolve_from_obtainable_pre_evolution(self):
    # Pikachu wild in SM (SN, MN); edge 25-0 -> 26-1
    e = out[("SM", 26, 1)][0]
    self.assertEqual((e.method, e.place, e.versions), ("Evolve", "Evolve Pikachu", ("SN", "MN")))
def test_three_stage_line(self):
    self.assertIn(("RBY", 3, 0), out)        # Bulbasaur gift -> Ivysaur -> Venusaur
def test_trade_evolution_labelled(self):
    self.assertEqual(out[("RBY", 65, 0)][0].place, "Evolve Kadabra (trade)")
def test_version_exclusive_carries_through_evolution(self):
    # Oddish only FR -> Gloom only FR
    self.assertEqual(out[("FRLG", 44, 0)][0].versions, ("FR",))
def test_breed_needs_a_parent_in_that_game(self):     # the spec's anti-goal
    # SM has an egg encounter for Meowth-0 but no obtainable Meowth-0 / Persian-0
    self.assertNotIn(("SM", 52, 0), out)
def test_breed_when_parent_obtainable(self):
    # Pikachu wild in SM, egg encounter for Pichu-0
    self.assertEqual(out[("SM", 172, 0)][-1].method, "Breed")
def test_evolve_not_ended_if_any_live_route(self):
    self.assertFalse(e.ended)
def test_no_evolve_into_form_absent_from_group(self):
    self.assertNotIn(("RBY", 26, 1), out)
```

- [ ] **Step 2: Run** — Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run tests** — Expected: PASS.
- [ ] **Step 5: Commit** `feat: derive evolve and breed availability`

---

### Task 7: Rows

**Files:**
- Create: `builder/dexbuild/rows.py`
- Modify: `builder/dexbuild/model.py` (add `Row`, `LeftOut`)
- Test: `builder/tests/test_rows.py`

**Interfaces:**
- Produces, in `model.py`:

```python
@dataclass
class Row:
    id: str; dex: int; name: str; form_name: str
    species: int; form: int; gender: str | None      # "m" / "f" / None
    mega: list[str]; gmax: bool; gmax_unverified: bool
    cells: dict[str, list[Entry]]                     # group id -> entries, filled in Task 8
    other: list[Entry]
@dataclass(frozen=True)
class LeftOut:
    species: int; form: int; name: str; form_name: str; reason: str; verified: bool
```

- Produces: `rows.build_rows(raw: dict, rules: Rules) -> tuple[list[Row], list[LeftOut]]`, rows sorted by `(dex, form, gender)` with male before female.

Rules: one row per form that is not `battle_only`, not `fused`, and not matched by a `forms.json` `exclude` entry. Excluded-by-rule forms go to `LeftOut` with the rule's `reason` and `verified`. A species in `gender_diff` and not in `form_is_gender` gets two rows per form (`-m`, `-f`), `form_name` "Male" / "Female", or `"<form name>, Male"` when the form itself has a name. `form_name` for a species' only row is `""`. `mega` from `raw["megas"]`; `gmax` from `rules.gmax`.

- [ ] **Step 1: Write the failing tests:**

```python
def test_single_form_species_has_one_row(self):
    self.assertEqual([r.id for r in rows if r.dex == 143], ["0143-0"])
def test_gender_difference_makes_two_rows(self):
    self.assertEqual([(r.id, r.form_name) for r in rows if r.dex == 25][:2],
                     [("0025-0-m", "Male"), ("0025-0-f", "Female")])
def test_form_is_gender_not_doubled(self):
    self.assertEqual(len([r for r in rows if r.dex == 678]), 2)
def test_mega_is_flag_not_row(self):
    z = [r for r in rows if r.dex == 6]
    self.assertEqual(len(z), 1); self.assertEqual(z[0].mega, ["Mega X", "Mega Y"]); self.assertTrue(z[0].gmax)
def test_excluded_form_is_reported_not_dropped(self):
    self.assertEqual([r.id for r in rows if r.dex == 493], ["0493-0"])
    self.assertEqual(len([l for l in left if l.species == 493]), 17)
def test_order(self):
    self.assertEqual([r.dex for r in rows], sorted(r.dex for r in rows))
def test_ids_unique(self):
    self.assertEqual(len({r.id for r in rows}), len(rows))
```

- [ ] **Step 2: Run** — Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run tests** — Expected: PASS.
- [ ] **Step 5: Commit** `feat: build the row list with left-out report`

---

### Task 8: Assemble, check, and CLI

**Files:**
- Create: `builder/dexbuild/assemble.py`, `builder/dexbuild/checks.py`, `builder/dexbuild/__main__.py`
- Test: `builder/tests/test_assemble.py`, `builder/tests/test_cli.py`, `builder/tests/test_golden.py`

**Interfaces:**
- Consumes: everything above.
- Produces: `assemble.assemble(raw, rules) -> tuple[list[Row], list[LeftOut]]` with `cells`/`other` filled; `assemble.to_json(rows, rules, raw) -> dict`; `checks.structural_problems(rows, rules, raw) -> list[str]`.
- Produces: `site/data/dex.json`:

```json
{"meta": {"pkhex": "26.10.18", "rows": 1400},
 "groups": [{"id": "SwSh", "label": "Sword / Shield",
             "versions": [{"code": "SW", "label": "Sword", "mark": "Sw"}],
             "home_route": "direct", "home_route_unverified": true}],
 "rows": [{"id": "0052-1", "dex": 52, "name": "Meowth", "form": "Alola",
           "mega": [], "gmax": false, "gmax_unverified": false,
           "cells": {"SwSh": [{"method": "Static", "place": "Fields of Honor", "versions": ["SW", "SH"],
                               "dlc": "Isle of Armor", "ended": false, "unverified": false, "note": null}]},
           "other": []}]}
```

  `groups` excludes the `GO` pseudo-group. A group with no entries is absent from a row's `cells`.

Assembly rules:
- A row's cell for a group = entries for `(group, species, form)` after Tasks 5–6. Then `forms.json` `methods` entries for that species/form/group **replace** the cell (each becomes an `Entry` with `unverified = not verified`). Then `annotate` entries add their `note` to every entry left in the cell and set `unverified = not verified` on them.
- Gender rows drop entries whose `gender` is the other one.
- Order inside a cell: not-ended before ended; then method in this order — Wild, Static, Gift, In-game trade, Raid, Evolve, Breed, Form change, Event; then place A–Z. Merge entries equal in everything but `versions` by unioning versions.
- `other` is filled from the `GO` key **only when the row has no not-ended entry in any main group**. GO encounters become `Entry("GO", "Pokémon GO → HOME", ())`.

Structural checks (each failure is one string naming the row):
- every dex number from 1 to the highest has at least one row;
- no row is empty in every cell and `other` — unless it has a `forms.json` method entry;
- every version code in every entry belongs to its group;
- no duplicate row ids.

CLI: `python3 -m dexbuild --raw PATH --rules DIR --out PATH [--write]`. Always prints: row count, left-out list (`unverified` ones marked), count of unverified cells, problems. Exit 1 if any problem or `UnknownKind` / `RulesError` (print the message, no traceback). Without `--write` nothing is written. With `--write` and no problems: write to `PATH.tmp` then `os.replace` onto `PATH`.

- [ ] **Step 1: Write the failing tests.**

`test_assemble.py` (synthetic data):

```python
def test_form_method_rule_replaces_cell(self): ...       # asserts method "Form change", unverified True
def test_annotate_keeps_cell_and_adds_note(self):
    self.assertEqual((e.method, e.versions, e.note, e.unverified), ("Static", ("FR",), "Does not carry to HOME", True))
def test_gender_row_drops_other_gender_entries(self): ...
def test_order_live_before_ended_then_method(self):
    self.assertEqual([e.method for e in cell], ["Wild", "Static", "Evolve", "Event"])
def test_same_place_versions_merged(self): self.assertEqual(cell[0].versions, ("SW", "SH"))
def test_other_only_when_no_live_main_entry(self):
    self.assertEqual(row_with_wild.other, []); self.assertEqual(row_go_only.other[0].method, "GO")
def test_check_flags_empty_row(self): self.assertRegex(problems[0], "0999-1")
def test_check_flags_missing_dex_number(self): ...
```

`test_cli.py`:

```python
def test_default_is_report_only(self):
    run(["--raw", raw, "--rules", rules, "--out", out]); self.assertFalse(os.path.exists(out))
def test_write_is_atomic_and_valid_json(self):          # Review Focus 4
    run([..., "--write"]); json.load(open(out)); self.assertFalse(os.path.exists(out + ".tmp"))
def test_problems_block_write(self):
    self.assertEqual(run([..., "--write"]).returncode, 1); self.assertFalse(os.path.exists(out))
def test_unknown_kind_exits_1_naming_type(self):        # Review Focus 5
    self.assertIn("EncounterBrandNew12", run([...]).stderr)
```

`test_golden.py` (real `build/raw.json` + real `rules/`; helper `cell(rows, id, group)`), the spec's "Checking it is right" list:

```python
def test_galarian_farfetchd_sword_only(self): self.assertEqual(versions(cell(rows, "0083-1", "SwSh")), {"SW"})
def test_galarian_ponyta_shield_only(self):   self.assertEqual(versions(cell(rows, "0077-1", "SwSh")), {"SH"})
def test_oddish_firered_bellsprout_leafgreen(self):
    self.assertEqual(versions(cell(rows, "0043-0", "FRLG")), {"FR"})   # use the row ids build_rows actually gives
    self.assertEqual(versions(cell(rows, "0069-0", "FRLG")), {"LG"})
def test_deoxys_forms(self):
    self.assertEqual(versions(cell(rows, "0386-1", "FRLG")), {"FR"})
    self.assertEqual(versions(cell(rows, "0386-2", "FRLG")), {"LG"})
    self.assertEqual(versions(cell(rows, "0386-3", "RSE")), {"E"})
def test_alolan_meowth_swsh_static(self):
    e = cell(rows, "0052-1", "SwSh")[0]; self.assertEqual((e.method, e.place, e.dlc), ("Static", "Fields of Honor", "Isle of Armor"))
def test_bloodmoon_ursaluna(self): self.assertEqual(cell(rows, "0901-1", "SV")[0].place, "Timeless Woods")
def test_roaming_gimmighoul_go_only(self):
    r = row(rows, "0999-1"); self.assertEqual(r.cells, {}); self.assertEqual(r.other[0].method, "GO")
def test_original_magearna_home_gift(self): self.assertEqual(row(rows, "0801-1").other[0].method, "HOME gift")
def test_kantonian_meowth_not_in_sun_moon(self): self.assertNotIn("SM", row(rows, "0052-0").cells)
def test_larvitar_scarlet_bagon_violet(self):
    self.assertEqual(live_versions(cell(rows, "0246-0", "SV")), {"SL"})
    self.assertEqual(live_versions(cell(rows, "0371-0", "SV")), {"VL"})
def test_frlg_switch_deoxys_is_live(self): self.assertFalse(cell(rows, "0386-1", "FRLG")[0].ended)
def test_no_structural_problems(self): self.assertEqual(structural_problems(rows, rules, raw), [])
```

  Where a species in these tests turns out to have gender rows, use its `-m` row; fix the id in the test, not the rule.

- [ ] **Step 2: Run** — Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run all Python tests** — Expected: PASS. If a golden test fails because PKHeX disagrees with the expected fact, stop and report it to the owner; do not adjust the expectation.
- [ ] **Step 5: Run the CLI without `--write`, read the left-out list and unverified count, then with `--write`.** Expected: `site/data/dex.json` exists, exit 0.
- [ ] **Step 6: Commit** `feat: assemble dex data with structural and golden checks`

---

### Task 9: Page logic — filtering and cell summaries

**Files:**
- Create: `site/package.json` (`{"type": "module", "private": true}`), `site/logic.js`
- Test: `site/tests/logic.test.js`

**Interfaces:**
- Consumes: `dex.json` shape (Task 8).
- Produces (all pure, exported from `site/logic.js`):

```js
visibleGroups(groups, owned)        // owned: Set of version codes. Empty set -> all groups. Else groups with >=1 owned version.
entryOwned(entry, owned)            // true when owned is empty, entry.versions is empty, or they intersect
summarize(entries, max = 3)         // -> {shown: Entry[], more: number}
versionMarks(entry, group)          // -> string[] of marks; [] when the entry covers every version of the group
rowMatches(row, query)              // case-insensitive on name and form; a query of digits matches dex number exactly ("25", "025")
rowAvailability(row, groups, owned) // -> "owned" | "elsewhere" | "none": any not-ended entry in an owned version / only in unowned ones / nowhere
elsewhereLabels(row, groups, owned) // -> string[] of group labels (plus "Pokémon GO" / "HOME gift" from row.other) where the row is available
```

- [ ] **Step 1: Write the failing tests** with a three-group fixture (FRLG, SwSh, SV) and rows for Pikachu, Galarian Meowth, Roaming Gimmighoul:

```js
test("no owned versions shows every group", () => assert.equal(visibleGroups(groups, new Set()).length, 3));
test("owning Sword shows only its group", () => assert.deepEqual(visibleGroups(groups, new Set(["SW"])).map(g => g.id), ["SwSh"]));
test("entry for the other version is not owned", () => assert.equal(entryOwned({versions: ["SH"]}, new Set(["SW"])), false));
test("summarize keeps order and counts the rest", () => assert.deepEqual(summarize([a, b, c, d, e], 3), {shown: [a, b, c], more: 2}));
test("no mark when entry covers all versions", () => assert.deepEqual(versionMarks({versions: ["SW", "SH"]}, swsh), []));
test("mark for a single version", () => assert.deepEqual(versionMarks({versions: ["SW"]}, swsh), ["Sw"]));
test("search by number ignores leading zeros", () => { assert.ok(rowMatches(pikachu, "025")); assert.ok(!rowMatches(pikachu, "5")); });
test("search by form name", () => assert.ok(rowMatches(galarMeowth, "galar")));
test("row only in GO is 'elsewhere' with a GO label", () => {
  assert.equal(rowAvailability(gimmighoul, groups, new Set(["SW"])), "elsewhere");
  assert.deepEqual(elsewhereLabels(gimmighoul, groups, new Set(["SW"])), ["Pokémon GO"]); });
test("ended-only entry does not count as available", () => assert.equal(rowAvailability(eventOnly, groups, new Set(["SW"])), "none"));
```

- [ ] **Step 2: Run** `cd site && node --test tests/` — Expected: FAIL.
- [ ] **Step 3: Implement `site/logic.js`.**
- [ ] **Step 4: Run** — Expected: PASS.
- [ ] **Step 5: Commit** `feat: page logic for filters and cell summaries`

---

### Task 10: Page logic — saved state, export, import

**Files:**
- Modify: `site/logic.js`
- Test: `site/tests/state.test.js`

**Interfaces:**
- Produces:

```js
STATE_KEY = "lfd-state-v1"
emptyState()                         // -> {version: 1, ticks: [], owned: []}
parseState(text)                     // -> {ok: true, state} | {ok: false, error: string}. Never throws.
serializeState(state)                // -> JSON string, ticks and owned sorted
toggleTick(state, rowId)             // -> new state
orphanTicks(state, rows)             // -> string[] of ticked ids not present in rows
tickedCount(state, rows)             // -> number of rows that are ticked (orphans not counted)
```

  `parseState` accepts only an object with `version === 1`, `ticks` an array of strings, `owned` an array of strings; anything else is `{ok: false}` with a sentence a person can read. It keeps ids it does not recognise.

- [ ] **Step 1: Write the failing tests:**

```js
test("round trip", () => assert.deepEqual(parseState(serializeState(s)).state, s));
test("orphan ticks are kept and reported", () => {              // Review Focus 1
  const s = {version: 1, ticks: ["0025-0-m", "9999-9"], owned: []};
  assert.deepEqual(orphanTicks(s, rows), ["9999-9"]);
  assert.ok(parseState(serializeState(s)).state.ticks.includes("9999-9"));
  assert.equal(tickedCount(s, rows), 1); });
test("garbage is rejected, not thrown", () => {                 // Review Focus 2
  for (const bad of ["", "not json", "[]", "null", '{"version":2,"ticks":[],"owned":[]}', '{"version":1,"ticks":"x","owned":[]}', '{"version":1,"ticks":[1],"owned":[]}'])
    assert.equal(parseState(bad).ok, false); });
test("toggle adds then removes without mutating", () => { /* original state object unchanged */ });
```

- [ ] **Step 2: Run** — Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** — Expected: PASS.
- [ ] **Step 5: Commit** `feat: saved state with safe import and orphan-tick reporting`

---

### Task 11: The page

**Files:**
- Create: `site/index.html`, `site/style.css`, `site/app.js`
- Test: manual checklist below (DOM code; logic is covered by Tasks 9–10)

**Interfaces:**
- Consumes: `site/logic.js`, `data/dex.json` (fetched relative to the page).

What the page does (spec "The page"):
- Top bar: "I own" — one toggle button per individual version, grouped by game group in column order; search box; "Hide ticked" toggle; `ticked / total` count; Export and Import buttons.
- Table: header row with group labels; each header shows its HOME route as a second line, with an "unverified" mark when `home_route_unverified`. Columns `tick, #, Name, Form` stay pinned on horizontal scroll (`position: sticky`). Then `Mega`, `Gmax`, one column per `visibleGroups`, then `Other`.
- `#` shows the dex number zero-padded to 4. `Mega` shows the names joined by ", " or `–`. `Gmax` shows `Yes` or `–`.
- Cell: `summarize(entries, 3)`; each entry reads `Method: place` + DLC name + version marks; `–` when empty. Entries with `ended` are visibly muted and labelled "ended"; `unverified` entries carry a small "unverified" mark with a `title` explaining it; `note` is shown. Entries for which `entryOwned` is false are dimmed, not hidden. A cell with `more > 0` shows `+N`; clicking the cell toggles the full list in place.
- When at least one version is owned and `rowAvailability` is not `"owned"`, the row shows, in its first visible game cell area, "Not in your games — available in: " + `elsewhereLabels`, or "Not currently obtainable" for `"none"`.
- Ticking writes state immediately. If `orphanTicks` is non-empty, a line under the top bar says "N ticks refer to rows that are no longer listed. They are kept in your saved state."
- Export downloads `living-form-dex-state.json` (`serializeState`). Import reads a chosen file through `parseState`; on `ok: false` show the error and change nothing; on success ask for confirmation stating how many ticks will replace how many, then replace.
- Storage: wrap every `localStorage` read/write in `try`/`catch`. If it throws or is absent, keep state in memory and show "Ticks cannot be saved in this browser. Use Export to keep them." (Review Focus 3)
- Data load: if the fetch fails or the JSON does not parse or has no `rows`, replace the table with "Could not load the dex data. Run the build, then reload." and the underlying error text. (Review Focus 4)
- Accessibility: real `<table>`, `<th scope>`, tick boxes are `<input type="checkbox">` with an `aria-label` naming the Pokémon and form; toggles are `<button aria-pressed>`; visible focus styles; colours must also carry a text label (never colour alone for ended / unverified).
- Light and dark via `prefers-color-scheme`. No external fonts or assets.

- [ ] **Step 1: Write `index.html`, `style.css`, `app.js`.** Build the table with DOM methods and `textContent`; never assign data to `innerHTML`.

- [ ] **Step 2: Serve locally and check by hand.**
  Run: `python3 -m http.server 8599 --bind 127.0.0.1 --directory site` then `curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8599/data/dex.json` — Expected: `200`. Then, in a browser against the real data, confirm each line and record the result in the commit message:
  1. All rows render; scrolling sideways keeps tick/#/Name/Form pinned.
  2. Ticking Pikachu, reloading: still ticked; count shows `1 / total`.
  3. Owning only Sword: only the SwSh column (plus Other) shows; Shield-only entries dimmed; Roaming Gimmighoul reads "Not in your games — available in: Pokémon GO".
  4. Search `025`, `galar`, `meowth` each narrow correctly; clearing restores.
  5. A cell with `+N` expands and collapses.
  6. Export, clear site data, Import the file: ticks return. Importing `rules/games.json` instead is refused with a message and ticks are unchanged.
  7. Temporarily rename `site/data/dex.json`: the page shows the load error, not an empty table. Rename back.
  8. Keyboard only: can reach and toggle a tick box, a version button and a cell expansion.

- [ ] **Step 3: Stop the local server. Commit** `feat: dex page with my-games filter, ticks, export and import`

---

### Task 12: Serve on port 8507

**Files:**
- Create: `deploy/living-form-dex.service`
- Modify: `~/bin/launcher/network_diagrams.py` (tailnet-only row), `README.md`

**Interfaces:**
- Consumes: `site/`.

- [ ] **Step 1: Confirm the port is free.** Run: `ss -tln | grep -c ':8507 '` — Expected: `0`.

- [ ] **Step 2: Write `deploy/living-form-dex.service`:**

```ini
[Unit]
Description=Living form dex (static page, Tailscale only)
After=network-online.target

[Service]
# Bound to the Tailscale address only: reachable on the tailnet, not on LAN.
# Restart covers boot ordering, when tailscaled has not brought the address up yet.
ExecStart=/usr/bin/python3 -m http.server 8507 --bind <tailscale-ip> --directory ~/living-form-dex/site
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
```

- [ ] **Step 3: Install and start.**

```bash
ln -s ~/living-form-dex/deploy/living-form-dex.service ~/.config/systemd/user/living-form-dex.service
systemctl --user daemon-reload
systemctl --user enable --now living-form-dex.service
```

- [ ] **Step 4: Verify.**
  Run: `curl -s -o /dev/null -w "%{http_code}\n" http://<tailscale-ip>:8507/` — Expected: `200`
  Run: `curl -s -m 3 -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8507/` — Expected: `000` (not bound on loopback)
  Run: `systemctl --user is-enabled living-form-dex.service` — Expected: `enabled`

- [ ] **Step 5: Update the network diagram.** In `~/bin/launcher/network_diagrams.py` add `("Living form dex", ":8507 TS IP")` to the tailnet-only row and adjust spacing so six nodes fit; mention the port in the page's prose where the other tailnet-only ports are listed. Run it without `--write` first and read the report, then with `--write`.

- [ ] **Step 6: Add to `README.md`:** the URL `http://<host>.<tailnet>.ts.net:8507/`, how to rebuild data, how to restart the service, and that a rebuild needs only a browser refresh.

- [ ] **Step 7: Commit** (in this repo) `feat: serve the dex on port 8507 over Tailscale`. The launcher script lives outside this repo; report that change to the owner separately.

- [ ] **Step 8: Tell the owner** two things that this plan does not do: the wiki's machine-context port table needs the 8507 row (it is updated through the owner's `/dump` flow, and the weekly lint will flag the mismatch until then), and every hand-kept fact is still `verified: false` — list the unverified count from the build report and where the rule files are.

---

## Not in this plan

- Verifying hand-kept facts against Bulbapedia / HOME — the owner's job, by eye; the page marks what is unverified.
- Public hosting, sprites, shiny, spin-off columns, device sync (spec non-goals).
- Winds / Waves: later, by bumping the `PKHeX.Core` version, adding a group to `rules/games.json`, and re-running export and build.
