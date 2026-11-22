# Add a dandiset

The dashboard lists the dandisets in [`dandisets.yaml`](https://github.com/kabilar/dandi-bican/blob/main/dandisets.yaml). To add one, you only need its six-digit ID. The title, species, size, contributors and links come from DANDI, and refresh every day.

## Edit the list in your browser

1. Open [`dandisets.yaml` in GitHub's editor](https://github.com/kabilar/dandi-bican/edit/main/dandisets.yaml).
2. Add a line with the dandiset ID. Keep the quotes, so the leading zeros stay:

    ```yaml
    - id: "000636"
    ```

    To show a short line on the card, add a note:

    ```yaml
    - id: "000636"
      note: "Data for Lee et al. 2023, Science"
    ```

3. Commit the change and open a pull request. GitHub walks you through it.

A check runs on the pull request. It fails if the ID is mistyped, already listed, or not public on DANDI, and tells you which. Once the pull request is merged, the site updates within a few minutes.

## What belongs here

Dandisets from BICAN work: data produced under a BICAN grant, or the data behind a BICAN paper. If you're not sure, ask in your pull request.

## Edit or add a page

Pages are Markdown files in the [`docs/`](https://github.com/kabilar/dandi-bican/tree/main/docs) folder. To edit a page, use the pencil icon at the top of it. To add a page, create a `.md` file in `docs/` and list it under `nav` in [`zensical.toml`](https://github.com/kabilar/dandi-bican/blob/main/zensical.toml).

## How the site works

| File | What it is |
|---|---|
| [`dandisets.yaml`](https://github.com/kabilar/dandi-bican/blob/main/dandisets.yaml) | The list of dandisets. The only file most people edit. |
| [`scripts/fetch_dandisets.py`](https://github.com/kabilar/dandi-bican/blob/main/scripts/fetch_dandisets.py) | Looks up each dandiset on DANDI and writes `docs/data/dandisets.json`. |
| [`docs/`](https://github.com/kabilar/dandi-bican/tree/main/docs) | The site's pages (Markdown), plus the dashboard's script and styles. |
| [`zensical.toml`](https://github.com/kabilar/dandi-bican/blob/main/zensical.toml) | Site settings and navigation, for [Zensical](https://zensical.org/). |
| [`.github/workflows/site.yml`](https://github.com/kabilar/dandi-bican/blob/main/.github/workflows/site.yml) | Checks pull requests, then rebuilds and publishes the site on every merge and once a day. |

## Preview the site on your computer

```bash
pip install -r requirements.txt
python scripts/fetch_dandisets.py   # downloads the dandiset details
zensical serve                      # then open http://localhost:8000
```

## Publishing

The site publishes to GitHub Pages automatically. It needs one setting, once: in the repository's **Settings → Pages**, set **Source** to **GitHub Actions**.
