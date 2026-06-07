"""Part 1 of §9.6: the contested-subset check.

Network-free. Reuses the frozen §9.6 machinery (``baselines`` + ``baseline_eval`` +
``baseline_robustness``) and asks the question RESULTS.md left open: Baseline A is
statistically tied with the const_mean floor *over all 22 files* — does A's per-group
signal earn its keep on the files that are actually CONTESTED?

This is a STRATIFIED RE-EVALUATION of the validated 22-file set, not a new data pull:
  * LOO predictions are computed once over all 22 files and HELD FIXED (Decision 6);
    only the evaluation sample is restricted to a contested subset.
  * "Contested" is defined under three transparent lenses so the partition is not
    secretly driving the answer:

      1. dispersion  — population stdev of the 9 observed group yes-rates on a file.
         High = groups disagree. THIS LENS IS A MECHANICAL UPPER BOUND for A vs
         const_mean: const_mean predicts one scalar for every group, so its per-file
         loss IS essentially that dispersion. Selecting high-dispersion files selects
         exactly const_mean's blind spot. A "win" here is near-tautological; reported
         as an upper bound, not as evidence.
      2. boundary    — closeness of the observed EP yes-share to 0.5 (outcome in
         doubt). Outcome-defined, not mechanically tied to per-group variance.
      3. rejected    — the REJECTED files only. Outcome-defined. (n=4: descriptive
         only, no inferential claim.)

  * Significance via the same paired cluster-bootstrap (seed 0, 10k) + Wilcoxon as
    §5b, restricted to the subset. n per subset is tiny (<=11), so CIs are wide and
    non-significance is the expected default — that is itself the honest finding.

CAVEAT (decisive, same family as the D0 result): the contested subsets are defined
USING the observed yes-rates, so this is post-hoc difficulty stratification — a
descriptive "where is A more accurate", NOT a prospective claim that A beats the
floor on votes flagged contested ahead of time. A prospective version would need a
pre-vote contestedness signal and a time split; that is the real frontier and is not
done here.

Reproduce (no network):

    uv run python -m praevisa.contested_subset
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from scipy import stats

from .baselines import CANONICAL_GROUPS, load_testset
from .baseline_robustness import _per_file_losses, SEED, N_BOOT

RESULTS_PATH = Path(__file__).resolve().parent.parent / "results" / "contested_subset.json"

ANCHOR = "baseline_A"
RIVALS = ["const_mean", "baseline_C", "const_0.95"]
MIN_N_FOR_WILCOXON = 6


def _dispersion(record) -> float:
    """Population stdev of the defined group yes-rates on one file."""
    vals = [v for v in record.yes_rates.values() if v is not None]
    return float(np.std(vals)) if vals else float("nan")


def _file_features(records):
    """Per-file contestedness scores, index-aligned to `records`."""
    disp = np.array([_dispersion(r) for r in records])
    dist_half = np.array([abs(r.observed_share - 0.5) for r in records])
    rejected = np.array([r.result == "REJECTED" for r in records])
    return disp, dist_half, rejected


def _subset_indices(records):
    """Return {lens_name: (np.array of file indices, description)}."""
    n = len(records)
    disp, dist_half, rejected = _file_features(records)
    order_disp = np.argsort(-disp)          # most dispersed first
    order_close = np.argsort(dist_half)     # closest to 0.5 first
    half = n // 2
    third = n // 3
    return {
        "full": (np.arange(n), "all 22 files (reference)"),
        "dispersion_top_half": (np.sort(order_disp[:half]),
                                 f"top {half} by cross-group dispersion (UPPER BOUND: mechanically favors A)"),
        "dispersion_bottom_half": (np.sort(order_disp[half:]),
                                    f"bottom {n - half} by dispersion (routine/agreeing files)"),
        "dispersion_top_third": (np.sort(order_disp[:third]),
                                 f"top {third} most dispersed (UPPER BOUND)"),
        "boundary_closest_half": (np.sort(order_close[:half]),
                                  f"{half} files closest to yes-share 0.5 (outcome in doubt)"),
        "rejected": (np.where(rejected)[0],
                     "REJECTED files only (outcome-defined; n=4, descriptive only)"),
    }


def _paired(loss_a, loss_r, idx, rng):
    """Paired A-vs-rival comparison restricted to file indices `idx`.

    mean_diff = mean(loss_rival - loss_A) over idx; positive => rival worse than A.
    """
    a = loss_a[idx]
    r = loss_r[idx]
    d = r - a
    m = len(idx)
    boot = rng.integers(0, m, size=(N_BOOT, m))
    boot_mean = (d[boot]).mean(axis=1)
    lo, hi = np.percentile(boot_mean, [2.5, 97.5])
    # Wilcoxon needs >= a few nonzero paired diffs to mean anything
    nonzero = int(np.count_nonzero(d))
    if m >= MIN_N_FOR_WILCOXON and nonzero >= MIN_N_FOR_WILCOXON:
        wp = float(stats.wilcoxon(d, zero_method="wilcox").pvalue)
    else:
        wp = None
    return {
        "n_files": m,
        "mean_loss_A": float(np.mean(a)),
        "mean_loss_rival": float(np.mean(r)),
        "mean_diff": float(np.mean(d)),
        "mean_diff_ci95": [float(lo), float(hi)],
        "win_fraction_A_better": float(np.mean(boot_mean > 0)),
        "wilcoxon_p": wp,
        "ranking_real": bool(lo > 0 and wp is not None and wp < 0.05),
    }


def evaluate(records) -> dict:
    cell_loss, _share_loss = _per_file_losses(records)  # fixed LOO per-file cell losses
    subsets = _subset_indices(records)
    rng = np.random.default_rng(SEED)

    out_subsets = {}
    for lens, (idx, desc) in subsets.items():
        per_pred = {name: float(np.mean(cell_loss[name][idx])) for name in cell_loss}
        pairwise = {rival: _paired(cell_loss[ANCHOR], cell_loss[rival], idx, rng)
                    for rival in RIVALS}
        out_subsets[lens] = {
            "description": desc,
            "n_files": int(len(idx)),
            "file_ids": [records[i].id for i in idx],
            "mse_micro": per_pred,
            "pairwise_vs_baseline_A": pairwise,
        }

    disp, dist_half, rejected = _file_features(records)
    return {
        "protocol": "stratified re-evaluation of the 22-file set; LOO predictions held "
                    "fixed (Decision 6); evaluation restricted to contested subsets",
        "seed": SEED,
        "n_boot": N_BOOT,
        "anchor": ANCHOR,
        "caveat": "post-hoc stratification (subsets defined from observed yes-rates); "
                  "descriptive, not prospective. dispersion lens mechanically favors A.",
        "per_file": [
            {"id": r.id, "reference": r.reference, "result": r.result,
             "observed_share": round(r.observed_share, 4),
             "dispersion": round(float(disp[i]), 4),
             "dist_to_half": round(float(dist_half[i]), 4)}
            for i, r in enumerate(records)
        ],
        "subsets": out_subsets,
    }


def _fmt_p(p):
    return " n<6 " if p is None else f"{p:.4f}"


def main() -> None:
    records = load_testset()
    out = evaluate(records)
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_PATH.write_text(json.dumps(out, indent=1))

    print("CONTESTED-SUBSET CHECK — stratified re-eval of the 22-file set "
          "(LOO preds held fixed)\n")
    print("Question: does baseline_A (per-group) beat the const_mean floor on "
          "contested files?\n")

    order = ["full", "dispersion_bottom_half", "dispersion_top_half",
             "dispersion_top_third", "boundary_closest_half", "rejected"]
    for lens in order:
        s = out["subsets"][lens]
        a = s["mse_micro"]["baseline_A"]
        cm = s["mse_micro"]["const_mean"]
        cc = s["mse_micro"]["baseline_C"]
        print(f"[{lens}]  n={s['n_files']}  — {s['description']}")
        print(f"    MSE_micro:  baseline_A={a:.4f}   const_mean={cm:.4f}   "
              f"baseline_C={cc:.4f}")
        p = s["pairwise_vs_baseline_A"]["const_mean"]
        lo, hi = p["mean_diff_ci95"]
        print(f"    A vs const_mean:  mean_diff={p['mean_diff']:+.4f}  "
              f"CI[{lo:+.4f},{hi:+.4f}]  winfrac={p['win_fraction_A_better']:.3f}  "
              f"wilcox_p={_fmt_p(p['wilcoxon_p'])}  real={p['ranking_real']}")
        print()

    print(f"written: {RESULTS_PATH}")


if __name__ == "__main__":
    main()
