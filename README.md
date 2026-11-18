# Living form dex

A static page showing, for every Pokémon form, where it can be obtained in each main series game. Licence: GPL-3.0-or-later.

Pipeline: .NET exporter (PKHeX data) → `build/raw.json` → Python build step → static page.

```sh
export DOTNET_ROOT=$HOME/.dotnet DOTNET_CLI_TELEMETRY_OPTOUT=1 DOTNET_NOLOGO=1
~/.dotnet/dotnet run --project exporter -- rules/games.json build/raw.json   # about 25 s
(cd builder && python3 -m unittest discover -s tests -v)
(cd site && node --test tests/)
```

## Serving

Public copy: https://luff211.github.io/living-form-dex/ (GitHub Pages, `gh-pages` branch). After a `--write` build, run `deploy/publish-pages.sh` from the repo root to push the page files and `dex.json.gz` there. Ticks are saved per site, so use Export / Import to move them between this copy and the tailnet one.


The page is served by a systemd user service, bound to the Tailscale address only (not LAN, not loopback):

- `http://<host>.<tailnet>.ts.net:8507/` or `http://<tailscale-ip>:8507/`
- Put `BIND=<tailscale-ip>` in `~/.config/living-form-dex.env` first; the unit reads it from there.
- Unit: `deploy/living-form-dex.service`, symlinked into `~/.config/systemd/user/`. To install it:

  ```sh
  ln -s ~/living-form-dex/deploy/living-form-dex.service ~/.config/systemd/user/
  systemctl --user daemon-reload
  systemctl --user enable --now living-form-dex.service
  ```

  After any change to the unit file, run `systemctl --user daemon-reload` before restarting.
- Restart: `systemctl --user restart living-form-dex.service`
- Rebuild the data with the exporter command above, then from the repo root: `PYTHONPATH=builder python3 -m dexbuild --raw build/raw.json --rules rules --out site/data/dex.json --write`. Without `--write` the build only prints its report (rows, left out, unverified cells, problems); it writes only when there are no problems. It writes `site/data/dex.json` and a gzipped copy `dex.json.gz`, which is what the page fetches (about 270 KB instead of 6.9 MB; the browser unzips it with `DecompressionStream`). The server reads files per request, so a rebuild needs only a browser refresh.
