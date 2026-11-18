# Living Form Dex — Design

Date: 2026-11-14 · Status: approved by the owner 2026-11-14, with one change
(serve the page on a port instead of shipping a file)

## Abbreviations

| Short | Full |
|---|---|
| Dex | Pokédex — the numbered list of all Pokémon species |
| Living form dex | A collection holding one of every Pokémon in every form at the same time |
| HOME | Pokémon HOME — Nintendo's cloud storage app where a living dex is kept |
| GO | Pokémon GO — the mobile game; can send Pokémon to HOME |
| PKHeX | Open-source Pokémon save editor; ships a database of every legal encounter |
| DLC | Downloadable content (paid expansions such as Isle of Armor) |
| Mega | Mega Evolution — temporary in-battle form, cannot be stored |
| Gmax | Gigantamax — a storable flag on a Pokémon, not a separate form |
| RBY, GSC, RSE, FRLG, DPPt, HGSS, BW, B2W2, XY, ORAS, SM, USUM, LGPE, SwSh, BDSP, PLA, SV, Z-A | Game groups, listed in full under "Game columns" |
| GPL | GNU General Public License v3 — open-source licence that requires derived work to stay open under the same licence |

## Intent and why

The owner wants to start collecting a living form dex and found no reference
that says, for every form, **where it can actually be obtained** in each main
series game. The reference they know (PokéJungle's tracker) only says which
games *support* a Pokémon, which does not tell a collector where to go.

This project is that reference plus a personal checklist. It is for the owner
first. Opening it to the public is a possible second phase and is **not** part
of this design, but nothing here may block it.

## Goals

1. One row per Pokémon form, ordered by National Dex number, covering every
   species even when it has only one form.
2. For each row and each main series game group: how and where that exact form
   is obtained, or a clear "not obtainable here".
3. Version exclusives marked wherever a game group has more than one version.
4. A flag per row for "has a Mega" and "has a Gmax".
5. A tick box per row ("I have this"), kept between visits.
6. A "my games" filter: the owner ticks the versions they own, and the table
   shows only those games.
7. Everything the user reads is in English.

## Non-goals

- Shiny tracking.
- Spin-off games as columns (Colosseum, XD, Ranger, Mystery Dungeon, Pokopia,
  Champions, and so on).
- Pokémon GO as a full game column. GO appears only inside the single "Other"
  column, for rows that need it.
- Pokémon images or sprites.
- Public hosting, accounts, sync between devices. The port is reachable on
  the owner's private Tailscale network only.
- Mobile-first layout. It must not break on a phone, but the wide table is
  designed for a desktop screen.
- Pokémon Winds / Waves (2027). Added later by re-running the data build.

## Anti-goals

These would make the project a failure even if it runs:

- Showing a form as obtainable in a game where a player starting that game
  alone cannot get it. "Supported" or "legal" is not "obtainable". This is the
  whole reason the project exists.
- Showing a version-exclusive Pokémon without its version mark.
- Silently losing the owner's ticks.
- Copying text from Bulbapedia or Serebii into the data. Bulbapedia's licence
  (non-commercial, share-alike) is not compatible with GPL, and Serebii grants
  no reuse. Both are for checking by eye only.

## Constraints

- **Data source is PKHeX** (`PKHeX.Core` NuGet package, GPL-3.0-or-later).
  This project is therefore GPL-3.0-or-later too. Bulbapedia blocks automated
  access (HTTP 403 behind a Cloudflare bot check); do not work around it.
- PKHeX is a .NET library targeting .NET 10. The machine (the home server, Linux,
  i3-2330M, 7.7 GB RAM) has no .NET installed. A spike ran the .NET 10 SDK
  from a user-local folder with no trouble (20 hard cases in 1.3 s).
- The owner uses the result from another machine (Windows Main PC) in a
  browser. **The page is served from this server on its own port** (owner's
  decision), so a rebuild shows up on refresh with nothing to download again.
- Port **8507** (listed free in the machine's port table), bound to the
  Tailscale address `<tailscale-ip>` only, plain HTTP, static files only, run
  as a systemd user service so it survives reboots. *(My call on the port
  number, bind and method — this is how the server's other small pages are
  exposed, and a Tailscale-only bind needs no firewall change.)*
- Adding a listening port means the machine's port table and generated
  network diagram must be updated in the same piece of work (house rule).
- Project lives at `~/living-form-dex/`.
- Any script that writes important state defaults to report-only or dry-run;
  it writes only with an explicit flag (house rule).

## Approaches considered

**A. PKHeX encounter database — chosen.** A small .NET program asks PKHeX for
every encounter of every species and form in every game, and writes it out as
data. Gives form-level and version-level detail for all generations, including
gifts, in-game trades, events, raids and GO, and can be re-run when a new game
ships. Costs: needs .NET for the data build; some things are not in encounter
data and need hand-kept rule files (see "Gaps"); GPL licence.

**B. Read Bulbapedia by hand, page by page.** The wiki has the friendliest
location text, but it cannot be fetched automatically, there are about 1,025
species pages, the result cannot be re-run, and its text cannot be published
under GPL. Kept only as the by-eye checking source.

**C. PokéAPI alone.** Open and easy to fetch, but its encounter data is nearly
empty for Sword/Shield onward and has no gifts or events. Not enough.

The owner picked A after seeing the spike output, with hand-kept rule files
for the gaps.

## What the owner decided

- Every form is its own row, **including gender differences** (male and female
  Pikachu are two rows).
- "Obtainable" counts every method: wild, static, gift, in-game trade, raid,
  evolve, breed, DLC, and events — including events that have ended.
- All main series games are covered. Where a game has a Switch release, the
  Switch release is the one described (FireRed/LeafGreen = the 2026 Switch
  release).
- Version exclusives are marked.
- Mega and Gmax are flag columns, not rows.
- One "Other" column for sources outside the main series (Pokémon GO, HOME
  gifts), filled only where a row needs it.
- Events show their name when the data has one; otherwise just "Event".
- Forms that cannot be kept in HOME as themselves are not rows.
- Layout: a wide matrix (one column per game group) combined with the
  "my games" filter that chooses which game columns are shown.
- Data comes from PKHeX; Bulbapedia / Serebii are for checking only.

## Rows

A row is one form of one species that can sit in a HOME box **and stay in that
form**. The owner decided this: forms that cannot be kept in HOME are not
rows.

- Included: regional forms, gender differences, and permanent variants
  (Unown letters, Vivillon patterns, Alcremie creams and sweets, Tauros
  breeds, Rotom appliances, and so on).
- Not rows: Mega, Primal, Gmax, and other battle-only or fused forms. Mega
  and Gmax surface through the flag columns.
- Not rows: forms that exist only while an item is held or that revert when
  deposited, because HOME strips items. Believed to include Arceus and
  Silvally types, Genesect drives, Giratina Origin, Zacian / Zamazenta
  Crowned, Furfrou trims, Hoopa Unbound and Shaymin Sky. This list is from
  memory and is **unverified**.
- The single test for a borderline form is "does it stay this form in a HOME
  box". The builder records the answer per species in a rule file, with the
  same `verified` field as every other hand-kept fact; the owner confirms
  against the HOME app. Until confirmed, a doubtful form is left out and
  listed in a "left out, unconfirmed" report so nothing disappears silently.

Row fields: National Dex number, species name, form name, Mega flag (with the
Mega names when more than one), Gmax flag, one cell per game group, the
"Other" cell.

## Game columns

One column per game group, in this order:

| Column | Versions | Platform described |
|---|---|---|
| RBY | Red, Blue, Yellow | 3DS Virtual Console release (the only one that reaches HOME) |
| GSC | Gold, Silver, Crystal | 3DS Virtual Console release (the only one that reaches HOME) |
| RSE | Ruby, Sapphire, Emerald | Game Boy Advance |
| FRLG | FireRed, LeafGreen | **Switch (2026)** |
| DPPt | Diamond, Pearl, Platinum | DS |
| HGSS | HeartGold, SoulSilver | DS |
| BW | Black, White | DS |
| B2W2 | Black 2, White 2 | DS |
| XY | X, Y | 3DS |
| ORAS | Omega Ruby, Alpha Sapphire | 3DS |
| SM | Sun, Moon | 3DS |
| USUM | Ultra Sun, Ultra Moon | 3DS |
| LGPE | Let's Go Pikachu, Let's Go Eevee | Switch |
| SwSh | Sword, Shield (+ Isle of Armor, Crown Tundra) | Switch |
| BDSP | Brilliant Diamond, Shining Pearl | Switch |
| PLA | Legends: Arceus | Switch |
| SV | Scarlet, Violet (+ Teal Mask, Indigo Disk) | Switch |
| Z-A | Legends: Z-A (+ Mega Dimension) | Switch / Switch 2 |
| Other | Pokémon GO, HOME gifts | — |

Japan-only versions (Green, Japanese Blue) are dropped. *(My call.)*

**Re-releases differ from the originals.** PKHeX mostly describes the original
cartridges. Three columns describe a re-release (RBY, GSC, FRLG), so each gets
a short hand-kept list of differences that override the PKHeX result.
*(My call, raised by the reviewer.)* Known so far:

- FRLG on Switch puts the Mystic Ticket and Aurora Ticket in the bag after
  entering the Hall of Fame. Lugia and Ho-Oh (Navel Rock) and Deoxys (Birth
  Island) are therefore **available today** in that column, not ended events.
  Source: news coverage from February 2026 of a speedrunner's playthrough;
  several outlets noted official confirmation was pending.
- Virtual Console Crystal is believed to include the Celebi event in-game.
  From memory, unverified.
- In every *original* release, encounters that needed a distributed ticket or
  item are ended events and must be marked as such, even though PKHeX lists
  them as ordinary static encounters.

The builder checks first whether the PKHeX version in use already models
these re-releases, and keeps the hand list only for what it does not.

Each column header carries a short "route to HOME" note (for example
"3DS → Pokémon Bank → HOME" or "direct"), because a Pokémon that can be caught
but not moved is useless to a collector. This is about twenty facts, kept by
hand in one file. The FRLG Switch → HOME route was announced by Nintendo and
reported as starting October 2026; **whether it is live is unconfirmed** and
the note must say so until checked. *(My call to include these notes.)*

## Cells

A cell answers: in this game group, how do I get this exact form?

- Content: one or more entries of **method + place + version mark**.
- Methods, as labels: Wild, Static, Gift, In-game trade, Raid, Evolve, Breed,
  Form change, Event, GO, HOME gift.
- Version mark: shown when an entry applies to only some versions of the
  group, for example `[Sw]`, `[LG]`, `[Y]`. No mark means all versions.
- DLC entries name the DLC.
- Anything that can no longer be obtained by a new player is marked as such:
  ended events, time-limited raid distributions, shut-down services (for
  example Black/White's Dream World). They still count as obtainable, per the
  owner, but must be visibly different from things available today.
- `–` means not obtainable in that game group.
- PKHeX often returns dozens of places (Pikachu has 65 in Scarlet/Violet).
  The cell shows the most useful few and a "+N" count; the full list opens on
  click. Ordering rule *(my call)*: currently-available methods before ended
  ones; within that Wild, Static, Gift, In-game trade, Raid, Evolve, Breed.

### Rules that turn PKHeX data into "obtainable"

PKHeX answers "what origin is legal", which is close to but not the same as
"what can I get". The spike found these gaps; each needs an explicit rule.

1. **Breed.** PKHeX lists an egg for any species that can legally hatch in a
   game, even when the game has no parent to breed from (Kantonian Meowth
   shows as an egg in Sun/Moon). Rule: Breed counts only when some member of
   the same evolution family, in the same form line, is obtainable in that
   game group by a non-breed method.
2. **Evolve.** A form with no direct encounter is obtainable by Evolve when a
   pre-evolution is obtainable in that game group and the evolution can be
   done inside that game. Evolutions that need a trade are labelled as such.
3. **Scarlet/Violet exclusives.** PKHeX marks wild encounters there as "SV"
   for both versions, so Larvitar (Scarlet) and Bagon (Violet) look
   non-exclusive. Generations 1–8 come out correct. Fix with a hand-kept list
   of Scarlet-only and Violet-only species/forms, unless the builder finds the
   version gate inside PKHeX.
4. **Forms not decided by the encounter.** Alcremie (how it is spun), Rotom
   (item), Vivillon (the console's region), Unown (random or by room) and
   similar: PKHeX returns the base Pokémon or a "random form" marker. A
   hand-kept rule file gives the method text per form and game for these
   species.
5. **Gender differences.** Not present in encounter data. Both gender rows
   take the species' cells; fixed-gender encounters are respected. The list
   of species with a visible gender difference comes from another open
   source (builder's choice).
6. **Older games and forms.** Save formats before generation 6 have no form
   field for most species, so asking for "Alolan Meowth in Red" returns plain
   Meowth. Only accept an encounter when its species and form match the row,
   and only for games where that form exists.
7. **Event names.** Use the event's own title when the gift data has one;
   otherwise "Event".

8. **Forms that do not survive the trip to HOME.** A cell describes the game
   itself: can the form be obtained there. Some forms are lost when moved
   onward (for example a form that the game sets rather than the Pokémon
   carrying it). Where that is known, the form rule file adds a visible
   "does not carry to HOME" note to the cell. This is not a full model of
   every transfer step. *(My call, raised by the reviewer.)*

### Who writes the hand-kept facts

All hand-kept rule files live in one folder and are plain text a person can
edit. *(My call, raised by the reviewer:)*

- The builder drafts each entry from PKHeX output and general knowledge of
  the games. Nothing is fetched automatically from Bulbapedia or Serebii.
- Every entry carries a `verified` field, false when drafted, plus where and
  by whom it was checked once it is.
- The owner verifies entries by eye against Bulbapedia, Serebii or the HOME
  app, and flips the field.
- The page shows a small "unverified" mark on any cell that depends on an
  unverified entry, so a guess never looks like a fact.

## The page

A static page served over HTTP from this server (see Constraints). The page
and the data are separate files, so rebuilding the data never touches the
page. No application server and no database: the server only hands out files.

```
[ I own: (Sword) (Violet) (FireRed) ( Shield ) ( Scarlet ) ... ]   [search]  [hide ticked]

☐  #    Name      Form       Mega  Gmax | FRLG              | SwSh                    | SV
☑  025  Pikachu   Male        –    Yes  | Wild: Viridian F. | Static: Rolling Fields  | Wild: South Prov. 2 +64
☐  052  Meowth    Alolan      –    –    | –                 | Static: Fields of Honor | In-game trade
                                                              (Isle of Armor)
☐  052  Meowth    Galarian    –    –    | –                 | Raid: Max Raid dens +3  | Static: Uva Academy [V]
☐  999  Gimmighoul Roaming    –    –    | –                 | –                       | –        … Other: GO only
```

- The tick, number, name and form columns stay pinned while scrolling sideways.
- "I own" lists every individual version. Ticking versions shows only the
  game groups that contain one of them, and inside a shown column, entries for
  versions the owner does not have are dimmed, not hidden. With nothing
  ticked, all columns show.
- A row obtainable in none of the owned games says so plainly and names where
  it is available.
- Search by name or number; a toggle to hide rows already ticked; a count of
  ticked rows out of the total.
- Ticks and the "I own" selection are kept in the browser, tied to the page's
  address, so they survive every rebuild. Because browser storage can be
  wiped and is separate per device, the page has Export and Import of the
  owner's state as a file. Keeping ticks on the server instead was considered
  and left out: it needs a writing server, which the static setup avoids.
  *(My call.)*
- Rows are keyed by a stable id (species + form + gender), so a rebuilt data
  file never shifts ticks onto the wrong row.

## How it fits together

```
PKHeX.Core ──▶ exporter (.NET) ──▶ raw encounters ─┐
                                                   ├─▶ build step ──▶ data file ─┐
hand-kept rule files (exclusives, forms, routes) ──┘                             ├─▶ static server :8507 ──▶ browser
                                                                    page file ───┘
```

- **Exporter** — the only part that must be .NET. Walks every species and form
  through every game group and writes what PKHeX returns, untouched.
- **Build step** — applies the rules above, shortens cells, writes the page.
- **Rule files** — the hand-kept facts.
- Re-running the exporter with a newer PKHeX version is how new games and new
  events arrive.

## Checking it is right

- The spike's verified cases become automated checks that must stay true, for
  example: Galarian Farfetch'd is Sword-only; Galarian Ponyta is Shield-only;
  Oddish is FireRed-only and Bellsprout LeafGreen-only; Deoxys is Attack in
  FireRed, Defense in LeafGreen, Speed in Emerald; Alolan Meowth in
  Sword/Shield is a static at Fields of Honor; Bloodmoon Ursaluna is a static
  at Timeless Woods; Roaming Gimmighoul is GO only; Original Color Magearna is
  a HOME gift; Kantonian Meowth is **not** obtainable in Sun/Moon; Larvitar is
  Scarlet-only and Bagon Violet-only.
- Structural checks: every species from 1 to the current maximum has at least
  one row; no row is `–` in every column including Other without being listed
  as a known exception; every version mark names a real version of its group.
- The owner spot-checks a handful of rows against Bulbapedia by eye. Spike
  results so far were compared with memory only, not with the wiki.

## Left to the builder

- Language and layout of the build step, file formats, how the exporter is
  structured.
- Where .NET is installed (user-local is fine; no system-wide install needed).
- Source for the gender-difference list and for Mega / Gmax flags (PKHeX
  itself if it has them, otherwise another open dataset with a GPL-compatible
  licence).
- Exact wording of method labels, version marks and the "no longer available"
  marker; visual styling.
- How many places a cell shows before "+N".
- Whether to dig the Scarlet/Violet version gate out of PKHeX or keep the
  hand list.

## Open risks

- Accuracy rests on PKHeX plus hand rules. PKHeX is built for legality
  checking and is kept current, but the rules in "Gaps" are new work and are
  where mistakes will hide.
- Generation 1–2 output has not been examined closely (Japanese versions mix
  into the results).
- Evolution across forms (for example which game lets Pikachu become Alolan
  Raichu) was not exercised in the spike.
- If the project is ever published, its source must be published under GPL and
  the no-copied-text rule must have been kept from the start.
