"""Build the dashboard data from dandisets.yaml.

Reads the dandiset IDs listed in dandisets.yaml, looks each one up on the
DANDI Archive, and writes docs/data/dandisets.json for the dashboard page.

    python scripts/fetch_dandisets.py

Exits with an error if an entry is malformed, listed twice, or not found
on DANDI, so a typo in a pull request fails the check instead of the site.
"""

from __future__ import annotations

import json
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
LIST_FILE = ROOT / "dandisets.yaml"
OUT_FILE = ROOT / "docs" / "data" / "dandisets.json"
API = "https://api.dandiarchive.org/api"
GUI = "https://dandiarchive.org/dandiset"

# Common names for species, keyed by NCBI taxonomy ID.
SPECIES = {
    "9606": "Human",
    "10090": "Mouse",
    "10116": "Rat",
    "9544": "Rhesus macaque",
    "9541": "Cynomolgus macaque",
    "9545": "Pig-tailed macaque",
    "9483": "Marmoset",
    "9823": "Pig",
    "9685": "Cat",
    "9615": "Dog",
    "10141": "Guinea pig",
}

# Short labels for DANDI's "approach" terms.
APPROACHES = {
    "electrophysiological approach": "Electrophysiology",
    "microscopy approach; cell population imaging": "Imaging",
    "behavioral approach": "Behavior",
    "histological approach": "Histology",
    "multimodal approach": "Multimodal",
    "spatial transcriptomics approach": "Spatial transcriptomics",
}

DATA_STANDARDS = {
    "Neurodata Without Borders (NWB)": "NWB",
    "Brain Imaging Data Structure (BIDS)": "BIDS",
    "OME/NGFF Standard": "OME-Zarr",
}

PAPER_RELATIONS = {"dcite:IsDescribedBy", "dcite:IsPublishedIn", "dcite:IsSupplementTo"}
PAPER_TYPES = {"dcite:JournalArticle", "dcite:Preprint", "dcite:DataPaper"}


def get_json(url: str) -> dict:
    """GET a DANDI API URL, retrying on network errors and server errors."""
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as err:
            if err.code < 500 or attempt == 3:
                raise
        except urllib.error.URLError:
            if attempt == 3:
                raise
        time.sleep(2 ** attempt)
    raise RuntimeError("unreachable")


def read_list() -> list[dict]:
    """Read and validate dandisets.yaml. Returns entries as dicts with 'id'."""
    raw = yaml.safe_load(LIST_FILE.read_text()) or []
    if isinstance(raw, dict):  # also accept a top-level "dandisets:" key
        raw = raw.get("dandisets") or []
    errors, entries, seen = [], [], set()
    for n, item in enumerate(raw, 1):
        entry = {"id": item} if isinstance(item, (str, int)) else dict(item or {})
        did = str(entry.get("id", "")).strip()
        if did.isdigit() and len(did) < 6:
            did = did.zfill(6)  # YAML read an unquoted ID as a number
        if not re.fullmatch(r"\d{6}", did):
            errors.append(f"entry {n}: '{entry.get('id')}' is not a six-digit dandiset ID")
            continue
        if did in seen:
            errors.append(f"entry {n}: {did} is listed more than once")
            continue
        seen.add(did)
        entry["id"] = did
        entries.append(entry)
    if errors:
        sys.exit("dandisets.yaml has problems:\n  " + "\n  ".join(errors))
    return entries


def person_name(name: str) -> str:
    """'Lee, Brian' -> 'Brian Lee'."""
    if "," in name:
        last, first = (p.strip() for p in name.split(",", 1))
        return f"{first} {last}".strip()
    return name.strip()


def species_list(summary: dict) -> list[dict]:
    out, seen = [], set()
    for sp in summary.get("species") or []:
        taxon = (sp.get("identifier") or "").rsplit("_", 1)[-1].rsplit("/", 1)[-1]
        full = sp.get("name") or ""
        scientific = full.split(" - ")[0].strip()
        common = SPECIES.get(taxon) or (full.split(" - ")[-1].strip() if " - " in full else full)
        key = taxon or common.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append({"name": common, "scientific": scientific if scientific != common else ""})
    return out


def approach_list(summary: dict) -> list[str]:
    out = []
    for ap in summary.get("approach") or []:
        name = (ap.get("name") or "").strip()
        label = APPROACHES.get(name) or name.removesuffix(" approach").capitalize()
        if label and label not in out:
            out.append(label)
    return out


KEYWORD_SPECIES = {"mouse": "Mouse", "human": "Human", "rat": "Rat", "macaque": "Macaque", "marmoset": "Marmoset"}
KEYWORD_APPROACHES = {"calcium imaging": "Imaging", "two-photon": "Imaging", "2-photon": "Imaging",
                      "patch-seq": "Electrophysiology", "neuropixels": "Electrophysiology"}


def from_keywords(keywords: list[str], table: dict) -> list[str]:
    """Fallback for drafts whose files DANDI hasn't summarized yet."""
    out = []
    for kw in keywords:
        for term, label in table.items():
            if re.search(rf"\b{re.escape(term)}\b", kw.lower()) and label not in out:
                out.append(label)
    return out


def paper_links(meta: dict) -> list[dict]:
    out = []
    for res in meta.get("relatedResource") or []:
        url = res.get("url") or ""
        if not url and (res.get("identifier") or "").lower().startswith("doi:"):
            url = "https://doi.org/" + res["identifier"][4:]
        if not url.startswith(("http://", "https://")):
            continue
        if res.get("relation") in PAPER_RELATIONS and res.get("resourceType") in PAPER_TYPES:
            kind = "Preprint" if res.get("resourceType") == "dcite:Preprint" else "Paper"
            out.append({"label": kind, "url": url})
    return out


def build_record(entry: dict) -> dict:
    did = entry["id"]
    try:
        info = get_json(f"{API}/dandisets/{did}/")
    except urllib.error.HTTPError as err:
        if err.code == 404:
            raise LookupError(f"{did} was not found on DANDI. Check the ID in dandisets.yaml.")
        if err.code in (401, 403):
            raise LookupError(f"{did} is embargoed or private on DANDI, so it can't be shown yet.")
        raise
    version = info.get("most_recent_published_version") or info["draft_version"]
    meta = get_json(f"{API}/dandisets/{did}/versions/{version['version']}/")
    summary = meta.get("assetsSummary") or {}
    contributors = meta.get("contributor") or []

    def roles(c):
        return {r.removeprefix("dcite:") for r in c.get("roleName") or []}

    people = [c for c in contributors if c.get("schemaKey") == "Person"]
    contacts = [person_name(c["name"]) for c in people if "ContactPerson" in roles(c)]
    orgs = [
        c["name"] for c in contributors
        if c.get("schemaKey") == "Organization" and "Funder" not in roles(c) and c.get("name")
    ]
    published = version["version"] != "draft"
    doi = meta.get("doi") if published else None
    record = {
        "id": did,
        "title": meta.get("name") or info.get("draft_version", {}).get("name") or did,
        "description": " ".join((meta.get("description") or "").split()),
        "status": "published" if published else "draft",
        "version": version["version"],
        "url": f"{GUI}/{did}",
        "doi": doi,
        "doi_url": f"https://doi.org/{doi}" if doi else None,
        "papers": paper_links(meta),
        "species": species_list(summary),
        "approaches": approach_list(summary),
        "standards": [DATA_STANDARDS.get(s.get("name"), s.get("name")) for s in summary.get("dataStandard") or []],
        "subjects": summary.get("numberOfSubjects") or 0,
        "files": summary.get("numberOfFiles") or 0,
        "bytes": summary.get("numberOfBytes") or 0,
        "contacts": contacts[:3],
        "organizations": orgs[:2],
        "keywords": meta.get("keywords") or [],
        "license": [lic.removeprefix("spdx:") for lic in meta.get("license") or []],
        "created": (info.get("created") or meta.get("dateCreated") or "")[:10],
        "published": (meta.get("datePublished") or "")[:10] or None,
        "updated": (info.get("modified") or "")[:10],
    }
    if not record["species"]:
        record["species"] = [{"name": n, "scientific": ""} for n in from_keywords(record["keywords"], KEYWORD_SPECIES)]
    if not record["approaches"]:
        record["approaches"] = from_keywords(record["keywords"], KEYWORD_APPROACHES)
    if entry.get("note"):
        record["note"] = str(entry["note"]).strip()
    return record


def main() -> None:
    entries = read_list()
    records, errors = [], []
    for entry in entries:
        try:
            records.append(build_record(entry))
            print(f"  {entry['id']}  ok")
        except LookupError as err:
            errors.append(str(err))
            print(f"  {entry['id']}  ERROR")
    if errors:
        sys.exit("Could not load every dandiset:\n  " + "\n  ".join(errors))
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps({
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
        "dandisets": records,
    }, indent=1))
    print(f"Wrote {len(records)} dandisets to {OUT_FILE.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
