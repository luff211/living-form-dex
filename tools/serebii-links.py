#!/usr/bin/env python3
"""Link dex locations to Serebii PokéEarth pages.

  fetch: crawl the PokéEarth region indexes and each location's main page into build/serebii-cache/,
         slowly (one request every --delay seconds) and resumably; pages already cached are not fetched again.
  map:   match the locations in site/data/dex.json to cached pages and report the result;
         with --write, write rules/serebii.json. Only URLs that Serebii itself links to are used.
"""
import argparse, html, json, re, sys, time, urllib.request
from pathlib import Path

BASE = "https://www.serebii.net"
REGIONS = ["kanto", "johto", "hoenn", "sinnoh", "unova", "kalos", "alola", "galar", "hisui", "paldea",
           "kitakami", "terarium", "lumiosecity"]
CACHE = Path("build/serebii-cache")
UA = "living-form-dex link check"

# group -> [(region, generation folder)]; "" is the region's main page for that location.
# From the 2026-11 crawl: main pages are the newest game for that region (kanto = LGPE, johto = HGSS,
# hoenn = ORAS, sinnoh = BDSP, unova = BW and B2W2 together); older games live in the generation folders.
GROUP_PAGES: dict[str, list[tuple[str, str]]] = {
    "RBY": [("kanto", "1st")],
    "GSC": [("johto", "2nd"), ("kanto", "2nd")],
    "RSE": [("hoenn", "3rd")],
    "FRLG": [("kanto", "3rd")],
    "DPPt": [("sinnoh", "4th")],
    # Routes 26-28 and Tohjo Falls are not in LGPE, so their kanto main page is the HGSS one
    "HGSS": [("johto", ""), ("kanto", "4th"), ("kanto", "")],
    "BW": [("unova", "")],
    "B2W2": [("unova", "")],
    "XY": [("kalos", "")],
    "ORAS": [("hoenn", "")],
    "SM": [("alola", "")],
    "USUM": [("alola", "")],
    "LGPE": [("kanto", "")],
    "SwSh": [("galar", "")],
    "BDSP": [("sinnoh", "")],
    "PLA": [("hisui", "")],
    "SV": [("paldea", ""), ("kitakami", ""), ("terarium", "")],
    "ZA": [("lumiosecity", "")],
}


def cache_path(url_path: str) -> Path:
    return CACHE / (url_path.strip("/").replace("/", "__") or "index")


def get(url_path: str, delay: float) -> str | None:
    p = cache_path(url_path)
    if p.exists():
        return p.read_text(encoding="utf-8")
    time.sleep(delay)
    req = urllib.request.Request(BASE + url_path, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=30) as res:
            text = res.read().decode("latin-1")
    except urllib.error.HTTPError as e:
        text = f"<!-- HTTP {e.code} -->"
    except OSError as e:
        print(f"  skip {url_path}: {e}", file=sys.stderr)
        return None  # not cached: tried again next run
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return text


def region_locations(region: str, page: str) -> dict[str, str]:
    """name -> main location page path, from the region index's location dropdown."""
    opts = re.findall(r'<option[^>]*value="(/pokearth/' + region + r'/[^"/]+\.shtml)"[^>]*>([^<]+)', page)
    return {html.unescape(name).strip(): path for path, name in opts if not path.endswith("/index.shtml")}


def variants(page: str, region: str, slug: str) -> list[str]:
    """Generation folders this location page links to for the same location ("" = itself)."""
    found = set(re.findall(r'href="/pokearth/' + region + r'/([^"/]+)/' + re.escape(slug) + r'"', page))
    return sorted(found)


def norm(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower().replace("é", "e"))


# dex place name -> Serebii's name for it, where they differ
ALIASES = {"Silver Cave": "Mt. Silver", "Mt. Silver Cave": "Mt. Silver", "Team Rocket HQ": "Rocket Hideout",
           "Ruin Maniac Cave": "Ruins Maniac's Cave", "Mount Coronet": "Mt. Coronet",
           "Aqua Hideout": "Aqua/Magma Hideout", "Team Aqua Hideout": "Aqua/Magma Hideout",
           "Team Magma Hideout": "Magma Hideout", "Cold Storage/PWT": "Cold Storage",
           "Team Flare Secret HQ": "Team Flare HQ", "Wedgehurst Station": "Wedgehurst",
           "Motostoke Stadium": "Motostoke", "Area Zero Underdepths": "Area Zero",
           "the Pokémon Research Lab": "Pokemon Research Lab",
           # the lake caverns are on the lake pages
           "Acuity Cavern": "Lake Acuity", "Valor Cavern": "Lake Valor", "Verity Cavern": "Lake Verity",
           # the seven Tanoby chambers are on the Tanoby Ruins page
           **{f"{c} Chamber": "Tanoby Ruins" for c in ("Monean", "Liptoo", "Weepth", "Dilford", "Scufib", "Rixy",
                                                       "Viapois")}}


def candidates(place: str) -> list[str]:
    """The place, then with its '; note' and trailing '(...)' parts dropped one at a time:
    'Eterna Forest (2)' -> 'Eterna Forest', 'Axew’s Eye (Wild Area)' -> 'Axew’s Eye'."""
    out = [place]
    name = place.split(";")[0].strip()
    while True:
        # Z-A sectors, streets and plazas are on their district's page
        district = re.sub(r"^(Bleu|Jaune|Magenta|Rouge|Vert) (Sector \d+|Street|Plaza)$", r"\1 District", name)
        for n in (name, ALIASES.get(name), district):
            if n and n not in out:
                out.append(n)
        cut = re.sub(r"\s*\([^()]*\)$", "", name)
        if cut == name or not cut:
            return out
        name = cut


def fetch(delay: float):
    for region in REGIONS:
        index = get(f"/pokearth/{region}/", delay)
        if index is None:
            continue
        locs = region_locations(region, index)
        todo = [p for p in locs.values() if not cache_path(p).exists()]
        print(f"{region}: {len(locs)} locations, {len(todo)} to fetch", flush=True)
        for path in todo:
            get(path, delay)


def survey():
    """Print, per region, which generation folders the cached pages link to and a sample title for each."""
    for region in REGIONS:
        p = cache_path(f"/pokearth/{region}/")
        if not p.exists():
            continue
        locs = region_locations(region, p.read_text(encoding="utf-8"))
        folders, titles = {}, {}
        for path in locs.values():
            c = cache_path(path)
            if not c.exists():
                continue
            page = c.read_text(encoding="utf-8")
            t = re.search(r"<title>(.*?)</title>", page)
            titles.setdefault("", t.group(1) if t else "?")
            for f in variants(page, region, path.rsplit("/", 1)[1]):
                folders[f] = folders.get(f, 0) + 1
        print(region, len(locs), "main page e.g.", titles.get(""), "| folders:", folders)


def build_map(dex: dict) -> tuple[dict, dict]:
    links, missing = {}, {}
    for group in dex["groups"]:
        g = group["id"]
        places = sorted({e["place"] for r in dex["rows"] for e in r["cells"].get(g, [])
                         if e["place"] and e["method"] not in ("Evolve", "Breed")})
        pages = GROUP_PAGES.get(g, [])
        found = {}
        for region, folder in pages:
            p = cache_path(f"/pokearth/{region}/")
            if not p.exists():
                continue
            locs = {norm(n): path for n, path in region_locations(region, p.read_text(encoding="utf-8")).items()}
            for place in places:
                path = next((locs[norm(c)] for c in candidates(place) if norm(c) in locs), None)
                if place in found or not path or not cache_path(path).exists():
                    continue
                slug = path.rsplit("/", 1)[1]
                if folder == "":
                    found[place] = BASE + path
                else:
                    vs = variants(cache_path(path).read_text(encoding="utf-8"), region, slug)
                    if folder in vs:
                        found[place] = f"{BASE}/pokearth/{region}/{folder}/{slug}"
                    elif not vs:  # a page with no per-generation versions is the only page for that place
                        found[place] = BASE + path
        if found:
            links[g] = dict(sorted(found.items()))
        if pages:
            missing[g] = [p for p in places if p not in found]
    return links, missing


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", choices=["fetch", "survey", "map"])
    ap.add_argument("--delay", type=float, default=4.0, help="seconds between requests (fetch)")
    ap.add_argument("--write", action="store_true", help="map: write rules/serebii.json")
    a = ap.parse_args()
    if a.mode == "fetch":
        fetch(a.delay)
    elif a.mode == "survey":
        survey()
    else:
        links, missing = build_map(json.loads(Path("site/data/dex.json").read_text(encoding="utf-8")))
        for g in GROUP_PAGES:
            print(f"{g}: {len(links.get(g, {}))} linked, {len(missing.get(g, []))} not matched")
            for p in missing.get(g, [])[:40]:
                print(f"    {p}")
        if a.write:
            Path("rules/serebii.json").write_text(json.dumps({"links": links}, ensure_ascii=False, indent=1) + "\n",
                                                  encoding="utf-8")
            print("wrote rules/serebii.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
