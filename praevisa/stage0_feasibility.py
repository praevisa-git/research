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
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# committee corpus group code -> canonical 10th-term code
COMMITTEE_GROUP_MAP = {
    "PPE": "EPP", "S&D": "S&D", "Renew": "Renew", "Verts/ALE": "Greens",
    "The Left": "Left", "ECR": "ECR", "PfE": "PfE", "ESN": "ESN", "NI": "NI",
}
# Committee subjects that are a pre-plenary signal, with a PRIORITY (lower = preferred
# as the contestedness signal) and a stage label. The report-adoption / text-as-amended
# stage is the substantive committee decision and carries the real contestation; the
# mandate vote is next; the post-trilogue "provisional agreement" vote is usually a
# consensus rubber-stamp, used only when nothing earlier survives the rolling window.
#
# Kept for reference/back-compat: the original *exact-string* table. Committee PDFs are
# scraped, so real subject lines arrive with template noise ("1.1. ", a "·"/""
# bullet, a trailing "- Rejected", an appended "(Co-Rapporteurs: ...)"). Exact matching
# against this table silently dropped legitimate LEAD-committee report votes — a
# data-quality bug, not a methodology choice. `classify_signal_stage` below normalizes
# that noise and is the path used by `load_committee_cod`.
SIGNAL_STAGES = {
    "Adoption of draft report": (0, "report"),
    "Vote on draft report": (0, "report"),
    "Vote on text as amended": (0, "report"),
    "Vote on the decision to enter into interinstitutional negotiations": (1, "mandate"),
    "Vote on the mandate to enter into interinstitutional negotiations": (1, "mandate"),
    "Vote on the provisional agreement resulting from interinstitutional negotiations":
        (2, "provisional"),
}
# a committee vote is "contested" ex ante if its yes-rate is below this
CONTESTED_MAX_YES = 0.75


def _norm_subject(subject):
    """Strip committee-PDF template noise so stage matching is robust.

    Removes a leading enumeration / bullet ("1.1.", "·", "", "-"), collapses
    whitespace, lowercases, and drops a trailing "- rejected" annotation (the rejection
    is already captured by the tally, not the stage). Returns a normalized string.
    """
    s = subject or ""
    s = s.replace("", " ")                      # PDF bullet glyph
    s = re.sub(r"^[\s·\-–—.\d]+", "", s)  # leading bullets/numbers/dashes
    s = re.sub(r"\s+", " ", s).strip().lower()
    s = re.sub(r"\s*-\s*rejected\s*$", "", s)         # "... - rejected" annotation
    return s


def classify_signal_stage(subject):
    """Map a (noisy) committee-vote subject to (priority, stage_label) or None.

    Priority: report (0) > mandate (1) > provisional (2) — earliest/most-substantive
    preferred as the contestedness signal. Returns None for anything that is NOT a
    lead-committee whole-text signal: opinions, second-reading recommendations,
    resolutions/own-initiative, single-amendment votes, and rapporteur-header parse
    noise are all excluded (default-exclude, so unrecognized lines are dropped safely).
    """
    n = _norm_subject(subject)
    if not n:
        return None
    # --- explicit exclusions (checked first; these can co-occur with signal words) ---
    if "opinion" in n:                       # opinion committee, not the lead report
        return None
    if "second reading" in n:                # different procedural track
        return None
    if "resolution" in n:                    # motion for a resolution, not a COD report
        return None
    if n.startswith(("amendment", "compromise amendment", "am ")):
        return None                          # single-amendment vote, not the whole text
    if n.startswith("rapporteur") or "rapporteur:" in n or "rapporteur for" in n:
        return None                          # parse-noise header line
    # --- mandate / provisional (interinstitutional negotiation stages) ---
    if "enter into interinstitutional negotiations" in n:
        return (1, "mandate")
    if "provisional agreement" in n:
        return (2, "provisional")
    # --- report stage: explicit report wording, or a committee "final vote" ---
    if ("adoption of draft report" in n
            or "vote on draft report" in n
            or "vote on the draft report" in n
            or "vote on text as amended" in n):
        return (0, "report")
    if n.startswith("final vote") or n == "final vote by roll call":
        # a committee's final roll-call on its OWN text; opinions were excluded above
        return (0, "report")
    return None


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
    """COD procedure -> best pre-plenary committee record.

    'Best' = earliest substantive stage available (report > mandate > provisional),
    tie-broken by most MEPs voting. The chosen stage is stamped on the record as
    `_stage` so the contestedness reading can flag consensus-stage signals.
    """
    recs = []
    for f in glob.glob(str(REPO / "committee_corpus_*.json")):
        with open(f) as fh:
            recs.extend(json.load(fh)["records"])
    by_proc = {}
    for r in recs:
        p = r.get("procedure", "")
        if not p.endswith("(COD)"):
            continue
        if r.get("secret") or not r.get("votes"):
            continue
        stage = classify_signal_stage(r.get("subject"))
        if stage is None:
            continue
        prio, label = stage
        cur = by_proc.get(p)
        if (cur is None
                or prio < cur["_prio"]
                or (prio == cur["_prio"] and len(r["votes"]) > len(cur["votes"]))):
            r = dict(r, _prio=prio, _stage=label)
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
            "subject": rec["subject"], "signal_stage": rec.get("_stage"),
            "committee_n": n,
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

    print(f"{'procedure':16s} {'cmte':5s} {'stage':>11s} {'n':>4s} {'cmte_yes':>8s} "
          f"{'contested':>9s}  {'plenary':<16s}")
    print("-" * 76)
    for r in rows:
        if r["usable_pair"]:
            status = f"{r['plenary_vote_id']} {r['plenary_result'][:4].lower()}"
        elif r["plenary_vote_id"]:
            status = f"{r['plenary_vote_id']} (few groups)"
        else:
            status = "none (pending)"
        cy = r["committee_yes"] if r["committee_yes"] is not None else float("nan")
        print(f"{r['procedure']:16s} {r['committee']:5s} {str(r['signal_stage']):>11s} "
              f"{r['committee_n']:>4d} {cy:>8.2f} "
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
    n_committees = len(glob.glob(str(REPO / "committee_corpus_*.json")))
    n_prov = sum(1 for r in rows if r["usable_pair"] and r["contested_ex_ante"]
                 and r["signal_stage"] == "provisional")
    bar = "CLEARED" if (n_pair >= 10 and n_contested_pair >= 6) else "not yet cleared"
    print("\nwritten: results/stage0_feasibility.json")
    print(f"\nVERDICT: {n_pair} usable pairs ({n_contested_pair} contested) across "
          f"{n_committees} committees. Stage-A bar (>=10 pairs, >=6 contested): {bar}.")
    print(f"CAVEATS: (1) the votes page is a ROLLING WINDOW — this is a single snapshot; "
          f"deeper history needs accumulating scrapes over time (scraper now merges).")
    print(f"  (2) {n_prov}/{n_contested_pair} contested pairs rest on a provisional-agreement "
          f"(consensus-stage) signal, a weaker contestedness cue than report-adoption.")
    return out


if __name__ == "__main__":
    main()
