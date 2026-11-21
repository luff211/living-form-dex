"""Decide which rows exist and in what order."""
from .model import LeftOut, Row
from .rules import Rules


def build_rows(raw: dict, rules: Rules) -> tuple[list[Row], list[LeftOut]]:
    excluded = {}  # (species, form) -> rule entry
    for e in rules.forms["exclude"]["entries"]:
        for f in range(e["forms"][0], e["forms"][1] + 1):
            excluded[(e["species"], f)] = e

    variants = {e["species"]: e["names"] for e in rules.forms.get("variants", {"entries": []})["entries"]}
    rows, left = [], []
    for sp in raw["species"]:
        sid = sp["id"]
        mine = []
        for f in sp["forms"]:
            if f["battle_only"] or f["fused"]:
                continue
            rule = excluded.get((sid, f["form"]))
            if rule:
                left.append(LeftOut(sid, f["form"], sp["name"], f["name"], rule["reason"], rule["verified"]))
                continue
            both = (sid in rules.gender_diff and f["form"] == 0) or (sid, f["form"]) in rules.gender_diff_forms
            genders = ("m", "f") if both else (None,)
            for g in genders:
                label = {"m": "Male", "f": "Female"}.get(g)
                name = f["name"] if not label else f"{f['name']}, {label}" if f["name"] else label
                mine.append((f["form"], g, name))
        for form, g, name in mine:
            spec = rules.gmax.get(sid, False)   # False: no Gmax; None: form 0 only
            gmax = spec is not False and (spec == "all" or form in (spec or [0]))
            base_id = f"{sid:04d}-{form}" + (f"-{g}" if g else "")
            for v in variants.get(sid, [None]):
                label = "" if len(mine) == 1 and not v else ", ".join(x for x in (name, v) if x)
                rows.append(Row(
                    id=base_id + (f"-{v.split()[0].lower()}" if v else ""),
                    dex=sid, name=sp["name"], form_name=label,
                    species=sid, form=form, gender=g,
                    mega=list(raw["megas"].get(str(sid), [])) if form in rules.mega_forms.get(sid, [0]) else [],
                    gmax=gmax, gmax_unverified=gmax and sid in rules.gmax_unverified, variant=v))
    rows.sort(key=lambda r: (r.dex, r.form, r.gender == "f"))
    return rows, left
