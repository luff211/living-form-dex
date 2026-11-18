#!/usr/bin/env python3
"""List species with a visible gender difference, from PokéAPI's species CSV.

Report-only by default: prints the species ids. With --write, replaces the
'species' list in rules/gender_diff.json and keeps 'form_is_gender' and 'also_forms'.
"""
import argparse
import csv
import io
import json
import urllib.request
from pathlib import Path

URL = "https://raw.githubusercontent.com/PokeAPI/pokeapi/master/data/v2/csv/pokemon_species.csv"
OUT = Path(__file__).resolve().parents[1] / "rules" / "gender_diff.json"
SOURCE = "PokéAPI pokemon_species.csv, column has_gender_differences"


def fetch_ids():
    req = urllib.request.Request(URL, headers={"User-Agent": "living-form-dex-builder"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        text = resp.read().decode("utf-8")
    rows = csv.DictReader(io.StringIO(text))
    ids = sorted(int(r["id"]) for r in rows if r["has_gender_differences"] == "1")
    if not ids:
        raise SystemExit("no species with gender differences found; CSV layout changed?")
    return ids


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--write", action="store_true", help=f"update {OUT}")
    args = ap.parse_args()
    ids = fetch_ids()
    print(f"{len(ids)} species: {ids}")
    if not args.write:
        print("report only; pass --write to update", OUT)
        return
    old = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    data = {"source": SOURCE, "species": ids, "form_is_gender": old.get("form_is_gender", []),
            "also_forms": old.get("also_forms", [])}
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
