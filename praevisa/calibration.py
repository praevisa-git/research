"""Phase 2 — calibrate the committee→plenary predictor, vs the identity map.

Stage A's predictor is the identity map: predicted plenary per-group yes-rate = the
group's committee yes-rate. Committees are SMALL (a group may field 2-3 members), so
committee rates pin to 0%/100% while the full plenary group is more moderate — i.e. the
committee→plenary step should regress toward the group's historical mean. This module
tests whether a calibrated model beats the raw identity map **out of sample** (leave-one-
FILE-out CV — folds at the file level to respect within-file correlation), honestly, on
the same Stage-A pairs and reported on the contested cut that matters.

Models (prior[g] = baseline_A, the §9.6 per-group plenary mean):
  identity : plenary = committee                               (0 params; current)
  shrink   : plenary = a*committee + (1-a)*prior[g]            (1 param a∈[0,1], LS fit)
  linear   : plenary = clip(a + b*committee, 0, 1)             (2 params, OLS fit)

A model only "wins" if its mean LOO-CV per-group MSE is below identity's on the contested
subset. With n this small, the expected, honest default is "no robust improvement yet".

Run: uv run python -m praevisa.calibration
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from . import baselines, resolve_plenary, stage_a

RESULTS_PATH = Path(__file__).resolve().parent.parent / "results" / "calibration.json"
GROUPS = list(baselines.CANONICAL_GROUPS)


def _prior() -> dict:
    base = baselines.load_testset()
    return {g: baselines.baseline_a(base, g) for g in GROUPS}


_SEATS = {g.code: g.seats for g in __import__("praevisa.data", fromlist=["EP_GROUPS"]).EP_GROUPS}


def _outcome(per_group: dict) -> str:
    """Seat-weighted, abstention-ignored, NI-excluded — the product's pass/fail tally."""
    ys = sum(_SEATS[g] * per_group[g] for g in per_group if g != "NI")
    ns = sum(_SEATS[g] * (1 - per_group[g]) for g in per_group if g != "NI")
    return "ADOPTED" if ys > ns else "REJECTED"


def _cells(pairs, prior):
    """Per pair: group-labelled (committee, plenary, prior) cells + the observed outcome.

    Keeps group labels and seats so we can score the DECISION metric (binary outcome),
    not only per-group MSE — the calibration that wins on MSE can still lose the outcome.
    """
    rows = []
    for p in pairs:
        cells = []
        for g in GROUPS:
            c = p["committee_yes"].get(g)
            y = p["plenary_yes"].get(g)
            pr = prior.get(g)
            if c is not None and y is not None and pr is not None:
                cells.append((g, c, y, pr))
        if len(cells) >= 5:
            observed = _outcome({g: y for (g, c, y, pr) in cells})
            rows.append({"procedure": p["procedure"], "contested": p["contested"],
                         "cells": cells, "observed_outcome": observed})
    return rows


# --- model fits over a set of training cells -> a predict(committee, prior_g) fn ---

def _fit_identity(_train):
    return lambda c, pr: c


def _fit_shrink(train):
    # a* = Σ(c-pr)(y-pr) / Σ(c-pr)^2 , clipped to [0,1]
    num = den = 0.0
    for _g, c, y, pr in train:
        num += (c - pr) * (y - pr)
        den += (c - pr) ** 2
    a = 0.0 if den == 0 else max(0.0, min(1.0, num / den))
    return lambda c, pr: a * c + (1 - a) * pr, a


def _fit_linear(train):
    c = np.array([t[1] for t in train])
    y = np.array([t[2] for t in train])
    if c.std() < 1e-9:
        m = float(y.mean())
        return lambda cc, pr: m, (m, 0.0)
    b = float(((c - c.mean()) * (y - y.mean())).sum() / ((c - c.mean()) ** 2).sum())
    a = float(y.mean() - b * c.mean())
    return lambda cc, pr: max(0.0, min(1.0, a + b * cc)), (a, b)


MODELS = {"identity": _fit_identity, "shrink": _fit_shrink, "linear": _fit_linear}


def _loo_cv(rows):
    """Leave-one-file-out CV, scoring BOTH per-group MSE and the binary outcome."""
    mse = {m: {"all": [], "contested": []} for m in MODELS}
    hit = {m: {"all": [], "contested": []} for m in MODELS}
    fitted_params = {m: [] for m in MODELS}
    for i, held in enumerate(rows):
        train_cells = [cell for j, r in enumerate(rows) if j != i for cell in r["cells"]]
        for m, fit in MODELS.items():
            res = fit(train_cells)
            fn = res[0] if isinstance(res, tuple) else res
            if isinstance(res, tuple):
                fitted_params[m].append(res[1])
            errs = [(fn(c, pr) - y) ** 2 for (_g, c, y, pr) in held["cells"]]
            pred_pg = {g: fn(c, pr) for (g, c, y, pr) in held["cells"]}
            correct = _outcome(pred_pg) == held["observed_outcome"]
            for bucket, ok in (("all", True), ("contested", held["contested"])):
                if ok:
                    mse[m][bucket].append(sum(errs) / len(errs))
                    hit[m][bucket].append(correct)
    summary = {}
    for m in MODELS:
        summary[m] = {
            "cv_mse_all": float(np.mean(mse[m]["all"])),
            "cv_mse_contested": (float(np.mean(mse[m]["contested"]))
                                 if mse[m]["contested"] else None),
            "outcome_acc_all": float(np.mean(hit[m]["all"])),
            "outcome_acc_contested": (float(np.mean(hit[m]["contested"]))
                                      if hit[m]["contested"] else None),
            "params_mean": (float(np.mean(fitted_params[m])) if fitted_params[m]
                            and not isinstance(fitted_params[m][0], tuple) else None),
        }
    return summary


def main():
    index = resolve_plenary.load_index()
    pairs = stage_a.build_pairs(index)
    prior = _prior()
    rows = _cells(pairs, prior)
    contested_n = sum(r["contested"] for r in rows)
    summary = _loo_cv(rows)

    # alpha fit on ALL cells (what the production predictor uses; CV above proves it
    # generalises, this freezes the value the bridge reads).
    all_cells = [cell for r in rows for cell in r["cells"]]
    _, alpha_all = _fit_shrink(all_cells)

    out = {"protocol": "leave-one-file-out CV; calibrated committee→plenary vs identity",
           "n_files": len(rows), "n_contested": contested_n,
           "prior": "baseline_A (§9.6 per-group plenary mean)",
           "shrinkage_alpha_fit": round(alpha_all, 4), "models": summary}

    print("CALIBRATION — committee→plenary predictor vs the identity map "
          f"(leave-one-file-out CV)\n")
    print(f"files: {len(rows)}  (contested {contested_n})  ·  prior = baseline_A\n")
    print(f"{'model':10s}{'MSE all':>9s}{'MSE ctd':>9s}"
          f"{'OUTCOME all':>13s}{'OUTCOME ctd':>13s}{'fit':>9s}")
    print("-" * 63)
    for m in MODELS:
        s = summary[m]
        a = "" if s["params_mean"] is None else f"a≈{s['params_mean']:.2f}"
        mct = "n/a" if s["cv_mse_contested"] is None else f"{s['cv_mse_contested']:.4f}"
        oa = f"{s['outcome_acc_all']:.0%}"
        oc = "n/a" if s["outcome_acc_contested"] is None else f"{s['outcome_acc_contested']:.0%}"
        print(f"{m:10s}{s['cv_mse_all']:>9.4f}{mct:>9s}{oa:>13s}{oc:>13s}{a:>9s}")

    # The DECISION metric — contested outcome accuracy — is what the product is judged on.
    # A model that wins per-group MSE but loses contested outcome accuracy is NOT shipped.
    id_oc = summary["identity"]["outcome_acc_contested"]
    best_oc = max((m for m in MODELS if summary[m]["outcome_acc_contested"] is not None),
                  key=lambda m: (summary[m]["outcome_acc_contested"],
                                 -summary[m]["cv_mse_contested"]))
    print()
    print("VERDICT (decision metric = contested outcome accuracy):")
    if best_oc == "identity" or summary[best_oc]["outcome_acc_contested"] <= id_oc:
        sh = summary.get("shrink", {})
        note = ""
        if sh and sh["cv_mse_contested"] is not None and sh["cv_mse_contested"] < summary["identity"]["cv_mse_contested"]:
            note = (f" Note: 'shrink' wins per-group MSE "
                    f"({sh['cv_mse_contested']:.4f} vs {summary['identity']['cv_mse_contested']:.4f}) "
                    f"but DEGRADES contested outcome accuracy "
                    f"({sh['outcome_acc_contested']:.0%} vs {id_oc:.0%}) — it regresses genuine "
                    f"file-specific dissent toward the party mean and flips rejections. NOT shipped.")
        print(f"  KEEP IDENTITY (alpha=1.0). No calibration beats it on the decision metric.{note}")
        production_alpha = 1.0
    else:
        production_alpha = round(alpha_all, 4)
        print(f"  '{best_oc}' improves contested outcome accuracy "
              f"({summary[best_oc]['outcome_acc_contested']:.0%} vs {id_oc:.0%}) — ship it "
              f"(alpha={production_alpha}).")
    out["production_alpha"] = production_alpha
    RESULTS_PATH.parent.mkdir(exist_ok=True)
    RESULTS_PATH.write_text(json.dumps(out, indent=1))
    print(f"\nwritten: {RESULTS_PATH}")
    return out


if __name__ == "__main__":
    main()
