"""Best-effort committee-procedure -> plenary-vote join (Stage 0 input builder).

Network-touching, run once; output committed as data/htv_plenary_by_proc.json.

Method: scan the HowTheyVote `/api/votes` list, keep main votes whose responsible
committee is one of the 5 we scrape, fetch each one's detail, and index by the
authoritative procedure.reference.

KNOWN LIMITATION (the reason Stage 0 reports a LOWER BOUND): the `/api/votes` list
endpoint is a capped/rolling window (~2352 votes) and demonstrably omits older votes
that exist and are fetchable by id. So this index is incomplete; a procedure absent
from it has UNKNOWN plenary status, not confirmed-absent. A complete join would need a
reliable procedure->vote resolver, which this API does not cleanly provide.

Run:  .venv/bin/python scripts/build_plenary_join.py
"""
import collections
import json
import time
import urllib.request
from pathlib import Path

API = "https://howtheyvote.eu/api"
REPO = Path(__file__).resolve().parent.parent
COMMITTEES = {"ECON", "ENVI", "IMCO", "ITRE", "LIBE"}


def get(url):
    for _ in range(4):
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except Exception:
            time.sleep(1.5)
    return None


def main():
    # 1. list scan -> main votes whose responsible committee is one of ours
    candidates, page = [], 1
    while True:
        d = get(f"{API}/votes?page={page}&page_size=100")
        if not d or not d.get("results"):
            break
        for v in d["results"]:
            rc = v.get("responsible_committees") or []
            codes = {(c.get("code") if isinstance(c, dict) else c) for c in rc}
            if v.get("is_main") and codes & COMMITTEES:
                candidates.append(v["id"])
        if not d.get("has_next"):
            break
        page += 1
    print(f"main votes in {sorted(COMMITTEES)}: {len(candidates)} (from a capped list)")

    # 2. fetch detail, index by authoritative procedure.reference
    index = collections.defaultdict(list)
    for i, vid in enumerate(candidates):
        v = get(f"{API}/votes/{vid}")
        if not v:
            continue
        pr = v.get("procedure") or {}
        ref = pr.get("reference")
        if not ref:
            continue
        index[ref].append({
            "id": vid, "main": v.get("is_main"), "stage": pr.get("stage"),
            "result": v.get("result"), "ts": (v.get("timestamp") or "")[:10],
            "bg": bool((v.get("stats") or {}).get("by_group")),
        })
        if i % 100 == 0:
            print(f"  ...{i}")
        time.sleep(0.1)

    out = REPO / "data" / "htv_plenary_by_proc.json"
    out.write_text(json.dumps(dict(index), indent=1))
    print(f"wrote {out} ({len(index)} procedures)")


if __name__ == "__main__":
    main()
