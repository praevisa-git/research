"""Step 2 of the §9.6 baseline build: pull the resolved-OLP test set from
HowTheyVote.eu and commit the raw JSON.

Run once (touches the network):

    python -m praevisa.fetch_testset

It writes the raw per-vote detail JSON of the SELECTED test set to
``data/htv_raw/<id>.json`` and an auditable ``data/htv_raw/index.json``. Grading
(steps 3-4) reads only those committed files and never touches the network.

Inclusion filter is exactly the one frozen in METHODOLOGY.md §2:
  * is_main == true
  * procedure.type == "COD"
  * result in {ADOPTED, REJECTED}
  * a real per-group roll-call exists (stats.by_group non-empty, some ballots cast)

Selection (METHODOLOGY.md §2): from the eligible COD pool, pick a set spanning the
range of observed EP yes-share. Deterministic: sort the pool ascending by yes-share
and take TARGET_N evenly spaced positions (always including the min and max), so a
re-run picks the same files. No randomness, no cherry-picking by reference.

Observed EP yes-share uses the Decision-1 denominator (METHODOLOGY.md §1, §5):
  share = sum_g FOR / sum_g (FOR + AGAINST + ABSTENTION)   [DID_NOT_VOTE excluded]
"""

from __future__ import annotations

import json
import time
import urllib.request
from pathlib import Path

API = "https://howtheyvote.eu/api"
PAGE_SIZE = 100
THROTTLE_S = 0.10          # polite delay between detail fetches
TARGET_N = 22              # desired test-set size (clamped to [18, 25] by pool)
MIN_N, MAX_N = 18, 25

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "htv_raw"


def _get(url: str) -> dict:
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.load(resp)


def _ep_yes_share(by_group: list[dict]) -> float | None:
    """sum FOR / sum(FOR+AGAINST+ABSTENTION) over all groups (Decision 1)."""
    f = a = ab = 0
    for row in by_group:
        s = row["stats"]
        f += s.get("FOR", 0)
        a += s.get("AGAINST", 0)
        ab += s.get("ABSTENTION", 0)
    denom = f + a + ab
    if denom == 0:
        return None
    return f / denom


def list_candidates() -> list[dict]:
    """All list-level stubs that are is_main and ADOPTED/REJECTED."""
    out: list[dict] = []
    page = 1
    while True:
        d = _get(f"{API}/votes?page={page}&page_size={PAGE_SIZE}")
        for r in d["results"]:
            if r.get("is_main") and r.get("result") in ("ADOPTED", "REJECTED"):
                out.append(r)
        if not d.get("has_next"):
            break
        page += 1
    return out


def build_cod_pool(candidates: list[dict]) -> list[dict]:
    """Fetch detail per candidate; keep COD files with a real per-group RCV.

    Returns a list of dicts: {id, reference, result, stage, yes_share, n_groups, detail}.
    ``detail`` is the full raw vote JSON (committed for the selected subset).
    """
    pool: list[dict] = []
    n = len(candidates)
    for i, stub in enumerate(candidates, 1):
        vid = stub["id"]
        try:
            detail = _get(f"{API}/votes/{vid}")
        except Exception as exc:  # noqa: BLE001 - report and skip, do not crash the pull
            print(f"  [{i}/{n}] {vid}: FETCH ERROR {exc}; skipped")
            time.sleep(THROTTLE_S)
            continue
        proc = detail.get("procedure") or {}
        by_group = (detail.get("stats") or {}).get("by_group") or []
        share = _ep_yes_share(by_group) if by_group else None
        if proc.get("type") == "COD" and by_group and share is not None:
            pool.append(
                {
                    "id": vid,
                    "reference": proc.get("reference") or detail.get("reference"),
                    "result": detail.get("result"),
                    "stage": proc.get("stage"),
                    "yes_share": share,
                    "n_groups": len(by_group),
                    "detail": detail,
                }
            )
        if i % 100 == 0 or i == n:
            print(f"  scanned {i}/{n} candidates; COD pool so far: {len(pool)}")
        time.sleep(THROTTLE_S)
    return pool


def select_spread(pool: list[dict]) -> list[dict]:
    """Deterministically pick a yes-share-spanning subset (METHODOLOGY §2)."""
    ordered = sorted(pool, key=lambda x: (x["yes_share"], x["id"]))
    m = len(ordered)
    if m <= MIN_N:
        return ordered
    n = min(TARGET_N, MAX_N, m)
    # evenly spaced positions across [0, m-1], inclusive of both ends
    idx = sorted({round(k * (m - 1) / (n - 1)) for k in range(n)})
    return [ordered[j] for j in idx]


def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    print("Stage 1: listing candidates (is_main & ADOPTED/REJECTED) ...")
    candidates = list_candidates()
    print(f"  candidates: {len(candidates)}")

    print("Stage 2: fetching detail, filtering to COD with real per-group RCV ...")
    pool = build_cod_pool(candidates)
    print(f"  eligible COD pool: {len(pool)}")
    stage_dist: dict[str, int] = {}
    for p in pool:
        stage_dist[p["stage"]] = stage_dist.get(p["stage"], 0) + 1
    print(f"  COD stage distribution: {stage_dist}")

    print("Stage 3: selecting yes-share-spanning test set ...")
    selected = select_spread(pool)

    # Write raw detail JSON for the selected set; build the index.
    index_entries = []
    for p in selected:
        (RAW_DIR / f"{p['id']}.json").write_text(json.dumps(p["detail"], indent=1))
        index_entries.append(
            {
                "id": p["id"],
                "reference": p["reference"],
                "result": p["result"],
                "stage": p["stage"],
                "yes_share": round(p["yes_share"], 6),
                "n_groups": p["n_groups"],
            }
        )

    index = {
        "source": "howtheyvote.eu/api",
        "inclusion_filter": "is_main & procedure.type==COD & result in {ADOPTED,REJECTED} & non-empty stats.by_group",
        "yes_share_denominator": "FOR/(FOR+AGAINST+ABSTENTION) [DID_NOT_VOTE excluded]",
        "n_candidates_scanned": len(candidates),
        "n_cod_pool": len(pool),
        "cod_stage_distribution": stage_dist,
        "n_selected": len(selected),
        "selection_rule": "sort pool by yes_share asc; take evenly spaced positions incl. min and max",
        "votes": sorted(index_entries, key=lambda e: e["yes_share"]),
    }
    (RAW_DIR / "index.json").write_text(json.dumps(index, indent=1))

    print("\nStage 4: report")
    print(f"  selected files: {len(selected)}  (target {TARGET_N}, bounds [{MIN_N},{MAX_N}])")
    print(f"  written to: {RAW_DIR}")
    print("  references and EP yes-shares (sorted ascending):")
    for e in sorted(index_entries, key=lambda e: e["yes_share"]):
        print(f"    {e['yes_share']:.3f}  {e['result']:8s}  {e['reference']:18s}  id={e['id']}")


if __name__ == "__main__":
    main()
