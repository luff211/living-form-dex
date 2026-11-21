"""Join direct, Evolve and Breed entries with the hand-kept rules into finished rows and the dex.json shape."""
from dataclasses import replace

from .derive import add_evolve_and_breed
from .direct import direct_entries, dlc_for, sv_narrow
from .model import Entry, LeftOut, Row
from .rows import build_rows

_METHODS = ["Wild", "Static", "Gift", "In-game trade", "Raid", "Evolve", "Breed", "Form change", "Event"]
_GO = Entry("GO", "Pokémon GO → HOME", ())


def _matches(e, row, group):
    return e["species"] == row.species and e["group"] == group and e["form"] in (None, row.form)


def _tidy(entries, order):
    """Merge entries equal in everything but versions, then sort live first, by method, by place."""
    merged = {}
    for e in entries:
        k = replace(e, versions=(), gender=None)  # gender is filtered already and never output
        merged[k] = merged.get(k, set()) | set(e.versions)
    out = [replace(k, versions=tuple(sorted(v, key=lambda c: order.get(c, len(order))))) for k, v in merged.items()]
    return sorted(out, key=lambda e: (e.ended, e.needs_other_game, _METHODS.index(e.method) if e.method in _METHODS else len(_METHODS),
                                      e.place, e.versions))


def fill(rows: list[Row], entries: dict, rules) -> None:
    """Fill row.cells and row.other in place from `entries` (keyed (group, species, form))."""
    order = {g["id"]: {v["code"]: i for i, v in enumerate(g["versions"])} for g in rules.games["groups"]}
    mine = {g["id"]: [v["code"] for v in g["versions"]] for g in rules.games["groups"]}
    methods, notes = rules.forms["methods"]["entries"], rules.forms["annotate"]["entries"]
    variant_note = {e["species"]: e["note"] for e in rules.forms.get("variants", {"entries": []})["entries"]}
    for row in rows:
        def wanted(es):
            return [e for e in es if row.gender is None or e.gender in (None, row.gender)]

        for g in order:
            if g == "GO":
                continue
            cell = wanted(entries.get((g, row.species, row.form), []))
            rep = [m for m in methods if _matches(m, row, g)]
            if rep:
                cell = [Entry(m["method"], m["place"], tuple(m["versions"] or mine[g]), m.get("dlc"),
                              ended=m.get("ended", False), unverified=not m["verified"], note=m.get("note"),
                              needs_other_game=m.get("needs_other_game", False)) for m in rep]
            for a in (a for a in notes if _matches(a, row, g)):
                cell = [replace(e, note=f"{e.note}; {a['note']}" if e.note else a["note"],
                                unverified=e.unverified or not a["verified"]) for e in cell]
            if row.variant:   # the variant is chosen when it evolves or changes form, not by where it is found
                vn = variant_note[row.species].format(name=row.variant)
                cell = [replace(e, note=f"{e.note}; {vn}" if e.note else vn) if e.method in ("Evolve", "Form change")
                        else e for e in cell]
            cell = _tidy(cell, order[g])
            if cell:
                row.cells[g] = cell
        if not any(not e.ended and not e.needs_other_game for es in row.cells.values() for e in es):
            go = wanted(entries.get(("GO", row.species, row.form), []))
            row.other = _tidy([_GO if e.method == "GO" else e for e in go], {})


def derived_rules(entries: dict, rules) -> dict:
    """Apply species rules to Evolve/Breed entries: a DLC from dlc.json (e.g. an evolution item only in a DLC), and
    sv_exclusives (e.g. Armarouge from a Charcadet found in both versions)."""
    out = {}
    for (g, sid, form), es in entries.items():
        new = []
        for e in es:
            if e.method in ("Evolve", "Breed"):
                dlc, unv = (e.dlc, False) if e.dlc else dlc_for(rules.dlc, g, sid, form, e.method, "")
                vs, unv2 = sv_narrow(rules, g, sid, form, e.versions, e.ended)
                e = replace(e, dlc=dlc, versions=vs, unverified=e.unverified or unv or unv2)
            new.append(e)
        out[(g, sid, form)] = new
    return out


def merge_forms(entries: dict, rules) -> dict:
    """Move the entries of forms listed in forms.json merge onto the form they merge into. Done after Evolve and
    Breed are derived, so an evolution that needs the merged form (Own Tempo Rockruff -> Dusk Lycanroc) keeps it."""
    into = {(e["species"], f): e["into"] for e in rules.forms.get("merge", {"entries": []})["entries"] for f in e["forms"]}
    out = {}
    for (g, sid, form), es in entries.items():
        out.setdefault((g, sid, into.get((sid, form), form)), []).extend(es)
    return out


def assemble(raw: dict, rules) -> tuple[list[Row], list[LeftOut]]:
    rows, left = build_rows(raw, rules)
    entries = derived_rules(add_evolve_and_breed(direct_entries(raw, rules), raw, rules), rules)
    fill(rows, merge_forms(entries, rules), rules)
    return rows, left


def _entry_json(e: Entry) -> dict:
    return {"method": e.method, "place": e.place, "versions": list(e.versions), "dlc": e.dlc,
            "ended": e.ended, "unverified": e.unverified, "note": e.note, "needs_other_game": e.needs_other_game}


def to_json(rows: list[Row], rules, raw: dict) -> dict:
    groups = [g for g in rules.games["groups"] if not g.get("other")]
    order = [g["id"] for g in groups]
    return {
        "meta": {"pkhex": raw["pkhex"], "rows": len(rows), "sprite_base": rules.sprite_base},
        "groups": [{"id": g["id"], "label": g["label"],
                    "versions": [{k: v[k] for k in ("code", "label", "mark")} for v in g["versions"]],
                    "home_route": g["home_route"]["text"],
                    "home_route_unverified": not g["home_route"]["verified"],
                    "links": rules.serebii.get(g["id"], {})} for g in groups],
        "rows": [{"id": r.id, "dex": r.dex, "name": r.name, "form": r.form_name, "sprite": rules.sprites.get(r.id),
                  "mega": r.mega,
                  "gmax": r.gmax, "gmax_unverified": r.gmax_unverified,
                  "cells": {g: [_entry_json(e) for e in r.cells[g]] for g in order if g in r.cells},
                  "other": [_entry_json(e) for e in r.other]} for r in rows],
    }
