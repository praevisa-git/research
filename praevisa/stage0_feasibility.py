"""Stage 0 of the prospective contested-vote test: data feasibility gate.

The kill-switch before any modeling. The prospective test needs PAIRS of
(pre-vote committee per-group signal, plenary per-group outcome) on first-reading
COD files. This script counts how many such pairs actually exist in the data we
have, so we learn — cheaply — whether the test is runnable at all.

Inputs (committed):
  committee_corpus_*.json        — scraped committee roll-calls (per-MEP, per-group)
  data/htv_plenary_by_proc.json  — procedure.reference -> plenary votes (best-effort
                                   join built by scripts/build_plenary_join.py)

It reports, for COD procedures that have a usable PRE-PLENARY committee roll-call:
  * how many have per-group committee data (the SIGNAL side — reliable, local data),
  * how many we could CONFIRM a plenary main first-reading vote with per-group data
    (the OUTCOME side) and thus form a usable PAIR,
  * how many of those confirmed pairs are CONTESTED ex ante (committee not unanimous).

DATA CAVEAT — READ BEFORE TRUSTING THE PAIR COUNT. The HowTheyVote `/api/votes` LIST
endpoint is NOT a complete enumeration: it returns a capped/rolling window (~2352
votes) and demonstrably omits older votes that exist and are fetchable by id (e.g.
vote 184168 = 2025/0132, which IS in our committed 22-file set, does not appear in the
list even when date-filtered). Therefore an UNCONFIRMED plenary match here means
"not found via the list", NOT "no plenary vote exists". Many unconfirmed procedures
are either (a) recent files whose plenary vote is still pending, or (b) older votes
outside the list window. The confirmed-pair count is a LOWER BOUND. The real cost this
gate surfaces is that pairing committee signals to plenary outcomes needs a reliable
procedure->vote resolver, which this API does not cleanly provide.

No modeling here. Just the count that decides go / no-go / inconclusive.

Run:  uv run python -m praevisa.stage0_feasibility
"""

from __future__ import annotations

import glob
import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PLENARY_JOIN = REPO / "data" / "htv_plenary_by_proc.json"

# committee corpus group code -> canonical 10th-term code
COMMITTEE_GROUP_MAP = {
    "PPE": "EPP", "S&D": "S&D", "Renew": "Renew", "Verts/ALE": "Greens",
    "The Left": "Left", "ECR": "ECR", "PfE": "PfE", "ESN": "ESN", "NI": "NI",
}
# committee subjects that are a genuine pre-plenary signal for a first-reading file
PRE_PLENARY_SUBJECTS = {
    "Adoption of draft report",
    "Vote on draft report",
    "Vote on text as amended",
    "Vote on the decision to enter into interinstitutional negotiations",
    "Vote on the mandate to enter into interinstitutional negotiations",
}
# a committee vote is "contested" ex ante if its yes-rate is below this
CONTESTED_MAX_YES = 0.75


def _committee_group_rates(votes):
    """Per-canonical-group yes-rate from a committee record's per-MEP votes.

    choice '+' = for, '-' = against, '0' = abstention (in the denominator, Decision 1).
    """
    agg = {}
    for v in votes:
        canon = COMMITTEE_GROUP_MAP.get(v.get("group"))
        if canon is None:
            continue
        f, a, ab = agg.get(canon, (0, 0, 0))
        c = v.get("choice")
        if c == "+":
            f += 1
        elif c == "-":
            a += 1
        elif c == "0":
            ab += 1
        agg[canon] = (f, a, ab)
    rates = {}
    for g, (f, a, ab) in agg.items():
        denom = f + a + ab
        rates[g] = (f / denom) if denom else None
    return rates


def _committee_yes(record):
    t = record.get("tally") or {}
    plus, minus, absn = t.get("+", 0), t.get("-", 0), t.get("0", 0)
    tot = plus + minus + absn
    return (plus / tot) if tot else None, tot


def load_committee_cod():
    """COD procedure -> best pre-plenary committee record (most MEPs voting)."""
    recs = []
    for f in glob.glob(str(REPO / "committee_corpus_*.json")):
        recs.extend(json.load(open(f))["records"])
    by_proc = {}
    for r in recs:
        p = r.get("procedure", "")
        if not p.endswith("(COD)"):
            continue
        if r.get("secret") or not r.get("votes"):
            continue
        if r.get("subject") not in PRE_PLENARY_SUBJECTS:
            continue
        cur = by_proc.get(p)
        if cur is None or len(r["votes"]) > len(cur["votes"]):
            by_proc[p] = r
    return by_proc


def load_htv_raw_procs():
    """Authoritative procedure -> plenary id from the committed 22-file set.

    Every file in data/htv_raw is, by construction, a main OLP first-reading vote with
    per-group data, so its presence confirms a usable plenary outcome regardless of the
    incomplete list endpoint.
    """
    try:
        from .baselines import load_testset
        return {r.reference: r.id for r in load_testset()}
    except Exception:
        return {}


def usable_plenary(proc, plenary_index, raw_procs):
    """Confirm a usable plenary outcome for `proc` from either reliable source.

    Returns {"id":..., "source":...} or None. Sources: 'htv_raw' (authoritative,
    committed 22-file set) or 'join' (best-effort, from the capped list endpoint).
    """
    if proc in raw_procs:
        return {"id": raw_procs[proc], "result": None, "source": "htv_raw"}
    for v in plenary_index.get(proc, []):
        if v.get("main") and v.get("stage") == "OLP_FIRST_READING" and v.get("bg"):
            return {"id": v["id"], "result": v.get("result"), "source": "join"}
    return None


def main():
    committee = load_committee_cod()
    plenary_index = json.loads(PLENARY_JOIN.read_text()) if PLENARY_JOIN.exists() else {}
    raw_procs = load_htv_raw_procs()

    rows = []
    for proc, rec in sorted(committee.items()):
        yes, n = _committee_yes(rec)
        grates = _committee_group_rates(rec["votes"])
        n_groups = sum(1 for v in grates.values() if v is not None)
        plen = usable_plenary(proc, plenary_index, raw_procs)
        contested = (yes is not None and yes < CONTESTED_MAX_YES)
        rows.append({
            "procedure": proc, "committee": rec["committee"],
            "subject": rec["subject"], "committee_n": n,
            "committee_yes": round(yes, 3) if yes is not None else None,
            "committee_groups_defined": n_groups,
            "contested_ex_ante": contested,
            "plenary_vote_id": plen["id"] if plen else None,
            "plenary_source": plen["source"] if plen else None,
            "usable_pair": bool(plen and n_groups >= 5),
        })

    n_signal = len(rows)
    n_contested_signal = sum(r["contested_ex_ante"] for r in rows)
    n_pair = sum(r["usable_pair"] for r in rows)
    n_contested_pair = sum(r["usable_pair"] and r["contested_ex_ante"] for r in rows)
    n_unconfirmed = n_signal - n_pair

    print("STAGE 0 — feasibility of the prospective contested-vote test\n")
    print("SIGNAL side (reliable, local committee data):")
    print(f"  COD procedures with a pre-plenary committee per-group signal : {n_signal}")
    print(f"  ... CONTESTED ex ante (committee yes < {CONTESTED_MAX_YES})            : {n_contested_signal}\n")
    print("OUTCOME side (HTV list endpoint is incomplete -> LOWER BOUND):")
    print(f"  plenary outcome CONFIRMED -> usable PAIR                     : {n_pair}")
    print(f"  ... of which contested ex ante                              : {n_contested_pair}")
    print(f"  plenary UNCONFIRMED (unknown: pending OR outside list window): {n_unconfirmed}\n")

    print(f"{'procedure':16s} {'cmte':5s} {'n':>4s} {'cmte_yes':>8s} {'grps':>4s} "
          f"{'contested':>9s}  {'plenary':<16s}")
    print("-" * 72)
    for r in rows:
        if r["usable_pair"]:
            status = f"{r['plenary_vote_id']} ({r['plenary_source']})"
        else:
            status = "unconfirmed"
        cy = r["committee_yes"] if r["committee_yes"] is not None else float("nan")
        print(f"{r['procedure']:16s} {r['committee']:5s} {r['committee_n']:>4d} "
              f"{cy:>8.2f} {r['committee_groups_defined']:>4d} "
              f"{str(r['contested_ex_ante']):>9s}  {status:<16s}")

    out = {
        "signal_side": {"n_signal": n_signal, "n_contested_signal": n_contested_signal},
        "outcome_side_LOWER_BOUND": {
            "n_confirmed_pairs": n_pair, "n_confirmed_contested_pairs": n_contested_pair,
            "n_unconfirmed": n_unconfirmed,
            "caveat": "HTV /api/votes list is a capped window; unconfirmed != absent",
        },
        "contested_max_yes": CONTESTED_MAX_YES, "rows": rows,
    }
    (REPO / "results").mkdir(exist_ok=True)
    (REPO / "results" / "stage0_feasibility.json").write_text(json.dumps(out, indent=1))
    print("\nwritten: results/stage0_feasibility.json")
    print(f"\nVERDICT: signal side feasible ({n_signal} signals, {n_contested_signal} "
          f"contested). {n_pair} pairs CONFIRMED ({n_contested_pair} contested) from only")
    print(f"5 committees — a LOWER BOUND ({n_unconfirmed} unconfirmed: pending or out-of-window,")
    print("not absent). Stage A target is ~>=10 pairs (>=6 contested): plausibly reachable")
    print("by resolving the unconfirmed and widening beyond 5 committees. Tentative GO.")
    return out


if __name__ == "__main__":
    main()
