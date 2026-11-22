"""Build the dashboard data from dandisets.yaml.

Reads the dandiset IDs listed in dandisets.yaml, looks each one up on the
DANDI Archive, and writes docs/data/dandisets.json for the dashboard page.

    python scripts/fetch_dandisets.py

Exits with an error if an entry is malformed, listed twice, or not found
on DANDI, so a typo in a pull request fails the check instead of the site.
"""

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

# For drafts that DANDI hasn't summarized yet: guess species and data type from keywords.
KEYWORD_SPECIES = {"mouse": "Mouse", "human": "Human", "rat": "Rat", "macaque": "Macaque", "marmoset": "Marmoset"}
KEYWORD_APPROACHES = {"calcium imaging": "Imaging", "two-photon": "Imaging", "2-photon": "Imaging",
                      "patch-seq": "Electrophysiology", "neuropixels": "Electrophysiology"}

PAPER_RELATIONS = {"dcite:IsDescribedBy", "dcite:IsPublishedIn", "dcite:IsSupplementTo"}
PAPER_TYPES = {"dcite:JournalArticle", "dcite:Preprint", "dcite:DataPaper"}


def get_json(url):
    """GET a DANDI API URL, retrying network and server errors."""
    for attempt in range(4):
        try:
            with urllib.request.urlopen(url, timeout=60) as resp:
                return json.load(resp)
        except urllib.error.URLError as err:
            # Retrying won't fix a client error such as 404 (HTTPError has a code; URLError doesn't).
            if attempt == 3 or getattr(err, "code", 500) < 500:
                raise
            time.sleep(2 ** attempt)


def read_list():
    """Read and check dandisets.yaml. Returns its entries, each with a six-digit 'id'."""
    raw = yaml.safe_load(LIST_FILE.read_text()) or []
    if isinstance(raw, dict):  # also accept a top-level "dandisets:" key
        raw = raw.get("dandisets") or []
    entries, errors, seen = [], [], set()
    for n, item in enumerate(raw, 1):
        entry = dict(item) if isinstance(item, dict) else {"id": item}
        did = str(entry.get("id", "")).strip()
        if did.isdigit():
            did = did.zfill(6)  # YAML reads an unquoted ID as a number, dropping leading zeros
        if not re.fullmatch(r"\d{6}", did):
            errors.append(f"entry {n}: '{entry.get('id')}' is not a six-digit dandiset ID")
        elif did in seen:
            errors.append(f"entry {n}: {did} is listed more than once")
        else:
            seen.add(did)
            entries.append({**entry, "id": did})
    if errors:
        sys.exit("dandisets.yaml has problems:\n  " + "\n  ".join(errors))
    return entries


def unique(items):
    """Drop empty and repeated items, keeping the first of each."""
    return [x for x in dict.fromkeys(items) if x]


def from_keywords(keywords, table):
    return unique(label for kw in keywords for term, label in table.items()
                  if re.search(rf"\b{re.escape(term)}\b", kw.lower()))


def species_list(summary):
    found = {}
    for sp in summary.get("species") or []:
        taxon = (sp.get("identifier") or "").rsplit("_", 1)[-1].rsplit("/", 1)[-1]
        parts = (sp.get("name") or "").split(" - ")  # e.g. "Homo sapiens - Human"
        scientific, common = parts[0].strip(), SPECIES.get(taxon) or parts[-1].strip()
        found.setdefault(taxon or common.lower(), {"name": common, "scientific": scientific if scientific != common else ""})
    return list(found.values())


def paper_links(meta):
    links = []
    for res in meta.get("relatedResource") or []:
        url, ident = res.get("url") or "", res.get("identifier") or ""
        if not url and ident.lower().startswith("doi:"):
            url = "https://doi.org/" + ident[4:]
        if url.startswith(("http://", "https://")) and res.get("relation") in PAPER_RELATIONS \
                and res.get("resourceType") in PAPER_TYPES:
            links.append({"label": "Preprint" if res["resourceType"] == "dcite:Preprint" else "Paper", "url": url})
    return links


def build_record(entry):
    did = entry["id"]
    try:
        info = get_json(f"{API}/dandisets/{did}/")
    except urllib.error.HTTPError as err:
        if err.code == 404:
            raise LookupError(f"{did} was not found on DANDI. Check the ID in dandisets.yaml.")
        if err.code in (401, 403):
            raise LookupError(f"{did} is embargoed or private on DANDI, so it can't be shown yet.")
        raise
    version = (info.get("most_recent_published_version") or info["draft_version"])["version"]
    meta = get_json(f"{API}/dandisets/{did}/versions/{version}/")
    summary = meta.get("assetsSummary") or {}
    keywords = meta.get("keywords") or []
    contacts, orgs = [], []
    for c in meta.get("contributor") or []:
        roles = c.get("roleName") or []
        if c.get("schemaKey") == "Person" and "dcite:ContactPerson" in roles:
            last, _, first = c["name"].partition(",")  # "Lee, Brian" -> "Brian Lee"
            contacts.append(f"{first.strip()} {last.strip()}".strip())
        elif c.get("schemaKey") == "Organization" and "dcite:Funder" not in roles and c.get("name"):
            orgs.append(c["name"])
    published = version != "draft"
    doi = meta.get("doi") if published else None
    approaches = unique(APPROACHES.get(name) or name.removesuffix(" approach").capitalize()
                        for name in ((ap.get("name") or "").strip() for ap in summary.get("approach") or []))
    record = {
        "id": did,
        "title": meta.get("name") or did,
        "description": " ".join((meta.get("description") or "").split()),
        "status": "published" if published else "draft",
        "version": version,
        "url": f"https://dandiarchive.org/dandiset/{did}",
        "doi": doi,
        "doi_url": f"https://doi.org/{doi}" if doi else None,
        "papers": paper_links(meta),
        "species": species_list(summary)
        or [{"name": name, "scientific": ""} for name in from_keywords(keywords, KEYWORD_SPECIES)],
        "approaches": approaches or from_keywords(keywords, KEYWORD_APPROACHES),
        "subjects": summary.get("numberOfSubjects") or 0,
        "files": summary.get("numberOfFiles") or 0,
        "bytes": summary.get("numberOfBytes") or 0,
        "contacts": contacts[:3],
        "organizations": orgs[:2],
        "keywords": keywords,
        "created": (info.get("created") or meta.get("dateCreated") or "")[:10],
        "published": (meta.get("datePublished") or "")[:10] or None,
    }
    if entry.get("note"):
        record["note"] = str(entry["note"]).strip()
    return record


def main():
    records, errors = [], []
    for entry in read_list():
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
