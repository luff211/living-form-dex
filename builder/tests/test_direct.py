import unittest
from pathlib import Path

from dexbuild import direct
from dexbuild.direct import direct_entries
from dexbuild.kinds import UnknownKind, method_for
from dexbuild.rules import Rules, load_rules
from tests.util import load_raw

RULES_DIR = Path(__file__).resolve().parents[2] / "rules"


def enc(**kw):
    d = {"group": "SV", "species": 1, "form": 0, "form_random": False, "type": "EncounterSlot9",
         "label": "Wild Encounter (SL)", "versions": ["SL", "VL"], "location": "Somewhere", "egg": False,
         "event_title": None, "event_id": None, "gender": None}
    d.update(kw)
    return d


def sp(sid, forms):
    """forms: {form: groups}"""
    return {"id": sid, "name": str(sid), "forms": [
        {"form": f, "name": str(f), "battle_only": False, "fused": False, "groups": g} for f, g in forms.items()]}


def rules(**kw):
    base = dict(games={}, forms={"methods": {"entries": []}}, sv_exclusives=[], releases=[], dlc=[],
                gmax={}, gmax_unverified=set(), gender_diff=set())
    base.update(kw)
    return Rules(**base)


def run(encs, species=None, **kw):
    species = species or [sp(e["species"], {e["form"]: [e["group"]]}) for e in encs]
    return direct_entries({"species": species, "encounters": encs}, rules(**kw))


class KindTests(unittest.TestCase):
    def test_wild_static_trade_gift_labels(self):
        self.assertEqual(method_for("EncounterSlot8", "Wild Encounter (SW)"), ("Wild", False))
        self.assertEqual(method_for("EncounterStatic8", "Static Encounter"), ("Static", False))
        self.assertEqual(method_for("EncounterTrade8", "In-game Trade"), ("In-game trade", False))
        self.assertEqual(method_for("EncounterStatic4Pokewalker", "Pokéwalker Encounter (X)"), ("Gift", False))

    def test_events_and_distributions_are_ended(self):
        self.assertEqual(method_for("WC8", "Event Gift"), ("Event", True))
        self.assertEqual(method_for("EncounterStatic8ND", "Distribution Raid Den Encounter - 067")[1], True)
        self.assertEqual(method_for("EncounterStatic8N", "Stock Raid Den Encounter [144] 5★"), ("Raid", False))
        self.assertTrue(method_for("EncounterStatic5Entree", "Entree Forest Encounter (B)")[1])

    def test_gen1_gen3_gifts_are_events(self):
        for t, l in (("EncounterGift1", "Event Gift"), ("EncounterGift3", "Event Gift"),
                     ("EncounterGift3Colo", "Gift Encounter")):
            self.assertEqual(method_for(t, l), ("Event", True))
        self.assertEqual(method_for("EncounterGift9a", "Gift Encounter"), ("Gift", False))

    def test_no_event_gift_label_is_live(self):
        for e in load_raw()["encounters"]:
            if e["label"] == "Event Gift":
                self.assertTrue(method_for(e["type"], e["label"])[1], e["type"])

    def test_seven_star_raids_are_ended(self):
        self.assertEqual(method_for("EncounterMight9", "7-Star Tera Raid Encounter"), ("Raid", True))
        self.assertEqual(method_for("EncounterTera9", "Tera Raid Encounter [Base] 5★"), ("Raid", False))

    def test_unknown_type_raises(self):
        # fail closed: a new PKHeX class must be looked at by hand, not assumed live
        for t in ("EncounterBrandNew12", "EncounterStatic10", "EncounterGift10", "EncounterSlot10", "EncounterTrade10", "WC10"):
            with self.assertRaises(UnknownKind) as cm:
                method_for(t, "Something")
            self.assertIn(t, str(cm.exception))

    def test_every_real_type_is_mapped(self):
        for t, l in {(e["type"], e["label"]) for e in load_raw()["encounters"]}:
            method_for(t, l)


class DirectTests(unittest.TestCase):
    def test_sv_exclusive_narrows_versions(self):
        out = run([enc(species=246)], sv_exclusives=[{"species": 246, "form": None, "version": "SL", "verified": False}])
        self.assertEqual(out[("SV", 246, 0)][0].versions, ("SL",))
        self.assertTrue(out[("SV", 246, 0)][0].unverified)

    def test_sv_exclusive_narrows_every_live_method(self):
        excl = [{"species": 246, "form": None, "version": "SL", "verified": False}]
        for t, label in (("EncounterTera9", "Tera Raid Encounter [Base] 3★"), ("EncounterStatic9", "Static Encounter")):
            e = run([enc(species=246, type=t, label=label)], sv_exclusives=excl)[("SV", 246, 0)][0]
            self.assertEqual((e.versions, e.unverified), (("SL",), True), t)
        # in-game trades are the same in both versions
        e = run([enc(species=246, type="EncounterTrade9", label="In-game Trade")], sv_exclusives=excl)[("SV", 246, 0)][0]
        self.assertEqual((e.versions, e.unverified), (("SL", "VL"), False))

    def test_sv_raid_takes_dlc_from_its_map(self):
        for area, dlc in (("Paldea", None), ("Kitakami", "The Teal Mask"), ("Blueberry", "The Indigo Disk")):
            e = run([enc(type="EncounterTera9", label="Tera Raid Encounter [Base] 3★", area=area)])[("SV", 1, 0)][0]
            self.assertEqual((e.dlc, e.unverified), (dlc, False), area)

    def test_release_rule_limited_to_versions_splits_the_entry(self):
        out = run([enc(group="B2W2", species=379, type="EncounterStatic5", label="Static Encounter",
                       versions=["B2", "W2"], location="Iron Chamber")],
                  releases=[{"group": "B2W2", "species": 379, "location_contains": "Iron", "versions": ["W2"],
                             "set": {"needs_other_game": True, "note": "n"}, "verified": False}])
        self.assertEqual({(e.versions, e.needs_other_game, e.note, e.unverified) for e in out[("B2W2", 379, 0)]},
                         {(("B2",), False, None, False), (("W2",), True, "n", True)})

    def test_sv_exclusive_leaves_ended_entries_alone(self):
        out = run([enc(species=246, type="EncounterMight9", label="7-Star Tera Raid Encounter")],
                  sv_exclusives=[{"species": 246, "form": None, "version": "SL", "verified": False}])
        self.assertEqual(out[("SV", 246, 0)][0].versions, ("SL", "VL"))

    def test_release_rule_sets_needs_other_game(self):
        out = run([enc(group="BDSP", species=151, type="EncounterStatic8b", label="Static Encounter",
                       versions=["BD", "SP"], location="Floaroma Town")],
                  releases=[{"group": "BDSP", "species": 151, "location_contains": "Floaroma",
                             "set": {"needs_other_game": True, "note": "n"}, "verified": False}])
        e = out[("BDSP", 151, 0)][0]
        self.assertEqual((e.needs_other_game, e.ended, e.note, e.unverified), (True, False, "n", True))

    def test_no_spread_form_gets_no_form_varies(self):
        s = sp(666, {0: ["XY"], 18: ["XY"]})
        out = run([enc(group="XY", species=666, form=31, form_random=True, type="EncounterSlot6XY", versions=["X", "Y"])],
                  species=[s], no_spread={(666, 18)})
        self.assertIn(("XY", 666, 0), out)
        self.assertNotIn(("XY", 666, 18), out)

    def test_dlc_by_species(self):
        base = dict(group="SV", type="EncounterStatic9", label="Static Encounter")
        out = run([enc(species=250, location="South Province (Area Four)", **base), enc(species=251, **base)],
                  dlc=[{"group": "SV", "dlc": "The Indigo Disk", "species": [250], "verified": False}])
        self.assertEqual((out[("SV", 250, 0)][0].dlc, out[("SV", 250, 0)][0].unverified), ("The Indigo Disk", True))
        self.assertIsNone(out[("SV", 251, 0)][0].dlc)
        self.assertEqual(direct.dlc_for([{"group": "SwSh", "dlc": "Isle of Armor", "species": [80], "form": 1,
                                          "method": "Evolve", "verified": False}], "SwSh", 80, 1, "Evolve", ""),
                         ("Isle of Armor", True))
        self.assertEqual(direct.dlc_for([{"group": "SwSh", "dlc": "Isle of Armor", "species": [80], "form": 1,
                                          "method": "Evolve", "verified": False}], "SwSh", 80, 0, "Evolve", ""),
                         (None, False))

    def test_placeholder_event_titles_are_dropped(self):
        out = run([enc(type="WC6", label="Event Gift", event_title="This is A Dummy Card", location=None),
                   enc(species=2, type="WC6", label="Event Gift", event_title="Simulated Pokemon Bank Celebi.", location=None)])
        self.assertEqual((out[("SV", 1, 0)][0].place, out[("SV", 2, 0)][0].place), ("", ""))

    def test_language_copies_of_one_card_collapse_to_one_title(self):
        copies = [enc(species=302, type="WC6", label="Event Gift", location=None, event_id=551, event_title=t)
                  for t in ("Ein besonderes Zobiris!", "It's Sableye!", "¡Un Sableye!")]
        other = enc(species=302, type="WC6", label="Event Gift", location=None, event_id=600, event_title="Another")
        es = run(copies + [other])[("SV", 302, 0)]
        self.assertEqual(sorted(e.place for e in es), ["Another", "It's Sableye!"])

    def test_event_title_carries_its_year(self):
        e = run([enc(type="WC9", label="Event Gift", event_title="T", event_id=1, event_year=2023)])[("SV", 1, 0)][0]
        self.assertEqual(e.place, "T (2023)")

    def test_no_location_gives_empty_place(self):
        out = run([enc(group="RBY", type="EncounterStatic1", label="Static Encounter", location="", versions=["RD"])])
        self.assertEqual(out[("RBY", 1, 0)][0].place, "")

    def test_dlc_from_swsh_suffix_and_rule_file(self):
        base = dict(group="SwSh", type="EncounterStatic8", label="Static Encounter", versions=["SW", "SH"])
        out = run([enc(location="Fields of Honor (Isle of Armor)", **base), enc(location="Master Dojo", species=2, **base)],
                  dlc=[{"group": "SwSh", "dlc": "Isle of Armor", "locations": ["Master Dojo"], "verified": False}])
        e1, e2 = out[("SwSh", 1, 0)][0], out[("SwSh", 2, 0)][0]
        self.assertEqual((e1.dlc, e1.place, e1.unverified), ("Isle of Armor", "Fields of Honor", False))
        self.assertEqual((e2.dlc, e2.unverified), ("Isle of Armor", True))

    def test_release_rule_overrides_ended(self):
        out = run([enc(group="FRLG", species=386, type="EncounterStatic3", label="Static Encounter",
                       versions=["FR"], location="Birth Island")],
                  releases=[{"group": "FRLG", "species": 386, "location_contains": "Birth Island",
                             "set": {"ended": False, "note": "Aurora Ticket is given"}, "verified": False}])
        e = out[("FRLG", 386, 0)][0]
        self.assertFalse(e.ended)
        self.assertIn("Aurora Ticket", e.note)
        self.assertTrue(e.unverified)

    def test_event_title_and_no_title(self):
        out = run([enc(type="WC6", label="Event Gift", event_title="Pokémon 20th Anniversary", location=None),
                   enc(species=2, type="WC6", label="Event Gift", location=None)])
        self.assertEqual(out[("SV", 1, 0)][0].place, "Pokémon 20th Anniversary")
        e = out[("SV", 2, 0)][0]
        self.assertEqual((e.method, e.place, e.ended), ("Event", "", True))

    def test_home_gift_goes_to_other(self):
        out = run([enc(group="SwSh", species=801, form=1, type="WC8", label="Event Gift", location="Pokémon HOME")])
        e = out[("GO", 801, 1)][0]
        self.assertEqual((e.method, e.versions), ("HOME gift", ()))
        self.assertNotIn(("SwSh", 801, 1), out)

    def test_go_group_goes_to_other(self):
        out = run([enc(group="GO", type="EncounterSlot8GO", label="GO Encounter (X)", versions=["GO"])])
        self.assertEqual(out[("GO", 1, 0)][0].method, "GO")

    def test_random_form_spreads_to_all_forms(self):
        s = sp(201, {0: ["GSC"], 5: ["GSC"], 7: ["RSE"]})
        out = run([enc(group="GSC", species=201, form=31, form_random=True, type="EncounterSlot2")], species=[s])
        self.assertEqual(out[("GSC", 201, 5)][0].note, "Form varies")
        self.assertTrue(out[("GSC", 201, 5)][0].unverified)
        self.assertNotIn(("GSC", 201, 7), out)

    def test_random_form_keeps_release_note(self):
        s = sp(666, {0: ["XY"], 1: ["XY"]})
        out = run([enc(group="XY", species=666, form=31, form_random=True, type="EncounterSlot6XY", versions=["X", "Y"],
                       location="Friend Safari")], species=[s],
                  releases=[{"group": "XY", "species": None, "location_contains": "Friend Safari",
                             "set": {"note": "Needs friends"}, "verified": False}])
        self.assertEqual(out[("XY", 666, 1)][0].note, "Needs friends; Form varies")

    def test_random_form_old_format_uses_every_real_form(self):
        s = sp(201, {0: ["GSC"], 1: [], 2: []})
        out = run([enc(group="GSC", species=201, form=31, form_random=True, type="EncounterSlot2")], species=[s])
        self.assertEqual({k[2] for k in out}, {0, 1, 2})

    def test_random_form_skipped_when_methods_rule_exists(self):
        s = sp(201, {0: ["GSC"], 5: ["GSC"]})
        out = run([enc(group="GSC", species=201, form=31, form_random=True, type="EncounterSlot2")], species=[s],
                  forms={"methods": {"entries": [{"species": 201, "group": "GSC"}]}})
        self.assertEqual(out, {})

    def test_eggs_excluded_and_duplicates_collapse(self):
        out = run([enc(type="EncounterEgg7", label="Egg", egg=True), enc(), enc()])
        self.assertEqual(len(out[("SV", 1, 0)]), 1)

    def test_swsh_dlc_names_match_suffix_names(self):
        names = {r["dlc"] for r in load_rules(RULES_DIR).dlc if r["group"] == "SwSh"}
        suffixes = {s[2:-1] for s in direct._SWSH_DLC}
        self.assertEqual(names, suffixes)

    def test_real_data(self):
        out = direct_entries(load_raw(), load_rules(RULES_DIR))
        self.assertGreater(len(out), 1000)
        self.assertTrue(all(isinstance(e.versions, tuple) for v in out.values() for e in v))
        self.assertTrue(all(e.versions == () for k, v in out.items() if k[0] == "GO" for e in v))
        self.assertEqual(out, direct_entries(load_raw(), load_rules(RULES_DIR)))


if __name__ == "__main__":
    unittest.main()
