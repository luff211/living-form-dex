#!/bin/sh
# Publish site/ (with the built dex.json.gz) to the gh-pages branch that GitHub Pages serves.
# Run from the repo root after a --write build. Only the page files and the gzipped data go up.
set -eu
[ -f site/data/dex.json.gz ] || { echo "error: site/data/dex.json.gz missing; run the build with --write first" >&2; exit 1; }
tmp=$(mktemp -d)
trap 'git worktree remove --force "$tmp" 2>/dev/null || true; rm -rf "$tmp"' EXIT
if git ls-remote --exit-code --heads origin gh-pages >/dev/null; then
  git fetch -q origin gh-pages
  git worktree add -q "$tmp" FETCH_HEAD
else
  git worktree add -q --detach "$tmp"
  git -C "$tmp" checkout -q --orphan gh-pages
fi
git -C "$tmp" rm -rqf --ignore-unmatch .
mkdir -p "$tmp/data"
cp site/index.html site/app.js site/logic.js site/style.css "$tmp/"
cp site/data/dex.json.gz "$tmp/data/"
# version = date of the commit + its short hash (e.g. 2026.11.20-f30cc10); -dirty when site/ or rules/ have
# uncommitted changes. data-key = hash of the data file, so browsers fetch new data exactly when it changes.
version="$(git log -1 --format=%cd --date=format:%Y.%m.%d)-$(git rev-parse --short HEAD)"
[ -z "$(git status --porcelain -- site rules)" ] || version="$version-dirty"
key=$(sha256sum site/data/dex.json.gz | cut -c1-12)
sed -i -e "s|<meta name=\"version\" content=\"dev\">|<meta name=\"version\" content=\"$version\">|" \
       -e "s|<meta name=\"data-key\" content=\"dev\">|<meta name=\"data-key\" content=\"$key\">|" \
       -e "s|href=\"style.css\"|href=\"style.css?v=$version\"|" -e "s|src=\"app.js\"|src=\"app.js?v=$version\"|" \
       "$tmp/index.html"
# a reload refetches the page but may keep cached scripts, so each publish gives them new URLs too
sed -i "s|from \"./logic.js\"|from \"./logic.js?v=$version\"|" "$tmp/app.js"
for want in "content=\"$key\"" "style.css?v=" "app.js?v="; do
  grep -qF "$want" "$tmp/index.html" || { echo "error: could not stamp $want into index.html" >&2; exit 1; }
done
grep -qF "logic.js?v=" "$tmp/app.js" || { echo "error: could not stamp the version into app.js" >&2; exit 1; }
touch "$tmp/.nojekyll"
git -C "$tmp" add -A
if git -C "$tmp" diff --cached --quiet; then echo "gh-pages already up to date"; exit 0; fi
git -C "$tmp" commit -q -m "Publish site from $(git rev-parse --short HEAD)"
git -C "$tmp" push -q origin HEAD:gh-pages
echo "published gh-pages from $(git rev-parse --short HEAD)"
