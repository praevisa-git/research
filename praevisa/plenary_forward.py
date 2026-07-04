"""Forward ledger for a plenary part-session — the public auditability track record.

Predicts EVERY votable item on the published draft agenda (OJ), not only files with a
committee signal. The artifact is a timestamped, git-committed, gradeable prediction set
published BEFORE the votes; routine near-certain adopts are included deliberately — the
track record is the product, divergence on them is irrelevant.

Two rails, stamped per item:
  committee — a per-group committee roll-call exists in the corpus → the validated
              Stage-A rails (`ep_flip.forecast_for`, calibrated shrinkage alpha).
  prior     — no committee signal → baseline_A per-group plenary prior (party
              arithmetic), same seat math and flip lever.

Prior v2 (ledgers cut after 2026-06-11): each non-***II item additionally carries
  p_adopt                    — P(ADOPTED). Prior rail: the Jeffreys-smoothed Term-10
                               base rate for the item's procedure type (prior_v2.py,
                               committed artifact). Committee rail: 1 − the flip rate
                               under resampled historical committee→plenary residuals
                               (stress_set machinery), i.e. the same number the stress
                               battery grades the rail by.
  expected_share_if_adopted  — prior rail only: the type's mean observed yes-share
                               conditional on passing. Fixes the v1 confusion where one
                               topic-blind 68% read both as a confidence and as a split.
Items with p_adopt are Brier-scored at grading ((p_adopt − observed)², observed = 1 if
ADOPTED); items without it (the 2026-06-15 ledger) grade exactly as pre-registered.
A committee OPINION roll-call (not the lead committee) is used where it is all we have,
stamped `opinion(<committee>)` — weaker than a lead signal, disclosed as such.

Second reading (***II) is special-cased: plenary can only amend or reject the Council
position with an absolute majority of members (361). The prediction is the threshold
test, not a simple yes/no tally.

Grading is PRE-REGISTERED: the `grade` subcommand below is written and committed before
the session, so post-session scoring is mechanical — pairing rule, metrics, and subsets
are all fixed here, in code, ahead of the votes. Grading is APPEND-ONLY: it adds a
`graded` block per item and a top-level `scorecard`; it never touches a prediction.

Grading rules (the code is the registration; this is the summary):
  pairing  — official roll-call rows from the HowTheyVote bulk export, restricted to
             main votes dated within the session with a definite result and excluding
             Rule-71 mandate votes. An item with a procedure reference pairs by
             reference; otherwise by deterministic title-token containment (>= 0.6 of
             the ledger title's tokens found in the vote row's titles; ties -> latest).
             Items decided without a roll call are graded outcome-only from an explicit
             results file (`plenary_<session>_results.json`) transcribed from the
             official minutes — facts only, never predictions.
  metrics  — outcome hit/miss; |predicted - observed| yes-share error with the observed
             share computed for/(for+against); per-group MSE (Decision-1 yes-rates, via
             baselines._yes_rate) on committee-rail items, with the prior as comparator.
  subsets  — always-ADOPTED vs prior rail vs committee rail, contested broken out;
             never pooled into one headline number.
  ***II    — the Rule-68 threshold call is graded stands vs amended/rejected: the
             Council position is overturned only if an amendment or rejection proposal
             gathers >= 361 FOR among the session's roll calls; otherwise it stands
             (the act is deemed adopted, often with no main roll call at all).
  guard    — grading refuses to run before GRADE_OPENS (the day after the session
             closes); a vote dated on/before the ledger's generation date is not
             gradeable as prospective and is flagged, not scored. If HowTheyVote has
             not published the session yet, items are reported pending — never failed,
             never guessed.

Run:
    uv run python -m praevisa.plenary_forward          # predict: writes the ledger (pre-session only)
    uv run python -m praevisa.plenary_forward grade    # after 2026-07-10: score it in place
    uv run python -m praevisa.plenary_forward status   # pending vs graded summary
"""

from __future__ import annotations

import csv
import gzip
import json
import random
import subprocess
import sys
import unicodedata
from datetime import date
from pathlib import Path

from . import (baselines, corpus_health, ep_flip, prior_v2, resolve_plenary,
               stage0_feasibility as s0)
from .data import EP_GROUPS
from .flip import _ep_pivot_path

ROOT = Path(__file__).resolve().parent.parent
GROUPS = list(baselines.CANONICAL_GROUPS)
SEATS = {g.code: g.seats for g in EP_GROUPS}
TOTAL_MEMBERS = 720
ABS_MAJORITY = TOTAL_MEMBERS // 2 + 1  # Rule 68: amend/reject Council position at 2nd reading

SESSION = "2026-07-06"
AGENDA_SOURCE = ("https://data.europarl.europa.eu/distribution/doc/"
                 "OJ-10-2026-07-06-REV_en.pdf")  # FINAL DRAFT AGENDA 790.507/PDOJ
AGENDA_LAST_UPDATED = "2026-07-03"

# Every votable item on the FINAL DRAFT AGENDA (PDOJ 790.507, rev. 2026-07-03) for
# 6-9 July 2026 (Strasbourg). `corpus`: (committee_corpus file suffix, title substring,
# subject prefix) locating a candidate committee roll-call record; the H1 eligibility
# gate decides whether it may actually feed the signal rail.
MANIFEST = [
    # --- Tuesday 7 July, votes 12:00 ---
    dict(day="2026-07-07", a10=None, type="cod2", committee="LIBE",
         rapporteur=None, procedure="2025/0429(COD)",
         title="Amending Regulation (EU) 2021/1232 as regards the extension of its "
               "period of application",
         corpus=("LIBE", "2021/1232", None),
         note="Rule 170 urgency requested; recommendation for second reading. LIBE "
              "rejected the draft report 28-38-3 (tally disclosed; record is "
              "first-reading-stage, ineligible for a ***II floor object)."),
    dict(day="2026-07-07", a10="B10-0338/2026", type="resolution", committee=None,
         rapporteur=None, procedure="2026/2792(RSP)",
         title="Decision requesting the Authority for European Political Parties and "
               "European Political Foundations to verify whether Europe of Sovereign "
               "Nations Party complies with the conditions laid down in Article 3(1), "
               "points (d) and (e), of Regulation (EU, Euratom) 2025/2445",
         note="Rule 241 decision."),
    dict(day="2026-07-07", a10="B10-0343/2026", type="rso", committee=None,
         rapporteur=None, procedure="2026/2807(RSO)",
         title="Amending the decision of 18 December 2024 on setting up a special "
               "committee on the Housing Crisis in the European Union, extending its "
               "term of office and adjusting its responsibilities"),
    dict(day="2026-07-07", a10="A10-0190/2026", type="imm", committee="JURI",
         rapporteur="Mario Furore", procedure="2026/2010(IMM)",
         title="Request for the waiver of the immunity of Klára Dobrev"),
    dict(day="2026-07-07", a10="A10-0191/2026", type="cod3", committee="TRAN",
         rapporteur="Andrey Novakov", procedure="2013/0072(COD)",
         title="Air passenger rights",
         note="***III conciliation joint text (Regulation 261/2004 revision); simple "
              "majority of votes cast."),
    dict(day="2026-07-07", a10="A8-0386/2018", type="cod1", committee="EMPL",
         rapporteur="Gabriele Bischoff", procedure="2016/0397(COD)",
         title="Coordination of social security systems",
         note="Legacy 8th-term report (A8) returning to the vote; no usable "
              "committee record in the rolling-window corpus."),
    dict(day="2026-07-07", a10=None, type="cod1", committee=None,
         rapporteur=None, procedure="2026/0150(COD)",
         title="Temporary support and payment of advances regarding the increased "
               "fertiliser prices due to the Middle East crisis",
         note="No report or committee listed on the PDOJ (urgent-style adoption)."),
    dict(day="2026-07-07", a10="A10-0174/2026", type="cod1", committee="TRAN",
         rapporteur="Elissavet Vozemberg-Vrionidi", procedure="2025/0407(COD)",
         title="International road passenger transport services by coach and bus in "
               "the border regions: cabotage operations between Austria and "
               "Switzerland"),
    dict(day="2026-07-07", a10="A10-0180/2026", type="bud", committee="BUDG",
         rapporteur="Andrzej Halicki", procedure="2026/0090(BUD)",
         title="Draft amending budget no 1/2026: entering the surplus of the "
               "financial year 2025"),
    dict(day="2026-07-07", a10="A10-0179/2026", type="bud", committee="BUDG",
         rapporteur="Lucia Yar", procedure="2026/0126(BUD)",
         title="Mobilisation of the European Globalisation Adjustment Fund: "
               "Application EGF/2026/000 TA 2026 - Technical assistance at the "
               "initiative of the Commission"),
    dict(day="2026-07-07", a10="A10-0178/2026", type="bud", committee="BUDG",
         rapporteur="Bogdan Rzońca", procedure="2026/0120(BUD)",
         title="Mobilisation of the European Union Solidarity Fund: assistance to "
               "Romania, Cyprus and Spain with regard to natural disasters in 2025"),
    dict(day="2026-07-07", a10="A10-0170/2026", type="ini", committee="BUDG",
         rapporteur="Joachim Streit", procedure="2025/2213(INI)",
         title="Financial activities of the European Investment Bank Group - annual "
               "report 2025"),
    dict(day="2026-07-07", a10="A10-0189/2026", type="recommendation", committee="AFET",
         rapporteur="Adam Bielan", procedure="2025/2169(INI)",
         title="Recommendation on the changing geopolitical situation in East Asia "
               "and the need for closer cooperation with like-minded partners in the "
               "region",
         note="Rule 121 recommendation to Council/Commission/VP-HR."),
    dict(day="2026-07-07", a10="A10-0171/2026", type="ini", committee="ECON",
         rapporteur="Stéphanie Yon-Courtin", procedure="2025/2134(INI)",
         title="Competition policy - annual report 2025",
         note="ECON corpus holds a record for 2025/2134(INI) but its title/rapporteur "
              "fields contradict the PDOJ (scrape misalignment) - attribution "
              "untrusted, not wired to the signal rail."),
    dict(day="2026-07-07", a10="A10-0169/2026", type="ini", committee="ECON",
         rapporteur="Matthias Ecke", procedure="2024/2117(INI)",
         title="A coherent tax framework for the EU's financial sector",
         note="ECON corpus record for 2024/2117(INI) metadata-inconsistent (see "
              "competition policy note) - not wired."),
    dict(day="2026-07-07", a10="A10-0173/2026", type="ini", committee="CULT",
         rapporteur="Marcos Ros Sempere", procedure="2025/2181(INI)",
         title="A new strategy for media literacy and digital learning",
         corpus=("CULT", "media literacy", "FINAL VOTE")),
    dict(day="2026-07-07", a10="A10-0187/2026", type="ini", committee="DEVE/ENVI",
         rapporteur="Lukas Mandl, Pierfrancesco Maran", procedure="2025/2248(INI)",
         title="Implementation and delivery of the Sustainable Development Goals in "
               "view of the 2026 High-Level Political Forum",
         corpus=("DEVE", "Sustainable Development Goals", "FINAL VOTE")),
    dict(day="2026-07-07", a10="A10-0186/2026", type="ini", committee="ECON",
         rapporteur="Johan Van Overtveldt", procedure="2025/2208(INI)",
         title="Digital assets - challenges for the competitiveness and integrity of "
               "the European Union's financial system",
         corpus=("ECON", "Digital assets", None)),
    # --- Wednesday 8 July, votes 12:00 ---
    dict(day="2026-07-08", a10="B10-0337/2026", type="objection-dea", committee="ENVI",
         rapporteur=None, procedure="2026/2680(DEA)",
         title="Objection pursuant to Rule 114(3): Trajectory to decrease the "
               "contribution of high indirect land-use change-risk biofuels, "
               "bioliquids and biomass fuels to renewable energy targets"),
    dict(day="2026-07-08", a10="B10-0344/2026", type="objection-rps", committee="ENVI",
         rapporteur=None, procedure="2026/2714(RPS)",
         title="Objection pursuant to Rule 115(2) and (3), and (4)(c): Lead in "
               "certain fishing tackle"),
    dict(day="2026-07-08", a10="B10-0342/2026", type="objection-dea", committee="ENVI",
         rapporteur=None, procedure="2026/2668(DEA)",
         title="Objection pursuant to Rule 114(3): bluetongue virus, epizootic "
               "haemorrhagic disease virus and a derogation for movements of "
               "registered equine animals"),
    dict(day="2026-07-08", a10="A10-0181/2026", type="consent", committee="AFET/INTA",
         rapporteur="Javi López, Borja Giménez Larraz", procedure="2025/0810(NLE)",
         title="EU-Mexico Political, Economic and Cooperation Strategic Partnership "
               "Agreement"),
    dict(day="2026-07-08", a10="A10-0182/2026", type="resolution", committee="AFET/INTA",
         rapporteur="Javi López, Borja Giménez Larraz", procedure="2025/0810R(NLE)",
         title="EU-Mexico Political, Economic and Cooperation Strategic Partnership "
               "Agreement (Interim report)",
         note="Accompanying interim report - distinct floor object from the consent "
              "(R-suffixed procedure)."),
    dict(day="2026-07-08", a10=None, type="consent", committee="INTA",
         rapporteur="Borja Giménez Larraz", procedure="2025/0271(NLE)",
         title="EU-Mexico Interim Agreement on Trade",
         note="PDOJ: expected date of Council adoption 06/07; no A10 number at "
              "ledger time."),
    dict(day="2026-07-08", a10="A10-0156/2026", type="consent", committee="JURI",
         rapporteur="Ilhan Kyuchyuk", procedure="2025/0244(NLE)",
         title="Protection of the environment through criminal law"),
    dict(day="2026-07-08", a10="A10-0177/2026", type="consent", committee="TRAN",
         rapporteur="Tomas Tobé", procedure="2023/0142(NLE)",
         title="EU-Morocco Euro-Mediterranean Aviation Agreement: accession to the "
               "EU of Croatia (Protocol)",
         note="TRAN corpus holds a title-matching record but its rapporteur field "
              "contradicts the PDOJ (scrape misalignment) - not wired."),
    dict(day="2026-07-08", a10="A10-0151/2026", type="consent", committee="ITRE",
         rapporteur="Paolo Borchia", procedure="2025/0387(NLE)",
         title="EU-Morocco Agreement for scientific and technological cooperation "
               "setting out the terms and conditions for the participation of "
               "Morocco in the Partnership for Research and Innovation in the "
               "Mediterranean Area (PRIMA): amendment and supplement",
         corpus=("ITRE", "PRIMA", None)),
    dict(day="2026-07-08", a10="A10-0172/2026", type="ini", committee="AFET",
         rapporteur="Michael Gahler", procedure="2025/2259(INI)",
         title="2025 Commission report on Ukraine"),
    dict(day="2026-07-08", a10="A10-0164/2026", type="ini", committee="AFET",
         rapporteur="Sven Mikser", procedure="2025/2258(INI)",
         title="2025 Commission report on Moldova"),
    dict(day="2026-07-08", a10="A10-0163/2026", type="ini", committee="AFET",
         rapporteur="Tonino Picula", procedure="2025/2255(INI)",
         title="2025 Commission report on Serbia"),
    dict(day="2026-07-08", a10="B10-0333/2026", type="resolution", committee=None,
         rapporteur=None, procedure="2026/2617(RSP)",
         title="The impact of the 1974 Turkish invasion on Cypriot women and girls, "
               "and the crimes committed by Turkish forces and consequences on "
               "gender equality"),
    dict(day="2026-07-08", a10="B10-0335/2026", type="objection-rsp", committee="ENVI",
         rapporteur=None, procedure="2026/2745(RSP)",
         title="Objection pursuant to Rule 115(2) and (3): Genetically modified "
               "maize NK603 × T25"),
    dict(day="2026-07-08", a10="B10-0244/2025", type="objection-rsp", committee="ENVI",
         rapporteur=None, procedure="2025/2647(RSP)",
         title="Objection pursuant to Rule 115(2) and (3): Genetically modified "
               "soybean MON 87705",
         note="Motion tabled 2025 (B10-0244/2025); PDOJ marks a deferred vote."),
    dict(day="2026-07-08", a10="B10-0336/2026", type="objection-rsp", committee="ENVI",
         rapporteur=None, procedure="2026/2746(RSP)",
         title="Objection pursuant to Rule 115(2) and (3): Genetically modified "
               "maize DP202216 x NK603 x DAS-40278-9 and its sub-combinations "
               "DP202216 x NK603, DP202216 x DAS-40278-9"),
    # --- Thursday 9 July, votes 12:00 ---
    dict(day="2026-07-09", a10=None, type="resolution", committee=None,
         rapporteur=None, procedure="2026/2799(RSP)",
         title="The threat of war crimes, the escalating violations of international "
               "humanitarian law and the human rights situation in El-Obeid, Sudan",
         note="Rule 150 human-rights resolution."),
    dict(day="2026-07-09", a10=None, type="resolution", committee=None,
         rapporteur=None, procedure="2026/2800(RSP)",
         title="Ongoing persecution of Christians in Nigeria, notably the Kawel "
               "village massacre",
         note="Rule 150 human-rights resolution."),
    dict(day="2026-07-09", a10=None, type="resolution", committee=None,
         rapporteur=None, procedure="2026/2801(RSP)",
         title="The abduction, forced conversion and child marriage of Maria "
               "Shahbaz and the protection of girls in Pakistan",
         note="Rule 150 human-rights resolution."),
    dict(day="2026-07-09", a10="A10-0167/2026", type="ini", committee="ECON",
         rapporteur="Ľudovít Ódor", procedure="2025/2211(INI)",
         title="Feasibility of a 28th tax regime and its potential to support EU "
               "competitiveness",
         note="ECON corpus record for 2025/2211(INI) metadata-inconsistent (see "
              "competition policy note) - not wired."),
    dict(day="2026-07-09", a10="B10-0339/2026", type="resolution", committee="DEVE",
         rapporteur=None, procedure="2026/2734(RSP)",
         title="Joint communication on humanitarian aid (JOIN(2026)0025)",
         note="Motion following the DEVE oral question O-000026/2026. The DEVE "
              "corpus final-vote record on 'humanitarian aid' is the polycrisis INI "
              "report - a different floor object - and is not wired."),
]

NOT_PREDICTED = [
    "Narco-trafficking in Europe's waters (2026/2797(RSP)): PDOJ states the vote is "
    "held in September.",
    "Evaluation of the Common Fisheries Policy (2026/2778(RSP)): PDOJ states the "
    "vote is held in September.",
    "An updated regulatory framework for wool (2026/2804(RSP)): oral question only, "
    "no motion listed under this session's votes.",
    "The Rule-170 urgency-request vote itself on 2025/0429(COD): procedural, not a "
    "vote on a text.",
    "Statements/debates without a vote slot on this PDOJ (automotive sector, Irish "
    "Presidency, European Council conclusions, heatwaves, Gaza topical debate, "
    "Russian democratic forces, Ebola, bioeconomy, cybersecurity/AI action plan).",
    "Possible Rule 170 additions: the final agenda may add votes after this ledger "
    "is cut.",
]


def _prior_rail(item: dict) -> bool:
    """True for prior-rail items, including H1 demotions — their `signal` reads
    `"prior (signal demoted: …)"`, and they are measured as prior, not committee."""
    return item["signal"].startswith("prior")


def _git_rev() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
                              capture_output=True, text=True, check=True).stdout.strip()
    except Exception:
        return "unknown"


def _find_record(suffix: str, title_sub: str, subject_prefix: str | None) -> dict | None:
    path = ROOT / f"committee_corpus_{suffix}.json"
    data = json.loads(path.read_text())
    for r in data["records"]:
        if title_sub.lower() not in (r.get("title") or "").lower():
            continue
        if subject_prefix and not (r.get("subject") or "").upper().startswith(subject_prefix):
            continue
        return r
    return None


def _seat_math(per_group: dict) -> dict:
    """Outcome, share, margin and pivot — the same convention as ep_flip.forecast_for."""
    gyr = {g: (per_group[g] if per_group.get(g) is not None else 0.0) for g in GROUPS}
    pivot = _ep_pivot_path(ep_flip._EPForecast(group_yes_rates=gyr))
    yes = sum(SEATS[g] * gyr[g] for g in GROUPS if g != "NI")
    no = sum(SEATS[g] * (1.0 - gyr[g]) for g in GROUPS if g != "NI")
    tot = yes + no
    return {
        "per_group": {g: (round(v, 4) if v is not None else None)
                      for g, v in per_group.items()},
        "ep_yes_share": round(yes / tot, 4) if tot else None,
        "outcome": "ADOPTED" if yes > no else "REJECTED",
        "margin_seats": round(yes - no, 1),
        "pivot_headline": pivot.headline if pivot else None,
        "pivot_realistic": bool(pivot.realistic) if pivot else None,
    }


def _second_reading(entry: dict) -> dict:
    """***II: the question is whether 361 members can be found AGAINST the Council
    position (to amend or reject it), not whether a simple majority says yes."""
    no_seats = sum(SEATS[g] * (1.0 - (entry["per_group"].get(g) or 0.0)) for g in GROUPS)
    passes = no_seats < ABS_MAJORITY
    entry["second_reading"] = {
        "threshold": ABS_MAJORITY,
        "predicted_seats_against": round(no_seats, 1),
        "prediction": ("Council position stands (act deemed adopted) — predicted "
                       "opposition falls short of the absolute majority needed to "
                       "amend or reject" if passes else
                       "Absolute majority against — amendment/rejection viable"),
    }
    entry["outcome"] = "ADOPTED" if passes else "CONTESTED-2ND-READING"
    return entry


def _committee_p_adopt(entry: dict, residuals: list[dict] | None, rng) -> float | None:
    """P(ADOPTED) for a committee-rail call: 1 − the flip rate under resampled
    historical committee→plenary residual vectors (the stress-set Monte Carlo).

    Clamped to [0.5/(R+1), 1 − 0.5/(R+1)] where R = residual-pool size: the MC only
    has R distinct historical shocks, so 0 flips in 10k draws is evidence at
    resolution R, not certainty — same never-0-never-1 discipline as the Jeffreys
    smoothing on the prior rail."""
    if not residuals:
        return None
    from . import stress_set
    flip = stress_set._mc_flip_rate(entry, residuals, rng)
    lo = 0.5 / (len(residuals) + 1)
    p_predicted_holds = min(1.0 - lo, max(lo, 1.0 - flip))
    return round(p_predicted_holds if entry["outcome"] == "ADOPTED"
                 else 1.0 - p_predicted_holds, 4)


def _assign_rails(manifest: list[dict], committee_index: dict) -> list[dict]:
    """Locate each manifest item's committee record and decide its rail.

    Pure and network-free (reads only the local corpora via `committee_index` /
    `_find_record`), so the June manifest can be replayed against it in tests.
    Applies, in order:
      H1  — `s0.signal_rail_eligible`: responsible committee + final vote on the
            floor text + procedure-reference match; failures demote with a reason;
      H3  — no vector reuse: one committee record may feed at most ONE floor
            object — the one whose procedure reference matches the record (H1c).
            With no reference to disambiguate, ALL sharing items demote: assigning
            the vector to an arbitrary object is exactly the June Liberia failure.

    Returns one dict per item: {rec, via, eligible, why}.
    """
    out = []
    for m in manifest:
        proc = m.get("procedure")
        rec, via = None, None
        if proc and proc in committee_index:
            rec, via = committee_index[proc], "cod"
        elif m.get("corpus"):
            rec, via = _find_record(*m["corpus"]), "corpus"
        eligible, why = (s0.signal_rail_eligible(rec, m.get("committee"), proc,
                                                 bool(m.get("opinion_signal")),
                                                 item_type=m.get("type"))
                         if rec is not None else (False, None))
        if eligible and corpus_health.polarity_tripwire(rec):
            # Task-5 tripwire: even a responsible-committee final vote is
            # polarity-unreliable when the rapporteur's own group voted it down.
            eligible = False
            why = "polarity tripwire: rapporteur's own group majority-against"
        out.append({"rec": rec, "via": via, "eligible": eligible, "why": why})
    shared: dict[tuple, list[int]] = {}
    for i, r in enumerate(out):
        if r["rec"] is not None:
            key = (r["rec"].get("source"), r["rec"].get("title"),
                   r["rec"].get("subject"))
            shared.setdefault(key, []).append(i)
    for idxs in shared.values():
        elig = [i for i in idxs if out[i]["eligible"]]
        if len(elig) <= 1:
            continue
        ref = s0.record_procedure_ref(out[elig[0]]["rec"])
        matches = [i for i in elig if ref and manifest[i].get("procedure") == ref]
        keep = matches[0] if len(matches) == 1 else None
        for i in elig:
            if i == keep:
                continue
            out[i]["eligible"] = False
            out[i]["why"] = (
                f"vector reuse: one committee record maps to {len(elig)} floor "
                "objects" + (", assigned to "
                             f"{manifest[keep].get('a10') or manifest[keep]['title'][:40]}"
                             if keep is not None else ", none reference-matched"))
    return out


def build() -> dict:
    committee_index = s0.load_committee_cod()
    prior = ep_flip._baseline_A()
    alpha = ep_flip.load_alpha()
    type_priors = prior_v2.load()
    try:  # needs the detail API once per calibration pair; degrade, don't die
        from . import stress_set
        com_residuals = stress_set._committee_residuals()
        rng = random.Random(stress_set.SEED)
    except Exception:
        com_residuals, rng = None, None
    consent_vec = prior_v2.consent_vector(type_priors)
    # Rail assignment is H1 + H3 (no vector reuse), pre-registered: ineligible
    # records DEMOTE the item to the prior rail with the reason disclosed in
    # `signal` and the tally kept — the information is never silently dropped.
    rails = _assign_rails(MANIFEST, committee_index)
    items = []
    for m, rail in zip(MANIFEST, rails):
        proc = m.get("procedure")
        entry = {
            "day": m["day"], "a10": m["a10"], "title": m["title"], "type": m["type"],
            "committee": m["committee"], "rapporteur": m["rapporteur"],
            "procedure": proc, "note": m.get("note"),
        }
        rec, via, eligible, why = (rail["rec"], rail["via"], rail["eligible"],
                                   rail["why"])
        if rec is not None and eligible:
            if via == "cod":
                f = ep_flip.forecast_for(proc, committee_index, prior)
                entry["signal"] = f"committee:{f['stage']}"
                entry["contested"] = f["contested"]
                entry["committee_tally"] = rec.get("tally")
                entry.update(_seat_math(f["per_group"]))
            else:
                com = ep_flip.predictor_group_rates(rec["votes"])
                pred = ep_flip.predict_plenary_per_group(com, prior, alpha)
                yes_overall, _ = s0._committee_yes(rec)
                entry["signal"] = f"committee-rcv({rec.get('committee')})"
                entry["contested"] = bool(yes_overall is not None
                                          and yes_overall < s0.CONTESTED_MAX_YES)
                entry["committee_tally"] = rec.get("tally")
                entry.update(_seat_math(pred))
        else:
            entry["signal"] = ("prior" if rec is None
                               else f"prior (signal demoted: {why})")
            entry["contested"] = None
            if rec is not None:
                entry["committee_tally"] = rec.get("tally")
            vec = dict(prior)
            if m["type"] == "consent" and consent_vec:
                # H3: consent-type per-group prior (Term-10 NLE mains) instead of
                # the topic-blind baseline_A vector.
                vec.update({g: v for g, v in consent_vec.items() if v is not None})
                entry["prior_basis"] = "consent_per_group(prior_v2)"
            entry.update(_seat_math(vec))
        if m["type"] == "cod2":
            _second_reading(entry)   # threshold call — no adopt/reject probability
        elif entry["signal"].startswith("prior"):
            tp = prior_v2.for_ledger_type(m["type"], type_priors)
            if tp:
                entry["p_adopt"] = tp["p_adopt"]
                entry["expected_share_if_adopted"] = tp["share_adopted"]
                entry["prior_v2_type"] = tp["htv_type"]
                if tp["p_adopt"] < 0.5:
                    # The type base rate IS the prior in force: when it says the
                    # type usually fails (Term-10 DEA objections: 0/12 adopted),
                    # the outcome call follows it rather than the topic-blind
                    # seat-math vector, so `outcome` and `p_adopt` cannot
                    # contradict each other on the prior rail.
                    entry["outcome"] = "REJECTED"
            else:
                entry["note"] = ((entry.get("note") or "") +
                                 " No type prior (unmapped or n<5 in Term 10).").strip()
        else:
            entry["p_adopt"] = _committee_p_adopt(entry, com_residuals, rng)
            if entry["p_adopt"] is None:
                entry["note"] = ((entry.get("note") or "") +
                                 " p_adopt unavailable (residual pool offline).").strip()
        items.append(entry)
    return {
        "session": SESSION,
        "session_dates": f"{SESSION_FIRST_DAY}/{SESSION_LAST_DAY}",
        "agenda_source": AGENDA_SOURCE, "agenda_last_updated": AGENDA_LAST_UPDATED,
        "generated_at": date.today().isoformat(), "engine_rev": _git_rev(),
        "alpha": alpha,
        "methodology": ("committee rail = Stage-A per-group committee->plenary map "
                        "(ep_flip, shrinkage alpha); prior rail = baseline_A per-group "
                        "plenary historical mean (party arithmetic). Seat-weighted, "
                        "abstention-ignored, NI excluded from the tally. ***II items "
                        "predicted against the Rule-68 absolute-majority threshold."),
        "not_predicted": NOT_PREDICTED,
        "n_items": len(items),
        "items": items,
    }


def render_md(ledger: dict) -> str:
    L = [f"# Plenary forward ledger — {ledger['session_dates']} (Strasbourg)", ""]
    L.append(f"Cut {ledger['generated_at']} at engine rev `{ledger['engine_rev']}` from the "
             f"draft agenda of {ledger['agenda_last_updated']} "
             f"([OJ]({ledger['agenda_source']})). alpha={ledger['alpha']}. "
             f"{ledger['n_items']} votable items predicted, every one BEFORE the vote.")
    L.append("")
    L.append(f"_{ledger['methodology']}_")
    L.append("")
    sc = ledger.get("scorecard")
    if sc and sc["n_graded"]:
        L.append("## Scorecard (graded post-session; rules pre-registered in "
                 "`praevisa/plenary_forward.py` before the votes)")
        L.append("")
        hits = sum(st["outcome_hits"] for rail, st in sc["by_rail"].items()
                   if rail != "always-ADOPTED")
        cc = sc["contested"]
        L.append(f"**{hits}/{sc['n_graded']} outcome calls correct** — "
                 f"contested subset {cc['outcome_hits']}/{cc['n']}, graded through "
                 f"{sc['graded_through']}.")
        L.append("")
        L.append("| Rail | Outcome hits | Share MAE |")
        L.append("|---|---|---|")
        for rail, st in sc["by_rail"].items():
            mae = f"{st['share_mae']:.3f}" if st.get("share_mae") is not None else "—"
            L.append(f"| {rail} | {st['outcome_hits']}/{st['n']} | {mae} |")
        c = sc["contested"]
        L.append(f"| contested subset | {c['outcome_hits']}/{c['n']} | "
                 + (f"{c['share_mae']:.3f}" if c.get("share_mae") is not None else "—")
                 + " |")
        L.append("")
        L.append("_Skill is claimed only where the committee rail beats both "
                 "always-ADOPTED and the prior rail._")
        if sc["n_pending"]:
            L.append("")
            L.append(f"Still pending ({sc['n_pending']}): "
                     + "; ".join(sc["pending"]))
        L.append("")
    day = None
    for it in ledger["items"]:
        if it["day"] != day:
            day = it["day"]
            L.append("")
            L.append(f"## Votes of {day}")
            L.append("")
            L.append("| Item | Type | Signal | Prediction | EP yes-share | Flip lever |")
            L.append("|---|---|---|---|---|---|")
        name = f"{it['a10'] or '—'} {it['title'][:70]}"
        outcome = it["outcome"]
        if it.get("p_adopt") is not None:
            outcome += f" (p {it['p_adopt']:.0%})"
        if it.get("second_reading"):
            sr = it["second_reading"]
            outcome += (f" (predicted {sr['predicted_seats_against']:.0f} seats against "
                        f"< {sr['threshold']} needed to amend/reject)")
        g = it.get("graded")
        if g:
            mark = "hit" if g["outcome_hit"] else "**MISS**"
            outcome += f" → {g['observed_result']} ({mark})"
            if g.get("observed_share") is not None:
                outcome += f", observed {g['observed_share']:.0%}"
        contested = " **CONTESTED**" if it.get("contested") else ""
        share = f"{it['ep_yes_share']:.0%}" if it.get("ep_yes_share") is not None else "—"
        pivot = it.get("pivot_headline") or "—"
        L.append(f"| {name} | {it['type']} | {it['signal']}{contested} | {outcome} | "
                 f"{share} | {pivot} |")
    L.append("")
    L.append("## Not predicted in this ledger")
    L.append("")
    for n in ledger["not_predicted"]:
        L.append(f"- {n}")
    L.append("")
    return "\n".join(L)


# ---------------------------------------------------------------------------
# Grading — pre-registered before the session; append-only.
# ---------------------------------------------------------------------------

SESSION_FIRST_DAY = "2026-07-06"
SESSION_LAST_DAY = "2026-07-09"
GRADE_OPENS = "2026-07-10"  # the day after the part-session closes
MATCH_THRESHOLD = 0.6
_STOP = {"the", "and", "for", "with", "their", "its", "from", "into", "between",
         "certain", "european", "union", "report", "2025", "2026", "commission",
         "council", "parliament", "regulation", "directive", "decision", "agreement"}


def _tokens(s: str) -> set[str]:
    """Deterministic title normalization: casefold, strip accents, alnum words >2
    chars, minus boilerplate stopwords."""
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c)).casefold()
    words = "".join(c if c.isalnum() else " " for c in s).split()
    return {w for w in words if len(w) > 2 and w not in _STOP}


def _session_rows(mains_only: bool = True) -> list[dict]:
    """Plenary roll-call rows of the session, read straight from the bulk CSV (not
    load_index) so rows without a procedure reference — resolutions, urgent-procedure
    items — are kept. With mains_only (the default, for outcome pairing): main votes
    with a definite result, Rule-71 mandate votes excluded. With mains_only=False
    (***II threshold grading): every row in the window, amendments included."""
    resolve_plenary.ensure_votes_csv()
    rows = []
    with gzip.open(resolve_plenary.VOTES_CSV, "rt") as fh:
        for row in csv.DictReader(fh):
            day = (row.get("timestamp") or "")[:10]
            if not (SESSION_FIRST_DAY <= day <= SESSION_LAST_DAY):
                continue
            if mains_only:
                if row.get("is_main") != "True":
                    continue
                if row.get("result") not in resolve_plenary.VALID_RESULTS:
                    continue
                if resolve_plenary.classify_plenary(row) == "mandate":
                    continue
            rows.append(row)
    return rows


def _match_row(item: dict, rows: list[dict], overrides: dict) -> tuple[dict | None, str]:
    """Pair a ledger item with its plenary vote row. Precedence is fixed: explicit
    vote_id override > procedure reference > A10 report reference > title-token
    containment. Identifiers first, fuzzy text last — and never exact-string title
    equality (the Stage-A contamination, see resolve_plenary.py history)."""
    ov = overrides.get(item.get("a10") or item["title"]) or {}
    if ov.get("vote_id"):
        for r in rows:
            if str(r["id"]) == str(ov["vote_id"]):
                return r, "override:vote_id"
        return None, "override vote_id not in session window"
    if item.get("procedure"):
        cands = [r for r in rows if r.get("procedure_reference") == item["procedure"]]
        if cands:
            cands.sort(key=lambda r: r["timestamp"], reverse=True)
            return cands[0], "procedure"
    if item.get("a10"):
        cands = [r for r in rows if r.get("reference") == item["a10"]]
        if cands:
            cands.sort(key=lambda r: r["timestamp"], reverse=True)
            return cands[0], "reference"
    want = _tokens(item["title"])
    if not want:
        return None, "no usable title tokens"
    best, best_score = None, 0.0
    for r in rows:
        have = _tokens(f"{r.get('display_title', '')} {r.get('procedure_title', '')}")
        score = len(want & have) / len(want)
        if score > best_score or (score == best_score and best is not None
                                  and r["timestamp"] > best["timestamp"]):
            best, best_score = r, score
    if best is not None and best_score >= MATCH_THRESHOLD:
        return best, f"title:{best_score:.2f}"
    return None, f"no title match >= {MATCH_THRESHOLD} (best {best_score:.2f})"


def _observed_share(row: dict) -> float | None:
    f, a = int(row.get("count_for") or 0), int(row.get("count_against") or 0)
    return f / (f + a) if (f + a) else None


def _brier(item: dict, observed_result: str) -> float | None:
    """(p_adopt − observed)², observed = 1 iff ADOPTED. None for pre-v2 items."""
    p = item.get("p_adopt")
    if p is None or observed_result not in ("ADOPTED", "REJECTED"):
        return None
    return round((p - (1.0 if observed_result == "ADOPTED" else 0.0)) ** 2, 4)


def _grade_second_reading(item: dict, all_rows: list[dict], ov: dict,
                          today: str) -> dict | None:
    """***II: grade the Rule-68 threshold call. The Council position is overturned only
    if an amendment or rejection proposal gathers >= 361 FOR; otherwise it stands and
    the act is deemed adopted — often with no main roll call at all, which is why this
    scans every related session row instead of pairing one main vote."""
    if ov.get("second_reading") in ("stands", "amended"):
        stands = ov["second_reading"] == "stands"
        hit = (item["outcome"] == "ADOPTED") == stands
        return {
            "paired_by": "minutes(results file)", "rcv": False,
            "observed_result": ("POSITION STANDS" if stands
                                else "POSITION AMENDED/REJECTED"),
            "second_reading": {"threshold": ABS_MAJORITY, "threshold_hit": hit},
            "outcome_hit": hit,
            "graded_at": today,
        }
    want = _tokens(item["title"])
    related = []
    for r in all_rows:
        if item.get("procedure") and r.get("procedure_reference") == item["procedure"]:
            related.append(r)
            continue
        have = _tokens(f"{r.get('display_title', '')} {r.get('procedure_title', '')}")
        if want and len(want & have) / len(want) >= MATCH_THRESHOLD:
            related.append(r)
    if not related:
        item["grade_note"] = ("pending — no session roll-call matches this ***II file; "
                              "if the position was deemed adopted without a roll call, "
                              "record {\"second_reading\": \"stands\"} for it in the "
                              "results file from the minutes")
        return None

    def blob(r):
        return f"{r.get('description', '')} {r.get('display_title', '')}".casefold()

    challenges = [r for r in related
                  if r.get("amendment_number") or r.get("is_main") != "True"
                  or "rejet" in blob(r) or "reject" in blob(r)]
    overturned = [r for r in challenges if r.get("result") == "ADOPTED"
                  and int(r.get("count_for") or 0) >= ABS_MAJORITY]
    stands = not overturned
    hit = (item["outcome"] == "ADOPTED") == stands
    return {
        "paired_by": f"procedure/title scan ({len(related)} related roll-calls)",
        "rcv": True,
        "observed_result": "POSITION STANDS" if stands else "POSITION AMENDED/REJECTED",
        "second_reading": {
            "threshold": ABS_MAJORITY,
            "n_related_votes": len(related),
            "max_for_on_challenges": max((int(r.get("count_for") or 0)
                                          for r in challenges), default=0),
            "threshold_hit": hit,
        },
        "outcome_hit": hit,
        "graded_at": today,
    }


def grade() -> int:
    today = date.today().isoformat()
    if today < GRADE_OPENS:
        print(f"grade: refusing — grading opens {GRADE_OPENS}, the day after the "
              f"part-session closes (today is {today}). Predictions stay frozen.")
        return 1
    out = ROOT / "predictions" / f"plenary_{SESSION}_forward.json"
    if not out.exists():
        print(f"grade: {out} missing — nothing was pre-committed.")
        return 1
    ledger = json.loads(out.read_text())
    results_file = ROOT / "predictions" / f"plenary_{SESSION}_results.json"
    overrides = json.loads(results_file.read_text()) if results_file.exists() else {}
    rows = _session_rows()
    if not rows:
        # the cached bulk export may predate the session — refresh it once
        resolve_plenary.ensure_votes_csv(force=True)
        rows = _session_rows()
    if not rows:
        print("grade: HowTheyVote has not published this session's roll-calls yet — "
              "nothing graded, nothing failed. Re-run later. All items pending:")
        for i in ledger["items"]:
            if not i.get("graded"):
                print(f"  pending: {i.get('a10') or i['title'][:60]}")
        return 0
    all_rows = None  # lazy; only needed for ***II threshold grading
    prior = ep_flip._baseline_A()
    n_new = 0
    used: dict[str, str] = {}  # vote id -> item name, to catch double-pairing
    for item in ledger["items"]:
        if item.get("graded"):
            continue
        name = item.get("a10") or item["title"][:60]
        ov = overrides.get(item.get("a10") or item["title"]) or {}
        if item["type"] == "cod2":
            if all_rows is None:
                all_rows = _session_rows(mains_only=False)
            g = _grade_second_reading(item, all_rows, ov, today)
            if g:
                item["graded"] = g
                item.pop("grade_note", None)
                n_new += 1
            continue
        row, how = _match_row(item, rows, overrides)
        if row is None and ov.get("result") in resolve_plenary.VALID_RESULTS:
            # No roll call (e.g. show of hands) — outcome-only, from the minutes.
            item["graded"] = {
                "paired_by": "minutes(results file)", "rcv": False,
                "observed_result": ov["result"],
                "outcome_hit": (item["outcome"] == ov["result"]),
                "graded_at": today,
            }
            b = _brier(item, ov["result"])
            if b is not None:
                item["graded"]["brier"] = b
            item.pop("grade_note", None)
            n_new += 1
            continue
        if row is None:
            item["grade_note"] = f"pending — {how}"
            continue
        if how.startswith("title:") and row["id"] in used:
            item["grade_note"] = (f"pending — title match collides with "
                                  f"{used[row['id']]} on vote {row['id']}; add a "
                                  f"vote_id override in {results_file.name}")
            continue
        plen_date = row["timestamp"][:10]
        if plen_date <= ledger["generated_at"]:
            item["grade_note"] = (f"vote {plen_date} not after ledger "
                                  f"{ledger['generated_at']} — not prospective")
            continue
        used[row["id"]] = name
        g = {
            "paired_by": how, "rcv": True, "vote_id": row["id"],
            "vote_title": row.get("display_title") or row.get("procedure_title"),
            "vote_date": plen_date,
            "observed_result": row["result"],
            "outcome_hit": (item["outcome"] == row["result"]),
            "graded_at": today,
        }
        b = _brier(item, row["result"])
        if b is not None:
            g["brier"] = b
        obs_share = _observed_share(row)
        if obs_share is not None and item.get("ep_yes_share") is not None:
            g["observed_share"] = round(obs_share, 4)
            g["share_abs_err"] = round(abs(item["ep_yes_share"] - obs_share), 4)
        try:
            bg = resolve_plenary.fetch_by_group(row["id"])
        except Exception as exc:  # detail API down ≠ outcome unknown; grade anyway
            bg = None
            g["per_group_note"] = f"per-group fetch failed: {exc}"
        if bg:
            observed = {gr: baselines._yes_rate(s) for gr, s in bg.items()}
            g["observed_per_group"] = {gr: round(v, 4) for gr, v in observed.items()
                                       if v is not None}
            if not _prior_rail(item):
                groups = [gr for gr in GROUPS
                          if observed.get(gr) is not None
                          and item["per_group"].get(gr) is not None
                          and prior.get(gr) is not None]
                if len(groups) >= 5:
                    g["mse_signal"] = round(sum(
                        (item["per_group"][gr] - observed[gr]) ** 2
                        for gr in groups) / len(groups), 6)
                    g["mse_prior"] = round(sum(
                        (prior[gr] - observed[gr]) ** 2
                        for gr in groups) / len(groups), 6)
        item["graded"] = g
        item.pop("grade_note", None)
        n_new += 1
    ledger["scorecard"] = _scorecard(ledger)
    out.write_text(json.dumps(ledger, indent=1, ensure_ascii=False) + "\n")
    (ROOT / "predictions" / f"plenary_{SESSION}_forward.md").write_text(render_md(ledger))
    sc = ledger["scorecard"]
    print(f"grade: scored {n_new} newly-resolved items; "
          f"{sc['n_graded']}/{ledger['n_items']} graded, "
          f"{sc['n_pending']} pending.")
    for rail, st in sc["by_rail"].items():
        print(f"  {rail:14s} outcome {st['outcome_hits']}/{st['n']}"
              + (f"  share MAE {st['share_mae']:.3f}" if st.get("share_mae") is not None
                 else "")
              + (f"  Brier {st['brier']:.3f}" if st.get("brier") is not None else ""))
    c = sc["contested"]
    print(f"  {'contested':14s} outcome {c['outcome_hits']}/{c['n']}")
    for i in ledger["items"]:
        if not i.get("graded"):
            print(f"  pending: {i.get('a10') or i['title'][:60]}"
                  + (f" — {i['grade_note']}" if i.get("grade_note") else ""))
    return 0


def _scorecard(ledger: dict) -> dict:
    graded = [i for i in ledger["items"] if i.get("graded")]
    pending = [i for i in ledger["items"] if not i.get("graded")]

    def stats(items):
        if not items:
            return {"n": 0, "outcome_hits": 0, "share_mae": None, "brier": None}
        errs = [i["graded"]["share_abs_err"] for i in items
                if i["graded"].get("share_abs_err") is not None]
        briers = [i["graded"]["brier"] for i in items
                  if i["graded"].get("brier") is not None]
        return {
            "n": len(items),
            "outcome_hits": sum(1 for i in items if i["graded"]["outcome_hit"]),
            "share_mae": round(sum(errs) / len(errs), 4) if errs else None,
            "brier": round(sum(briers) / len(briers), 4) if briers else None,
        }

    by_rail = {
        # always-ADOPTED graded on the SAME items: hit iff the observed result is
        # ADOPTED (a ***II position standing = the act deemed adopted counts too).
        # This is the naive baseline every other row must beat.
        "always-ADOPTED": {
            "n": len(graded),
            "outcome_hits": sum(1 for i in graded
                                if i["graded"]["observed_result"]
                                in ("ADOPTED", "POSITION STANDS")),
            "share_mae": None,
        },
        "prior": stats([i for i in graded if _prior_rail(i)]),
        "committee": stats([i for i in graded if not _prior_rail(i)]),
    }
    return {
        "graded_through": max((i["graded"]["graded_at"] for i in graded), default=None),
        "n_graded": len(graded), "n_pending": len(pending),
        "pending": [i.get("a10") or i["title"][:60] for i in pending],
        "by_rail": by_rail,
        "contested": stats([i for i in graded if i.get("contested")]),
    }


def predict() -> int:
    today = date.today().isoformat()
    if today >= SESSION_FIRST_DAY:
        print(f"predict: refusing — the part-session opened {SESSION_FIRST_DAY}; "
              "re-cutting the ledger now would not be a pre-registered prediction. "
              "The committed ledger is the record; use grade or status.")
        return 1
    ledger = build()
    out = ROOT / "predictions" / f"plenary_{SESSION}_forward.json"
    out.write_text(json.dumps(ledger, indent=1, ensure_ascii=False) + "\n")
    md = ROOT / "predictions" / f"plenary_{SESSION}_forward.md"
    md.write_text(render_md(ledger))
    print(f"wrote {out.relative_to(ROOT)} and {md.relative_to(ROOT)} "
          f"({ledger['n_items']} items)")
    n_committee = sum(1 for i in ledger["items"] if not _prior_rail(i))
    n_contested = sum(1 for i in ledger["items"] if i.get("contested"))
    print(f"  signal rail: {n_committee} committee/opinion, "
          f"{ledger['n_items'] - n_committee} prior-only; {n_contested} contested")
    print(f">>> COMMIT predictions/ TO GIT NOW (before the session opens "
          f"{SESSION_FIRST_DAY}).")
    return 0


def status() -> int:
    out = ROOT / "predictions" / f"plenary_{SESSION}_forward.json"
    if not out.exists():
        print("status: no ledger yet — run predict (before the session).")
        return 1
    ledger = json.loads(out.read_text())
    n_committee = sum(1 for i in ledger["items"] if not _prior_rail(i))
    n_contested = sum(1 for i in ledger["items"] if i.get("contested"))
    print(f"forward ledger {ledger['session_dates']}: {ledger['n_items']} items, "
          f"cut {ledger['generated_at']} @ {ledger['engine_rev']} "
          f"({n_committee} committee/opinion rail, {n_contested} contested)")
    sc = ledger.get("scorecard")
    if not sc or not sc["n_graded"]:
        print(f"  ungraded — grading opens {GRADE_OPENS} "
              f"(uv run python -m praevisa.plenary_forward grade)")
        return 0
    for rail, st in sc["by_rail"].items():
        print(f"  {rail:14s} outcome {st['outcome_hits']}/{st['n']}"
              + (f"  share MAE {st['share_mae']:.3f}"
                 if st.get("share_mae") is not None else ""))
    c = sc["contested"]
    print(f"  {'contested':14s} outcome {c['outcome_hits']}/{c['n']}"
          + (f"  share MAE {c['share_mae']:.3f}"
             if c.get("share_mae") is not None else ""))
    if sc["n_pending"]:
        print(f"  pending ({sc['n_pending']}): " + "; ".join(sc["pending"]))
    return 0


def main() -> int:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "predict"
    fn = {"predict": predict, "grade": grade, "status": status}.get(cmd)
    if fn is None:
        print(f"unknown command {cmd!r}; use predict|grade|status")
        return 2
    return fn()


if __name__ == "__main__":
    raise SystemExit(main())
