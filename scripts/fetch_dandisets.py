"""Make the dashboard data.

Reads the IDs in dandisets.yaml, gets each dandiset's details from DANDI,
and writes them to data/dandisets.json.

    python scripts/fetch_dandisets.py

Stops with an error if an ID is invalid, repeated, or not on DANDI.
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
OUT_FILE = ROOT / "data" / "dandisets.json"
API = "https://api.dandiarchive.org/api"

# Common species names, by NCBI taxonomy ID.
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

# Short names for DANDI's data types.
APPROACHES = {
    "electrophysiological approach": "Electrophysiology",
    "microscopy approach; cell population imaging": "Imaging",
    "behavioral approach": "Behavior",
    "histological approach": "Histology",
    "multimodal approach": "Multimodal",
    "spatial transcriptomics approach": "Spatial transcriptomics",
}

# Used when DANDI has no species or data type yet: match these words in the keywords.
KEYWORD_SPECIES = {"mouse": "Mouse", "human": "Human", "rat": "Rat", "macaque": "Macaque", "marmoset": "Marmoset"}
KEYWORD_APPROACHES = {"calcium imaging": "Imaging", "two-photon": "Imaging", "2-photon": "Imaging",
                      "patch-seq": "Electrophysiology", "neuropixels": "Electrophysiology"}


def get_json(url):
    """Get JSON from the DANDI API, retrying network and server errors."""
    for attempt in range(4):
        try:
            with urllib.request.urlopen(url, timeout=60) as resp:
                return json.load(resp)
        except urllib.error.URLError as err:
            # Retry only network and server (5xx) errors.
            if attempt == 3 or getattr(err, "code", 500) < 500:
                raise
            time.sleep(2 ** attempt)


def read_list():
    """Read dandisets.yaml and check the IDs."""
    raw = yaml.load(LIST_FILE.read_text(), Loader=yaml.BaseLoader) or []  # read IDs as text, keeping leading zeros
    if isinstance(raw, dict):  # also allow a "dandisets:" key
        raw = raw.get("dandisets") or []
    ids, errors = [], []
    for n, item in enumerate(raw, 1):
        value = item.get("id") if isinstance(item, dict) else item  # also allow "id: ..." entries
        did = str(value).strip()
        if did.isdigit():
            did = did.zfill(6)  # allow short IDs, e.g. 636 -> 000636
        if not re.fullmatch(r"\d{6}", did):
            errors.append(f"entry {n}: '{value}' is not a six-digit dandiset ID")
        elif did in ids:
            errors.append(f"entry {n}: {did} is listed more than once")
        else:
            ids.append(did)
    if errors:
        sys.exit("dandisets.yaml has problems:\n  " + "\n  ".join(errors))
    return ids


def unique(items):
    """Remove blanks and repeats, keeping the order."""
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


def build_record(did):
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
    approaches = unique(APPROACHES.get(name) or name.removesuffix(" approach").capitalize()
                        for name in ((ap.get("name") or "").strip() for ap in summary.get("approach") or []))
    return {
        "id": did,
        "title": meta.get("name") or did,
        "description": meta.get("description") or "",  # searched, not shown
        "version": version,
        "url": f"https://dandiarchive.org/dandiset/{did}",
        "species": species_list(summary)
        or [{"name": name, "scientific": ""} for name in from_keywords(keywords, KEYWORD_SPECIES)],
        "approaches": approaches or from_keywords(keywords, KEYWORD_APPROACHES),
        "subjects": summary.get("numberOfSubjects") or 0,
        "files": summary.get("numberOfFiles") or 0,
        "bytes": summary.get("numberOfBytes") or 0,
        "contacts": contacts[:3],
        "organizations": orgs[:2],
        "keywords": keywords,
        "updated": info["draft_version"]["modified"][:10],  # when the draft last changed
        "published": (meta.get("datePublished") or "")[:10] or None,
    }


def main():
    records, errors = [], []
    for did in read_list():
        try:
            records.append(build_record(did))
            print(f"  {did}  ok")
        except LookupError as err:
            errors.append(str(err))
            print(f"  {did}  ERROR")
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
