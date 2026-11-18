"""Structural checks on assembled rows. Each problem is one string naming the row."""


def structural_problems(rows, rules, raw) -> list[str]:
    codes = {g["id"]: {v["code"] for v in g["versions"]} for g in rules.games["groups"]}
    explained = {(m["species"], m["form"]) for m in rules.forms["methods"]["entries"]} | rules.no_source
    problems, seen = [], set()
    for r in rows:
        if r.id in seen:
            problems.append(f"{r.id}: duplicate row id")
        seen.add(r.id)
        if not r.cells and not r.other and (r.species, r.form) not in explained \
                and (r.species, None) not in explained:
            problems.append(f"{r.id} ({r.name} {r.form_name}".rstrip() + "): no source in any game and nothing in Other")
        for g, es in r.cells.items():
            for e in es:
                bad = set(e.versions) - codes[g]
                if bad:
                    problems.append(f"{r.id}: {g} entry {e.method} {e.place!r} has versions {sorted(bad)} outside the group")
    have = {r.dex for r in rows}
    for n in range(1, max(s["id"] for s in raw["species"]) + 1):
        if n not in have:
            problems.append(f"dex {n}: no row")
    return problems
