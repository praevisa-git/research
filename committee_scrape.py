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

import re
import sys
import urllib.request
from dataclasses import dataclass, field

import pdfplumber

UA = {"User-Agent": "Mozilla/5.0 (Praevisa scoping spike)"}
GROUPS = ["Verts/ALE", "The Left", "GUE/NGL", "PPE", "S&D", "Renew",
          "ECR", "PfE", "ESN", "NI"]   # longest-first so "The Left" beats "NI"

REF_RE = re.compile(r"([A-Z]{2,6}/\d+/\d+)\s*[–-]\s*(\d{4}/\d+\([A-Z]+\))")
RAPP_RE = re.compile(r"Rapporteur[s]?:\s*(.+)")
TALLY_RE = re.compile(r"^(\d+)\s+([+\-0])$")


@dataclass
class CommitteeVote:
    ref: str
    procedure: str
    rapporteur: str
    subject: str
    tally: dict = field(default_factory=dict)        # {'+':n,'-':n,'0':n}
    votes: list = field(default_factory=list)         # [(group, mep, choice)]

    def extracted(self) -> int:
        return len(self.votes)

    def declared(self) -> int:
        return sum(self.tally.values())


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

    def flush() -> None:
        if cur is None or choice is None:
            return
        for group, parts in buffer.items():
            joined = " ".join(parts)
            for name in (n.strip() for n in joined.split(",") if n.strip()):
                cur.votes.append((group, name, choice))
        buffer.clear()

    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        m_ref = REF_RE.search(line)
        if m_ref:                                     # new vote block begins
            flush()
            cur = CommitteeVote(ref=m_ref.group(1), procedure=m_ref.group(2),
                                rapporteur="", subject="")
            votes.append(cur)
            choice = last_group = None
            continue
        if cur is None:
            continue                                  # preamble before the first ref
        m_rapp = RAPP_RE.match(line)
        if m_rapp and not cur.rapporteur:
            cur.rapporteur = m_rapp.group(1).strip()
            continue
        m_tally = TALLY_RE.match(line)
        if m_tally:
            flush()                                   # close the previous choice block
            choice = m_tally.group(2)
            cur.tally[choice] = int(m_tally.group(1))
            last_group = None
            continue
        if line.startswith("Key to symbols") or line == "EN EN":
            flush()
            choice = None
            continue
        if not cur.subject and choice is None and not line.startswith("Rapporteur"):
            cur.subject = line                        # subject line between rapporteur and tally
            continue
        if choice is not None:                        # inside a +/-/0 block: MEP names
            g, rest = _split_group_line(line)
            if g:
                last_group = g
            buffer.setdefault(last_group or "?", []).append(rest)
    flush()
    return votes


def main() -> None:
    committee = sys.argv[1] if len(sys.argv) > 1 else "ECON"
    pdfs = list_vote_pdfs(committee)
    print(f"{committee}: found {len(pdfs)} RCV result PDFs on the votes page")
    if not pdfs:
        return
    url = pdfs[2] if len(pdfs) > 2 else pdfs[0]        # skip the newest 'Votes' summaries
    print(f"parsing: {url.rsplit('/', 1)[-1]}")
    data = fetch(url, binary=True)
    tmp = "/tmp/_committee_rcv.pdf"
    with open(tmp, "wb") as f:
        f.write(data)
    votes = parse_pdf(tmp)
    print(f"extracted {len(votes)} vote(s) from the meeting PDF\n")
    for v in votes:
        ok = "ok" if v.extracted() == v.declared() else f"MISMATCH (decl {v.declared()})"
        print(f"  {v.ref}  {v.procedure}")
        print(f"    rapporteur : {v.rapporteur or '(none)'}")
        print(f"    subject    : {v.subject[:60]}")
        print(f"    tally      : {v.tally}  | MEPs parsed: {v.extracted()} [{ok}]")
        by_g: dict = {}
        for g, _, c in v.votes:
            by_g.setdefault(g, {"+": 0, "-": 0, "0": 0})[c] += 1
        print(f"    by group   : {by_g}")
        print()


if __name__ == "__main__":
    main()
