# BICAN Dandisets

A dashboard of data from the [BRAIN Initiative Cell Atlas Network (BICAN)](https://brain-bican.org/) on the [DANDI Archive](https://dandiarchive.org/).

**Site:** https://kabilar.github.io/dandi-bican/

## Add a dandiset

Add its ID to [`dandisets.yaml`](dandisets.yaml) and open a pull request:

```yaml
- id: "000636"
```

That's all. The title, species, size, contributors and links come from DANDI. The pull request check fails if the ID is mistyped, already listed, or not public on DANDI. You can also [suggest a dandiset](https://github.com/kabilar/dandi-bican/issues/new?template=add-dandiset.yml) instead. More detail is on the site's [Add a dandiset](docs/contributing.md) page.

## How it works

| Path | What it is |
|---|---|
| `dandisets.yaml` | The list of dandisets. The only file most people edit. |
| `scripts/fetch_dandisets.py` | Looks up each dandiset on DANDI and writes `docs/data/dandisets.json`. |
| `docs/` | The site's pages (Markdown), plus the dashboard's script and styles. |
| `zensical.toml` | Site settings and navigation, for [Zensical](https://zensical.org/). |
| `.github/workflows/site.yml` | Checks pull requests, then rebuilds and publishes the site on every merge and once a day. |

## Preview locally

```bash
pip install -r requirements.txt
python scripts/fetch_dandisets.py
zensical serve
```

## One-time setup

In the repository's **Settings → Pages**, set **Source** to **GitHub Actions**.
