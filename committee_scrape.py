# Praevisa — committee-vote scoping spike
"""Proof that EP committee roll-call votes assemble into structured data.

There is no clean committee-vote API (HowTheyVote and the EP Open Data portal are
plenary-only). But each committee publishes per-meeting roll-call results as PDFs
at europarl.europa.eu/cmsdata/. This script proves the full pipeline end-to-end:

  1. scrape a committee's votes page for the RCV PDF links
  2. download one PDF
  3. parse it into records: {ref, procedure, rapporteur, subject, tally, per-MEP votes}

This is a SPIKE — the parser handles the common ECON layout, not every edge case.
Its job is to confirm the data is reachable and structured enough to build on.

Run: .venv/bin/python committee_scrape.py
"""

from __future__ import annotations

import json
import re
import sys
import urllib.request
from dataclasses import dataclass, field

import pdfplumber

UA = {"User-Agent": "Mozilla/5.0 (Praevisa scoping spike)"}
GROUPS = ["Verts/ALE", "The Left", "GUE/NGL", "PPE", "S&D", "Renew",
          "ECR", "PfE", "ESN", "NI"]   # longest-first so "The Left" beats "NI"

# Two committee-ref layouts:
#  - committee-led: "ECON/10/01016 – 2023/0112(COD)" or joint "CJ12/10/02943 - 2025/0131(COD)"
#  - procedure-led (summary PDFs): line starts "2023/0210(COD) COM(2023)0367 – C9-..."
REF_RE = re.compile(r"([A-Z0-9]{2,8}/\d+/\d+)\s*[–-]\s*(\d{4}/\d+\([A-Z]+\))")
PROC_RE = re.compile(r"^(\d{4}/\d+\([A-Z]+\))")          # procedure-led summary layout
RAPP_RE = re.compile(r"Rapporteur[s]?:\s*(.+)")
TALLY_RE = re.compile(r"^(\d+)\s+([+\-0])$")
# Lines that are never part of a vote title (legend, headers, page numbers).
SKIP_TITLE = re.compile(r"^(Committee on |Key to symbols|EN EN|[+\-0] :|\d+\s*$|PE\d)")


@dataclass
class CommitteeVote:
    ref: str
    procedure: str
    rapporteur: str
    subject: str
    title: str = ""
    secret: bool = False
    tally: dict = field(default_factory=dict)        # {'+':n,'-':n,'0':n}
    votes: list = field(default_factory=list)         # [(group, mep, choice)]

    def extracted(self) -> int:
        return len(self.votes)

    def declared(self) -> int:
        return sum(self.tally.values())

    def reconciled(self) -> bool:
        if self.declared() == 0:
            return False
        return self.secret or self.extracted() == self.declared()


def fetch(url: str, binary: bool = False):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=40) as r:
        return r.read() if binary else r.read().decode("utf-8", "replace")


def list_vote_pdfs(committee: str) -> list[str]:
    html = fetch(f"https://www.europarl.europa.eu/committees/en/{committee.lower()}/meetings/votes")
    return re.findall(r'https://www\.europarl\.europa\.eu/cmsdata/[^"\']*\.pdf', html)


def _split_group_line(line: str) -> tuple[str | None, str]:
    for g in GROUPS:
        if line.startswith(g):
            return g, line[len(g):].strip()
    return None, line


def parse_pdf(path: str) -> list[CommitteeVote]:
    with pdfplumber.open(path) as pdf:
        lines: list[str] = []
        for pg in pdf.pages:
            lines.extend((pg.extract_text() or "").splitlines())

    votes: list[CommitteeVote] = []
    cur: CommitteeVote | None = None
    choice: str | None = None
    last_group: str | None = None
    # Buffer raw name text per group for the current +/-/0 block, so names that
    # wrap across a line break ("Markus\nFerber") are joined BEFORE comma-splitting.
    buffer: dict[str, list[str]] = {}
    title_buf: list[str] = []                          # title text seen between votes

    def flush() -> None:
        if cur is None or choice is None:
            return
        for group, parts in buffer.items():
            joined = " ".join(parts)
            for name in (n.strip() for n in joined.split(",") if n.strip()):
                cur.votes.append((group, name, choice))
        buffer.clear()

    def start(ref: str, proc: str) -> CommitteeVote:
        nonlocal cur, choice, last_group, title_buf
        flush()
        cur = CommitteeVote(ref=ref, procedure=proc, rapporteur="", subject="",
                            title=" ".join(title_buf).strip())
        votes.append(cur)
        choice = last_group = None
        title_buf = []
        return cur

    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        m_ref = REF_RE.search(line)
        m_proc = PROC_RE.match(line) if not m_ref else None
        if m_ref:                                      # committee/joint ref layout
            start(m_ref.group(1), m_ref.group(2))
            continue
        if m_proc:                                     # procedure-led summary layout
            start(m_proc.group(1), m_proc.group(1))
            continue
        m_rapp = RAPP_RE.match(line)
        if m_rapp:
            if cur is None or cur.tally:               # ref-less layout, or next vote
                start("", "")
            if not cur.rapporteur:
                cur.rapporteur = m_rapp.group(1).strip()
            continue
        m_tally = TALLY_RE.match(line)
        if m_tally and cur is not None:
            flush()                                    # close the previous choice block
            choice = m_tally.group(2)
            cur.tally[choice] = int(m_tally.group(1))
            last_group = None
            continue
        if line.startswith("Key to symbols") or line == "EN EN":
            flush()
            choice = None
            cur = None                                 # vote closed; next title accrues
            continue
        if cur is not None and choice is None and not cur.subject:
            cur.subject = line                         # subject between rapporteur and tally
            if "secret vote" in line.lower():
                cur.secret = True
            continue
        if choice is not None:                         # inside a +/-/0 block: MEP names
            g, rest = _split_group_line(line)
            if g:
                last_group = g
            buffer.setdefault(last_group or "?", []).append(rest)
            continue
        if cur is None and not SKIP_TITLE.match(line):  # between votes: collect title
            title_buf.append(line)
    flush()
    return votes


def build_corpus(committee: str, max_pdfs: int | None = None) -> dict:
    """Download and parse every RCV PDF on a committee's votes page into one corpus."""
    pdfs = list_vote_pdfs(committee)
    if max_pdfs:
        pdfs = pdfs[:max_pdfs]
    print(f"{committee}: {len(pdfs)} RCV PDFs on the votes page — parsing all")
    records, n_pdf_ok, n_pdf_empty = [], 0, 0
    for i, url in enumerate(pdfs, 1):
        name = url.rsplit("/", 1)[-1]
        try:
            blob = fetch(url, binary=True)
            with open("/tmp/_corpus.pdf", "wb") as f:
                f.write(blob)
            votes = parse_pdf("/tmp/_corpus.pdf")
        except Exception as e:                        # noqa: BLE001 — spike resilience
            print(f"  [{i:2}/{len(pdfs)}] {name[:40]:42} ERR {type(e).__name__}")
            continue
        parsed = [v for v in votes if v.declared() > 0]
        (n_pdf_ok := n_pdf_ok + 1) if parsed else (n_pdf_empty := n_pdf_empty + 1)
        for v in parsed:
            records.append({
                "committee": committee, "source": url,
                "ref": v.ref, "procedure": v.procedure, "rapporteur": v.rapporteur,
                "title": v.title, "subject": v.subject, "secret": v.secret,
                "tally": v.tally, "reconciled": v.reconciled(),
                "votes": [{"group": g, "mep": m, "choice": c} for g, m, c in v.votes],
            })
        flag = f"{len(parsed)} votes" if parsed else "no votes (broken/empty)"
        print(f"  [{i:2}/{len(pdfs)}] {name[:40]:42} {flag}")

    decided = [r for r in records if not r["secret"]]               # named roll-calls
    reconciled = [r for r in decided if r["reconciled"]]
    secret = [r for r in records if r["secret"]]
    procs = {r["procedure"] for r in records if "(" in r["procedure"]}
    rapp = sum(1 for r in records if r["rapporteur"])
    print("\n— corpus summary —")
    print(f"  PDFs with votes / empty : {n_pdf_ok} / {n_pdf_empty}")
    print(f"  vote records            : {len(records)}  ({len(procs)} unique procedures)")
    print(f"  rapporteur captured     : {rapp}/{len(records)}")
    print(f"  secret (no names, ok)   : {len(secret)}")
    print(f"  roll-call reconciled    : {len(reconciled)}/{len(decided)} "
          f"= {len(reconciled)/max(1,len(decided)):.0%} of named votes")
    return {"committee": committee, "n_records": len(records), "records": records}


def main() -> None:
    committee = sys.argv[1] if len(sys.argv) > 1 else "ECON"
    corpus = build_corpus(committee)
    out = f"committee_corpus_{committee}.json"
    with open(out, "w") as f:
        json.dump(corpus, f, ensure_ascii=False, indent=1)
    print(f"\nwrote {out} ({corpus['n_records']} vote records)")


if __name__ == "__main__":
    main()
