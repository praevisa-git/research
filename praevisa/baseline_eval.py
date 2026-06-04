"""Step 4 of the §9.6 baseline build: leave-one-out evaluation harness.

Network-free. Reads the committed ``data/htv_raw/`` test set, runs the LOO protocol
(METHODOLOGY.md §4) for Baseline A, Baseline C, and the two reference constants,
and computes the metrics frozen in METHODOLOGY.md §5:

  * per-group MSE  (== per-group Brier on the [0,1] yes-rate; identity noted)
  * MSE macro mean (groups weighted equally) and micro mean (cells weighted equally)
  * aggregate EP yes-share SSE (seat-share weighted predicted share; Decision 3)

Writes ``results/baseline_eval.json`` and prints a summary table.

Reproduce (one command, no network):

    uv run python -m praevisa.baseline_eval
"""

from __future__ import annotations

import json
from pathlib import Path

from .baselines import (
    CANONICAL_GROUPS,
    SEAT_WEIGHTS,
    FileRecord,
    baseline_a,
    baseline_c,
    const_095,
    const_mean,
    load_testset,
)

RESULTS_PATH = Path(__file__).resolve().parent.parent / "results" / "baseline_eval.json"

# Each predictor maps (training records for the fold, group) -> predicted yes-rate
# or None ("undefined for this cell"; dropped from grading per METHODOLOGY §3-4).
# Baseline C and const-0.95 ignore `train` (file-independent); the LOO loop still
# evaluates them on every held-out file for comparability.
PREDICTORS = {
    "baseline_A": lambda train, g: baseline_a(train, g),
    "baseline_C": lambda train, g: baseline_c(g),
    "const_0.95": lambda train, g: const_095(g),
    "const_mean": lambda train, g: const_mean(train),
}


def _predicted_share(preds: dict[str, float | None]) -> float:
    """Seat-share-weighted EP yes-share (Decision 3).

    Weights are renormalised over the groups with a defined prediction so an
    undefined cell neither contributes nor distorts the total. With the current
    test set every cell is defined, so this is a no-op; it guards the general case.
    """
    num = den = 0.0
    for g, p in preds.items():
        if p is None:
            continue
        w = SEAT_WEIGHTS[g]
        num += w * p
        den += w
    return num / den if den else float("nan")


def evaluate(records: list[FileRecord]) -> dict:
    n = len(records)
    groups = list(CANONICAL_GROUPS)

    # accumulators per predictor
    sq_err_by_group: dict[str, dict[str, list[float]]] = {
        name: {g: [] for g in groups} for name in PREDICTORS
    }
    share_sq_err: dict[str, list[float]] = {name: [] for name in PREDICTORS}
    undefined_cells: dict[str, int] = {name: 0 for name in PREDICTORS}

    for i in range(n):
        target = records[i]
        train = records[:i] + records[i + 1 :]
        for name, fn in PREDICTORS.items():
            preds: dict[str, float | None] = {}
            for g in groups:
                pred = fn(train, g)
                preds[g] = pred
                obs = target.yes_rates[g]
                if obs is None:
                    continue  # cell undefined in ground truth -> not graded
                if pred is None:
                    undefined_cells[name] += 1
                    continue
                sq_err_by_group[name][g].append((pred - obs) ** 2)
            # aggregate EP yes-share for this held-out file
            pred_share = _predicted_share(preds)
            share_sq_err[name].append((pred_share - target.observed_share) ** 2)

    # reduce to metrics
    results: dict[str, dict] = {}
    for name in PREDICTORS:
        per_group_mse = {
            g: (sum(v) / len(v) if v else None) for g, v in sq_err_by_group[name].items()
        }
        defined_groups = [g for g in groups if per_group_mse[g] is not None]
        all_cell_errs = [e for g in groups for e in sq_err_by_group[name][g]]
        mse_macro = (
            sum(per_group_mse[g] for g in defined_groups) / len(defined_groups)
            if defined_groups
            else None
        )
        mse_micro = sum(all_cell_errs) / len(all_cell_errs) if all_cell_errs else None
        sse = sum(share_sq_err[name])
        results[name] = {
            "per_group_mse": {g: per_group_mse[g] for g in groups},
            # per-group Brier is, by construction, identical to per-group MSE on the
            # [0,1] yes-rate (METHODOLOGY §5); reported under both names for traceability.
            "per_group_brier": {g: per_group_mse[g] for g in groups},
            "mse_macro": mse_macro,
            "mse_micro": mse_micro,
            "ep_yes_share_sse": sse,
            "ep_yes_share_rmse": (sse / len(records)) ** 0.5,
            "n_cells_graded": len(all_cell_errs),
            "n_cells_undefined": undefined_cells[name],
        }

    return {
        "test_set": {
            "n_files": n,
            "n_groups": len(groups),
            "groups": groups,
            "files": [
                {"id": r.id, "reference": r.reference, "result": r.result,
                 "observed_share": round(r.observed_share, 6)}
                for r in sorted(records, key=lambda r: r.observed_share)
            ],
        },
        "protocol": "leave-one-out, one fold per file (METHODOLOGY §4)",
        "metric_defs": {
            "per_group_mse": "mean_f (pred - obs)^2 over files where the group is defined",
            "per_group_brier": "identical to per_group_mse on the [0,1] yes-rate (METHODOLOGY §5)",
            "mse_macro": "mean of per_group_mse across groups (groups weighted equally)",
            "mse_micro": "mean (pred-obs)^2 across all defined cells (cells weighted equally)",
            "ep_yes_share_sse": "sum_f (pred_share - obs_share)^2; pred_share seat-weighted (Decision 3)",
            "yes_rate_denominator": "FOR/(FOR+AGAINST+ABSTENTION) (Decision 1)",
        },
        "results": results,
    }


def _fmt(x: float | None) -> str:
    return "  n/a " if x is None else f"{x:.4f}"


def main() -> None:
    records = load_testset()
    out = evaluate(records)
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_PATH.write_text(json.dumps(out, indent=1))

    groups = out["test_set"]["groups"]
    names = list(PREDICTORS)
    print(f"LOO over {out['test_set']['n_files']} files x {len(groups)} groups "
          f"({out['results']['baseline_A']['n_cells_graded']} cells)\n")

    # headline table
    hdr = f"{'predictor':12s} {'MSE_macro':>10s} {'MSE_micro':>10s} {'share_SSE':>10s} {'share_RMSE':>11s}"
    print(hdr)
    print("-" * len(hdr))
    for name in names:
        r = out["results"][name]
        print(f"{name:12s} {_fmt(r['mse_macro']):>10s} {_fmt(r['mse_micro']):>10s} "
              f"{_fmt(r['ep_yes_share_sse']):>10s} {_fmt(r['ep_yes_share_rmse']):>11s}")

    # per-group MSE table
    print(f"\nper-group MSE (== per-group Brier):")
    print(f"{'group':8s} " + " ".join(f"{n:>11s}" for n in names))
    for g in groups:
        row = " ".join(f"{_fmt(out['results'][n]['per_group_mse'][g]):>11s}" for n in names)
        print(f"{g:8s} {row}")

    print(f"\nwritten: {RESULTS_PATH}")


if __name__ == "__main__":
    main()
