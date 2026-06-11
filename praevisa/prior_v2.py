"""Prior v2 — type-conditional base rates for the prior rail (the fix for "68%").

The v1 prior rail stamped every no-signal item with the same number: the §9.6
baseline_A seat split (68%), a mean over 18 COD files including 4 rejections. That one
number did two jobs badly — it read as a probability when it is a seat split, and it
ignored that vote TYPES behave differently (Term-10 mains: INI 98% adopted at ~76%
share; consent/NLE ~100% at ~90%; DEA objection motions 0% adopted).

v2 separates the jobs, still fully mechanical, conditioned only on procedure type:

  p_adopt              — P(ADOPTED) for the item's HTV procedure type, Jeffreys-
                         smoothed ((k + 1/2) / (n + 1)) so an unbroken record never
                         prints a fake 100%.
  share_adopted        — mean observed yes-share (for/(for+against)) over the type's
                         ADOPTED mains: the expected split conditional on passing.
  share_rejected       — same conditional on failing (None if the type has none).

Source: the cached HowTheyVote bulk export, Term 10 mains (timestamp >= 2024-07-16)
with a definite result, Rule-71 mandate votes excluded — the same filter every other
module uses. The build is frozen into results/prior_v2.json (source release tag
recorded); ledger prediction reads ONLY the committed artifact, so cutting a ledger
stays network-free and the prior in force is the one in git, not a moving target.

Types with n < MIN_N are not tabulated; items mapping to them get no v2 prior and the
ledger says so. Second-reading threshold calls (cod2) are out of scope by design: the
prediction there is a Rule-68 threshold test, not an adopt/reject call, and Term-10
has no usable base of second-reading mains to condition on.

Grading hook: a ledger item that carries `p_adopt` is Brier-scored at grading time
((p_adopt - observed)^2, observed = 1 if ADOPTED else 0) — probabilities join the
public track record instead of hiding behind hit/miss. Items without the field (the
pre-v2 2026-06-15 ledger) grade exactly as before; the registration is append-only.

Run: uv run python -m praevisa.prior_v2        # rebuild + freeze results/prior_v2.json
"""

from __future__ import annotations

import csv
import gzip
import json
from pathlib import Path

from . import resolve_plenary

ROOT = Path(__file__).resolve().parent.parent
RESULTS_PATH = ROOT / "results" / "prior_v2.json"

TERM10_START = "2024-07-16"
MIN_N = 5

# Ledger manifest `type` -> HTV `procedure_type`. cod2 is deliberately absent (Rule-68
# threshold call, not an adopt/reject prediction).
LEDGER_TYPE_MAP = {
    "cod1": "COD",
    "ini": "INI",
    "cns": "CNS",
    "consent": "NLE",
    "bud": "BUD",
    "resolution": "RSP",
    "recommendation": "INI",
}


def jeffreys(k: int, n: int) -> float:
    """Jeffreys-smoothed proportion: (k + 1/2) / (n + 1). Never 0, never 1."""
    return (k + 0.5) / (n + 1)


def build() -> dict:
    """Tabulate Term-10 main-vote base rates by procedure type from the bulk export."""
    resolve_plenary.ensure_votes_csv()
    tag = resolve_plenary.TAG_FILE.read_text().strip()
    shares: dict[str, dict[str, list[float]]] = {}
    with gzip.open(resolve_plenary.VOTES_CSV, "rt") as fh:
        for row in csv.DictReader(fh):
            if row.get("is_main") != "True":
                continue
            if (row.get("timestamp") or "") < TERM10_START:
                continue
            if row.get("result") not in resolve_plenary.VALID_RESULTS:
                continue
            if resolve_plenary.classify_plenary(row) == "mandate":
                continue
            f = int(row.get("count_for") or 0)
            a = int(row.get("count_against") or 0)
            if f + a == 0:
                continue
            t = row.get("procedure_type")
            if not t:
                continue
            shares.setdefault(t, {"ADOPTED": [], "REJECTED": []})
            shares[t][row["result"]].append(f / (f + a))
    types = {}
    for t, by_res in sorted(shares.items()):
        ad, rj = by_res["ADOPTED"], by_res["REJECTED"]
        n = len(ad) + len(rj)
        if n < MIN_N:
            continue
        types[t] = {
            "n": n,
            "n_adopted": len(ad),
            "p_adopt": round(jeffreys(len(ad), n), 4),
            "share_adopted": round(sum(ad) / len(ad), 4) if ad else None,
            "share_rejected": round(sum(rj) / len(rj), 4) if rj else None,
        }
    return {
        "protocol": ("Term-10 main votes (>= " + TERM10_START + "), definite result, "
                     "Rule-71 mandate votes excluded; p_adopt Jeffreys-smoothed "
                     "(k+0.5)/(n+1); shares = for/(for+against)"),
        "source_release": tag,
        "min_n": MIN_N,
        "ledger_type_map": LEDGER_TYPE_MAP,
        "types": types,
    }


def load() -> dict:
    """The committed artifact — the prior in force. Network-free."""
    return json.loads(RESULTS_PATH.read_text())


def for_ledger_type(ledger_type: str, artifact: dict | None = None) -> dict | None:
    """Type prior for a ledger manifest type, or None (unmapped / thin type)."""
    art = artifact if artifact is not None else load()
    htv = art["ledger_type_map"].get(ledger_type)
    tp = art["types"].get(htv) if htv else None
    if tp is None:
        return None
    return {"htv_type": htv, **tp}


def main() -> int:
    art = build()
    RESULTS_PATH.write_text(json.dumps(art, indent=1, ensure_ascii=False) + "\n")
    print(f"PRIOR v2 — type-conditional base rates (HTV export {art['source_release']})\n")
    print(f"{'type':<8}{'n':>5}{'adopted':>9}{'p_adopt':>9}{'share|A':>9}{'share|R':>9}")
    print("-" * 49)
    for t, s in sorted(art["types"].items(), key=lambda kv: -kv[1]["n"]):
        sa = f"{s['share_adopted']:.3f}" if s["share_adopted"] is not None else "—"
        sr = f"{s['share_rejected']:.3f}" if s["share_rejected"] is not None else "—"
        print(f"{t:<8}{s['n']:>5}{s['n_adopted'] / s['n']:>8.0%}{s['p_adopt']:>9.3f}"
              f"{sa:>9}{sr:>9}")
    print(f"\nwrote {RESULTS_PATH.relative_to(ROOT)} — commit it; ledgers read the "
          "artifact, never the live export.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
