"""Load and validate the hand-kept rule files in rules/."""
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

SPRITE_BASE = "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/"


class RulesError(Exception):
    pass


@dataclass
class Rules:
    games: dict
    forms: dict
    sv_exclusives: list
    releases: list
    dlc: list
    gmax: dict[int, list[int] | str | None]   # species -> forms with a Gmax: None = form 0 only, a list, or "all"
    gmax_unverified: set[int]
    gender_diff: set[int]
    gender_diff_forms: set[tuple[int, int]] = field(default_factory=set)   # (species, form) with a gender difference besides form 0
    no_source: set[tuple[int, int]] = field(default_factory=set)   # (species, form) rows known to have no source
    no_spread: set[tuple[int, int]] = field(default_factory=set)   # (species, form) never given "Form varies" or Evolve/Breed
    mega_forms: dict[int, list[int]] = field(default_factory=dict)   # species -> forms that have the Mega (default form 0)
    serebii: dict[str, dict[str, str]] = field(default_factory=dict)   # group -> place -> PokéEarth URL
    sprite_base: str = ""                                                # sprites: row id -> image path under the base
    sprites: dict[str, str] = field(default_factory=dict)


def _read(rules_dir, name):
    try:
        return json.loads((rules_dir / name).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise RulesError(f"{name}: {e}") from None


def _require(cond, where, msg):
    if not cond:
        raise RulesError(f"{where}: {msg}")


def _check_flags(obj, where):
    _require(isinstance(obj, dict), where, "must be an object")
    _require(isinstance(obj.get("verified"), bool), where, "needs a boolean 'verified'")
    _require(isinstance(obj.get("checked"), str), where, "needs a string 'checked'")


def _entries(data, name):
    """Return data['entries'] after checking every entry carries the verified flags."""
    _require(isinstance(data, dict) and isinstance(data.get("entries"), list), name, "needs an 'entries' list")
    for i, e in enumerate(data["entries"]):
        _check_flags(e, f"{name} entry {i} {json.dumps(e, ensure_ascii=False)}")
    return data["entries"]


def _check_games(games):
    groups = games.get("groups") if isinstance(games, dict) else None
    _require(isinstance(groups, list) and groups, "games.json", "needs a non-empty 'groups' list")
    ids, codes = set(), set()
    for g in groups:
        where = f"games.json group {g.get('id')!r}" if isinstance(g, dict) else "games.json"
        _require(isinstance(g, dict) and isinstance(g.get("id"), str) and isinstance(g.get("label"), str),
                 where, "needs string 'id' and 'label'")
        _require(g["id"] not in ids, where, "duplicate group id")
        ids.add(g["id"])
        _require(isinstance(g.get("versions"), list) and g["versions"], where, "needs a non-empty 'versions' list")
        for v in g["versions"]:
            _require(isinstance(v, dict) and all(isinstance(v.get(k), str) for k in ("code", "label", "mark")),
                     where, f"version {v} needs string 'code', 'label' and 'mark'")
            _require(v["code"] not in codes, where, f"duplicate version code {v['code']}")
            codes.add(v["code"])
        if not g.get("other"):
            _require("home_route" in g, where, "needs a 'home_route'")
            _check_flags(g["home_route"], f"{where} home_route")
            _require(isinstance(g["home_route"].get("text"), str), f"{where} home_route", "needs a string 'text'")
    return {g["id"]: [v["code"] for v in g["versions"]] for g in groups}


def _int_list(x):
    return isinstance(x, list) and all(isinstance(y, int) for y in x)


def _check_group(e, where, versions_of):
    _require(e.get("group") in versions_of, where, f"unknown group {e.get('group')!r}")


def _check_species(e, where):
    _require(isinstance(e.get("species"), int), where, "needs an integer 'species'")


def _check_form(e, where):
    _require(e.get("form") is None or isinstance(e.get("form"), int), where, "'form' must be an integer or null")


def load_rules(rules_dir: Path) -> Rules:
    rules_dir = Path(rules_dir)
    games = _read(rules_dir, "games.json")
    versions_of = _check_games(games)

    forms = _read(rules_dir, "forms.json")
    _require(isinstance(forms, dict), "forms.json", "must be an object")
    for section in ("exclude", "methods", "annotate"):
        name = f"forms.json {section}"
        for i, e in enumerate(_entries(forms.get(section), name)):
            where = f"{name} entry {i}"
            _check_species(e, where)
            if section == "exclude":
                r = e.get("forms")
                _require(isinstance(r, list) and len(r) == 2 and all(isinstance(x, int) for x in r) and r[0] <= r[1],
                         where, "'forms' must be [first, last]")
                continue
            _check_form(e, where)
            _check_group(e, where, versions_of)
            if section == "methods":
                for k in ("method", "place"):
                    _require(isinstance(e.get(k), str), where, f"needs a string '{k}'")
                vs = e.get("versions")
                _require(vs is None or isinstance(vs, list), where, "'versions' must be a list or null")
                for v in vs or []:
                    _require(v in versions_of[e["group"]], where, f"version {v!r} is not in group {e['group']}")
                for k in ("ended", "needs_other_game"):
                    _require(isinstance(e.get(k, False), bool), where, f"'{k}' must be a boolean")
            else:
                _require(isinstance(e.get("note"), str), where, "needs a string 'note'")

    no_source = forms.get("no_source", {"entries": []})
    for i, e in enumerate(_entries(no_source, "forms.json no_source")):
        where = f"forms.json no_source entry {i}"
        _check_species(e, where)
        _require(isinstance(e.get("form"), int), where, "needs an integer 'form'")
        _require(isinstance(e.get("reason"), str), where, "needs a string 'reason'")

    no_spread = forms.get("no_spread", {"entries": []})
    for i, e in enumerate(_entries(no_spread, "forms.json no_spread")):
        where = f"forms.json no_spread entry {i}"
        _check_species(e, where)
        _require(isinstance(e.get("form"), int), where, "needs an integer 'form'")
        _require(isinstance(e.get("reason"), str), where, "needs a string 'reason'")

    for i, e in enumerate(_entries(forms.get("form_varies", {"entries": []}), "forms.json form_varies")):
        where = f"forms.json form_varies entry {i}"
        _check_species(e, where)
        _require(e.get("group") in versions_of, where, "unknown 'group'")
        _require(isinstance(e.get("note"), str) and e["note"], where, "needs a string 'note'")

    for i, e in enumerate(_entries(forms.get("merge", {"entries": []}), "forms.json merge")):
        where = f"forms.json merge entry {i}"
        _check_species(e, where)
        _require(_int_list(e.get("forms")) and isinstance(e.get("into"), int) and e["into"] not in e["forms"], where,
                 "'forms' must be a list of integers and 'into' another integer form")
        _require(isinstance(e.get("reason"), str) and e["reason"], where, "needs a string 'reason'")

    for i, e in enumerate(_entries(forms.get("variants", {"entries": []}), "forms.json variants")):
        where = f"forms.json variants entry {i}"
        _check_species(e, where)
        _require(isinstance(e.get("names"), list) and len(e["names"]) > 1 and all(isinstance(n, str) and n for n in e["names"])
                 and len(set(e["names"])) == len(e["names"]), where, "'names' must be two or more distinct strings")
        _require(isinstance(e.get("note"), str) and "{name}" in e["note"], where, "'note' must be a string holding {name}")

    mega_forms = forms.get("mega_forms", {"entries": []})
    for i, e in enumerate(_entries(mega_forms, "forms.json mega_forms")):
        where = f"forms.json mega_forms entry {i}"
        _check_species(e, where)
        _require(_int_list(e.get("forms")), where, "'forms' must be a list of integers")

    sv = _entries(_read(rules_dir, "sv_exclusives.json"), "sv_exclusives.json")
    for i, e in enumerate(sv):
        where = f"sv_exclusives.json entry {i}"
        _check_species(e, where)
        _check_form(e, where)
        _require(e.get("version") in versions_of["SV"], where, f"version {e.get('version')!r} is not in group SV")

    releases = _entries(_read(rules_dir, "releases.json"), "releases.json")
    for i, e in enumerate(releases):
        where = f"releases.json entry {i}"
        _check_group(e, where, versions_of)
        _require(e.get("species") is None or isinstance(e["species"], int), where, "'species' must be an integer or null (any)")
        _require(isinstance(e.get("location_contains"), str), where, "needs a string 'location_contains'")
        s = e.get("set")
        _require(isinstance(s, dict) and s and set(s) <= {"ended", "method", "note", "needs_other_game", "drop"}, where,
                 "'set' must hold only 'ended', 'method', 'note', 'needs_other_game', 'drop'")
        for k in ("ended", "needs_other_game", "drop"):
            _require(isinstance(s.get(k, False), bool), where, f"'{k}' must be a boolean")
        _require("versions" not in e or (isinstance(e["versions"], list) and set(e["versions"]) <= set(versions_of[e["group"]])),
                 where, "'versions' must list versions of the group")

    dlc = _entries(_read(rules_dir, "dlc.json"), "dlc.json")
    for i, e in enumerate(dlc):
        where = f"dlc.json entry {i}"
        _check_group(e, where, versions_of)
        _require(isinstance(e.get("dlc"), str), where, "needs a string 'dlc'")
        _require("locations" in e or "species" in e, where, "needs 'locations' or 'species'")
        if "locations" in e:
            _require(isinstance(e["locations"], list) and all(isinstance(x, str) for x in e["locations"]),
                     where, "'locations' must be a list of strings")
        if "species" in e:
            _require(_int_list(e["species"]), where, "'species' must be a list of integers")
            _check_form(e, where)
            _require(e.get("method") is None or isinstance(e["method"], str), where, "'method' must be a string")

    gmax_entries = _entries(_read(rules_dir, "gmax.json"), "gmax.json")
    for i, e in enumerate(gmax_entries):
        _check_species(e, f"gmax.json entry {i}")
        f = e.get("forms")
        _require(f is None or f == "all" or _int_list(f), f"gmax.json entry {i}", "'forms' must be a list of integers or \"all\"")

    gd = _read(rules_dir, "gender_diff.json")
    _require(isinstance(gd, dict) and isinstance(gd.get("source"), str), "gender_diff.json", "needs a string 'source'")
    for k in ("species", "form_is_gender"):
        _require(isinstance(gd.get(k), list) and all(isinstance(x, int) for x in gd[k]),
                 "gender_diff.json", f"'{k}' must be a list of integers")

    also = gd.get("also_forms", [])
    _require(isinstance(also, list) and all(isinstance(x, list) and len(x) == 2 and all(isinstance(y, int) for y in x)
                                            for x in also),
             "gender_diff.json", "'also_forms' must be a list of [species, form] integer pairs")

    serebii = {}
    if (rules_dir / "serebii.json").exists():   # optional: written by tools/serebii-links.py
        links = _read(rules_dir, "serebii.json").get("links")
        _require(isinstance(links, dict), "serebii.json", "needs a 'links' object")
        group_ids = set(versions_of)
        for g, places in links.items():
            _require(g in group_ids, f"serebii.json group {g!r}", "is not a group in games.json")
            _require(isinstance(places, dict) and all(
                isinstance(u, str) and u.startswith("https://www.serebii.net/pokearth/") for u in places.values()),
                f"serebii.json group {g!r}", "must map place names to https://www.serebii.net/pokearth/ URLs")
        serebii = links

    sprite_base, sprites = "", {}
    if (rules_dir / "sprites.json").exists():   # optional: written by tools/sprites.py
        sp = _read(rules_dir, "sprites.json")
        _require(sp.get("base") == SPRITE_BASE, "sprites.json", f"'base' must be {SPRITE_BASE}")
        _require(isinstance(sp.get("sprites"), dict) and all(
            isinstance(v, str) and re.fullmatch(r"(female/)?[0-9]+(-[a-z0-9-]+)?\.png", v) for v in sp["sprites"].values()),
            "sprites.json", "'sprites' must map row ids to PokeAPI sprite file names")
        sprite_base, sprites = sp["base"], sp["sprites"]

    return Rules(
        games=games,
        forms=forms,
        sv_exclusives=sv,
        releases=releases,
        dlc=dlc,
        gmax={e["species"]: e.get("forms") for e in gmax_entries},
        gmax_unverified={e["species"] for e in gmax_entries if not e["verified"]},
        # form_is_gender species already have one row per gender form, so no extra -m/-f rows
        gender_diff=set(gd["species"]) - set(gd["form_is_gender"]),
        gender_diff_forms={(a, b) for a, b in also},
        no_source={(e["species"], e["form"]) for e in no_source["entries"]},
        no_spread={(e["species"], e["form"]) for e in no_spread["entries"]},
        mega_forms={e["species"]: e["forms"] for e in mega_forms["entries"]},
        serebii=serebii,
        sprite_base=sprite_base,
        sprites=sprites,
    )
