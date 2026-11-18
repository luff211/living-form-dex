"""Add Evolve and Breed entries: forms a player can reach in a game by evolving or breeding."""
from .model import Entry

# A route is {version: class}. A class says how good the way into that version is; lower is better:
# live before needs-another-game before ended, verified before unverified, base game before DLC.


def _cls(e):
    return (e.ended, e.needs_other_game, e.unverified, e.dlc is not None, e.dlc or "")


def _agg(routes):
    """Merge routes into one: each version keeps the best class any route gives it."""
    out = {}
    for r in routes:
        for v, c in r.items():
            if v not in out or c < out[v]:
                out[v] = c
    return out


def _limit(route, only):
    return route if only is None else {v: c for v, c in route.items() if v in only}


def _entries(method, place, route, order):
    by_cls = {}
    for v, c in route.items():
        by_cls.setdefault(c, set()).add(v)
    return [Entry(method, place, tuple(sorted(vs, key=lambda v: order.get(v, len(order)))), dlc or None,
                  ended, unv, needs_other_game=needs)
            for (ended, needs, unv, _, dlc), vs in sorted(by_cls.items())]


# Egg kin: (female species, male species) whose eggs can hatch as either one.
_EGG_KIN = ((29, 32), (314, 313))
# shortcut: before Generation 5 only the female side lays both, so there the male side never yields the female one
_FEMALE_ONLY_LAYS_BOTH = {"GSC", "RSE", "FRLG", "DPPt", "HGSS"}


def _kin(key, group):
    """Other species whose family can lay an egg that hatches as `key`."""
    for f, m in _EGG_KIN:
        if key == (m, 0):
            yield (f, 0)
        if key == (f, 0) and group not in _FEMALE_ONLY_LAYS_BOTH:
            yield (m, 0)


def _family(edges):
    comp = {}
    for a, b, *_ in edges:
        merged = comp.get(a, {a}) | comp.get(b, {b})
        for m in merged:
            comp[m] = merged
    return comp


def _group(direct_g, edges, eggs, names, order, no_derive, group=""):
    # allr: every route to a key; solid: routes that do not depend on Breed
    base = {k: [{v: _cls(e) for v in e.versions} for e in es] for k, es in direct_g.items()}
    edges = [x for x in edges if x[1] not in no_derive]
    family = _family(edges)
    allr, solid = base, base
    while True:   # terminates: each version's best class only improves, and classes are finite
        evo, breed = {}, {}
        n_all = {k: list(r) for k, r in base.items()}
        n_solid = {k: list(r) for k, r in base.items()}
        for a, b, trade, only in edges:   # only: the versions this evolution happens in (None = all)
            if a in allr and (r := _limit(_agg(allr[a]), only)):
                evo.setdefault(b, {})[(a, trade)] = r
                n_all.setdefault(b, []).append(r)
            if a in solid and (r := _limit(_agg(solid[a]), only)):
                n_solid.setdefault(b, []).append(r)
        for key, egg_vs in eggs.items():
            if key in no_derive:
                continue
            layers = set().union(*(family.get(k, {k}) for k in (key, *_kin(key, group))))
            parents = _agg(r for m in layers for r in solid.get(m, []))
            route = {v: c for v, c in parents.items() if v in egg_vs}
            if route:
                breed[key] = route
                n_all.setdefault(key, []).append(route)
        if (n_all, n_solid) == (allr, solid) and allr is not base:
            break
        allr, solid = n_all, n_solid
    out = {}
    for b, pres in evo.items():
        for (a, trade), route in pres.items():
            place = names[a[0]] + (" (trade)" if trade else "")
            out.setdefault(b, []).extend(_entries("Evolve", place, route, order))
    for key, route in breed.items():
        out.setdefault(key, []).extend(_entries("Breed", names[key[0]], route, order))
    return out


def add_evolve_and_breed(direct: dict, raw: dict, rules=None, no_derive=frozenset()) -> dict:
    """Return a new dict: `direct` plus Evolve/Breed entries. Group GO is passed through untouched.

    Version order comes from rules.games when given; otherwise from first appearance in the source entries.
    No Evolve or Breed entry is made for a (species, form) in `no_derive` (rules.no_spread when rules are given).
    """
    if rules is not None:
        no_derive = rules.no_spread
    names = {s["id"]: s["name"] for s in raw["species"]}
    groups = {k[0] for k in direct} | {e["group"] for e in raw["evolutions"]} | {e["group"] for e in raw["encounters"]}
    groups.discard("GO")
    result = {k: list(v) for k, v in direct.items()}
    for g in sorted(groups):
        if rules is not None:
            gm = next((x for x in rules.games["groups"] if x["id"] == g), None)
            order = {v["code"]: i for i, v in enumerate(gm["versions"])} if gm else {}
        else:
            order = {}
            for k, es in direct.items():
                if k[0] == g:
                    for e in es:
                        for v in e.versions:
                            order.setdefault(v, len(order))
        direct_g = {(k[1], k[2]): es for k, es in direct.items() if k[0] == g}
        edges = [((e["from"][0], e["from"][1]), (e["to"][0], e["to"][1]), e["trade"], e.get("versions"))
                 for e in raw["evolutions"] if e["group"] == g]
        eggs = {}
        for e in raw["encounters"]:
            if e["egg"] and e["group"] == g:
                eggs.setdefault((e["species"], e["form"]), set()).update(e["versions"])
        for (sid, form), es in _group(direct_g, edges, eggs, names, order, no_derive, g).items():
            cur = result.setdefault((g, sid, form), [])
            cur.extend(x for x in es if x not in cur)
    return dict(sorted(result.items()))
