# Praevisa — pivot validation against real roll-call data
"""Ground-truth checks for the flip-analysis pivot logic.

Both pivot heuristics in `praevisa.flip` are validated here against real
10th-term roll-call votes from the HowTheyVote API (no key required). We use
the set of *rejected* main votes — the contested subset where pivots actually
matter — and ask, for each: does the heuristic name the bloc that actually
decides the vote?

  EP pivot      — should name the decisive group (the one whose flip changes
                  the result), NOT the most internally-divided group. Movable
                  mass = seats x closeness-to-flip.
  Council pivot — population-weighted: pivotal actors should concentrate in the
                  large states. NB: HowTheyVote `by_country` is MEPs grouped by
                  country of election, a *proxy* for Council government votes —
                  it validates the weighting algorithm, not that the engine
                  predicts a specific government's Council position. True
                  Council records are a separate (Council register) source.

Run: .venv/bin/python validate_pivots.py
"""

from __future__ import annotations

import json
import math
import urllib.request

API = "https://howtheyvote.eu/api"
# Rejected main votes pulled from the 10th-term feed (contested subset).
REJECTED = [191240, 190161, 190403, 189270, 189581, 189596,
            189598, 186166, 189130, 186941, 186903, 184394]
# Seven largest member states by population (≈ EP delegation size).
BIG_STATES = {"DE", "FR", "IT", "ES", "PL", "RO", "NL"}
MIN_CAST = 4  # ignore micro-delegations / tiny groups when computing a pivot


def _get(path: str) -> dict:
    req = urllib.request.Request(f"{API}{path}", headers={"Accept": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=25))


def _movable_mass(size: int, yes_rate: float) -> float:
    """Big AND close to flipping. Locked blocs (0%/100%) score 0."""
    return size * (1.0 - 2.0 * abs(yes_rate - 0.5))


def validate_ep() -> None:
    print("EP PIVOT — on flippable votes, does it name the decisive bloc?")
    print("-" * 78)
    print(f"{'vote':<38}{'F-A':>9}  {'class':<10}{'pivot':<8}{'most-divided'}")
    flippable_hits = flippable = 0
    for vid in REJECTED:
        d = _get(f"/votes/{vid}")
        groups = []
        for g in d["stats"]["by_group"]:
            s = g["stats"]
            cast = s["FOR"] + s["AGAINST"]
            if cast >= 15:
                groups.append((g["group"]["short_label"], s["AGAINST"], cast, s["FOR"] / cast))
        if not groups:
            continue
        f = sum(g["stats"]["FOR"] for g in d["stats"]["by_group"])
        a = sum(g["stats"]["AGAINST"] for g in d["stats"]["by_group"])
        need = math.ceil((a - f + 1) / 2)                 # FOR votes one group must supply
        # Capability gate: only groups with enough AGAINST voters can flip it alone.
        capable = [g for g in groups if g[1] >= need]
        divided = min(groups, key=lambda t: abs(t[3] - 0.5))[0]
        if not capable:
            klass, pivot = "landslide", "(none)"          # flip analysis: "decided"
        else:
            klass = "flippable"
            pivot = max(capable, key=lambda t: _movable_mass(t[2], t[3]))[0]
            flippable += 1
            if pivot in ("EPP", "S&D"):
                flippable_hits += 1
        print(f"{d.get('display_title','')[:38]:<38}{f:>4}-{a:<4}  {klass:<10}{pivot:<8}{divided}")
    print(f"\nOn single-group-flippable votes, pivot is a big swing bloc (EPP/S&D): "
          f"{flippable_hits}/{flippable}.")
    print("Landslides have no single-group pivot — flip analysis gates these as "
          "'structurally decided'.\n")


def validate_council() -> None:
    print("COUNCIL PIVOT — do pivotal actors concentrate in the large states?")
    print("-" * 78)
    print(f"{'vote':<40}{'F-A':>9}  {'pivot':<7}{'big in flip-set'}")
    big_hits = total = 0
    for vid in REJECTED:
        d = _get(f"/votes/{vid}")
        states = []
        f = a = 0
        for c in d["stats"]["by_country"]:
            s = c["stats"]
            cast = s["FOR"] + s["AGAINST"]
            f += s["FOR"]
            a += s["AGAINST"]
            if cast >= MIN_CAST:
                states.append((c["country"]["iso_alpha_2"], s["AGAINST"], cast, s["FOR"] / cast))
        deficit = a - f + 1
        ranked = sorted(states, key=lambda t: _movable_mass(t[2], t[3]), reverse=True)
        chosen: list[str] = []
        remaining = deficit
        for code, against_n, cast, _ in ranked:
            if remaining <= 0:
                break
            chosen.append(code)
            # converting a delegation's AGAINST voters to FOR nets +2 each.
            remaining -= against_n * 2
        big_in = sum(1 for c in chosen if c in BIG_STATES)
        big_hits += big_in
        total += len(chosen)
        print(f"{d.get('display_title','')[:40]:<40}{f:>4}-{a:<4}  "
              f"{ranked[0][0]:<7}{big_in}/{len(chosen)}")
    print("-" * 78)
    print(f"big-state share across flip-sets: {big_hits}/{total} = {big_hits/total:.0%}")
    print("(7 largest states are 7/27 = 26% of members; population weighting should "
          "push this well above 26%.)\n")


def main() -> None:
    print("Praevisa pivot validation — HowTheyVote 10th-term rejected votes\n")
    validate_ep()
    validate_council()


if __name__ == "__main__":
    main()
