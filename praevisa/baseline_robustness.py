"""Robustness / significance check for the §9.6 baselines (METHODOLOGY §5b).

Network-free. Holds the LOO predictions fixed (Decision 6) and cluster-bootstraps
the 22-file evaluation sample (Decision 5: seed 0, 10,000 resamples) to test whether
the ranking from ``baseline_eval`` is real or sampling noise.

Reports, per predictor, MSE_micro and mean per-file EP-yes-share squared error each
with a 95% percentile bootstrap CI; and, paired against the apparent winner
baseline_A, the mean per-file loss difference with its bootstrap CI, win-fraction,
and a two-sided Wilcoxon signed-rank p-value.

Writes ``results/baseline_robustness.json`` and prints a summary.

Reproduce (no network):

    uv run python -m praevisa.baseline_robustness
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from scipy import stats

from .baselines import CANONICAL_GROUPS, SEAT_WEIGHTS, load_testset
from .baseline_eval import PREDICTORS, _predicted_share

RESULTS_PATH = Path(__file__).resolve().parent.parent / "results" / "baseline_robustness.json"

SEED = 0          # Decision 5
N_BOOT = 10_000   # Decision 5
ANCHOR = "baseline_A"


def _per_file_losses(records):
    """Compute, holding LOO predictions fixed, per-file arrays for each predictor.

    Returns:
      cell_loss[name]  : (n_files,) mean of the 9 cell squared errors per file (==
                         per-file contribution to MSE_micro under the balanced design)
      share_loss[name] : (n_files,) squared error of the aggregate EP yes-share per file
    """
    groups = list(CANONICAL_GROUPS)
    n = len(records)
    cell_loss = {name: np.full(n, np.nan) for name in PREDICTORS}
    share_loss = {name: np.full(n, np.nan) for name in PREDICTORS}

    for i in range(n):
        target = records[i]
        train = records[:i] + records[i + 1 :]
        for name, fn in PREDICTORS.items():
            preds = {g: fn(train, g) for g in groups}
            errs = []
            for g in groups:
                obs = target.yes_rates[g]
                pred = preds[g]
                if obs is None or pred is None:
                    continue
                errs.append((pred - obs) ** 2)
            cell_loss[name][i] = float(np.mean(errs)) if errs else np.nan
            pred_share = _predicted_share(preds)
            share_loss[name][i] = (pred_share - target.observed_share) ** 2
    return cell_loss, share_loss


def _ci(samples: np.ndarray) -> list[float]:
    lo, hi = np.percentile(samples, [2.5, 97.5])
    return [float(lo), float(hi)]


def evaluate(records) -> dict:
    cell_loss, share_loss = _per_file_losses(records)
    n = len(records)
    rng = np.random.default_rng(SEED)
    # one shared set of bootstrap file-index resamples (paired comparisons use the same draws)
    idx = rng.integers(0, n, size=(N_BOOT, n))

    names = list(PREDICTORS)
    point = {}
    boot_means_cell = {}
    boot_means_share = {}
    for name in names:
        cl, sl = cell_loss[name], share_loss[name]
        point[name] = {
            "mse_micro": float(np.mean(cl)),
            "share_mse": float(np.mean(sl)),
        }
        boot_means_cell[name] = cl[idx].mean(axis=1)   # (N_BOOT,)
        boot_means_share[name] = sl[idx].mean(axis=1)

    per_predictor = {}
    for name in names:
        per_predictor[name] = {
            "mse_micro": point[name]["mse_micro"],
            "mse_micro_ci95": _ci(boot_means_cell[name]),
            "share_mse": point[name]["share_mse"],
            "share_mse_ci95": _ci(boot_means_share[name]),
        }

    # pairwise vs anchor (baseline_A): is each rival worse?
    pairwise = {}
    a_cell, a_share = cell_loss[ANCHOR], share_loss[ANCHOR]
    for name in names:
        if name == ANCHOR:
            continue
        d_cell = cell_loss[name] - a_cell      # >0 means rival worse than A
        d_share = share_loss[name] - a_share
        boot_d_cell = boot_means_cell[name] - boot_means_cell[ANCHOR]
        boot_d_share = boot_means_share[name] - boot_means_share[ANCHOR]
        # Wilcoxon signed-rank (two-sided) on the 22 paired diffs
        wp_cell = float(stats.wilcoxon(d_cell, zero_method="wilcox").pvalue)
        wp_share = float(stats.wilcoxon(d_share, zero_method="wilcox").pvalue)
        pairwise[name] = {
            "vs": ANCHOR,
            "cell": {
                "mean_diff": float(np.mean(d_cell)),
                "mean_diff_ci95": _ci(boot_d_cell),
                "win_fraction_A_better": float(np.mean(boot_d_cell > 0)),
                "wilcoxon_p": wp_cell,
                "ranking_real": bool((np.percentile(boot_d_cell, 2.5) > 0) and wp_cell < 0.05),
            },
            "share": {
                "mean_diff": float(np.mean(d_share)),
                "mean_diff_ci95": _ci(boot_d_share),
                "win_fraction_A_better": float(np.mean(boot_d_share > 0)),
                "wilcoxon_p": wp_share,
                "ranking_real": bool((np.percentile(boot_d_share, 2.5) > 0) and wp_share < 0.05),
            },
        }

    return {
        "protocol": "cluster bootstrap over files, LOO predictions held fixed (METHODOLOGY §5b)",
        "seed": SEED,
        "n_boot": N_BOOT,
        "n_files": n,
        "anchor": ANCHOR,
        "note": "cell unit = per-file mean of 9 cell squared errors; mean over files == MSE_micro",
        "per_predictor": per_predictor,
        "pairwise_vs_anchor": pairwise,
    }


def main() -> None:
    records = load_testset()
    out = evaluate(records)
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_PATH.write_text(json.dumps(out, indent=1))

    print(f"Cluster bootstrap over {out['n_files']} files, {out['n_boot']} resamples, "
          f"seed {out['seed']}; LOO predictions held fixed.\n")
    print(f"{'predictor':12s} {'MSE_micro':>10s} {'95% CI':>20s}")
    print("-" * 44)
    for name, r in out["per_predictor"].items():
        lo, hi = r["mse_micro_ci95"]
        print(f"{name:12s} {r['mse_micro']:>10.4f}   [{lo:.4f}, {hi:.4f}]")

    print(f"\nPaired vs {out['anchor']} (per-file cell loss; positive = rival worse):")
    print(f"{'rival':12s} {'mean_diff':>10s} {'95% CI':>22s} {'winfrac':>8s} {'wilcox_p':>9s}  real?")
    for name, p in out["pairwise_vs_anchor"].items():
        c = p["cell"]
        lo, hi = c["mean_diff_ci95"]
        print(f"{name:12s} {c['mean_diff']:>+10.4f}   [{lo:+.4f}, {hi:+.4f}] "
              f"{c['win_fraction_A_better']:>8.3f} {c['wilcoxon_p']:>9.4f}  {c['ranking_real']}")

    print(f"\nPaired vs {out['anchor']} (per-file EP yes-share squared error):")
    print(f"{'rival':12s} {'mean_diff':>10s} {'95% CI':>22s} {'winfrac':>8s} {'wilcox_p':>9s}  real?")
    for name, p in out["pairwise_vs_anchor"].items():
        s = p["share"]
        lo, hi = s["mean_diff_ci95"]
        print(f"{name:12s} {s['mean_diff']:>+10.4f}   [{lo:+.4f}, {hi:+.4f}] "
              f"{s['win_fraction_A_better']:>8.3f} {s['wilcoxon_p']:>9.4f}  {s['ranking_real']}")

    print(f"\nwritten: {RESULTS_PATH}")


if __name__ == "__main__":
    main()
