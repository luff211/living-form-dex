#!/usr/bin/env python3
"""Pick a PokeAPI sprite for every dex row and check each one exists.

Reads PokeAPI's pokemon.csv and pokemon_forms.csv (downloaded once into build/pokeapi/) and site/data/dex.json.
A row's form is matched to a PokeAPI form by name first (form labels differ in order between PKHeX and PokeAPI),
then by position. Every chosen image is checked with a HEAD request (results cached in build/sprites-head.json).
Report-only; with --write, writes rules/sprites.json. The site loads the images from BASE.
"""
import argparse, csv, json, re, sys, time, urllib.error, urllib.request
from pathlib import Path

BASE = "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/"
CSV = "https://raw.githubusercontent.com/PokeAPI/pokeapi/master/data/v2/csv/"
DIR = Path("build/pokeapi")
HEADS = Path("build/sprites-head.json")
UA = "living-form-dex sprite check"
ALIASES = {"medium": "average", "jumbo": "super"}  # PKHeX label -> PokeAPI form name
SAME_AS_BASE = {414}  # Mothim: PKHeX keeps Burmy's cloak as a form, but every Mothim looks the same


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower().replace("é", "e"))


def load_forms() -> dict[int, list[dict]]:
    """species -> PokeAPI forms that are not Megas or Gigantamax, in PokeAPI order."""
    for name in ("pokemon", "pokemon_forms"):
        p = DIR / f"{name}.csv"
        if not p.exists():
            DIR.mkdir(parents=True, exist_ok=True)
            req = urllib.request.Request(CSV + p.name, headers={"User-Agent": UA})
            p.write_bytes(urllib.request.urlopen(req, timeout=60).read())
    species_of = {r["id"]: int(r["species_id"]) for r in csv.DictReader(open(DIR / "pokemon.csv", encoding="utf-8"))}
    forms: dict[int, list[dict]] = {}
    for r in csv.DictReader(open(DIR / "pokemon_forms.csv", encoding="utf-8")):
        if r["is_mega"] == "0" and "gmax" not in r["form_identifier"]:
            forms.setdefault(species_of[r["pokemon_id"]], []).append(r)
    for fs in forms.values():
        fs.sort(key=lambda r: int(r["order"]))
    return forms


def sprite_path(form: dict, species: int) -> str:
    if int(form["pokemon_id"]) != species:      # a form with its own Pokémon entry (regional forms, ...)
        return f"{form['pokemon_id']}.png"
    return f"{species}-{form['form_identifier']}.png" if form["form_identifier"] and form["is_default"] == "0" \
        else f"{species}.png"


def pick(row: dict, forms: dict[int, list[dict]]) -> str | None:
    species, form_no, *gender = row["id"].split("-")
    species, form_no = int(species), int(form_no)
    label = "" if row["form"] in ("Male", "Female") else row["form"]
    if species in SAME_AS_BASE:
        form_no, label = 0, ""
    fs = forms.get(species, [])
    want = slug(ALIASES.get(label.lower(), label))
    named = [f for f in fs if want and want in slug(f["form_identifier"])]
    plain = [f for f in fs if f["is_battle_only"] == "0"]
    default = [f for f in fs if f["is_default"] == "1"][:1]
    form = named[0] if named else default[0] if form_no == 0 and not label and default \
        else plain[form_no] if form_no < len(plain) else None
    if form is None:
        return None
    path = sprite_path(form, species)
    return f"female/{path}" if gender == ["f"] else path


def exists(path: str, heads: dict) -> bool:
    if path not in heads:
        time.sleep(0.05)
        req = urllib.request.Request(BASE + path, method="HEAD", headers={"User-Agent": UA})
        try:
            urllib.request.urlopen(req, timeout=30)
            heads[path] = True
        except urllib.error.HTTPError as e:
            heads[path] = e.code != 404 and None   # None: not known, asked again next run
        except OSError:
            heads[path] = None
    return bool(heads[path])


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--write", action="store_true", help="write rules/sprites.json")
    a = ap.parse_args()
    assert slug("Poké Ball") == "pokeball" and ALIASES["jumbo"] == "super"
    forms = load_forms()
    dex = json.loads(Path("site/data/dex.json").read_text(encoding="utf-8"))
    heads = {k: v for k, v in json.loads(HEADS.read_text()).items() if v is not None} if HEADS.exists() else {}
    out, missing = {}, []
    try:
        for row in dex["rows"]:
            path = pick(row, forms)
            if path and path.startswith("female/") and not exists(path, heads):
                path = path[len("female/"):]   # no separate female image: the male one is the same drawing
            if path and exists(path, heads):
                out[row["id"]] = path
            else:
                missing.append(f"{row['id']}\t{row['name']}\t{row['form']}\t{path}")
    finally:
        HEADS.write_text(json.dumps(heads, indent=0, sort_keys=True))
    print(f"{len(out)} rows have a sprite, {len(missing)} do not")
    print("\n".join(missing))
    if a.write:
        Path("rules/sprites.json").write_text(json.dumps({"base": BASE, "sprites": out}, indent=1) + "\n", encoding="utf-8")
        print("wrote rules/sprites.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
