"""Grading-day leak spot-check for the forward ledger.

Prints every plenary roll-call row in the part-session window with the TYPE that
``resolve_plenary.classify_plenary`` assigns it (mandate / provisional / text), so you
can confirm BY EYE — before grading — that no Rule-71 "decision to enter
interinstitutional negotiations" (mandate) vote is typed ``text`` and about to be graded
as a substantive outcome. That mis-typing is the leak class withdrawn on 2026-06-10
(see ``resolve_plenary.py``); the grading paths now exclude ``mandate`` rows, but the
exclusion is only as good as the substring markers in ``classify_plenary``.

This tool therefore runs a SECOND-OPINION scan on top of the listing, over BOTH gradeable
types (``text`` and ``provisional`` — only ``mandate`` is excluded from outcome grading).
A ``text`` row should carry no procedural token at all, so it is scanned against the full
marker list. A ``provisional`` row is SUPPOSED to carry the provisional-agreement markers,
so those are dropped from its scan and it is flagged only when it ALSO carries
mandate/negotiation tokens — a Rule-71 mandate hiding as a deal. Any hit is flagged LOUDLY.
That is precisely the unknown-phrasing / other-language / typo failure mode the exact-
substring matcher cannot catch on its own.
False positives here are fine and expected (a substantive "negotiating directives" vote
will trip it) — the output is a CHECK-BY-HAND list, not an auto-exclude. The cost of a
false positive is ten seconds of reading; the cost of a false negative is a re-leak.

Network-dependent: needs the HowTheyVote bulk export (``votes.csv.gz``) at grade time.
Run on/after the grading window, once HowTheyVote has published the session. Before then
it correctly reports "no rows yet" and exits 0.

    uv run python -m praevisa.leak_spotcheck
    uv run python -m praevisa.leak_spotcheck --first 2026-06-15 --last 2026-06-18

Exit code is non-zero (2) when the second-opinion scan flags anything, so a human (or a
pre-grade CI step) notices rather than grading blind.
"""

from __future__ import annotations

import argparse
import csv
import gzip

from . import resolve_plenary

# Keep in sync with plenary_forward.SESSION_FIRST_DAY / SESSION_LAST_DAY. Hardcoded
# (not imported) so this stays runnable with only the stdlib-only resolve_plenary even
# in a partial environment; override on the command line for other sessions.
DEFAULT_FIRST = "2026-06-15"
DEFAULT_LAST = "2026-06-18"

# Tokens that, inside a row CLASSIFY_PLENARY typed `text`, suggest a procedural / mandate
# / post-trilogue-agreement vote the exact markers may have missed — across languages and
# spellings. Substring match, casefolded. Deliberately broad: over-flagging is safe here.
_SUSPICIOUS = (
    "interinstitution",   # interinstitutional / interinstitutionnelle / interinstitutioneller
    "negotiat",           # negotiation(s)  [EN]
    "négoci", "negoci",   # négociations    [FR] / negociaciones [ES]
    "verhandlung",        # Verhandlungen   [DE]
    "mandat",             # mandate / mandat / Mandat
    "trilog",             # trilogue / Trilog
    "provisional", "provisoire", "provvisori", "vorläufig",  # provisional agreement EN/FR/IT/DE
    "rule 71", "article 71",
    "enter into negotiations", "aufnahme",  # DE "Aufnahme von Verhandlungen"
)

# The provisional-agreement markers are the LEGITIMATE reason a row is typed `provisional`,
# so they are dropped when scanning that bucket (else every provisional row self-trips). What
# remains — the mandate / negotiation / Rule-71 tokens — is what a mandate hiding as a deal
# would carry. `text` rows are scanned against the full _SUSPICIOUS list (they should carry
# neither class of token).
_PROVISIONAL_TOKENS = ("provisional", "provisoire", "provvisori", "vorläufig")
_MANDATE_TOKENS = tuple(t for t in _SUSPICIOUS if t not in _PROVISIONAL_TOKENS)


def suspicious_tokens(row: dict, tokens: tuple[str, ...] = _SUSPICIOUS) -> list[str]:
    """Off-marker procedural tokens (from `tokens`) present in a row's description/titles."""
    blob = " ".join((
        row.get("description") or "",
        row.get("display_title") or "",
        row.get("procedure_title") or "",
    )).casefold()
    return sorted({w for w in tokens if w in blob})


def _session_rows(first: str, last: str) -> list[dict]:
    """Every roll-call row in [first, last], straight from the bulk CSV (no filtering)."""
    resolve_plenary.ensure_votes_csv()
    out = []
    with gzip.open(resolve_plenary.VOTES_CSV, "rt") as fh:
        for row in csv.DictReader(fh):
            day = (row.get("timestamp") or "")[:10]
            if first <= day <= last:
                out.append(row)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--first", default=DEFAULT_FIRST, help="session first day (YYYY-MM-DD)")
    ap.add_argument("--last", default=DEFAULT_LAST, help="session last day (YYYY-MM-DD)")
    args = ap.parse_args()

    rows = _session_rows(args.first, args.last)
    if not rows:
        print(f"No roll-call rows in {args.first}..{args.last} yet — HowTheyVote may not "
              f"have published the session. Re-run after the part-session closes.")
        return 0

    by_type: dict[str, list[dict]] = {"mandate": [], "provisional": [], "text": []}
    for r in rows:
        by_type[resolve_plenary.classify_plenary(r)].append(r)

    print(f"Session {args.first}..{args.last}: {len(rows)} roll-call rows")
    print(f"  classify_plenary →  text {len(by_type['text'])}   "
          f"provisional {len(by_type['provisional'])}   mandate {len(by_type['mandate'])}")
    print()

    for typ in ("mandate", "provisional", "text"):
        if not by_type[typ]:
            continue
        tag = "  [EXCLUDED from outcome grading]" if typ == "mandate" else ""
        print(f"── {typ.upper()} ({len(by_type[typ])}){tag}")
        for r in sorted(by_type[typ], key=lambda r: r.get("timestamp", "")):
            main_flag = "main" if r.get("is_main") == "True" else "    "
            desc = (r.get("description") or r.get("display_title") or "").replace("\n", " ")
            print(f"   {str(r.get('id')):>7}  {(r.get('timestamp') or '')[:10]}  "
                  f"{main_flag}  {(r.get('result') or ''):8}  {desc[:88]}")
        print()

    # Second opinion over BOTH gradeable types. `text` rows should carry no procedural
    # token, so scan them against the full list; `provisional` rows are flagged only on
    # mandate/negotiation tokens (their own provisional markers are expected, not suspect).
    flagged: list[tuple[str, dict, list[str]]] = []
    for r in by_type["text"]:
        if hits := suspicious_tokens(r):
            flagged.append(("text", r, hits))
    for r in by_type["provisional"]:
        if hits := suspicious_tokens(r, _MANDATE_TOKENS):
            flagged.append(("provisional", r, hits))
    if flagged:
        print("!!! SECOND-OPINION FLAG — these rows are typed `text`/`provisional` (so they")
        print("!!! WILL be graded as substantive outcomes) but carry procedural tokens that")
        print("!!! suggest a mis-typed Rule-71 mandate. CHECK EACH BY HAND before grading:")
        print()
        for typ, r, hits in flagged:
            print(f"   [{typ:11}] vote {r.get('id')} ({(r.get('timestamp') or '')[:10]}): {hits}")
            print(f"        {(r.get('description') or r.get('display_title') or '')[:150]}")
        print()
        print("   If any is a genuine Rule-71 mandate or post-trilogue agreement vote, either")
        print("   add a vote_id override in predictions/plenary_2026-06-15_results.json, or")
        print("   extend resolve_plenary._MANDATE_MARKERS / _PROVISIONAL_MARKERS to cover the")
        print("   phrasing, then re-run grading. Do NOT grade until each flag is resolved.")
        return 2

    print("Second-opinion scan: no `text` row carries un-matched procedural tokens. Clean.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
