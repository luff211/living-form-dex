import copy
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "builder"))

from dexbuild.rows import build_rows  # noqa: E402
from dexbuild.rules import load_rules  # noqa: E402
from tests.util import load_raw  # noqa: E402


class Rows(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = load_raw()
        cls.rules = load_rules(REPO / "rules")
        cls.rows, cls.left = build_rows(cls.raw, cls.rules)

    def ids(self, dex):
        return [r.id for r in self.rows if r.dex == dex]

    def test_single_form_species_has_one_row(self):
        self.assertEqual(self.ids(143), ["0143-0"])
        self.assertEqual([r.form_name for r in self.rows if r.dex == 143], [""])

    def test_gender_difference_makes_two_rows(self):
        self.assertEqual([(r.id, r.form_name) for r in self.rows if r.dex == 25][:2],
                         [("0025-0-m", "Male"), ("0025-0-f", "Female")])

    def test_gender_rows_only_for_form_zero_and_listed_forms(self):
        pika = [r for r in self.rows if r.dex == 25]
        self.assertEqual([r.id for r in pika][:3], ["0025-0-m", "0025-0-f", "0025-1"])
        self.assertEqual(pika[2].form_name, "Original")
        self.assertEqual([r.id for r in self.rows if r.dex == 215 and r.form == 1], ["0215-1-m", "0215-1-f"])

    def test_variants_split_each_form(self):
        alc = [r for r in self.rows if r.dex == 869]
        self.assertEqual(len(alc), 63)
        self.assertEqual((alc[0].id, alc[0].form_name, alc[0].variant),
                         ("0869-0-strawberry", "Vanilla Cream, Strawberry Sweet", "Strawberry Sweet"))
        self.assertEqual(alc[-1].id, "0869-8-ribbon")
        self.assertEqual(len({r.id for r in alc}), 63)

    def test_merged_forms_have_no_row(self):
        self.assertEqual(self.ids(414), ["0414-0"])
        self.assertEqual(self.ids(658), ["0658-0"])
        self.assertEqual(self.ids(718), ["0718-0", "0718-1"])
        self.assertEqual([r.form_name for r in self.rows if r.dex == 414], [""])

    def test_form_is_gender_not_doubled(self):
        self.assertEqual(len(self.ids(678)), 2)

    def test_mega_is_flag_not_row(self):
        z = [r for r in self.rows if r.dex == 6]
        self.assertEqual(len(z), 1)
        self.assertEqual(z[0].mega, ["Mega X", "Mega Y"])
        self.assertTrue(z[0].gmax)

    def test_flags_only_on_form_zero_unless_named(self):
        by = {r.id: r for r in self.rows}
        self.assertTrue(by["0052-0"].gmax)
        self.assertFalse(by["0052-2"].gmax)           # Galarian Meowth has no Gmax
        self.assertEqual(by["0080-2"].mega, [])        # Galarian Slowbro has no Mega
        self.assertTrue(by["0025-0-m"].gmax and by["0025-0-f"].gmax)
        self.assertFalse(by["0025-1"].gmax)
        self.assertTrue(all(r.gmax for r in self.rows if r.dex in (849, 869, 892)))
        self.assertEqual(by["0670-0"].mega, [])
        self.assertEqual(by["0670-5"].mega, ["Mega"])

    def test_scatterbug_spewpa_one_row_each(self):
        self.assertEqual(self.ids(664), ["0664-0"])
        self.assertEqual(self.ids(665), ["0665-0"])
        self.assertEqual(len([x for x in self.left if x.species in (664, 665)]), 38)

    def test_context_forms_are_left_out_not_rows(self):
        self.assertFalse([r for r in self.rows if r.form >= 100])
        left = {(x.species, x.form_name) for x in self.left}
        self.assertIn((25, "Rock Star"), left)
        self.assertIn((172, "Spiky"), left)

    def test_excluded_form_is_reported_not_dropped(self):
        self.assertEqual(self.ids(493), ["0493-0"])
        want = sum(e["forms"][1] - e["forms"][0] + 1
                   for e in self.rules.forms["exclude"]["entries"] if e["species"] == 493)
        self.assertEqual(len([x for x in self.left if x.species == 493]), want)

    def test_order(self):
        keys = [(r.dex, r.form, r.gender == "f") for r in self.rows]
        self.assertEqual(keys, sorted(keys))

    def test_ids_unique(self):
        self.assertEqual(len({r.id for r in self.rows}), len(self.rows))

    def test_does_not_mutate_inputs(self):
        raw = copy.deepcopy(self.raw)
        build_rows(self.raw, self.rules)
        self.assertEqual(raw, self.raw)

    def test_rows_do_not_share_state(self):
        self.rows[0].other.append(None)
        try:
            self.assertEqual(self.rows[1].other, [])
        finally:
            self.rows[0].other.pop()


if __name__ == "__main__":
    unittest.main()
