import unittest
from pathlib import Path

from dexbuild.derive import add_evolve_and_breed
from dexbuild.direct import direct_entries
from dexbuild.model import Entry
from dexbuild.rules import load_rules
from tests.util import load_raw

RULES_DIR = Path(__file__).resolve().parents[2] / "rules"
NAMES = {79: "Slowpoke", 80: "Slowbro", 665: "Spewpa", 666: "Vivillon", 25: "Pikachu", 26: "Raichu", 172: "Pichu", 52: "Meowth", 53: "Persian", 313: "Volbeat", 314: "Illumise", 790: "Cosmoem", 791: "Solgaleo", 1: "Bulbasaur", 2: "Ivysaur", 3: "Venusaur"}


def d(group, sid, form=0, versions=("SN", "MN"), ended=False, unv=False, method="Wild"):
    return (group, sid, form), [Entry(method, "x", versions, None, ended, unv)]


def edge(a, b, group="SM", trade=False):
    return {"group": group, "from": list(a), "to": list(b), "trade": trade}


def egg(sid, form=0, group="SM", versions=("SN", "MN")):
    return {"group": group, "species": sid, "form": form, "versions": list(versions), "egg": True}


def run(direct, edges=(), eggs=(), no_derive=frozenset()):
    raw = {"species": [{"id": i, "name": n, "forms": []} for i, n in NAMES.items()],
           "evolutions": list(edges), "encounters": list(eggs)}
    return add_evolve_and_breed(dict([direct] if isinstance(direct, tuple) else direct), raw, no_derive=no_derive)


class DeriveTests(unittest.TestCase):
    def test_version_bound_evolution_keeps_only_its_versions(self):
        out = run(d("SM", 790), [dict(edge((790, 0), (791, 0)), versions=["SN"])])
        self.assertEqual([e.versions for e in out[("SM", 791, 0)]], [("SN",)])
        out = run(d("SM", 790, versions=("MN",)), [dict(edge((790, 0), (791, 0)), versions=["SN"])])
        self.assertNotIn(("SM", 791, 0), out)

    def test_egg_kin_breed_from_the_other_species(self):
        # an Illumise can lay Volbeat eggs in every generation; the reverse only from Generation 5
        out = run(d("XY", 314, versions=("Y",)), eggs=[egg(313, group="XY", versions=("X", "Y"))])
        self.assertEqual([(e.method, e.versions) for e in out[("XY", 313, 0)]], [("Breed", ("Y",))])
        out = run(d("XY", 313, versions=("X",)), eggs=[egg(314, group="XY", versions=("X", "Y"))])
        self.assertEqual([(e.method, e.versions) for e in out[("XY", 314, 0)]], [("Breed", ("X",))])
        out = run(d("RSE", 313, versions=("R",)), eggs=[egg(314, group="RSE", versions=("R",))])
        self.assertNotIn(("RSE", 314, 0), out)

    def test_evolve_keeps_versions(self):
        out = run(d("SM", 25), [edge((25, 0), (26, 1))])
        e = out[("SM", 26, 1)][0]
        self.assertEqual((e.method, e.place, e.versions), ("Evolve", "Pikachu", ("SN", "MN")))

    def test_three_stage_and_trade_label(self):
        out = run(d("SM", 1), [edge((1, 0), (2, 0)), edge((2, 0), (3, 0), trade=True)])
        self.assertEqual(out[("SM", 3, 0)][0].place, "Ivysaur (trade)")

    def test_breed_needs_parent_in_game(self):
        out = run(d("SM", 25), [edge((52, 0), (53, 0))], [egg(52)])
        self.assertNotIn(("SM", 52, 0), out)

    def test_breed_when_parent_obtainable(self):
        out = run(d("SM", 25), [edge((172, 0), (25, 0))], [egg(172)])
        self.assertEqual(out[("SM", 172, 0)][-1].place, "Pichu")

    def test_baby_from_breed_can_evolve_but_cannot_justify_breed(self):
        # Pichu bred (parent Pikachu); Raichu comes from Pikachu directly and from Pichu route
        out = run(d("SM", 26), [edge((172, 0), (25, 0)), edge((25, 0), (26, 0))], [egg(172), egg(25)])
        self.assertIn(("SM", 25, 0), out)  # breed via Raichu in family
        out = run([], [edge((172, 0), (25, 0))], [egg(172), egg(25)])
        self.assertEqual(out, {})

    def test_breed_versions_intersect(self):
        out = run(d("SM", 25, versions=("SN",)), [edge((172, 0), (25, 0))], [egg(172)])
        self.assertEqual(out[("SM", 172, 0)][0].versions, ("SN",))
        out = run(d("SM", 25, versions=("SN",)), [edge((172, 0), (25, 0))], [egg(172, versions=("MN",))])
        self.assertNotIn(("SM", 172, 0), out)

    def test_ended_only_if_every_route_ended(self):
        both = [("SM", 25, 0), [Entry("Event", "x", ("SN",), None, True), Entry("Wild", "y", ("SN",))]]
        self.assertFalse(run([tuple(both)], [edge((25, 0), (26, 0))])[("SM", 26, 0)][0].ended)
        self.assertTrue(run(d("SM", 25, ended=True), [edge((25, 0), (26, 0))])[("SM", 26, 0)][0].ended)

    def test_ended_route_does_not_widen_live_versions(self):
        # C1: an ended event in SH plus live wild in SW must not give a live SW+SH derived entry
        src = [(("SM", 25, 0), [Entry("Event", "x", ("MN",), None, True), Entry("Wild", "y", ("SN",))])]
        es = run(src, [edge((25, 0), (26, 0))])[("SM", 26, 0)]
        self.assertEqual({(e.versions, e.ended) for e in es}, {(("SN",), False), (("MN",), True)})
        es = run(src, [edge((172, 0), (25, 0))], [egg(172)])[("SM", 172, 0)]
        self.assertEqual({(e.versions, e.ended) for e in es}, {(("SN",), False), (("MN",), True)})

    def test_unverified_route_does_not_widen_verified(self):
        src = [(("SM", 25, 0), [Entry("Wild", "y", ("SN", "MN")), Entry("Wild", "x", ("MN",), None, False, True)])]
        es = run(src, [edge((25, 0), (26, 0))])[("SM", 26, 0)]
        self.assertEqual([(e.versions, e.unverified) for e in es], [(("SN", "MN"), False)])
        src = [(("SM", 25, 0), [Entry("Wild", "x", ("MN",), None, False, True), Entry("Wild", "y", ("SN",))])]
        es = run(src, [edge((25, 0), (26, 0))])[("SM", 26, 0)]
        self.assertEqual({(e.versions, e.unverified) for e in es}, {(("SN",), False), (("MN",), True)})

    def test_needs_other_game_carries_unless_a_plain_route_exists(self):
        src = [(("SM", 25, 0), [Entry("Static", "x", ("SN", "MN"), needs_other_game=True)])]
        es = run(src, [edge((25, 0), (26, 0))])[("SM", 26, 0)]
        self.assertEqual([(e.versions, e.needs_other_game) for e in es], [(("SN", "MN"), True)])
        src[0][1].append(Entry("Wild", "y", ("SN",)))
        es = run(src, [edge((25, 0), (26, 0))])[("SM", 26, 0)]
        self.assertEqual({(e.versions, e.needs_other_game) for e in es}, {(("SN",), False), (("MN",), True)})

    def test_dlc_carries_when_every_route_has_it(self):
        src = [(("SwSh", 79, 1), [Entry("Wild", "x", ("SW", "SH"), "Isle of Armor")])]
        es = run(src, [edge((79, 1), (80, 1), group="SwSh")])[("SwSh", 80, 1)]
        self.assertEqual([(e.versions, e.dlc) for e in es], [(("SW", "SH"), "Isle of Armor")])
        src[0][1].append(Entry("Wild", "y", ("SW",)))
        es = run(src, [edge((79, 1), (80, 1), group="SwSh")])[("SwSh", 80, 1)]
        self.assertEqual({(e.versions, e.dlc) for e in es}, {(("SW",), None), (("SH",), "Isle of Armor")})

    def test_no_derive_into_listed_form(self):
        out = run(d("XY", 665, form=18, versions=("X", "Y")), [edge((665, 18), (666, 18), group="XY")],
                  no_derive={(666, 18)})
        self.assertNotIn(("XY", 666, 18), out)

    def test_no_evolve_into_other_group_or_go(self):
        out = run(d("RBY", 25, versions=("RD",)), [edge((25, 0), (26, 1))])
        self.assertNotIn(("RBY", 26, 1), out)
        out = run(d("GO", 25, versions=()), [edge((25, 0), (26, 0), group="GO")])
        self.assertEqual(list(out), [("GO", 25, 0)])

    def test_input_not_mutated_and_no_duplicates(self):
        src = dict([d("SM", 25), d("SM", 26)])
        before = {k: list(v) for k, v in src.items()}
        raw = {"species": [{"id": i, "name": n, "forms": []} for i, n in NAMES.items()],
               "evolutions": [edge((25, 0), (26, 0))], "encounters": []}
        out = add_evolve_and_breed(src, raw)
        self.assertEqual(src, before)
        self.assertEqual(len(out[("SM", 26, 0)]), 2)


class RealDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        raw = load_raw()
        cls.out = add_evolve_and_breed(direct_entries(raw, load_rules(RULES_DIR)), raw, load_rules(RULES_DIR))

    def test_alolan_raichu(self):
        self.assertEqual(self.out[("SM", 26, 1)][0].place, "Pikachu")

    def test_venusaur_in_rby(self):
        self.assertIn(("RBY", 3, 0), self.out)

    def test_kadabra_trade(self):
        self.assertEqual(self.out[("RBY", 65, 0)][0].place, "Kadabra (trade)")

    def test_version_exclusive_carries(self):
        self.assertEqual(self.out[("FRLG", 44, 0)][0].versions, ("FR",))

    def test_kantonian_meowth_not_in_sm(self):
        self.assertNotIn(("SM", 52, 0), self.out)

    def test_pichu_bred_in_sm(self):
        self.assertEqual(self.out[("SM", 172, 0)][-1].method, "Breed")

    def test_no_raichu_form1_in_rby(self):
        self.assertNotIn(("RBY", 26, 1), self.out)


if __name__ == "__main__":
    unittest.main()
