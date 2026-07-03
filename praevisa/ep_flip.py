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

import json
import sys
from dataclasses import dataclass
from pathlib import Path

from . import baselines, stage0_feasibility as s0
from .data import EP_GROUPS
from .flip import _ep_pivot_path

GROUPS = list(baselines.CANONICAL_GROUPS)
_SEATS = {g.code: g.seats for g in EP_GROUPS}
_CALIB = Path(__file__).resolve().parent.parent / "results" / "calibration.json"


def load_alpha() -> float:
    """Production shrinkage weight, from the committed calibration artifact.

    α=1.0 is the identity map; α<1 regresses the committee rate toward the group's plenary
    prior. `praevisa.calibration` picks `production_alpha` by the DECISION metric (contested
    outcome accuracy), NOT per-group MSE — so a calibration that lowers MSE but flips
    rejections is rejected and this stays 1.0. Defaults to 1.0 if the artifact is absent,
    so the bridge never silently adopts an unvalidated transform.
    """
    try:
        with open(_CALIB) as fh:
            a = json.load(fh).get("production_alpha")
        return float(a) if a is not None else 1.0
    except (OSError, ValueError, TypeError):
        return 1.0


@dataclass
class _EPForecast:
    """Minimal adapter: `_ep_pivot_path` reads only `.group_yes_rates`."""
    group_yes_rates: dict


def _baseline_A() -> dict:
    """Per-group plenary historical mean — the prior for groups absent in committee."""
    base = baselines.load_testset()
    return {g: baselines.baseline_a(base, g) for g in GROUPS}


def predictor_group_rates(votes) -> dict:
    """H2 — committee per-group rates as the PREDICTOR consumes them
    (pre-registered forward hypothesis, 2026-07).

    Abstentions leave the denominator: rate = FOR / (FOR + AGAINST). A group whose
    committee members ONLY abstained gets None, so it contributes no committee
    signal and falls back to its prior inside `predict_plenary_per_group` — an
    abstention on a committee text is not an opposition forecast for the floor
    (June 2026: Renew's 3 abstentions became a 0.0 FOR prediction; observed 1.0).

    PREDICTION ONLY. The measurement basis is untouched: Decision 1 (abstentions
    in the denominator, `stage0_feasibility._committee_group_rates`) stands
    wherever historical rates are measured — stage_a, stage_b, stage0, stress-set
    residuals, and everything §9.6 grades against.
    """
    agg: dict[str, tuple[int, int]] = {}
    for v in votes:
        canon = s0.COMMITTEE_GROUP_MAP.get(v.get("group"))
        if canon is None:
            continue
        f, a = agg.get(canon, (0, 0))
        c = v.get("choice")
        if c == "+":
            f += 1
        elif c == "-":
            a += 1
        agg[canon] = (f, a)
    return {g: (f / (f + a) if (f + a) else None) for g, (f, a) in agg.items()}


def predict_plenary_per_group(committee_rates: dict, prior: dict,
                              alpha: float | None = None) -> dict:
    """The model: predicted plenary per-group yes-rate.

    Calibrated shrinkage (Phase 2): plenary ≈ α·committee + (1−α)·prior[g], where
    prior[g] = baseline_A and α is fit + CV-validated by `praevisa.calibration`
    (committee rates are extreme because committees are small, so they regress toward the
    plenary mean). α defaults to the committed calibration artifact; α=1.0 recovers the
    Phase-1 identity map. Groups with NO committee signal fall back to the prior, not a
    fabricated 0%.
    """
    a = load_alpha() if alpha is None else alpha
    out = {}
    for g in GROUPS:
        v = committee_rates.get(g)
        pr = prior.get(g)
        if v is None:
            out[g] = pr
        elif pr is None:
            out[g] = v
        else:
            out[g] = a * v + (1 - a) * pr
    return out


def forecast_for(proc: str, committee: dict | None = None, prior: dict | None = None):
    """Build the EP forecast + flip for one procedure, or None if we have no signal."""
    committee = committee if committee is not None else s0.load_committee_cod()
    rec = committee.get(proc)
    if rec is None:
        return None
    prior = prior if prior is not None else _baseline_A()
    com = predictor_group_rates(rec["votes"])
    com = {g: (round(v, 4) if v is not None else None) for g, v in com.items()}
    pred = predict_plenary_per_group(com, prior)
    yes_overall, _n = s0._committee_yes(rec)
    # ONE seat tally drives outcome, margin AND the pivot — so the headline can never
    # contradict the flip lever near 50%. Convention matches _ep_pivot_path: seat-weighted,
    # abstention-ignored, NI excluded (non-attached — no party line to lobby).
    gyr = {g: (pred[g] if pred[g] is not None else 0.0) for g in GROUPS}
    pivot = _ep_pivot_path(_EPForecast(group_yes_rates=gyr))
    yes_seats = sum(_SEATS[g] * gyr[g] for g in GROUPS if g != "NI")
    no_seats = sum(_SEATS[g] * (1.0 - gyr[g]) for g in GROUPS if g != "NI")
    tot = yes_seats + no_seats
    share = yes_seats / tot if tot else float("nan")
    return {
        "procedure": proc, "committee": rec["committee"], "stage": rec.get("_stage"),
        "contested": bool(yes_overall is not None and yes_overall < s0.CONTESTED_MAX_YES),
        "per_group": pred, "ep_yes_share": share,
        "outcome": "ADOPTED" if yes_seats > no_seats else "REJECTED",
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
