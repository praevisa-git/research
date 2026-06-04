"""Step 3 of the §9.6 baseline build: data loading + Baseline A and Baseline C.

Pure, network-free. Reads only the committed raw JSON in ``data/htv_raw/`` and
implements exactly the definitions frozen in METHODOLOGY.md. The leave-one-out
orchestration and metrics live in step 4 (``praevisa.baseline_eval``); this module
provides the building blocks:

  * ``load_testset``      -> list[FileRecord] with per-group yes-rates (Decision 1)
  * ``baseline_a``        -> LOO group mean (METHODOLOGY §3)
  * ``baseline_c``        -> constant 0.95/0.05 group-line (METHODOLOGY §3, Decision 2)
  * ``const_095``         -> reference: 0.95 everywhere (METHODOLOGY §3)
  * ``const_mean``        -> reference: global pooled mean (METHODOLOGY §3)

Run ``python -m praevisa.baselines`` for a self-check of the loaded matrix and the
Baseline C assignment.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .data import EP_GROUPS

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "htv_raw"

# Canonical 10th-term groups (single source of truth: praevisa.data).
CANONICAL_GROUPS: tuple[str, ...] = tuple(g.code for g in EP_GROUPS)

# HowTheyVote group code -> canonical code (METHODOLOGY §1).
GROUP_CODE_MAP: dict[str, str] = {
    "EPP": "EPP",
    "SD": "S&D",
    "PFE": "PfE",
    "ECR": "ECR",
    "RENEW": "Renew",
    "GREEN_EFA": "Greens",
    "GUE_NGL": "Left",
    "ESN": "ESN",
    "NI": "NI",
}

# Baseline C majority set (Decision 2): centrist pro-legislation trio -> 0.95.
MAJORITY_SET: frozenset[str] = frozenset({"EPP", "S&D", "Renew"})
C_HIGH, C_LOW = 0.95, 0.05

# Seat-share weights for the aggregate EP yes-share (Decision 3).
_TOTAL_SEATS = sum(g.seats for g in EP_GROUPS)
SEAT_WEIGHTS: dict[str, float] = {g.code: g.seats / _TOTAL_SEATS for g in EP_GROUPS}


@dataclass(frozen=True)
class FileRecord:
    """One roll-call file, reduced to what the baselines need."""

    id: str
    reference: str
    result: str
    # canonical group -> observed yes-rate in [0,1], or None if undefined on this file
    yes_rates: dict[str, float | None]
    # canonical group -> (FOR, AGAINST, ABSTENTION) raw counts (for the aggregate share)
    ballots: dict[str, tuple[int, int, int]]
    observed_share: float  # whole-EP yes-share, Decision-1 denominator


def _yes_rate(stats: dict) -> float | None:
    """FOR / (FOR + AGAINST + ABSTENTION); None if no ballots cast (Decision 1)."""
    f = stats.get("FOR", 0)
    a = stats.get("AGAINST", 0)
    ab = stats.get("ABSTENTION", 0)
    denom = f + a + ab
    if denom == 0:
        return None
    return f / denom


def load_testset(raw_dir: Path = RAW_DIR) -> list[FileRecord]:
    """Load every committed vote JSON into a FileRecord. Network-free."""
    records: list[FileRecord] = []
    for path in sorted(raw_dir.glob("*.json")):
        if path.name == "index.json":
            continue
        detail = json.loads(path.read_text())
        by_group = (detail.get("stats") or {}).get("by_group") or []
        yes_rates: dict[str, float | None] = {g: None for g in CANONICAL_GROUPS}
        ballots: dict[str, tuple[int, int, int]] = {g: (0, 0, 0) for g in CANONICAL_GROUPS}
        tot_f = tot_a = tot_ab = 0
        for row in by_group:
            htv_code = row["group"]["code"]
            canon = GROUP_CODE_MAP.get(htv_code)
            if canon is None:
                raise KeyError(
                    f"Unmapped HTV group code {htv_code!r} in vote {detail.get('id')}; "
                    f"known: {sorted(GROUP_CODE_MAP)}"
                )
            s = row["stats"]
            f, a, ab = s.get("FOR", 0), s.get("AGAINST", 0), s.get("ABSTENTION", 0)
            ballots[canon] = (f, a, ab)
            yes_rates[canon] = _yes_rate(s)
            tot_f += f
            tot_a += a
            tot_ab += ab
        denom = tot_f + tot_a + tot_ab
        proc = detail.get("procedure") or {}
        records.append(
            FileRecord(
                id=str(detail.get("id")),
                reference=proc.get("reference") or detail.get("reference"),
                result=detail.get("result"),
                yes_rates=yes_rates,
                ballots=ballots,
                observed_share=(tot_f / denom) if denom else float("nan"),
            )
        )
    return records


# --- Predictors -----------------------------------------------------------------
# Each takes the TRAINING records for a fold (already excluding the target file)
# and returns a predicted yes-rate. None means "undefined for this cell" and the
# evaluation harness drops such cells from grading (METHODOLOGY §3, §4).


def baseline_a(train: list[FileRecord], group: str) -> float | None:
    """Baseline A: mean observed yes-rate of `group` over training files (§3)."""
    vals = [r.yes_rates[group] for r in train if r.yes_rates[group] is not None]
    if not vals:
        return None
    return sum(vals) / len(vals)


def baseline_c(group: str) -> float:
    """Baseline C: constant group-line, file-independent (§3, Decision 2)."""
    return C_HIGH if group in MAJORITY_SET else C_LOW


def const_095(group: str) -> float:
    """Reference: predict 0.95 for every group on every file (§3)."""
    return C_HIGH


def const_mean(train: list[FileRecord]) -> float | None:
    """Reference: global pooled mean over all defined cells in `train` (§3)."""
    vals = [
        v
        for r in train
        for v in r.yes_rates.values()
        if v is not None
    ]
    if not vals:
        return None
    return sum(vals) / len(vals)


def _self_check() -> None:
    recs = load_testset()
    print(f"loaded {len(recs)} files from {RAW_DIR}")
    defined = sum(1 for r in recs for v in r.yes_rates.values() if v is not None)
    cells = len(recs) * len(CANONICAL_GROUPS)
    print(f"groups: {CANONICAL_GROUPS}")
    print(f"defined (group,file) cells: {defined} / {cells}")
    print(f"Baseline C assignment (Decision 2):")
    for g in CANONICAL_GROUPS:
        print(f"  {g:7s} -> {baseline_c(g):.2f}")
    print(f"seat weights sum = {sum(SEAT_WEIGHTS.values()):.6f}")
    print("observed EP yes-share per file (recomputed from raw):")
    for r in sorted(recs, key=lambda r: r.observed_share):
        print(f"  {r.observed_share:.3f}  {r.result:8s}  {r.reference}")


if __name__ == "__main__":
    _self_check()
