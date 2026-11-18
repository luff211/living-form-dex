"""Turn PKHeX's direct encounters into labelled Entry objects per (group, species, form)."""
from dataclasses import replace

from .kinds import method_for
from .model import Entry

_SWSH_DLC = (" (Isle of Armor)", " (Crown Tundra)")
_SV_RAID_DLC = {"Kitakami": "The Teal Mask", "Blueberry": "The Indigo Disk"}   # PKHeX's map name for a Tera raid den
_PLACEHOLDER_TITLES = ("This is a Dummy Card", "This is A Dummy Card", "Simulated ")   # PKHeX test cards, not event names


_ENGLISH = {"the", "a", "an", "is", "it's", "its", "of", "for", "and", "with", "from", "your", "you", "here", "get"}


def _title_score(t):
    # shortcut: guesses the English copy by common English words; PKHeX gives no card language for older gifts
    words = t.lower().replace("’", "'").split()
    return (-sum(w in _ENGLISH for w in words), not t.isascii(), t)


def _card_titles(encounters):
    """One title per (group, species, card id): language copies of one card collapse to its most English title."""
    titles = {}
    for e in encounters:
        if e.get("event_id") is not None and e["event_title"] and not e["event_title"].startswith(_PLACEHOLDER_TITLES):
            titles.setdefault((e["group"], e["species"], e["event_id"]), set()).add(e["event_title"])
    return {k: min(v, key=_title_score) for k, v in titles.items()}


def sv_narrow(rules, group, sid, form, versions, ended, method=None) -> tuple[tuple, bool]:
    """(versions, unverified): a live SV entry for both versions of a Scarlet- or Violet-only form keeps only its version.

    In-game trades are left alone: the same trades are offered in both versions."""
    if group == "SV" and not ended and method != "In-game trade" and set(versions) == {"SL", "VL"}:
        for r in rules.sv_exclusives:
            if r["species"] == sid and r["form"] in (None, form):
                return (r["version"],), not r["verified"]
    return versions, False


def dlc_for(dlc_rules, group, sid, form, method, loc) -> tuple[str | None, bool]:
    """(dlc, unverified) from dlc.json: an entry matches by location, or by species (optional form and method)."""
    for r in dlc_rules:
        if r["group"] != group:
            continue
        if loc in r.get("locations", ()) or (sid in r.get("species", ()) and r.get("form") in (None, form)
                                             and r.get("method") in (None, method)):
            return r["dlc"], not r["verified"]
    return None, False


def _forms_in_group(sp, group):
    present = [f["form"] for f in sp["forms"] if group in f["groups"]]
    if len(present) > 1:
        return present
    # old save formats only know form 0, so spread over every real form
    return [f["form"] for f in sp["forms"] if not f["battle_only"] and not f["fused"] and "pkhex_form" not in f]


def _sort_key(e):
    return (e.method, e.place, e.versions, e.dlc or "", e.ended, e.unverified, e.note or "", e.gender or "")


def direct_entries(raw: dict, rules) -> dict[tuple[str, int, int], list[Entry]]:
    species = {s["id"]: s for s in raw["species"]}
    has_method = {(m["species"], m["group"]) for m in rules.forms["methods"]["entries"]}
    out: dict[tuple[str, int, int], set[Entry]] = {}
    card_titles = _card_titles(raw["encounters"])

    for enc in raw["encounters"]:
        if enc["egg"] or enc["type"].startswith("EncounterEgg"):
            continue
        group, sid, loc = enc["group"], enc["species"], enc["location"] or ""
        method, ended = method_for(enc["type"], enc["label"])
        other = group == "GO" or (method == "Event" and loc == "Pokémon HOME")
        if group == "GO":
            method = "GO"
        elif other:
            method = "HOME gift"

        if method == "Event":
            place = enc["event_title"] or ""
            place = "" if place.startswith(_PLACEHOLDER_TITLES) else card_titles.get((group, sid, enc.get("event_id")), place)
            if place and enc.get("event_year"):
                place = f"{place} ({enc['event_year']})"
        else:
            place = loc
        # a release rule limited to some versions splits the encounter: (versions, method, ended, note, needs, unverified)
        parts = [(tuple(enc["versions"]), method, ended, None, False, False)]
        for r in rules.releases:
            if r["group"] == group and r["species"] in (None, sid) and r["location_contains"] in loc:
                s, new = r["set"], []
                for vs, m, en, no, ne, un in parts:
                    hit = tuple(v for v in vs if v in r.get("versions", vs))
                    miss = tuple(v for v in vs if v not in hit)
                    if hit and not s.get("drop"):   # drop: that version never had this encounter
                        new.append((hit, s.get("method", m), s.get("ended", en), s.get("note", no),
                                    s.get("needs_other_game", ne), un or not r["verified"]))
                    if miss:
                        new.append((miss, m, en, no, ne, un))
                parts = new
        for part in parts:
            _add(out, rules, species, has_method, enc, other, place, *part)

    return {k: sorted(v, key=_sort_key) for k, v in sorted(out.items())}


def _add(out, rules, species, has_method, enc, other, place, versions, method, ended, note, needs, unverified):
    group, sid, loc = enc["group"], enc["species"], enc["location"] or ""

    if enc["form_random"]:
        if (sid, group) in has_method:
            return
        forms = [f for f in _forms_in_group(species[sid], group) if (sid, f) not in rules.no_spread]
        rule = next((r for r in rules.forms.get("form_varies", {"entries": []})["entries"]
                     if r["species"] == sid and r["group"] == group), None)
        text = rule["note"] if rule else "Form varies"
        note, unverified = f"{note}; {text}" if note else text, unverified or not (rule and rule["verified"])
    else:
        forms = [enc["form"]]

    for form in forms:
        p, dlc, u = place, None, unverified
        if group == "SwSh":
            for suffix in _SWSH_DLC:
                if p.endswith(suffix):
                    dlc, p = suffix[2:-1], p[: -len(suffix)]
        if dlc is None:
            dlc = _SV_RAID_DLC.get(enc.get("area")) if group == "SV" else None
        if dlc is None:
            dlc, du = dlc_for(rules.dlc, group, sid, form, method, loc)
            u = u or du
        v, nu = sv_narrow(rules, group, sid, form, versions, ended, method)
        u = u or nu
        if other:
            v = ()
        entry = Entry(method, p, v, dlc, ended, u, note, enc["gender"], needs)
        out.setdefault(("GO" if other else group, sid, form), set()).add(entry)
