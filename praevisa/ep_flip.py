"""EP flip layer on the validated committee signal — the sellable artifact.

This bridges the two halves of the engine. Stage A/B proved a per-group forecast:
a group's COMMITTEE vote predicts its PLENARY vote (significant on contested files).
`flip.py` has the targeting logic a public-affairs team actually buys: *which group
would have to move to flip the outcome*. Until now they were disconnected — the proven
signal produced only a per-group number, and the flip layer ran on the old Monte-Carlo
engine. This module feeds the validated signal into `flip.py::_ep_pivot_path` to produce,
per file, the lobbyist deliverable on proven rails:

    predicted plenary outcome + EP yes-share  →  named pivot group + what flips it

Scope: EP only. The Council levers in `flip.py` need per-member-state Council data, which
is access-gated (see COUNCIL_LAYER.md); they stay dormant here. The predictor is currently
the Stage-A identity map (predicted plenary per group = committee per group); Phase 2
calibrates it — this module reads whatever `predict_plenary_per_group` returns, so the
calibration drops in without touching the bridge.

Run:
    uv run python -m praevisa.ep_flip 2025/0825(COD)   # one file
    uv run python -m praevisa.ep_flip all              # every file with a committee signal
"""

from __future__ import annotations

import sys
from dataclasses import dataclass

from . import baselines, stage0_feasibility as s0
from .data import EP_GROUPS
from .flip import _ep_pivot_path

GROUPS = list(baselines.CANONICAL_GROUPS)
SEAT_W = baselines.SEAT_WEIGHTS
_SEATS = {g.code: g.seats for g in EP_GROUPS}


@dataclass
class _EPForecast:
    """Minimal adapter: `_ep_pivot_path` reads only `.group_yes_rates`."""
    group_yes_rates: dict


def _baseline_A() -> dict:
    """Per-group plenary historical mean — the prior for groups absent in committee."""
    base = baselines.load_testset()
    return {g: baselines.baseline_a(base, g) for g in GROUPS}


def predict_plenary_per_group(committee_rates: dict, prior: dict) -> dict:
    """The model: predicted plenary per-group yes-rate.

    Phase 1 = the Stage-A identity map (plenary ≈ committee). Groups with NO committee
    signal fall back to their plenary baseline_A prior rather than a fabricated 0%.
    Phase 2 replaces the identity line with a calibrated committee→plenary transform;
    nothing downstream changes.
    """
    out = {}
    for g in GROUPS:
        v = committee_rates.get(g)
        out[g] = v if v is not None else prior.get(g)
    return out


def _ep_share(per_group: dict) -> float:
    num = den = 0.0
    for g in GROUPS:
        v = per_group.get(g)
        if v is None:
            continue
        num += SEAT_W[g] * v
        den += SEAT_W[g]
    return num / den if den else float("nan")


def forecast_for(proc: str, committee: dict | None = None, prior: dict | None = None):
    """Build the EP forecast + flip for one procedure, or None if we have no signal."""
    committee = committee if committee is not None else s0.load_committee_cod()
    rec = committee.get(proc)
    if rec is None:
        return None
    prior = prior if prior is not None else _baseline_A()
    com = s0._committee_group_rates(rec["votes"])
    com = {g: (round(v, 4) if v is not None else None) for g, v in com.items()}
    pred = predict_plenary_per_group(com, prior)
    share = _ep_share(pred)
    yes_overall, _n = s0._committee_yes(rec)
    pivot = _ep_pivot_path(_EPForecast(group_yes_rates={g: (pred[g] or 0.0) for g in GROUPS}))
    # predicted seats for the margin line (abstention-ignored, same approx as the pivot)
    yes_seats = sum(_SEATS[g] * (pred[g] or 0.0) for g in GROUPS if g != "NI")
    no_seats = sum(_SEATS[g] * (1.0 - (pred[g] or 0.0)) for g in GROUPS if g != "NI")
    return {
        "procedure": proc, "committee": rec["committee"], "stage": rec.get("_stage"),
        "contested": bool(yes_overall is not None and yes_overall < s0.CONTESTED_MAX_YES),
        "per_group": pred, "ep_yes_share": share,
        "outcome": "ADOPTED" if share > 0.5 else "REJECTED",
        "margin_seats": yes_seats - no_seats, "pivot": pivot,
    }


def report(f: dict) -> str:
    if f is None:
        return "no committee signal for that procedure"
    L = []
    tag = "CONTESTED" if f["contested"] else "routine"
    L.append(f"EP flip forecast — {f['procedure']}  ({f['committee']}, "
             f"{f['stage']} signal, {tag})")
    L.append(f"  Predicted plenary : {f['outcome']}  "
             f"(EP yes-share {f['ep_yes_share']:.0%}, "
             f"seat margin {f['margin_seats']:+.0f})")
    L.append("  Per-group predicted yes-rate (from the committee signal):")
    for g in sorted(GROUPS, key=lambda g: -(f["per_group"].get(g) or 0.0)):
        v = f["per_group"].get(g)
        if v is None:
            continue
        bar = "#" * int(round(v * 20))
        L.append(f"    {g:7s} {v:5.0%}  {bar}")
    p = f["pivot"]
    L.append("")
    if p is None:
        L.append("  Flip: no EP pivot computable.")
    else:
        L.append(f"  FLIP LEVER — {p.headline}"
                 + ("" if p.realistic else "  [not movable by one group]"))
        for d in p.detail:
            L.append(f"    · {d}")
    L.append("  (EP only; Council levers dormant — access-gated, see COUNCIL_LAYER.md)")
    return "\n".join(L)


def main() -> int:
    arg = sys.argv[1] if len(sys.argv) > 1 else "all"
    committee = s0.load_committee_cod()
    prior = _baseline_A()
    if arg == "all":
        procs = sorted(committee)
        print(f"EP flip forecasts for {len(procs)} files with a committee signal "
              f"(validated Stage-A rails)\n")
        for proc in procs:
            f = forecast_for(proc, committee, prior)
            if f:
                print(report(f))
                print()
        return 0
    f = forecast_for(arg, committee, prior)
    if f is None:
        print(f"no committee signal for {arg!r}; try `all` to list available files")
        return 1
    print(report(f))
    return 0


if __name__ == "__main__":
    sys.exit(main())
