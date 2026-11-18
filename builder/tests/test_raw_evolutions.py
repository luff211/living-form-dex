import unittest

from util import load_raw

raw = None


def setUpModule():
    global raw
    raw = load_raw()


def evos(raw, group):
    return {(e["from"][0], e["from"][1], e["to"][0], e["to"][1]) for e in raw["evolutions"] if e["group"] == group}


class RawEvolutionsTest(unittest.TestCase):
    def test_pikachu_becomes_alolan_raichu_in_alola(self):
        self.assertIn((25, 0, 26, 1), evos(raw, "SM"))
        self.assertNotIn((25, 0, 26, 0), evos(raw, "SM"))

    def test_galarian_meowth_evolves_to_perrserker(self):
        self.assertIn((52, 2, 863, 0), evos(raw, "SwSh"))

    def test_trade_evolution_flagged(self):
        self.assertTrue(any(e["trade"] for e in raw["evolutions"] if e["group"] == "RBY" and e["from"] == [64, 0]))

    def test_no_evolution_into_absent_species(self):
        present = {(s["id"], f["form"]) for s in raw["species"] for f in s["forms"] if "RBY" in f["groups"]}
        self.assertTrue(all((t, tf) in present for (_, _, t, tf) in evos(raw, "RBY")))

    def test_no_go_evolutions(self):
        self.assertFalse(evos(raw, "GO"))


if __name__ == "__main__":
    unittest.main()
