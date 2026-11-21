# Living form dex

**Open it: https://luff211.github.io/living-form-dex/**

A checklist for a Pokémon *living form dex*: every species and every form, one row each, in National Dex order. For each row it shows where that form can actually be obtained in every main-series game, from Red / Blue / Yellow to the latest release.

## How to use

- **I own:** pick the games you have. Only their columns are shown, and rows you cannot get in them say where else they are available (naming the exact version when only one version of a pair has it).
- **Tick** a row when you have caught that form. The counter shows ticked / total. **Hide ticked** shows only what is left.
- **Search** by name, form or dex number (`25`, `025`, `galar meowth`).
- Ticks and owned games are saved in your browser only. Use **Export** to save them to a file and **Import** to load them on another browser or device.
- Each cell lists how to get the form: wild area, static encounter, gift, trade, evolve, breed and so on. Long cells show the first three; click `+N` for the rest. Letters in brackets (for example `[S]`) mark a version exclusive.
- Tags on an entry:
  - **ended**: the route existed but is gone, such as a past distribution event or a closed online service.
  - **needs another game or player**: the route needs a second game, a trade or another player (Friend Safari, paired-game unlocks, sold only in the other version).
  - **unverified**: not yet checked by hand against a game guide.
- The **Mega** and **Gmax** columns show whether the form has a Mega Evolution or a Gigantamax form.

## What "obtainable" means

A form counts as obtainable in a game if a player who starts that one game alone can get it today. That rules out trades and other players, other games, and events that have ended. Such routes are still listed, but tagged, so you can see how they used to work. Forms that Pokémon HOME cannot hold (battle-only forms, for example) are not rows.

## Data and accuracy

Encounter, evolution and form data come from [PKHeX.Core](https://github.com/kwsch/PKHeX). PKHeX checks whether a Pokémon is *legal*, which is looser than *obtainable*: it accepts anything that could have been traded in or received from an event. Hand-kept rules in `rules/` correct this, for example for version-specific fossils, ended events and Pokéwalker courses. The rules were checked against game guides and wikis, but mistakes are likely. If you find one, please [open an issue](https://github.com/luff211/living-form-dex/issues) naming the row, the game and a source.

Sprites are loaded from [PokeAPI/sprites](https://github.com/PokeAPI/sprites) on GitHub (`tools/sprites.py` picks one per row and checks it exists). Place names link to [Serebii PokéEarth](https://www.serebii.net/pokearth/) where Serebii has a page for that place (`tools/serebii-links.py`).

## Building it yourself

Pipeline: .NET exporter (PKHeX data) → `build/raw.json` → Python build step (stdlib only) → static page in `site/`.

Needs the .NET 10 SDK (`dotnet` on your PATH; the first run downloads PKHeX.Core from NuGet), Python 3 and Node 18 or later (for the page tests). Run the exporter first: the builder tests read `build/raw.json`.

```sh
dotnet run --project exporter -- rules/games.json build/raw.json      # about 25 s
PYTHONPATH=builder python3 -m dexbuild --raw build/raw.json --rules rules --out site/data/dex.json --write
(cd builder && python3 -m unittest discover -s tests)
(cd site && node --test tests/)
python3 -m http.server 8000 --bind 127.0.0.1 --directory site          # then open http://localhost:8000/
```

Without `--write` the build only prints its report (rows, left out, unverified cells, problems); it writes only when there are no problems. It writes `site/data/dex.json` and a gzipped copy, `dex.json.gz`, which is what the page fetches (about 270 KB instead of 6.9 MB; the browser unzips it with `DecompressionStream`).

### Maintainer notes

- **GitHub Pages:** after a `--write` build, run `deploy/publish-pages.sh` from the repo root. It pushes the page files and `dex.json.gz` to the `gh-pages` branch.
- **Private copy:** `deploy/living-form-dex.service` is a systemd user unit that serves `site/` on port 8507, bound to a Tailscale address only. Put `BIND=<tailscale-ip>` in `~/.config/living-form-dex.env`, symlink the unit into `~/.config/systemd/user/`, then run `systemctl --user daemon-reload && systemctl --user enable --now living-form-dex.service`. Ticks are saved per site, so use Export / Import to move them between this copy and GitHub Pages.

## Licence

GPL-3.0-or-later (see `LICENSE`), because it builds on PKHeX.Core.

This is an unofficial fan project, not affiliated with or endorsed by Nintendo, Game Freak, Creatures or The Pokémon Company. Pokémon and its names are trademarks of their respective owners.
