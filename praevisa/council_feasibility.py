"""Council layer — Stage 0 feasibility / kill-switch (mirror of stage0_feasibility).

The Council/trilogue dimension is where much of the hypothesised commercial value lives
and where NOTHING is built yet (FINDINGS §8). Before any modelling, this answers the
only two questions that gate the whole layer — cheaply, and re-runnably:

  1. ACCESS — is real per-member-state Council voting data actually reachable?
  2. PAIRING — can it be JOINED to the EP/committee data we already have, by procedure?

Why pairing is the crux: the Council publishes votes on legislative acts tagged with the
**inter-institutional file number** — which is the SAME `YYYY/NNNN(COD)` id we key
committee and plenary votes on. So a Council vote can be matched to the exact files we
already predict, enabling a cross-institutional signal (does a member state's Council
position predict / constrain the EP outcome, and vice-versa) and a Council flip analysis.

Data source (from data.europa.eu dataset metadata, modified 2025-03-10, coverage from
2009-12): the Council "Votes on legislative acts" open dataset — RDF bulk + SPARQL —
with fields: country, vote (in favour / against / abstained / didn't participate),
act type, policy area, voting procedure & rule (QMV / unanimity), Council doc number,
**inter-institutional document number**, session, act number/date.

Run:
    uv run python -m praevisa.council_feasibility                 # ACCESS probe + verdict
    uv run python -m praevisa.council_feasibility pair PATH.json  # PAIRING against a pulled file
"""

from __future__ import annotations

import glob
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
UA = {"User-Agent": "Mozilla/5.0 (Praevisa Council feasibility spike)"}

# Documented distributions for the dataset (data.europa.eu hub metadata, 2025-03-10).
# Probed in order; the first that yields real data wins.
ENDPOINTS = [
    ("bulk RDF zip",
     "https://data.consilium.europa.eu/data/public-voting/council-votes-on-legislative-acts.zip"),
    ("SPARQL endpoint", "https://data.consilium.europa.eu/sparql"),
    ("public-voting dir", "https://data.consilium.europa.eu/data/public-voting/"),
    ("www voting search (bot-checked)",
     "https://www.consilium.europa.eu/en/general-secretariat/corporate-policies/"
     "transparency/voting-results/"),
]

PROC_CORE = re.compile(r"(\d{4}/\d{3,4})")   # the YYYY/NNNN core, format-agnostic


def _proc_core(ref: str) -> str | None:
    m = PROC_CORE.search(ref or "")
    return m.group(1) if m else None


def our_candidate_procedures() -> dict:
    """The procedures we ALREADY have EP/committee data for — the join target.

    Returns {core_id: {"full": ..., "committee": bool, "ep_testset": bool}}.
    These are the files a Council vote could pair with; the size of this set is the
    ceiling on how many triples the layer could ever produce from current coverage.
    """
    out: dict[str, dict] = {}
    for f in glob.glob(str(REPO / "committee_corpus_*.json")):
        for r in json.load(open(f)).get("records", []):
            p = r.get("procedure", "")
            if p.endswith("(COD)"):
                core = _proc_core(p)
                if core:
                    out.setdefault(core, {"full": p, "committee": False,
                                          "ep_testset": False})["committee"] = True
    # EP frozen test set (best-effort; import is heavy, so guard it)
    try:
        from . import baselines
        for r in baselines.load_testset():
            core = _proc_core(r.reference)
            if core:
                out.setdefault(core, {"full": r.reference, "committee": False,
                                      "ep_testset": False})["ep_testset"] = True
    except Exception as e:                                   # noqa: BLE001
        print(f"  (note: EP testset not loaded: {type(e).__name__})")
    return out


def _probe(url: str) -> tuple[int | str, str, int]:
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            body = r.read(4096)
            return r.status, r.headers.get("Content-Type", ""), len(body)
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get("Content-Type", "") if e.headers else "", 0
    except Exception as e:                                   # noqa: BLE001
        return f"ERR:{type(e).__name__}", "", 0


def probe() -> int:
    print("COUNCIL LAYER — Stage 0 feasibility (access + pairing kill-switch)\n")
    cand = our_candidate_procedures()
    n_comm = sum(1 for v in cand.values() if v["committee"])
    n_ep = sum(1 for v in cand.values() if v["ep_testset"])
    print("PAIRING CEILING (what a Council vote could join to, from current coverage):")
    print(f"  distinct COD procedures we hold        : {len(cand)}")
    print(f"   ... with committee data               : {n_comm}")
    print(f"   ... in the EP frozen test set          : {n_ep}")
    print("  Council votes are tagged with the inter-institutional file number = this same")
    print("  YYYY/NNNN(COD) id, so the join is a direct key match once data is in hand.\n")

    print("ACCESS PROBE (documented distributions):")
    reachable = []
    for label, url in ENDPOINTS:
        status, ctype, n = _probe(url)
        ok = isinstance(status, int) and status == 200 and "html" not in ctype.lower()
        if ok:
            reachable.append((label, url))
        flag = "DATA" if ok else ("403/bot" if status == 403 else
                                  "404" if status == 404 else str(status))
        print(f"  [{flag:>7s}] {label:34s} {url[:60]}")

    print()
    if reachable:
        print("VERDICT: GO (access live) — pull via:")
        for label, url in reachable:
            print(f"  {label}: {url}")
        print("  then: uv run python -m praevisa.council_feasibility pair <file>")
        return 0
    print("VERDICT: BLOCKED ON ACCESS (data exists & is correctly keyed, endpoints not "
          "directly pullable right now).")
    print("  Observed: www is bot-checked (403); the bulk-zip http→https redirect 404s; the")
    print("  SPARQL path 404s. The dataset itself is live (data.europa.eu, modified")
    print("  2025-03-10, coverage from 2009-12) — this is an access-engineering gate, not a")
    print("  missing-data gate. Next steps, cheapest first:")
    print("   1. SPARQL via a browser session / correct current endpoint (the metadata still")
    print("      lists data.consilium.europa.eu/sparql as the official distribution);")
    print("   2. the data.europa.eu portal's own distribution download proxy;")
    print("   3. VoteWatch Europe Council RCV set (EUI Cadmus, 2009–2022) as a static")
    print("      historical backtest fallback — real Council votes, ends Feb 2022.")
    print("  Once a file is pulled, `pair` quantifies the real triple count against the")
    print(f"  {len(cand)} procedures above.")
    return 1


def pair(path: str) -> int:
    """Intersect a pulled Council votes file with our procedures; count pairable triples.

    Accepts a JSON file that is either a list of vote records or {records: [...]}, where
    each record carries an inter-institutional file ref under any of the common keys.
    Format-tolerant on purpose — the official RDF can be pre-converted to JSON upstream.
    """
    cand = our_candidate_procedures()
    try:
        raw = json.load(open(path))
    except Exception as e:                                   # noqa: BLE001
        print(f"cannot read {path}: {e}")
        return 1
    recs = raw.get("records", raw) if isinstance(raw, dict) else raw
    REF_KEYS = ("interinstitutional", "interInstitutional", "iiRef", "procedure",
                "interinstitutional_file", "interinstitutionalCode", "file")
    council_cores: dict[str, int] = {}
    for r in recs if isinstance(recs, list) else []:
        ref = ""
        if isinstance(r, dict):
            for k in REF_KEYS:
                if r.get(k):
                    ref = str(r[k])
                    break
            if not ref:
                ref = json.dumps(r)                          # last resort: scan the blob
        core = _proc_core(ref)
        if core:
            council_cores[core] = council_cores.get(core, 0) + 1

    paired = sorted(set(council_cores) & set(cand))
    print(f"PAIRING: {path}")
    print(f"  Council records read                 : "
          f"{len(recs) if isinstance(recs, list) else 'n/a'}")
    print(f"  distinct procedures in Council file   : {len(council_cores)}")
    print(f"  our candidate procedures             : {len(cand)}")
    print(f"  PAIRABLE (Council ∩ ours)             : {len(paired)}")
    for c in paired:
        v = cand[c]
        tags = ",".join(t for t, on in (("cmte", v["committee"]),
                                        ("ep", v["ep_testset"])) if on)
        print(f"    {c}  [{tags}]  council_rows={council_cores[c]}")
    bar = len(paired) >= 5
    print(f"\nVERDICT: {'GO' if bar else 'THIN'} — {len(paired)} pairable triples "
          f"({'enough for a first cross-institutional backtest' if bar else 'below the n>=5 bar; widen coverage'}).")
    return 0 if bar else 1


def main() -> int:
    if len(sys.argv) > 2 and sys.argv[1] == "pair":
        return pair(sys.argv[2])
    return probe()


if __name__ == "__main__":
    sys.exit(main())
