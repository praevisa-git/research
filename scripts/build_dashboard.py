"""Generate the public forward-ledger dashboard (docs/index.html) from the committed
prediction ledger. Pure read → render: the page is a view of the JSON, never a source.

Brand: praevisa.eu — paper #f3efe6, ink #0c0d10, gold #7a6020, navy #0f1d3a,
Cormorant Garamond display + DM Mono data labels, hairline rules, corner marks.

Run:
    uv run python scripts/build_dashboard.py
Re-run after `plenary_forward grade` — the scorecard section fills itself in.
"""

from __future__ import annotations

import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SESSION = "2026-06-15"
LEDGER = ROOT / "predictions" / f"plenary_{SESSION}_forward.json"
OUT = ROOT / "docs" / "index.html"

GROUP_ORDER = ["EPP", "S&D", "PfE", "ECR", "Renew", "Greens", "Left", "ESN", "NI"]
SEATS = {"EPP": 188, "S&D": 136, "PfE": 84, "ECR": 78, "Renew": 77,
         "Greens": 53, "Left": 46, "ESN": 25, "NI": 33}

TYPE_LABEL = {
    "cod1": "Ordinary legislative · 1st reading",
    "cod2": "Ordinary legislative · 2nd reading",
    "cns": "Consultation",
    "consent": "Consent",
    "ini": "Own-initiative report",
    "bud": "Budgetary",
    "resolution": "Resolution",
    "recommendation": "Recommendation",
}

DAY_LABEL = {
    "2026-06-16": ("Tuesday 16 June", "votes at 12:30"),
    "2026-06-17": ("Wednesday 17 June", "votes at 12:30"),
    "2026-06-18": ("Thursday 18 June", "votes at 12:00"),
}


def esc(s) -> str:
    return html.escape(str(s)) if s is not None else ""


def pct(v) -> str:
    return f"{v * 100:.0f}%" if v is not None else "—"


def rail_of(item) -> str:
    return "prior" if item["signal"] == "prior" else "signal"


def signal_label(item) -> str:
    s = item["signal"]
    if s == "prior":
        return "baseline · party arithmetic"
    if s.startswith("opinion"):
        return f"committee signal · {s}"
    return f"committee signal · {s.split(':', 1)[-1]} vote"


def group_bars(item) -> str:
    rows = []
    pg = item.get("per_group") or {}
    for g in GROUP_ORDER:
        v = pg.get(g)
        if v is None:
            continue
        w = max(1.5, v * 100)
        rows.append(
            f'<div class="gb"><span class="gb-code">{esc(g)}</span>'
            f'<span class="gb-track"><span class="gb-fill" style="width:{w:.1f}%">'
            f'</span></span><span class="gb-val">{pct(v)}</span></div>')
    return "\n".join(rows)


def graded_chip(item) -> str:
    g = item.get("graded")
    if not g:
        return '<span class="chip chip-pending">awaiting vote</span>'
    if g["outcome_hit"]:
        return (f'<span class="chip chip-hit">hit — {esc(g["observed_result"])}'
                + (f' at {pct(g["observed_share"])}' if g.get("observed_share")
                   is not None else "") + "</span>")
    return (f'<span class="chip chip-miss">miss — {esc(g["observed_result"])}'
            + (f' at {pct(g["observed_share"])}' if g.get("observed_share")
               is not None else "") + "</span>")


def featured_card(item) -> str:
    sr = item.get("second_reading")
    contested = ('<span class="chip chip-contested">contested</span>'
                 if item.get("contested") else "")
    tally = item.get("committee_tally")
    tally_html = ""
    if tally:
        tally_html = (f'<div class="mono dim small">committee roll-call '
                      f'{tally.get("+", 0)} for · {tally.get("-", 0)} against · '
                      f'{tally.get("0", 0)} abstaining</div>')
    if sr:
        seats_no = sr["predicted_seats_against"]
        marker = 361 / 720 * 100
        fillw = seats_no / 720 * 100
        body = f"""
      <div class="sr">
        <div class="mono dim small">Rule 68 — amending or rejecting the Council
        position needs an absolute majority of members</div>
        <div class="sr-track">
          <span class="sr-fill" style="width:{fillw:.1f}%"></span>
          <span class="sr-marker" style="left:{marker:.1f}%"></span>
        </div>
        <div class="sr-legend mono small">
          <span>predicted against: <b>{seats_no:.0f}</b> seats</span>
          <span>threshold: <b>361</b> of 720</span>
        </div>
        <p class="verdict">Predicted: <em>the Council position stands</em> — the
        act is deemed adopted.</p>
      </div>"""
    else:
        body = f'<div class="bars">{group_bars(item)}</div>'
    pivot = item.get("pivot_headline") or ""
    return f"""
    <article class="card">
      <header class="card-head">
        <div class="mono gold small">{esc(item.get("a10") or "—")} ·
          {esc(item.get("committee") or "")} · {esc(TYPE_LABEL.get(item["type"], item["type"]))}</div>
        <h3>{esc(item["title"])}</h3>
        <div class="mono dim small">{esc(item.get("rapporteur") or "")}</div>
      </header>
      <div class="card-call">
        <span class="outcome">{esc(item["outcome"] if not sr else "POSITION STANDS")}</span>
        <span class="share mono">{pct(item.get("ep_yes_share"))} predicted yes-share</span>
        {contested} {graded_chip(item)}
      </div>
      {tally_html}
      {body}
      <footer class="mono dim small">flip lever — {esc(pivot.lower())}</footer>
    </article>"""


def table_row(item) -> str:
    note = f' <span class="dim">({esc(item["note"])})</span>' if item.get("note") else ""
    if item["signal"] == "prior":
        rail = '<span class="rail rail-prior">baseline</span>'
    else:
        rail = '<span class="rail rail-signal">committee</span>'
    if item.get("contested"):
        rail += ' <span class="rail rail-contested">contested</span>'
    return f"""
      <tr>
        <td class="mono small">{esc(item.get("a10") or "—")}</td>
        <td>{esc(item["title"])}{note}</td>
        <td class="mono small">{esc(TYPE_LABEL.get(item["type"], item["type"]))}</td>
        <td class="mono small">{esc(item["outcome"])} · {pct(item.get("ep_yes_share"))}
          <br>{rail}</td>
        <td>{graded_chip(item)}</td>
      </tr>"""


def scorecard_html(ledger) -> str:
    sc = ledger.get("scorecard")
    if not sc or not sc.get("n_graded"):
        return """
    <div class="score-pending">
      <div class="mono gold small eyebrow-line">scorecard</div>
      <p class="big">Grading opens when the votes close.</p>
      <p>Every line above is frozen in git before the session. Afterwards each is
      scored against the official results by pre-registered rules — outcome hit or
      miss, share error, and the contested subset broken out — next to the one
      number that keeps us honest: <em>a coin with ADOPTED printed on both sides
      gets roughly nine in ten EP votes right.</em> We claim skill only where the
      committee rail beats that coin and our own published baseline.</p>
    </div>"""
    rows = []
    names = {"always-ADOPTED": "Always-ADOPTED (the naive coin)",
             "prior": "Baseline rail (party arithmetic)",
             "committee": "Committee rail (the signal)"}
    for rail, st in sc["by_rail"].items():
        mae = f"{st['share_mae']:.3f}" if st.get("share_mae") is not None else "—"
        rows.append(f"<tr><td>{esc(names.get(rail, rail))}</td>"
                    f"<td class='mono'>{st['outcome_hits']}/{st['n']}</td>"
                    f"<td class='mono'>{mae}</td></tr>")
    c = sc["contested"]
    cmae = f"{c['share_mae']:.3f}" if c.get("share_mae") is not None else "—"
    pending = ""
    if sc["n_pending"]:
        pending = (f'<p class="mono dim small">still pending: '
                   f'{esc("; ".join(sc["pending"]))}</p>')
    return f"""
    <div class="score-done">
      <div class="mono gold small eyebrow-line">scorecard ·
        graded {esc(sc.get("graded_through"))}</div>
      <table class="score-table">
        <thead><tr><th>rail</th><th>outcome hits</th><th>share error (MAE)</th></tr></thead>
        <tbody>{''.join(rows)}
          <tr class="contested-row"><td>Contested subset</td>
            <td class="mono">{c['outcome_hits']}/{c['n']}</td>
            <td class="mono">{cmae}</td></tr>
        </tbody>
      </table>
      <p class="dim">Skill is claimed only where the committee rail beats both the
      naive coin and the published baseline. {pending}</p>
    </div>"""


def build() -> str:
    ledger = json.loads(LEDGER.read_text())
    items = ledger["items"]
    featured = [i for i in items if i["signal"] != "prior" or i["type"] == "cod2"]
    n_contested = sum(1 for i in items if i.get("contested"))

    days_html = []
    for day, (label, when) in DAY_LABEL.items():
        day_items = [i for i in items if i["day"] == day]
        if not day_items:
            continue
        rows = "".join(table_row(i) for i in day_items)
        days_html.append(f"""
      <section class="day">
        <h2 class="day-head"><span>{esc(label)}</span>
          <span class="mono dim small">{esc(when)} · {len(day_items)} items</span></h2>
        <table class="ledger-table">
          <thead><tr><th>ref</th><th>motion</th><th>procedure</th>
            <th>prediction</th><th>result</th></tr></thead>
          <tbody>{rows}</tbody>
        </table>
      </section>""")

    featured_html = "".join(featured_card(i) for i in featured)
    not_predicted = "".join(f"<li>{esc(n)}</li>" for n in ledger["not_predicted"])

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="description" content="Praevisa forward ledger — every vote of the European Parliament part-session, predicted and committed to git before the session opens, graded in public afterwards.">
<title>Praevisa — Forward Ledger · {esc(ledger["session_dates"])}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,300;0,400;0,600;1,300;1,400&family=DM+Mono:wght@300;400&display=swap" rel="stylesheet">
<style>
*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
:root {{
  --ink: #0c0d10; --paper: #f3efe6; --gold: #7a6020; --gold-l: #9a7d2e;
  --navy: #0f1d3a; --muted: #4a4640; --border: #cfc9b8;
  --dim: rgba(12,13,16,0.10); --hit: #2e5e34; --miss: #7a2020;
}}
html {{ font-size: 17px; scroll-behavior: smooth; }}
body {{
  background: var(--paper); color: var(--ink);
  font-family: 'Cormorant Garamond', Georgia, serif; line-height: 1.45;
}}
body::before {{
  content: ''; position: fixed; inset: 0; pointer-events: none; z-index: 999;
  background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='0.04'/%3E%3C/svg%3E");
  opacity: 0.55;
}}
.corner {{ position: fixed; width: 36px; height: 36px; pointer-events: none; z-index: 100; }}
.corner-tl {{ top:0; left:0; border-top:1px solid var(--gold); border-left:1px solid var(--gold); opacity:.3; }}
.corner-br {{ bottom:0; right:0; border-bottom:1px solid var(--gold); border-right:1px solid var(--gold); opacity:.3; }}
.mono {{ font-family: 'DM Mono', monospace; }}
.gold {{ color: var(--gold); }}
.dim  {{ color: var(--muted); }}
.small {{ font-size: 0.72rem; letter-spacing: 0.08em; }}
.eyebrow-line {{ text-transform: uppercase; letter-spacing: 0.22em; margin-bottom: 0.8rem; }}
.wrap {{ max-width: 1060px; margin: 0 auto; padding: 0 clamp(1.2rem, 4vw, 3rem); }}

/* hero */
header.hero {{ padding: clamp(3rem,7vw,5.5rem) 0 clamp(2rem,4vw,3rem);
  border-bottom: 1px solid var(--dim); }}
.wordmark {{ font-size: clamp(2.2rem,4.6vw,4rem); font-weight:600; letter-spacing:.06em;
  text-transform: uppercase; line-height: .95; }}
.wordmark span {{ color: var(--gold); }}
.hero h1 {{ font-size: clamp(1.6rem,3vw,2.5rem); font-weight: 300; max-width: 26ch;
  margin-top: clamp(1.2rem,2.5vw,2rem); line-height: 1.25; }}
.hero h1 em {{ font-style: italic; color: var(--gold); }}
.rule {{ width: 3rem; height: 1px; background: var(--gold); margin: 1.4rem 0; }}
.meta-strip {{ display:flex; flex-wrap:wrap; gap:1.6rem 2.6rem; margin-top:1.8rem; }}
.meta-strip div b {{ display:block; font-size:1.45rem; font-weight:600; }}
.meta-strip div span {{ font-family:'DM Mono',monospace; font-size:.62rem;
  letter-spacing:.18em; text-transform:uppercase; color:var(--muted); }}

/* sections */
section.block {{ padding: clamp(2.2rem,4.5vw,3.6rem) 0; border-bottom:1px solid var(--dim); }}
section.block > .wrap > p.lede {{ max-width: 62ch; font-size: 1.08rem; }}
.big {{ font-size: 1.5rem; font-weight: 300; margin-bottom: .6rem; }}

/* featured cards */
.cards {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(300px,1fr));
  gap:1.4rem; margin-top:1.6rem; }}
.card {{ border:1px solid var(--border); background:rgba(255,255,255,.35);
  padding:1.4rem 1.5rem 1.1rem; display:flex; flex-direction:column; gap:.8rem;
  transition: border-color .25s, transform .25s; }}
.card:hover {{ border-color: var(--gold-l); transform: translateY(-2px); }}
.card h3 {{ font-size:1.18rem; font-weight:600; line-height:1.25; margin-top:.35rem; }}
.card-call {{ display:flex; align-items:baseline; gap:.7rem; flex-wrap:wrap; }}
.outcome {{ font-weight:600; letter-spacing:.04em; }}
.share {{ font-size:.7rem; color:var(--muted); letter-spacing:.06em; }}
.card footer {{ border-top:1px solid var(--dim); padding-top:.6rem; margin-top:auto; }}

/* rail stamps */
.rail {{ font-family:'DM Mono',monospace; font-size:.55rem; letter-spacing:.14em;
  text-transform:uppercase; }}
.rail-prior {{ color: var(--muted); opacity:.75; }}
.rail-signal {{ color: var(--gold); }}
.rail-contested {{ color: var(--navy); }}

/* chips */
.chip {{ font-family:'DM Mono',monospace; font-size:.58rem; letter-spacing:.14em;
  text-transform:uppercase; padding:.22em .65em; border:1px solid; border-radius:2px; }}
.chip-contested {{ color:var(--navy); border-color:var(--navy); }}
.chip-pending {{ color:var(--muted); border-color:var(--border); }}
.chip-hit {{ color:var(--hit); border-color:var(--hit); }}
.chip-miss {{ color:#fff; background:var(--miss); border-color:var(--miss); }}

/* group bars */
.bars {{ display:flex; flex-direction:column; gap:.32rem; }}
.gb {{ display:grid; grid-template-columns:3.4rem 1fr 2.8rem; align-items:center; gap:.6rem; }}
.gb-code {{ font-family:'DM Mono',monospace; font-size:.62rem; letter-spacing:.1em; }}
.gb-track {{ height:7px; background:var(--dim); position:relative; }}
.gb-fill {{ position:absolute; inset:0 auto 0 0; background:var(--gold); }}
.gb-val {{ font-family:'DM Mono',monospace; font-size:.62rem; text-align:right;
  color:var(--muted); }}

/* second reading */
.sr-track {{ height:12px; background:var(--dim); position:relative; margin:.7rem 0 .45rem; }}
.sr-fill {{ position:absolute; inset:0 auto 0 0; background:var(--navy); opacity:.85; }}
.sr-marker {{ position:absolute; top:-5px; bottom:-5px; width:2px; background:var(--gold); }}
.sr-legend {{ display:flex; justify-content:space-between; color:var(--muted);
  letter-spacing:.06em; }}
.verdict {{ margin-top:.7rem; }}
.verdict em {{ color:var(--gold); }}

/* day tables */
.day {{ margin-top: 2.4rem; }}
.day-head {{ display:flex; align-items:baseline; justify-content:space-between;
  gap:1rem; font-size:1.35rem; font-weight:600; border-bottom:1px solid var(--ink);
  padding-bottom:.45rem; }}
.ledger-table {{ width:100%; border-collapse:collapse; margin-top:.4rem; }}
.ledger-table th {{ font-family:'DM Mono',monospace; font-size:.6rem; font-weight:400;
  letter-spacing:.18em; text-transform:uppercase; color:var(--muted);
  text-align:left; padding:.7rem .6rem .45rem; border-bottom:1px solid var(--border); }}
.ledger-table td {{ padding:.62rem .6rem; border-bottom:1px solid var(--dim);
  vertical-align:top; font-size:.98rem; }}
.ledger-table tr:hover td {{ background:rgba(122,96,32,0.05); }}

/* scorecard */
.score-pending, .score-done {{ border:1px solid var(--border); padding:1.8rem 2rem;
  background:rgba(255,255,255,.35); max-width:46rem; }}
.score-pending p, .score-done p {{ max-width:58ch; }}
.score-pending em {{ color:var(--gold); }}
.score-table {{ width:100%; border-collapse:collapse; margin:.8rem 0 1rem; }}
.score-table th {{ font-family:'DM Mono',monospace; font-size:.6rem; font-weight:400;
  letter-spacing:.18em; text-transform:uppercase; color:var(--muted); text-align:left;
  padding:.5rem .4rem; border-bottom:1px solid var(--border); }}
.score-table td {{ padding:.55rem .4rem; border-bottom:1px solid var(--dim); }}
.contested-row td {{ color: var(--navy); font-weight: 600; }}

/* how to read */
.how ol {{ margin:1rem 0 0 1.2rem; max-width:62ch; display:flex; flex-direction:column;
  gap:.7rem; }}
.how em {{ color: var(--gold); }}
.not-predicted {{ margin-top:1.4rem; }}
.not-predicted ul {{ margin:.5rem 0 0 1.2rem; color:var(--muted); max-width:62ch; }}

footer.site {{ padding:2.4rem 0 3rem; }}
footer.site .wordmark {{ font-size:1.1rem; }}
@media (max-width: 700px) {{
  .ledger-table th:nth-child(3), .ledger-table td:nth-child(3) {{ display:none; }}
  .meta-strip {{ gap:1rem 1.6rem; }}
}}
@media print {{
  * {{ -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
  body::before, .corner {{ display: none; }}
  .card, .score-pending, .score-done, .day, tr {{ break-inside: avoid; }}
  .card:hover {{ transform: none; }}
  header.hero {{ padding-top: 1.5rem; }}
  section.block {{ padding: 1.6rem 0; }}
}}
</style>
</head>
<body>
<div class="corner corner-tl"></div>
<div class="corner corner-br"></div>

<header class="hero">
  <div class="wrap">
    <div class="mono gold small eyebrow-line">praevisa · forward ledger · strasbourg part-session</div>
    <div class="wordmark">Prae<span>visa</span></div>
    <h1>Every vote of the 15–18 June 2026 session, predicted
    <em>before it happens</em> — and graded in public after.</h1>
    <div class="rule"></div>
    <div class="meta-strip">
      <div><b>{ledger["n_items"]}</b><span>votes predicted</span></div>
      <div><b>{n_contested}</b><span>contested calls</span></div>
      <div><b>{esc(ledger["generated_at"])}</b><span>ledger cut</span></div>
      <div><b>{esc(ledger["engine_rev"])}</b><span>engine rev · git-timestamped</span></div>
      <div><b>α = {ledger["alpha"]:.1f}</b><span>calibration in force</span></div>
    </div>
  </div>
</header>

<section class="block">
  <div class="wrap">
    <div class="mono gold small eyebrow-line">the calls that carry information</div>
    <p class="lede">Most Parliament votes pass, and a topic-blind baseline predicts
    that. These are the items where a recorded committee vote gives the engine
    something the baseline does not have — including every <b>contested</b> call
    of the week.</p>
    <div class="cards">{featured_html}
    </div>
  </div>
</section>

<section class="block">
  <div class="wrap">
    <div class="mono gold small eyebrow-line">the full ledger — nothing cherry-picked</div>
    <p class="lede">All {ledger["n_items"]} votable items on the published draft
    agenda ({esc(ledger["agenda_last_updated"])}), each stamped with the rail that
    produced it. Items marked <em>baseline</em> share identical numbers by
    construction — they are coverage, not insight, and we say so.</p>
    {''.join(days_html)}
    <div class="not-predicted">
      <div class="mono gold small eyebrow-line">declared out of scope, in advance</div>
      <ul>{not_predicted}</ul>
    </div>
  </div>
</section>

<section class="block">
  <div class="wrap">{scorecard_html(ledger)}</div>
</section>

<section class="block how">
  <div class="wrap">
    <div class="mono gold small eyebrow-line">how to read these numbers</div>
    <ol>
      <li>The percentage is a <em>predicted seat share</em> — the expected share of
      votes cast in favour — not a probability of adoption.</li>
      <li>Each group gets a predicted yes-rate: its recorded committee vote where
      one exists, its historical average otherwise. Seats × rates, summed: that is
      the whole model. No discretionary overrides.</li>
      <li>The second-reading item is a threshold call: overturning the Council
      position takes 361 of 720 members, not a simple majority.</li>
      <li>The flip lever names the one group that could reverse the predicted
      outcome by moving its own voters — the pivot, not the most divided group.</li>
      <li>Grading rules were committed to git before the session: pairing,
      metrics, and subsets are frozen in <span class="mono">praevisa/plenary_forward.py</span>.
      The ledger is append-only.</li>
    </ol>
  </div>
</section>

<footer class="site">
  <div class="wrap">
    <div class="wordmark">Prae<span>visa</span></div>
    <p class="mono dim small" style="margin-top:.6rem">simulation intelligence for
    eu policy · brussels · pre-registered, append-only, graded in public ·
    methodology in the repository alongside this page</p>
  </div>
</footer>
</body>
</html>"""


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(build())
    print(f"wrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
