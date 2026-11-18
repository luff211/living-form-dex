"""Known game facts, checked against the real data. These pin the games, not the code."""
import unittest
from pathlib import Path

from dexbuild.assemble import assemble
from dexbuild.checks import structural_problems
from dexbuild.rules import load_rules
from tests.util import load_raw

RULES_DIR = Path(__file__).resolve().parents[2] / "rules"


def row(rows, rid):
    return next(r for r in rows if r.id == rid)


def cell(rows, rid, group):
    return row(rows, rid).cells[group]


def of_method(entries, method):
    return {v for e in entries if e.method == method for v in e.versions}


def live_versions(entries):
    """Versions of entries a player starting that game alone can use: not ended, not needing another game."""
    return {v for e in entries if not e.ended and not e.needs_other_game for v in e.versions}


class Golden(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = load_raw()
        cls.rules = load_rules(RULES_DIR)
        cls.rows, _ = assemble(cls.raw, cls.rules)

    def test_ruby_bulbasaur_line_has_no_live_entry(self):
        # Bulbasaur reaches RSE only through Colosseum/event gifts, so a Ruby-only start cannot get it
        for r in self.rows:
            if r.id.startswith(("0001-0", "0002-0", "0003-0")):
                self.assertEqual(live_versions(r.cells.get("RSE", [])), set(), r.id)

    def test_galarian_farfetchd_sword_only(self):
        self.assertEqual(live_versions(cell(self.rows, "0083-1", "SwSh")), {"SW"})

    def test_galarian_ponyta_shield_only(self):
        self.assertEqual(live_versions(cell(self.rows, "0077-1", "SwSh")), {"SH"})

    def test_oddish_firered_bellsprout_leafgreen(self):
        self.assertEqual(live_versions(cell(self.rows, "0043-0", "FRLG")), {"FR"})
        self.assertEqual(live_versions(cell(self.rows, "0069-0", "FRLG")), {"LG"})

    def test_pinsir_sword_only(self):
        self.assertEqual(live_versions(cell(self.rows, "0127-0", "SwSh")), {"SW"})

    def test_sableye_alpha_sapphire_only(self):
        self.assertEqual(live_versions(cell(self.rows, "0302-0", "ORAS")), {"AS"})

    def test_cosmoem_evolves_by_version(self):
        self.assertEqual(of_method(cell(self.rows, "0791-0", "SM"), "Evolve"), {"SN"})
        self.assertEqual(of_method(cell(self.rows, "0792-0", "SM"), "Evolve"), {"MN"})
        self.assertEqual(of_method(cell(self.rows, "0791-0", "USUM"), "Evolve"), {"US"})
        self.assertEqual(of_method(cell(self.rows, "0792-0", "SwSh"), "Evolve"), {"SH"})

    def test_sv_dlc_only_lines_carry_a_dlc_on_every_live_entry(self):
        for rid in ("1011-0", "1012-0", "1013-0", "1018-0", "1019-0"):
            for e in cell(self.rows, rid, "SV"):
                self.assertTrue(e.dlc or e.ended, (rid, e))

    def test_b2w2_regis_split_by_version(self):
        self.assertEqual(live_versions(cell(self.rows, "0377-0", "B2W2")), {"B2", "W2"})
        self.assertEqual(live_versions(cell(self.rows, "0378-0", "B2W2")), {"W2"})
        self.assertEqual(live_versions(cell(self.rows, "0379-0", "B2W2")), {"B2"})
        self.assertEqual(live_versions(cell(self.rows, "0486-0", "B2W2")), set())

    def test_forms_that_do_not_survive_home_are_not_rows(self):
        ids = {r.id for r in self.rows}
        self.assertFalse(ids & {"0020-2", "0778-2", "0025-8", "0133-1"})

    def test_cap_pikachu_not_in_oras(self):
        self.assertNotIn("ORAS", row(self.rows, "0025-1").cells)

    def test_fancy_vivillon_is_wild_only_in_scarlet_violet(self):
        for g, es in row(self.rows, "0666-18").cells.items():
            live = [e for e in es if e.method in ("Wild", "Evolve") and not e.ended]
            self.assertEqual(bool(live), g == "SV", g)
        # every other pattern needs a Pokémon GO postcard there
        self.assertEqual(live_versions(cell(self.rows, "0666-6", "SV")), set())

    def test_sv_dlc_exclusives_keep_their_version(self):
        self.assertEqual(live_versions(cell(self.rows, "0207-0-m", "SV")), {"SL"})   # Gligar
        self.assertEqual(live_versions(cell(self.rows, "0877-0", "SV")), {"VL"})     # Morpeko
        self.assertEqual(live_versions(cell(self.rows, "0037-1", "SV")), {"SL"})     # Alolan Vulpix
        self.assertEqual(live_versions(cell(self.rows, "0249-0", "SV")), {"VL"})     # Lugia: solo treat in Violet only

    def test_legends_arceus_save_bonuses(self):
        notes = {rid: " ".join(e.note or "" for e in cell(self.rows, rid, "PLA")) for rid in ("0491-0", "0492-0")}
        self.assertIn("Brilliant Diamond", notes["0491-0"])
        self.assertIn("Sword or Shield", notes["0492-0"])

    def test_bdsp_mew_not_plainly_obtainable(self):
        self.assertEqual(live_versions(cell(self.rows, "0151-0", "BDSP")), set())

    def test_deoxys_forms(self):
        self.assertEqual(of_method(cell(self.rows, "0386-1", "FRLG"), "Static"), {"FR"})
        self.assertEqual(of_method(cell(self.rows, "0386-2", "FRLG"), "Static"), {"LG"})
        e = cell(self.rows, "0386-3", "RSE")  # original release: the ticket was an event item, so ended
        self.assertEqual({v for x in e for v in x.versions}, {"E"})
        self.assertTrue(all(x.ended for x in e))

    def test_alolan_meowth_swsh_static(self):
        e = cell(self.rows, "0052-1", "SwSh")[0]
        self.assertEqual((e.method, e.place, e.dlc), ("Static", "Fields of Honor", "Isle of Armor"))

    def test_bloodmoon_ursaluna(self):
        self.assertEqual(cell(self.rows, "0901-1", "SV")[0].place, "Timeless Woods")

    def test_roaming_gimmighoul_go_only(self):
        r = row(self.rows, "0999-1")
        self.assertEqual(r.cells, {})
        self.assertEqual(r.other[0].method, "GO")

    def test_original_magearna_home_gift(self):
        gift = row(self.rows, "0801-1").other[0]
        self.assertEqual((gift.method, gift.ended), ("HOME gift", False))   # National Pokédex reward, still given

    def test_kantonian_meowth_not_in_sun_moon(self):
        self.assertNotIn("SM", row(self.rows, "0052-0").cells)

    def test_larvitar_scarlet_bagon_violet(self):
        self.assertEqual(live_versions(cell(self.rows, "0246-0", "SV")), {"SL"})
        self.assertEqual(live_versions(cell(self.rows, "0371-0", "SV")), {"VL"})

    def test_frlg_switch_deoxys_is_live(self):
        self.assertFalse(cell(self.rows, "0386-1", "FRLG")[0].ended)

    def test_random_form_spreads_are_sourced(self):
        e = cell(self.rows, "0774-7", "SM")
        self.assertTrue(all(not x.unverified for x in e))
        self.assertIn("Core colour is random", {x.note for x in e})
        self.assertFalse(any(x.unverified for x in cell(self.rows, "0666-6", "USUM")))
        self.assertEqual(live_versions(cell(self.rows, "0201-26", "HGSS")), {"HG", "SS"})

    def test_version_facts_pkhex_leaves_open(self):
        for rid, group, want in (
            ("0408-0", "DPPt", {"D", "Pt"}), ("0410-0", "BDSP", {"SP"}), ("0408-0", "SM", {"SN"}),
            ("0566-0", "USUM", {"US", "UM"}),                              # fossils sold or dug in one version
            ("0138-0", "HGSS", {"HG"}), ("0345-0", "HGSS", {"SS"}), ("0408-0", "HGSS", set()),
            ("0140-0", "ORAS", {"OR"}), ("0564-0", "ORAS", {"AS"}), ("0696-0", "ORAS", set()),
            ("0698-0", "SM", set()),                                       # Jaw/Sail never sold in Sun/Moon
            ("0380-0", "ORAS", {"AS"}), ("0381-0", "ORAS", {"OR"}),        # the other needs the Eon Ticket
            ("0123-0-m", "RBY", {"RD", "YW"}), ("0127-0", "RBY", {"GN", "YW"}), ("0038-0", "RBY", {"GN", "YW"}),
            ("0137-0", "RBY", {"RD", "GN", "YW"}),                         # Game Corner prizes
            ("0273-0", "RSE", {"R", "E"}), ("0283-0", "RSE", {"R", "S"}),  # outbreaks from record mixing
            ("0874-0", "SwSh", {"SW"}), ("0246-0", "SwSh", {"SH"}),        # Dynamax Crystal dens were an event
            ("0641-1", "ORAS", {"OR"}), ("0905-1", "PLA", {"PLA"}),        # Therian Forme by Reveal Glass
            ("0645-0", "BW", set()),                                       # needs both of the other two
        ):
            self.assertEqual(live_versions(cell(self.rows, rid, group)), want, (rid, group))

    def test_friend_safari_needs_another_player(self):
        self.assertEqual(live_versions(cell(self.rows, "0037-0", "XY")), set())      # Vulpix: Safari only
        self.assertEqual(live_versions(cell(self.rows, "0127-0", "XY")), {"X"})      # Pinsir: wild in X, Safari in both
        self.assertEqual(live_versions(cell(self.rows, "0090-0", "XY")), {"Y"})      # Shellder

    def test_event_pokewalker_courses_ended(self):
        # Rally, Sightseeing, Beyond the Sea: species found on no normal course
        for rid in ("0441-0", "0302-0", "0133-0-m", "0255-0-m", "0224-0-f", "0222-0"):
            walker = [e for e in cell(self.rows, rid, "HGSS") if "Pokéwalker" in (e.place or e.method)]
            self.assertTrue(walker and all(e.ended for e in walker), rid)
        walker = [e for e in cell(self.rows, "0025-0-m", "HGSS") if "Pokéwalker" in (e.place or e.method)]
        self.assertFalse(all(e.ended for e in walker))   # Pikachu is also on Resort

    def test_no_duplicate_entries_in_a_cell(self):
        dup = [(r.id, g) for r in self.rows for g, es in list(r.cells.items()) + [("other", r.other)]
               if len({(e.method, e.place, e.versions, e.dlc, e.ended, e.unverified, e.note, e.needs_other_game)
                       for e in es}) != len(es)]
        self.assertEqual(dup, [])

    def test_no_structural_problems(self):
        self.assertEqual(structural_problems(self.rows, self.rules, self.raw), [])


if __name__ == "__main__":
    unittest.main()
