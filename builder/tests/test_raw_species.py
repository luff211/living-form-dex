import unittest

from util import form, load_raw, species


class RawSpecies(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = load_raw()

    def test_meowth_forms(self):
        m = species(self.raw, 52)
        self.assertEqual(m["name"], "Meowth")
        self.assertTrue({f["form"] for f in m["forms"]} >= {0, 1, 2})
        self.assertNotIn("RBY", form(m, 1)["groups"])  # no Alolan Meowth in Red
        self.assertIn("SwSh", form(m, 2)["groups"])  # Galarian Meowth in Sword/Shield

    def test_megas_are_flagged_not_lost(self):
        self.assertEqual(sorted(self.raw["megas"]["6"]), ["Mega X", "Mega Y"])
        megas = [f for f in species(self.raw, 6)["forms"] if f["name"].startswith("Mega")]
        self.assertTrue(megas)
        self.assertTrue(all(f["battle_only"] for f in megas))

    def test_every_species_present(self):
        ids = [s["id"] for s in self.raw["species"]]
        self.assertEqual(ids, list(range(1, len(ids) + 1)))
        self.assertGreaterEqual(len(ids), 1025)


if __name__ == "__main__":
    unittest.main()
