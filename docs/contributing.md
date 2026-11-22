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

## Preview the site on your computer

```bash
pip install -r requirements.txt
python scripts/fetch_dandisets.py   # downloads the dandiset details
zensical serve                      # then open http://localhost:8000
```
