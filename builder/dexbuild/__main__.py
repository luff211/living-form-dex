"""python3 -m dexbuild --raw PATH --rules DIR --out PATH [--write]"""
import argparse
import gzip
import json
import os
import sys
from pathlib import Path

from .assemble import assemble, to_json
from .checks import structural_problems
from .kinds import UnknownKind
from .rules import RulesError, load_rules


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="dexbuild")
    ap.add_argument("--raw", required=True, type=Path)
    ap.add_argument("--rules", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--write", action="store_true", help="write --out (default is report only)")
    a = ap.parse_args(argv)
    try:
        raw = json.loads(a.raw.read_text(encoding="utf-8"))
        rules = load_rules(a.rules)
        rows, left = assemble(raw, rules)
    except (OSError, ValueError, KeyError) as e:
        print(f"error: cannot read input ({a.raw}): {e}", file=sys.stderr)
        return 1
    except (RulesError, UnknownKind) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    problems = structural_problems(rows, rules, raw)
    unverified = sum(any(e.unverified for e in es) for r in rows for es in r.cells.values())
    print(f"rows: {len(rows)}")
    print(f"left out: {len(left)}")
    for x in left:
        print(f"  {x.species:04d}-{x.form} {x.name} {x.form_name}".rstrip()
              + f": {x.reason}" + ("" if x.verified else " [unverified]"))
    print(f"unverified cells: {unverified}")
    print(f"problems: {len(problems)}")
    for p in problems:
        print(f"  {p}")
    if problems:
        return 1
    if a.write:
        data = (json.dumps(to_json(rows, rules, raw), ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
        # the page fetches the .gz (~40x smaller); the plain file is for people and scripts
        for path, body in ((a.out, data), (Path(f"{a.out}.gz"), gzip.compress(data, mtime=0))):
            tmp = Path(f"{path}.tmp")
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                tmp.write_bytes(body)
                os.replace(tmp, path)
            except OSError as e:
                print(f"error: cannot write {path}: {e}", file=sys.stderr)
                tmp.unlink(missing_ok=True)
                return 1
            print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
