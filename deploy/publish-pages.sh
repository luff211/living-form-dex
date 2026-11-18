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
touch "$tmp/.nojekyll"
git -C "$tmp" add -A
if git -C "$tmp" diff --cached --quiet; then echo "gh-pages already up to date"; exit 0; fi
git -C "$tmp" commit -q -m "Publish site from $(git rev-parse --short HEAD)"
git -C "$tmp" push -q origin HEAD:gh-pages
echo "published gh-pages from $(git rev-parse --short HEAD)"
