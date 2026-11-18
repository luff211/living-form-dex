import json
import unittest
from pathlib import Path

RAW = Path(__file__).resolve().parents[2] / "build" / "raw.json"


def load_raw():
    if not RAW.exists():
        raise unittest.SkipTest("build/raw.json missing; run the exporter first")
    return json.loads(RAW.read_text(encoding="utf-8"))


def species(raw, sid):
    return next(s for s in raw["species"] if s["id"] == sid)


def form(sp, n):
    return next(f for f in sp["forms"] if f["form"] == n)
