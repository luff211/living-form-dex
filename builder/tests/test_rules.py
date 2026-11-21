import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "builder"))

from dexbuild.rules import RulesError, load_rules  # noqa: E402


class Rules(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name) / "rules"
        shutil.copytree(REPO / "rules", self.tmp)

    def tearDown(self):
        self._tmp.cleanup()

    def edit(self, name, change):
        p = self.tmp / name
        data = json.loads(p.read_text(encoding="utf-8"))
        change(data)
        p.write_text(json.dumps(data), encoding="utf-8")

    def test_loads_real_rules(self):
        r = load_rules(REPO / "rules")
        self.assertIn("RBY", [g["id"] for g in r.games["groups"]])
        self.assertIn(6, r.gmax)
        self.assertLessEqual(r.gmax_unverified, set(r.gmax))
        self.assertIn(3, r.gender_diff)
        self.assertNotIn(678, r.gender_diff)  # Meowstic genders are forms already

    def test_malformed_also_forms_is_rejected(self):
        self.edit("gender_diff.json", lambda d: d.update(also_forms=[[215]]))
        with self.assertRaisesRegex(RulesError, r"gender_diff\.json.*also_forms"):
            load_rules(self.tmp)

    def test_serebii_links_loaded(self):
        (self.tmp / "serebii.json").write_text(json.dumps(
            {"links": {"GSC": {"Route 7": "https://www.serebii.net/pokearth/kanto/2nd/route7.shtml"}}}), encoding="utf-8")
        self.assertEqual(load_rules(self.tmp).serebii["GSC"]["Route 7"],
                         "https://www.serebii.net/pokearth/kanto/2nd/route7.shtml")

    def test_sprites_loaded_and_checked(self):
        from dexbuild.rules import SPRITE_BASE
        (self.tmp / "sprites.json").write_text(json.dumps(
            {"base": SPRITE_BASE, "sprites": {"0666-19": "666-poke-ball.png", "0003-0-f": "female/3.png"}}), encoding="utf-8")
        r = load_rules(self.tmp)
        self.assertEqual((r.sprite_base, r.sprites["0666-19"]), (SPRITE_BASE, "666-poke-ball.png"))
        for bad in ({"base": "https://example.com/", "sprites": {}},
                    {"base": SPRITE_BASE, "sprites": {"0001-0": "../x.png"}},
                    {"base": SPRITE_BASE, "sprites": {"0001-0": "javascript:alert(1)"}}):
            (self.tmp / "sprites.json").write_text(json.dumps(bad), encoding="utf-8")
            with self.assertRaises(RulesError):
                load_rules(self.tmp)
        (self.tmp / "sprites.json").unlink()
        self.assertEqual(load_rules(self.tmp).sprites, {})

    def test_serebii_file_is_optional(self):
        (self.tmp / "serebii.json").unlink(missing_ok=True)
        self.assertEqual(load_rules(self.tmp).serebii, {})

    def test_serebii_link_outside_pokearth_is_rejected(self):
        (self.tmp / "serebii.json").write_text(json.dumps(
            {"links": {"GSC": {"Route 7": "https://example.com/x"}}}), encoding="utf-8")
        with self.assertRaises(RulesError):
            load_rules(self.tmp)

    def test_serebii_unknown_group_is_rejected(self):
        (self.tmp / "serebii.json").write_text(json.dumps(
            {"links": {"NOPE": {"Route 7": "https://www.serebii.net/pokearth/kanto/route7.shtml"}}}), encoding="utf-8")
        with self.assertRaises(RulesError):
            load_rules(self.tmp)

    def test_also_forms_loaded(self):
        self.assertIn((215, 1), load_rules(REPO / "rules").gender_diff_forms)

    def test_entry_without_verified_is_rejected(self):
        self.edit("forms.json", lambda d: d["exclude"]["entries"][0].pop("verified"))
        with self.assertRaisesRegex(RulesError, r"forms\.json.*verified"):
            load_rules(self.tmp)

    def test_unknown_group_is_rejected(self):
        self.edit("releases.json", lambda d: d["entries"][0].update(group="XX"))
        with self.assertRaisesRegex(RulesError, r"releases\.json.*XX"):
            load_rules(self.tmp)

    def test_unknown_version_is_rejected(self):
        self.edit("sv_exclusives.json", lambda d: d["entries"][0].update(version="SW"))
        with self.assertRaisesRegex(RulesError, r"sv_exclusives\.json.*SW"):
            load_rules(self.tmp)

    def test_malformed_json_names_the_file(self):
        (self.tmp / "dlc.json").write_text("{not json", encoding="utf-8")
        with self.assertRaisesRegex(RulesError, r"dlc\.json"):
            load_rules(self.tmp)

    def test_main_group_without_home_route_is_rejected(self):
        self.edit("games.json", lambda d: d["groups"][0].pop("home_route"))
        with self.assertRaisesRegex(RulesError, r"games\.json.*RBY.*home_route"):
            load_rules(self.tmp)

    def test_duplicate_version_code_is_rejected(self):
        self.edit("games.json", lambda d: d["groups"][1]["versions"][0].update(code="RD"))
        with self.assertRaisesRegex(RulesError, r"games\.json.*RD"):
            load_rules(self.tmp)

    def test_dlc_entry_by_species_loads_and_needs_locations_or_species(self):
        self.edit("dlc.json", lambda d: d["entries"].append(
            {"group": "SV", "dlc": "The Indigo Disk", "species": [250], "method": "Static", "verified": False, "checked": ""}))
        self.assertIn(250, load_rules(self.tmp).dlc[-1]["species"])
        self.edit("dlc.json", lambda d: d["entries"].append({"group": "SV", "dlc": "X", "verified": False, "checked": ""}))
        with self.assertRaisesRegex(RulesError, r"dlc\.json.*locations.*species"):
            load_rules(self.tmp)

    def test_dlc_species_must_be_integers(self):
        self.edit("dlc.json", lambda d: d["entries"].append(
            {"group": "SV", "dlc": "X", "species": ["250"], "verified": False, "checked": ""}))
        with self.assertRaisesRegex(RulesError, r"dlc\.json.*species"):
            load_rules(self.tmp)

    def test_release_needs_other_game_must_be_boolean(self):
        self.edit("releases.json", lambda d: d["entries"][0]["set"].update(needs_other_game="yes"))
        with self.assertRaisesRegex(RulesError, r"releases\.json.*needs_other_game"):
            load_rules(self.tmp)

    def test_gmax_forms_and_mega_forms(self):
        r = load_rules(REPO / "rules")
        self.assertEqual(r.gmax[892], "all")
        self.assertIsNone(r.gmax[25])
        self.assertEqual(r.mega_forms[670], [5])
        self.edit("gmax.json", lambda d: d["entries"][0].update(forms="some"))
        with self.assertRaisesRegex(RulesError, r"gmax\.json.*forms"):
            load_rules(self.tmp)

    def test_mega_forms_needs_form_list(self):
        self.edit("forms.json", lambda d: d.setdefault("mega_forms", {"entries": []})["entries"].append(
            {"species": 670, "forms": 5, "verified": False, "checked": ""}))
        with self.assertRaisesRegex(RulesError, r"mega_forms.*forms"):
            load_rules(self.tmp)

    def test_no_spread_loaded(self):
        self.assertIn((666, 18), load_rules(REPO / "rules").no_spread)


if __name__ == "__main__":
    unittest.main()
