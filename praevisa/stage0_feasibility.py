"""Stage 0 of the prospective contested-vote test: data feasibility gate.

The kill-switch before any modeling. The prospective test needs PAIRS of
(pre-vote committee per-group signal, plenary per-group outcome) on first-reading
COD files. This script counts how many such pairs actually exist in the data we
have, so we learn — cheaply — whether the test is runnable at all.

Inputs:
  committee_corpus_*.json  — scraped committee roll-calls (per-MEP, per-group; local)
  praevisa.resolve_plenary — procedure -> plenary vote, via HTV's COMPLETE bulk export
                             (not the capped /api/votes list); per-group via by-id API

It reports, for COD procedures that have a usable PRE-PLENARY committee roll-call:
  * how many have per-group committee data (the SIGNAL side),
  * how many resolve to a plenary main first-reading vote with per-group data (the
    OUTCOME side) and thus form a usable PAIR,
  * how many of those pairs are CONTESTED ex ante (committee not unanimous).

The earlier list-window ambiguity is GONE: resolve_plenary indexes the full ~24k-vote
bulk table, so a procedure with no plenary match here genuinely has no plenary main
first-reading COD vote yet (pending or routed otherwise) — an authoritative answer,
not "unknown / outside a window".

No modeling here. Just the count that decides go / no-go.

Run:  uv run python -m praevisa.stage0_feasibility
"""

from __future__ import annotations

import glob
import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

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


def usable_plenary(proc, index):
    """Authoritatively resolve a usable plenary outcome for `proc`, or None.

    Uses the bulk-export resolver (praevisa.resolve_plenary), which is complete — so
    None here means the procedure genuinely has NO plenary main first-reading COD vote
    yet (pending or routed otherwise), not "unknown / outside a window". Per-group
    availability is confirmed by a by-id detail fetch.
    """
    from . import resolve_plenary
    row = resolve_plenary.resolve_first_reading(proc, index)
    if row is None:
        return None
    bg = resolve_plenary.fetch_by_group(row["id"])
    n_groups = len(bg) if bg else 0
    return {"id": row["id"], "result": row["result"], "groups": n_groups,
            "ts": row.get("timestamp", "")[:10]}


def main():
    from . import resolve_plenary
    committee = load_committee_cod()
    index = resolve_plenary.load_index()  # complete bulk-export index

    rows = []
    for proc, rec in sorted(committee.items()):
        yes, n = _committee_yes(rec)
        grates = _committee_group_rates(rec["votes"])
        n_groups = sum(1 for v in grates.values() if v is not None)
        plen = usable_plenary(proc, index)
        contested = (yes is not None and yes < CONTESTED_MAX_YES)
        rows.append({
            "procedure": proc, "committee": rec["committee"],
            "subject": rec["subject"], "committee_n": n,
            "committee_yes": round(yes, 3) if yes is not None else None,
            "committee_groups_defined": n_groups,
            "contested_ex_ante": contested,
            "plenary_vote_id": plen["id"] if plen else None,
            "plenary_result": plen["result"] if plen else None,
            "plenary_groups": plen["groups"] if plen else 0,
            "usable_pair": bool(plen and n_groups >= 5 and plen["groups"] >= 5),
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
    print("OUTCOME side (authoritative via bulk-export resolver):")
    print(f"  resolves to a usable plenary PAIR                           : {n_pair}")
    print(f"  ... of which contested ex ante                              : {n_contested_pair}")
    print(f"  no plenary first-reading vote yet (pending / routed otherwise): {n_unconfirmed}\n")

    print(f"{'procedure':16s} {'cmte':5s} {'n':>4s} {'cmte_yes':>8s} {'grps':>4s} "
          f"{'contested':>9s}  {'plenary':<16s}")
    print("-" * 72)
    for r in rows:
        if r["usable_pair"]:
            status = f"{r['plenary_vote_id']} {r['plenary_result'][:4].lower()}"
        elif r["plenary_vote_id"]:
            status = f"{r['plenary_vote_id']} (few groups)"
        else:
            status = "none (pending)"
        cy = r["committee_yes"] if r["committee_yes"] is not None else float("nan")
        print(f"{r['procedure']:16s} {r['committee']:5s} {r['committee_n']:>4d} "
              f"{cy:>8.2f} {r['committee_groups_defined']:>4d} "
              f"{str(r['contested_ex_ante']):>9s}  {status:<16s}")

    out = {
        "resolver": "praevisa.resolve_plenary (HTV bulk export, complete table)",
        "signal_side": {"n_signal": n_signal, "n_contested_signal": n_contested_signal},
        "outcome_side": {
            "n_pairs": n_pair, "n_contested_pairs": n_contested_pair,
            "n_no_plenary_yet": n_unconfirmed,
        },
        "contested_max_yes": CONTESTED_MAX_YES, "rows": rows,
    }
    (REPO / "results").mkdir(exist_ok=True)
    (REPO / "results" / "stage0_feasibility.json").write_text(json.dumps(out, indent=1))
    print("\nwritten: results/stage0_feasibility.json")
    print(f"\nVERDICT: signal side feasible ({n_signal} signals, {n_contested_signal} "
          f"contested). {n_pair} usable pairs ({n_contested_pair} contested) from only the")
    print(f"5 scraped committees; {n_unconfirmed} have no first-reading plenary vote yet")
    print("(pending). Stage A target ~>=10 pairs (>=6 contested): widen the committee scrape")
    print("(resolver now makes pairing reliable across ALL committees and full history).")
    return out


if __name__ == "__main__":
    main()
