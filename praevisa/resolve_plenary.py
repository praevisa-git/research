"""Procedure -> plenary-vote resolver.

Solves the problem Stage 0 surfaced: the HowTheyVote `/api/votes` LIST endpoint is a
capped/rolling window (~2352) that omits older votes, so you cannot enumerate votes —
or find a given procedure's plenary vote — by listing. The fix is HTV's BULK export
(`votes.csv.gz`, ~24k votes, the complete table), which carries `procedure_reference`,
`procedure_type`, `procedure_stage`, `is_main`, and `result`. We index that offline and
resolve any procedure reference to its plenary vote id deterministically. Per-group
stats (`stats.by_group`) are still fetched per id from the detail API — but by-id fetch
is reliable; only the *list* is windowed.

Pipeline:
    reference --(votes.csv index)--> vote id --(detail API)--> per-group stats

The bulk file is a regenerable cache (data/htv_export/, gitignored). Re-download with
``ensure_votes_csv(force=True)`` or just delete the cache.

Self-check:  uv run python -m praevisa.resolve_plenary 2025/0132(COD)
"""

from __future__ import annotations

import csv
import gzip
import json
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
EXPORT_DIR = REPO / "data" / "htv_export"
VOTES_CSV = EXPORT_DIR / "votes.csv.gz"
TAG_FILE = EXPORT_DIR / "release_tag.txt"

GH_LATEST = "https://api.github.com/repos/HowTheyVote/data/releases/latest"
ASSET = "votes.csv.gz"

FIRST_READING = "OLP_FIRST_READING"
VALID_RESULTS = {"ADOPTED", "REJECTED"}


def _get(url, binary=False):
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read() if binary else json.loads(r.read())


def ensure_votes_csv(force: bool = False) -> str:
    """Download the latest HTV votes.csv.gz into the cache if missing. Returns the tag."""
    if VOTES_CSV.exists() and TAG_FILE.exists() and not force:
        return TAG_FILE.read_text().strip()
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    rel = _get(GH_LATEST)
    tag = rel.get("tag_name", "unknown")
    url = next((a["browser_download_url"] for a in rel.get("assets", [])
                if a["name"] == ASSET), None)
    if url is None:
        raise RuntimeError(f"{ASSET} not found in latest HTV release {tag}")
    VOTES_CSV.write_bytes(_get(url, binary=True))
    TAG_FILE.write_text(tag)
    return tag


def load_index(force: bool = False) -> dict[str, list[dict]]:
    """procedure_reference -> list of vote rows (full bulk table, all stages/types)."""
    ensure_votes_csv(force=force)
    index: dict[str, list[dict]] = {}
    with gzip.open(VOTES_CSV, "rt") as fh:
        for row in csv.DictReader(fh):
            ref = row.get("procedure_reference")
            if ref:
                index.setdefault(ref, []).append(row)
    return index


def resolve_first_reading(reference: str, index: dict[str, list[dict]] | None = None):
    """Return the plenary MAIN first-reading COD vote row for `reference`, or None.

    If several qualify (rare), the most recent is returned. `result` and counts come
    straight from the bulk table; per-group stats are a separate by-id detail fetch.
    """
    if index is None:
        index = load_index()
    cands = [
        r for r in index.get(reference, [])
        if r.get("is_main") == "True"
        and r.get("procedure_type") == "COD"
        and r.get("procedure_stage") == FIRST_READING
        and r.get("result") in VALID_RESULTS
    ]
    if not cands:
        return None
    cands.sort(key=lambda r: r.get("timestamp", ""), reverse=True)
    return cands[0]


def fetch_by_group(vote_id) -> dict | None:
    """Per-canonical-group raw ballots for a vote id, via the reliable detail API."""
    from .baselines import GROUP_CODE_MAP
    d = _get(f"https://howtheyvote.eu/api/votes/{vote_id}")
    bg = (d.get("stats") or {}).get("by_group") or []
    if not bg:
        return None
    out = {}
    for row in bg:
        canon = GROUP_CODE_MAP.get(row["group"]["code"])
        if canon:
            out[canon] = row["stats"]
    return out


def _selfcheck(reference: str) -> None:
    idx = load_index()
    tag = TAG_FILE.read_text().strip()
    print(f"HTV export {tag}: {sum(len(v) for v in idx.values())} votes, "
          f"{len(idx)} procedures")
    row = resolve_first_reading(reference, idx)
    if not row:
        print(f"{reference}: no plenary main first-reading COD vote found")
        return
    print(f"{reference} -> vote {row['id']} | {row['result']} | {row['timestamp'][:10]} "
          f"| {row.get('procedure_stage')}")
    bg = fetch_by_group(row["id"])
    print(f"  per-group available: {bool(bg)} ({len(bg) if bg else 0} groups)")


if __name__ == "__main__":
    import sys
    _selfcheck(sys.argv[1] if len(sys.argv) > 1 else "2025/0132(COD)")
