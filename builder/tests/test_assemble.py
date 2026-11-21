import unittest

from dexbuild.assemble import fill, derived_rules, to_json
from dexbuild.checks import structural_problems
from dexbuild.model import Entry, Row
from dexbuild.rules import Rules

GAMES = {"groups": [
    {"id": "FRLG", "label": "FireRed / LeafGreen", "versions": [{"code": "FR", "label": "FireRed", "mark": "FR"}, {"code": "LG", "label": "LeafGreen", "mark": "LG"}],
     "home_route": {"text": "route", "verified": False, "checked": ""}},
    {"id": "SwSh", "label": "Sword / Shield", "versions": [{"code": "SW", "label": "Sword", "mark": "Sw"}, {"code": "SH", "label": "Shield", "mark": "Sh"}],
     "home_route": {"text": "direct", "verified": False, "checked": ""}},
    {"id": "GO", "label": "Other", "other": True, "versions": [{"code": "GO", "label": "GO", "mark": "GO"}]},
]}


def rules(methods=(), annotate=(), no_source=()):
    f = lambda xs: {"entries": list(xs)}
    return Rules(games=GAMES, forms={"exclude": f([]), "methods": f(methods), "annotate": f(annotate)},
                 sv_exclusives=[], releases=[], dlc=[], gmax={}, gmax_unverified=set(), gender_diff=set(),
                 no_source={(s, fo) for s, fo in no_source})


def row(sid=1, form=0, gender=None):
    return Row(f"{sid:04d}-{form}", sid, "X", "", sid, form, gender, [], False, False)


def run(entries, r=None, rl=None, **kw):
    r = r or row()
    fill([r], entries, rl or rules(**kw))
    return r


class AssembleTests(unittest.TestCase):
    def test_form_method_rule_replaces_cell(self):
        m = {"species": 1, "form": 0, "group": "SwSh", "method": "Form change", "place": "Use item", "versions": None,
             "verified": False, "checked": ""}
        r = run({("SwSh", 1, 0): [Entry("Wild", "Route 1", ("SW",))]}, methods=[m])
        self.assertEqual([(e.method, e.versions, e.unverified) for e in r.cells["SwSh"]], [("Form change", ("SW", "SH"), True)])

    def test_annotate_keeps_cell_and_adds_note(self):
        a = {"species": 1, "form": 0, "group": "FRLG", "note": "Does not carry to HOME", "verified": False, "checked": ""}
        r = run({("FRLG", 1, 0): [Entry("Static", "Cave", ("FR",))]}, annotate=[a])
        e = r.cells["FRLG"][0]
        self.assertEqual((e.method, e.versions, e.note, e.unverified), ("Static", ("FR",), "Does not carry to HOME", True))

    def test_annotate_joins_existing_note(self):
        a = {"species": 1, "form": 0, "group": "FRLG", "note": "B", "verified": True, "checked": ""}
        r = run({("FRLG", 1, 0): [Entry("Static", "Cave", ("FR",), note="A")]}, annotate=[a])
        self.assertEqual((r.cells["FRLG"][0].note, r.cells["FRLG"][0].unverified), ("A; B", False))

    def test_variant_note_only_on_evolve_and_form_change(self):
        rl = rules()
        rl.forms["variants"] = {"entries": [{"species": 1, "names": ["Star Sweet", "Love Sweet"], "note": "Evolve holding a {name}"}]}
        r = row()
        r.variant = "Star Sweet"
        run({("SwSh", 1, 0): [Entry("Evolve", "Milcery", ("SW",)), Entry("Raid", "Den", ("SW",), note="A")]}, r, rl)
        self.assertEqual(sorted((e.method, e.note) for e in r.cells["SwSh"]),
                         [("Evolve", "Evolve holding a Star Sweet"), ("Raid", "A")])

    def test_gender_row_drops_other_gender_entries(self):
        es = {("SwSh", 1, 0): [Entry("Wild", "A", ("SW",), gender="f"), Entry("Wild", "B", ("SW",), gender="m"),
                               Entry("Wild", "C", ("SW",))]}
        self.assertEqual([e.place for e in run(es, row(gender="m")).cells["SwSh"]], ["B", "C"])
        self.assertEqual([e.place for e in run(es).cells["SwSh"]], ["A", "B", "C"])

    def test_none_and_gendered_duplicates_merge(self):
        es = {("SwSh", 1, 0): [Entry("Raid", "p", ("SW",), ended=True), Entry("Raid", "p", ("SW",), ended=True, gender="m")]}
        self.assertEqual(len(run(es, row(gender="m")).cells["SwSh"]), 1)
        self.assertEqual(len(run(es).cells["SwSh"]), 1)

    def test_order_live_before_ended_then_method(self):
        es = {("SwSh", 1, 0): [Entry("Event", "e", ("SW",)), Entry("Wild", "old", ("SW",), ended=True),
                               Entry("Evolve", "x", ("SW",)), Entry("Static", "s", ("SW",)), Entry("Wild", "w", ("SW",))]}
        cell = run(es).cells["SwSh"]
        self.assertEqual([e.method for e in cell], ["Wild", "Static", "Evolve", "Event", "Wild"])
        self.assertTrue(cell[-1].ended)

    def test_same_place_versions_merged(self):
        es = {("SwSh", 1, 0): [Entry("Wild", "p", ("SH",)), Entry("Wild", "p", ("SW",))]}
        cell = run(es).cells["SwSh"]
        self.assertEqual((len(cell), cell[0].versions), (1, ("SW", "SH")))

    def test_other_only_when_no_live_main_entry(self):
        go = [Entry("GO", "Pokémon GO", ()), Entry("GO", "Pokémon GO", (), note="x")]
        with_wild = run({("SwSh", 1, 0): [Entry("Wild", "p", ("SW",))], ("GO", 1, 0): go})
        only_ended = run({("SwSh", 1, 0): [Entry("Wild", "p", ("SW",), ended=True)], ("GO", 1, 0): go})
        go_only = run({("GO", 1, 0): go})
        self.assertEqual(with_wild.other, [])
        self.assertEqual(go_only.other[0], Entry("GO", "Pokémon GO → HOME", ()))
        self.assertEqual(len(go_only.other), 1)
        self.assertEqual(len(only_ended.other), 1)

    def test_check_flags_empty_row(self):
        raw = {"species": [{"id": 1}]}
        problems = structural_problems([row(1, 1)], rules(), raw)
        self.assertRegex(problems[0], "0001-1")
        self.assertEqual(structural_problems([row(1, 1)], rules(no_source=[(1, 1)]), raw), [])

    def test_check_flags_missing_dex_number(self):
        r = row(1)
        r.other = [Entry("GO", "x", ())]
        problems = structural_problems([r], rules(), {"species": [{"id": 1}, {"id": 2}]})
        self.assertEqual(problems, ["dex 2: no row"])

    def test_check_flags_foreign_version_and_duplicate_id(self):
        r = row(1)
        r.cells = {"FRLG": [Entry("Wild", "p", ("SW",))]}
        problems = structural_problems([r, r], rules(), {"species": [{"id": 1}]})
        self.assertEqual(len(problems), 3)  # duplicate id, plus the foreign version on each of the two rows

    def test_derived_rules_rule_marks_derived_entries(self):
        rl = rules()
        rl.dlc = [{"group": "SwSh", "dlc": "Isle of Armor", "species": [80], "form": 2, "method": "Evolve", "verified": False}]
        out = derived_rules({("SwSh", 80, 2): [Entry("Evolve", "Slowpoke", ("SW", "SH"))],
                           ("SwSh", 80, 0): [Entry("Evolve", "Slowpoke", ("SW", "SH"))]}, rl)
        e = out[("SwSh", 80, 2)][0]
        self.assertEqual((e.dlc, e.unverified), ("Isle of Armor", True))
        self.assertIsNone(out[("SwSh", 80, 0)][0].dlc)

    def test_sv_exclusive_narrows_derived_entries(self):
        rl = rules()
        rl.sv_exclusives = [{"species": 936, "form": None, "version": "SL", "verified": False}]
        out = derived_rules({("SV", 936, 0): [Entry("Evolve", "Charcadet", ("SL", "VL")),
                                              Entry("Evolve", "Charcadet", ("SL", "VL"), ended=True)]}, rl)
        self.assertEqual([e.versions for e in out[("SV", 936, 0)]], [("SL",), ("SL", "VL")])

    def test_to_json_carries_needs_other_game(self):
        r = run({("SwSh", 1, 0): [Entry("Static", "p", ("SW",), needs_other_game=True, note="n")]})
        self.assertTrue(to_json([r], rules(), {"pkhex": "1"})["rows"][0]["cells"]["SwSh"][0]["needs_other_game"])

    def test_other_shown_when_main_entries_need_another_game(self):
        go = [Entry("GO", "Pokémon GO", ())]
        r = run({("SwSh", 1, 0): [Entry("Static", "p", ("SW",), needs_other_game=True)], ("GO", 1, 0): go})
        self.assertEqual(len(r.other), 1)

    def test_to_json_shape(self):
        r = run({("SwSh", 1, 0): [Entry("Wild", "p", ("SW",))]})
        d = to_json([r], rules(), {"pkhex": "1.2"})
        self.assertEqual([g["id"] for g in d["groups"]], ["FRLG", "SwSh"])
        self.assertEqual(d["groups"][0]["home_route_unverified"], True)
        self.assertEqual(d["rows"][0]["cells"]["SwSh"][0]["versions"], ["SW"])
        self.assertEqual(d["meta"], {"pkhex": "1.2", "rows": 1, "sprite_base": ""})
        self.assertEqual(d["groups"][0]["links"], {})

    def test_to_json_carries_serebii_links_per_group(self):
        rl = rules()
        rl.serebii = {"SwSh": {"Route 1": "https://www.serebii.net/pokearth/galar/route1.shtml"}}
        d = to_json([run({})], rl, {"pkhex": "1"})
        self.assertEqual(d["groups"][1]["links"], {"Route 1": "https://www.serebii.net/pokearth/galar/route1.shtml"})

    def test_to_json_carries_sprite_per_row(self):
        rl = rules()
        row = run({})
        rl.sprite_base, rl.sprites = "https://x/", {row.id: "1.png"}
        d = to_json([row], rl, {"pkhex": "1"})
        self.assertEqual((d["meta"]["sprite_base"], d["rows"][0]["sprite"]), ("https://x/", "1.png"))
        rl.sprites = {}
        self.assertIsNone(to_json([row], rl, {"pkhex": "1"})["rows"][0]["sprite"])


if __name__ == "__main__":
    unittest.main()
