"""CHES 2024 → Praevisa ideal-points.

Loads the Chapel Hill Expert Survey 2024 dataset and aggregates party-level
positions into:

  * EP group ideal-points  — seats-weighted average of parties in each group
  * Member-state ideal-points — vote-weighted average of governing parties

CHES native scales are remapped to the engine's [-10, +10] space:
  * lrecon       0..10  → (x - 5) * 2   (left ↔ right)
  * galtan       0..10  → (x - 5) * 2   (GAL ↔ TAN)
  * eu_position  1..7   → (x - 4) * 10/3 (eurosceptic ↔ pro-integration)

The curated mappings (party_id → EP group, country → governing parties) are
political-knowledge snapshots dated to the 10th-term EP and the post-2024
national legislatures. Refresh them when governments change.

Source: Jolly, S. et al. (2024). Chapel Hill Expert Survey 2024.
        https://www.chesdata.eu/2024-chapel-hill-expert-survey-ches
"""

from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

CHES_CSV = Path(__file__).parent / "data" / "CHES_2024_final_v2.csv"


# CHES integer country codes → ISO 2-letter codes used elsewhere in the engine.
# Codes 11 (UK), 34 (Turkey), 35 (Norway), 36 (Switzerland), 45 omitted (non-EU).
# Code 9 (Luxembourg) is absent from CHES 2024 — handled by FALLBACK_MS_POSITION.
CHES_COUNTRY_TO_ISO: dict[int, str] = {
    1: "BE", 2: "DK", 3: "DE", 4: "EL", 5: "ES", 6: "FR", 7: "IE", 8: "IT",
    10: "NL", 12: "PT", 13: "AT", 14: "FI", 16: "SE", 20: "BG", 21: "CZ",
    22: "EE", 23: "HU", 24: "LV", 25: "LT", 26: "PL", 27: "RO", 28: "SK",
    29: "SI", 31: "HR", 37: "MT", 40: "CY",
}


# Curated mapping: CHES party_id → 10th-term EP group code.
# Coverage: parties holding seats in the 720-MEP 10th-term EP plus larger
# domestic parties (used in MS coalition aggregation).
# Sources: EP group affiliations as published after the June 2024 election,
# updated for known group switches through early 2026.
PARTY_TO_EP_GROUP: dict[int, str] = {
    # Belgium
    102: "S&D",   103: "S&D",   104: "Greens", 105: "Greens", 106: "Renew",
    107: "Renew", 108: "EPP",   109: "EPP",    110: "ECR",    111: "Renew",
    112: "PfE",   119: "Left",
    # Denmark
    201: "S&D",   202: "Renew", 203: "EPP",   206: "Greens", 211: "Renew",
    213: "Left",  215: "PfE",   218: "ECR",   219: "Greens", 220: "NI",
    221: "Renew", 222: "ECR",
    # Germany
    301: "EPP",   302: "S&D",   303: "Renew", 304: "Greens", 306: "Left",
    308: "EPP",   310: "ESN",
    # Greece
    401: "S&D",   402: "EPP",   403: "Left",  404: "NI",    416: "ESN",
    # Spain
    501: "S&D",   502: "EPP",   504: "Left",  506: "Renew", 511: "Greens",
    513: "Greens", 524: "Left", 525: "Left",  527: "PfE",   550: "NI",
    551: "Left",
    # France
    601: "Left",  602: "S&D",   605: "Greens", 609: "EPP",   610: "PfE",
    613: "Renew", 626: "Renew", 627: "Left",   631: "EPP",
    # Ireland
    701: "Renew", 702: "EPP",   703: "S&D",    705: "Greens", 707: "Left",
    709: "Left",  710: "S&D",
    # Italy
    811: "PfE",   815: "EPP",   827: "EPP",    832: "Renew",  837: "S&D",
    838: "Greens", 844: "ECR",  845: "NI",     849: "Renew",  850: "Greens",
    # Netherlands
    1001: "EPP",  1002: "S&D",  1003: "Renew", 1004: "Renew", 1005: "Greens",
    1006: "ECR",  1014: "Left", 1016: "ECR",   1017: "PfE",   1018: "Left",
    1050: "NI",   1051: "ESN",  1052: "Greens", 1054: "EPP",  1056: "EPP",
    # Portugal
    1201: "Left", 1202: "EPP",  1205: "S&D",   1206: "EPP",   1208: "Left",
    1250: "Greens", 1251: "Greens", 1252: "Renew", 1253: "PfE",
    # Austria
    1301: "S&D",  1302: "EPP",  1303: "PfE",   1304: "Greens", 1306: "Renew",
    # Finland
    1401: "S&D",  1402: "EPP",  1403: "Renew", 1404: "Left",  1405: "ECR",
    1406: "Renew", 1408: "Greens", 1409: "EPP", 1410: "NI",
    # Sweden
    1601: "Left", 1602: "S&D",  1603: "Renew", 1604: "Renew", 1605: "EPP",
    1606: "EPP",  1607: "Greens", 1610: "ECR",
    # Bulgaria
    2003: "S&D",  2010: "EPP",  2018: "EPP",   2019: "PfE",   2020: "ESN",
    2021: "Renew", 2022: "Renew",
    # Czechia
    2102: "ECR",  2104: "EPP",  2109: "EPP",   2111: "PfE",   2114: "Greens",
    2115: "ESN",  2116: "EPP",
    # Estonia
    2201: "EPP",  2202: "Renew", 2203: "Renew", 2204: "S&D",  2209: "ECR",
    2210: "Renew",
    # Hungary
    2301: "S&D",  2302: "PfE",   2308: "NI",   2309: "Greens", 2311: "S&D",
    2314: "Renew", 2316: "ESN",
    # Latvia
    2405: "Greens", 2406: "ECR", 2412: "EPP",   2418: "NI",   2419: "ECR",
    2420: "S&D",
    # Lithuania
    2501: "S&D",  2506: "EPP",   2507: "Greens", 2511: "ECR", 2518: "Renew",
    2525: "ESN",  2526: "Renew",
    # Poland
    2601: "S&D",  2603: "EPP",   2605: "ECR",  2606: "EPP",   2619: "ESN",
    2620: "Left", 2623: "EPP",
    # Romania
    2701: "S&D",  2705: "EPP",   2706: "EPP",  2713: "Renew", 2715: "ECR",
    2716: "ESN",  2717: "NI",
    # Slovakia
    2803: "NI",   2805: "EPP",   2812: "ECR",  2814: "EPP",   2819: "S&D",
    2823: "S&D",
    # Slovenia
    2902: "EPP",  2903: "S&D",   2905: "EPP",  2912: "Left",  2916: "Renew",
    # Croatia
    3101: "EPP",  3102: "S&D",   3115: "ECR",  3120: "Greens", 3122: "ECR",
    # Malta
    3701: "S&D",  3702: "EPP",
    # Cyprus
    4001: "EPP",  4003: "Left",  4004: "S&D",  4005: "S&D",  4006: "Greens",
    4009: "PfE",  4015: "Renew",
}


# Governing-coalition snapshot, early 2026. Each value is a list of
# (party_id, weight) pairs where weight is the relative pull on the
# government's foreign-policy line — typically vote share or seat share
# in the cabinet. Use a uniform 1.0 if you don't want to weight.
GOVERNMENT_PARTIES: dict[str, list[tuple[int, float]]] = {
    "BE": [(110, 1.0), (106, 1.0), (108, 1.0), (109, 1.0), (103, 1.0)],   # De Wever "Arizona"
    "DK": [(201, 1.5), (211, 1.0), (221, 1.0)],                            # SVM coalition
    "DE": [(301, 1.5), (308, 0.5), (302, 1.0)],                            # CDU/CSU + SPD (Merz)
    "EL": [(402, 1.0)],                                                    # ND single-party
    "ES": [(501, 1.5), (551, 1.0)],                                        # PSOE + Sumar
    "FR": [(626, 1.5), (613, 1.0), (631, 1.0)],                            # Macron camp
    "IE": [(701, 1.0), (702, 1.0)],                                        # FF + FG (+ Inds)
    "IT": [(844, 1.5), (811, 1.0), (815, 1.0)],                            # Meloni
    "NL": [(1017, 1.5), (1003, 1.0), (1056, 1.0), (1054, 0.5)],            # Schoof / right
    "PT": [(1206, 1.5), (1202, 0.5)],                                      # AD minority
    "AT": [(1302, 1.5), (1301, 1.0), (1306, 0.7)],                         # ÖVP-SPÖ-NEOS
    "FI": [(1402, 1.5), (1405, 1.0), (1409, 0.5), (1406, 0.5)],            # Orpo
    "SE": [(1605, 1.5), (1606, 1.0), (1604, 0.7)],                         # Tidö (M-KD-L)
    "BG": [(2010, 1.5), (2021, 1.0), (2018, 0.7)],                         # GERB-PP-DB
    "CZ": [(2111, 1.5), (2115, 0.5)],                                      # ANO-led (post Oct 2025)
    "EE": [(2203, 1.5), (2210, 0.7), (2204, 0.7)],                         # Reform-led
    "HU": [(2302, 2.0)],                                                   # Fidesz
    "LV": [(2412, 1.5), (2420, 0.7), (2405, 0.7)],                         # New Unity-led
    "LT": [(2501, 1.5), (2526, 0.7), (2525, 0.7)],                         # LSDP-led (Paluckas)
    "PL": [(2603, 1.5), (2623, 1.0), (2606, 0.7), (2601, 0.7)],            # Tusk
    "RO": [(2701, 1.5), (2705, 1.0), (2706, 0.5)],                         # PSD-PNL-UDMR
    "SK": [(2803, 1.5), (2823, 1.0)],                                      # Fico
    "SI": [(2916, 1.5), (2903, 0.7), (2912, 0.5)],                         # Golob
    "HR": [(3101, 1.5), (3122, 0.7)],                                      # HDZ + DP
    "MT": [(3701, 2.0)],                                                   # Labour majority
    "CY": [(4001, 1.0), (4004, 1.0), (4005, 0.7)],                         # Christodoulides bloc
    # LU absent from CHES 2024
}


# Fallback (LU is missing from CHES 2024). Hand-coded.
FALLBACK_MS_POSITION: dict[str, tuple[float, float, float]] = {
    "LU": (1.0, -1.0, 7.0),
}


def _load_ches() -> list[dict[str, str]]:
    with CHES_CSV.open(newline="") as f:
        return list(csv.DictReader(f))


def _to_float(s: str) -> float | None:
    try:
        v = float(s)
    except (TypeError, ValueError):
        return None
    # CHES uses 99/missing markers in some columns; drop wildly out-of-range.
    return v if -1e6 < v < 1e6 else None


def _remap(econ: float, gal: float, eu: float) -> tuple[float, float, float]:
    return ((econ - 5.0) * 2.0, (gal - 5.0) * 2.0, (eu - 4.0) * (10.0 / 3.0))


def _party_position(row: dict[str, str]) -> tuple[float, float, float] | None:
    econ = _to_float(row["lrecon"])
    gal = _to_float(row["galtan"])
    eu = _to_float(row["eu_position"])
    if econ is None or gal is None or eu is None:
        return None
    return _remap(econ, gal, eu)


def compute_ep_group_positions() -> dict[str, tuple[float, float, float]]:
    """Seats-weighted ideal-point per EP group.

    Weights use CHES `seat` (national parliament seats) as a proxy for the
    party's EP delegation size — accurate to within reordering for our purposes,
    since the only CHES proxy with EP context (`epvote`) is sparser.
    """
    sums: dict[str, list[float]] = defaultdict(lambda: [0.0, 0.0, 0.0])
    weights: dict[str, float] = defaultdict(float)
    for row in _load_ches():
        party_id = int(row["party_id"])
        group = PARTY_TO_EP_GROUP.get(party_id)
        if group is None:
            continue
        pos = _party_position(row)
        seat = _to_float(row["seat"]) or 0.0
        if pos is None or seat <= 0:
            continue
        sums[group][0] += pos[0] * seat
        sums[group][1] += pos[1] * seat
        sums[group][2] += pos[2] * seat
        weights[group] += seat

    out: dict[str, tuple[float, float, float]] = {}
    for group, w in weights.items():
        if w > 0:
            out[group] = (sums[group][0] / w, sums[group][1] / w, sums[group][2] / w)
    # NI rarely has well-defined positions; default to centre.
    out.setdefault("NI", (0.0, 0.0, 0.0))
    return out


def compute_member_state_positions() -> dict[str, tuple[float, float, float]]:
    """Government-coalition-weighted ideal-point per member state."""
    rows_by_id = {int(r["party_id"]): r for r in _load_ches()}
    out: dict[str, tuple[float, float, float]] = {}
    for iso, parties in GOVERNMENT_PARTIES.items():
        sx = sy = sz = wsum = 0.0
        for party_id, w in parties:
            row = rows_by_id.get(party_id)
            if row is None:
                continue
            pos = _party_position(row)
            if pos is None:
                continue
            sx += pos[0] * w
            sy += pos[1] * w
            sz += pos[2] * w
            wsum += w
        if wsum > 0:
            out[iso] = (sx / wsum, sy / wsum, sz / wsum)
    out.update(FALLBACK_MS_POSITION)
    return out
