import unittest

from util import load_raw

raw = None


def setUpModule():
    global raw
    raw = load_raw()


def encs(raw, group, species, form=None):
    return [e for e in raw["encounters"] if e["group"] == group and e["species"] == species
            and (form is None or e["form"] == form)]


class RawEncounters(unittest.TestCase):
    def test_galarian_farfetchd_is_sword_only(self):
        wild = [e for e in encs(raw, "SwSh", 83, 1) if e["type"].startswith("EncounterSlot")]
        self.assertTrue(wild)
        self.assertTrue(all(e["versions"] == ["SW"] for e in wild))

    def test_deoxys_forms_by_game(self):
        self.assertEqual({tuple(e["versions"]) for e in encs(raw, "FRLG", 386, 1)}, {("FR",)})
        self.assertEqual({tuple(e["versions"]) for e in encs(raw, "FRLG", 386, 2)}, {("LG",)})
        self.assertTrue(any(e["versions"] == ["E"] for e in encs(raw, "RSE", 386, 3)))

    def test_no_alolan_meowth_before_it_existed(self):
        self.assertEqual(encs(raw, "RBY", 52, 1), [])

    def test_no_cross_group_leak(self):
        self.assertTrue(all(set(e["versions"]) <= {"X", "Y"} for e in raw["encounters"] if e["group"] == "XY"))

    def test_only_direct_encounters(self):
        self.assertEqual(encs(raw, "RBY", 3), [])  # Venusaur has no direct encounter in Red/Blue/Yellow
        self.assertTrue(encs(raw, "RBY", 1))       # Bulbasaur has

    def test_roaming_gimmighoul_is_go_only(self):
        groups = {e["group"] for e in raw["encounters"] if e["species"] == 999 and e["form"] == 1}
        self.assertEqual(groups, {"GO"})

    def test_unown_random_form_marked(self):
        self.assertTrue(any(e["form_random"] for e in encs(raw, "GSC", 201)))


if __name__ == "__main__":
    unittest.main()
