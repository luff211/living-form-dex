import gzip
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.util import RAW, load_raw

REPO = Path(__file__).resolve().parents[2]
BUILDER = REPO / "builder"


class CliTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = load_raw()

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.out = str(self.tmp / "dex.json")

    def tearDown(self):
        self._tmp.cleanup()

    def run_cli(self, *extra, raw=RAW, rules=REPO / "rules", out=None):
        return subprocess.run([sys.executable, "-m", "dexbuild", "--raw", str(raw), "--rules", str(rules),
                               "--out", out or self.out, *extra], cwd=BUILDER, capture_output=True, text=True)

    def test_default_is_report_only(self):
        p = self.run_cli()
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("problems: 0", p.stdout)
        self.assertFalse(os.path.exists(self.out))

    def test_write_is_atomic_and_valid_json(self):
        p = self.run_cli("--write")
        self.assertEqual(p.returncode, 0, p.stderr)
        d = json.loads(Path(self.out).read_text(encoding="utf-8"))
        self.assertEqual(d["meta"]["rows"], len(d["rows"]))
        self.assertFalse(os.path.exists(self.out + ".tmp"))
        first = Path(self.out).read_bytes()
        self.assertEqual(gzip.decompress(Path(self.out + ".gz").read_bytes()), first)   # what the page fetches
        gz = Path(self.out + ".gz").read_bytes()
        self.run_cli("--write")
        self.assertEqual(Path(self.out).read_bytes(), first)
        self.assertEqual(Path(self.out + ".gz").read_bytes(), gz)

    def test_problems_block_write(self):
        rules = self.tmp / "rules"
        shutil.copytree(REPO / "rules", rules)
        f = json.loads((rules / "forms.json").read_text(encoding="utf-8"))
        f["exclude"]["entries"].append({"species": 132, "forms": [0, 0], "reason": "t", "verified": False, "checked": ""})
        (rules / "forms.json").write_text(json.dumps(f), encoding="utf-8")
        p = self.run_cli("--write", rules=rules)
        self.assertEqual(p.returncode, 1)
        self.assertIn("dex 132", p.stdout)
        self.assertFalse(os.path.exists(self.out))

    def test_unknown_kind_exits_1_naming_type(self):
        raw = json.loads(json.dumps(self.raw))
        e = dict(raw["encounters"][0], type="EncounterBrandNew12", egg=False)
        raw["encounters"].append(e)
        bad = self.tmp / "raw.json"
        bad.write_text(json.dumps(raw), encoding="utf-8")
        p = self.run_cli(raw=bad)
        self.assertEqual(p.returncode, 1)
        self.assertIn("EncounterBrandNew12", p.stderr)
        self.assertNotIn("Traceback", p.stderr)

    def test_bad_inputs_exit_1_without_traceback(self):
        junk = self.tmp / "junk.json"
        junk.write_text("{nope", encoding="utf-8")
        for p in (self.run_cli(raw=self.tmp / "missing.json"), self.run_cli(raw=junk),
                  self.run_cli(rules=self.tmp / "norules"),
                  self.run_cli("--write", out="/proc/nope/dex.json")):
            self.assertEqual(p.returncode, 1, p.stderr)
            self.assertTrue(p.stderr.startswith("error:"), p.stderr)
            self.assertNotIn("Traceback", p.stderr)


if __name__ == "__main__":
    unittest.main()
