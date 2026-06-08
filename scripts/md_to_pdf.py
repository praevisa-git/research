"""Minimal, dependency-light Markdown -> PDF renderer (reportlab).

Handles the subset used in our memos: H1/H2/H3, paragraphs, **bold**, `inline code`,
fenced ``` code blocks, bullet/numbered lists, > blockquotes, --- rules, and pipe
tables (with :---: alignment). Not a general Markdown engine — just enough for clean,
professional internal documents.

Usage:  .venv/bin/python scripts/md_to_pdf.py INPUT.md OUTPUT.pdf
"""
import html
import re
import sys

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (HRFlowable, ListFlowable, ListItem, Paragraph,
                                SimpleDocTemplate, Spacer, Table, TableStyle)

INK = colors.HexColor("#1f2933")
ACCENT = colors.HexColor("#1b3a5b")
MUTE = colors.HexColor("#52606d")
RULE = colors.HexColor("#cbd2d9")
HEADBG = colors.HexColor("#1b3a5b")
ZEBRA = colors.HexColor("#f0f3f7")
CODEBG = colors.HexColor("#f4f5f7")

# characters reportlab's WinAnsi core fonts cannot render -> safe equivalents
SANITIZE = {
    "→": "->", "←": "<-", "≈": "~", "−": "-", "–": "-",
    "≥": ">=", "≤": "<=", "≡": "=", "…": "...",
    "’": "'", "‘": "'", "“": '"', "”": '"', " ": " ",
}


def sanitize(t: str) -> str:
    for k, v in SANITIZE.items():
        t = t.replace(k, v)
    # drop anything still not encodable by the core-font encoding
    return t.encode("cp1252", "replace").decode("cp1252")


def inline(t: str) -> str:
    t = html.escape(sanitize(t), quote=False)
    t = re.sub(r"`([^`]+?)`", r'<font face="Courier" size="8.5" color="#9b2c2c">\1</font>', t)
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"(?<!\*)\*([^*\n]+?)\*(?!\*)", r"<i>\1</i>", t)
    return t


def styles():
    ss = getSampleStyleSheet()
    base = ParagraphStyle("body", parent=ss["Normal"], fontName="Helvetica",
                          fontSize=9.5, leading=13.5, textColor=INK, spaceAfter=6)
    return {
        "body": base,
        "h1": ParagraphStyle("h1", parent=base, fontName="Helvetica-Bold", fontSize=19,
                             leading=23, textColor=ACCENT, spaceBefore=4, spaceAfter=4),
        "h2": ParagraphStyle("h2", parent=base, fontName="Helvetica-Bold", fontSize=13,
                             leading=17, textColor=ACCENT, spaceBefore=14, spaceAfter=5),
        "h3": ParagraphStyle("h3", parent=base, fontName="Helvetica-Bold", fontSize=10.5,
                             leading=14, textColor=INK, spaceBefore=9, spaceAfter=3),
        "quote": ParagraphStyle("quote", parent=base, leftIndent=12, textColor=MUTE,
                                fontName="Helvetica-Oblique", borderPadding=(0, 0, 0, 6)),
        "cell": ParagraphStyle("cell", parent=base, fontSize=8.5, leading=11, spaceAfter=0),
        "cellh": ParagraphStyle("cellh", parent=base, fontSize=8.5, leading=11,
                                spaceAfter=0, textColor=colors.white, fontName="Helvetica-Bold"),
        "code": ParagraphStyle("code", parent=base, fontName="Courier", fontSize=8.3,
                               leading=11, textColor=colors.HexColor("#243b53")),
        "small": ParagraphStyle("small", parent=base, fontSize=8, textColor=MUTE),
    }


def _aligns(sep_cells):
    out = []
    for c in sep_cells:
        c = c.strip()
        if c.startswith(":") and c.endswith(":"):
            out.append(TA_CENTER)
        elif c.endswith(":"):
            out.append(TA_RIGHT)
        else:
            out.append(TA_LEFT)
    return out


def build(md: str, S):
    flow = []
    lines = md.splitlines()
    i, n = 0, len(lines)
    while i < n:
        line = lines[i]
        s = line.strip()

        if not s:
            i += 1
            continue

        # fenced code block
        if s.startswith("```"):
            i += 1
            buf = []
            while i < n and not lines[i].strip().startswith("```"):
                buf.append(sanitize(lines[i]))
                i += 1
            i += 1
            code_html = "<br/>".join(html.escape(b, quote=False).replace(" ", "&nbsp;")
                                     for b in buf)
            t = Table([[Paragraph(code_html, S["code"])]], colWidths=[16.6 * cm])
            t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), CODEBG),
                                   ("BOX", (0, 0), (-1, -1), 0.5, RULE),
                                   ("LEFTPADDING", (0, 0), (-1, -1), 8),
                                   ("TOPPADDING", (0, 0), (-1, -1), 6),
                                   ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
            flow += [Spacer(1, 4), t, Spacer(1, 6)]
            continue

        # horizontal rule
        if re.match(r"^---+$", s):
            flow.append(HRFlowable(width="100%", thickness=0.6, color=RULE,
                                   spaceBefore=8, spaceAfter=8))
            i += 1
            continue

        # table (header line, then |---| separator)
        if s.startswith("|") and i + 1 < n and re.match(r"^\|?[\s:|-]+\|?$", lines[i + 1].strip()) \
                and "-" in lines[i + 1]:
            def cells(row):
                return [c.strip() for c in row.strip().strip("|").split("|")]
            header = cells(lines[i])
            aligns = _aligns(cells(lines[i + 1]))
            i += 2
            body = []
            while i < n and lines[i].strip().startswith("|"):
                body.append(cells(lines[i]))
                i += 1
            data = [[Paragraph(inline(c), S["cellh"]) for c in header]]
            for r in body:
                data.append([Paragraph(inline(c), S["cell"]) for c in
                             (r + [""] * (len(header) - len(r)))])
            ncol = len(header)
            tbl = Table(data, colWidths=[16.6 / ncol * cm] * ncol, repeatRows=1)
            st = [("BACKGROUND", (0, 0), (-1, 0), HEADBG),
                  ("GRID", (0, 0), (-1, -1), 0.4, RULE),
                  ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                  ("LEFTPADDING", (0, 0), (-1, -1), 5),
                  ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                  ("TOPPADDING", (0, 0), (-1, -1), 4),
                  ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                  ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, ZEBRA])]
            amap = {TA_LEFT: "LEFT", TA_CENTER: "CENTER", TA_RIGHT: "RIGHT"}
            for ci, al in enumerate(aligns):
                st.append(("ALIGN", (ci, 0), (ci, -1), amap[al]))
            tbl.setStyle(TableStyle(st))
            flow += [Spacer(1, 4), tbl, Spacer(1, 8)]
            continue

        # headings
        m = re.match(r"^(#{1,3})\s+(.*)$", s)
        if m:
            lvl = len(m.group(1))
            flow.append(Paragraph(inline(m.group(2)), S[f"h{lvl}"]))
            if lvl == 1:
                flow.append(HRFlowable(width="100%", thickness=1.1, color=ACCENT,
                                       spaceBefore=3, spaceAfter=8))
            i += 1
            continue

        # blockquote
        if s.startswith(">"):
            buf = []
            while i < n and lines[i].strip().startswith(">"):
                buf.append(lines[i].strip()[1:].strip())
                i += 1
            flow.append(Paragraph(inline(" ".join(buf)), S["quote"]))
            flow.append(Spacer(1, 4))
            continue

        # lists (bullet or numbered); join soft-wrapped continuation lines
        if re.match(r"^(\-|\d+\.)\s+", s):
            parts, bullet = [], "bullet"
            cur = None
            while i < n:
                st_ln = lines[i].strip()
                m = re.match(r"^(\-|\d+\.)\s+(.*)$", st_ln)
                if m:
                    if re.match(r"^\d+\.", st_ln):
                        bullet = "1"
                    cur = [m.group(2)]
                    parts.append(cur)
                    i += 1
                elif (st_ln and cur is not None and lines[i].startswith(" ")
                      and not re.match(r"^(#{1,3}\s|\||>|```|---+$)", st_ln)):
                    cur.append(st_ln)          # continuation of the current item
                    i += 1
                else:
                    break
            items = [ListItem(Paragraph(inline(" ".join(p)), S["body"]), leftIndent=14)
                     for p in parts]
            flow.append(ListFlowable(items, bulletType=bullet, start="1" if bullet == "1" else None,
                                     bulletColor=ACCENT, leftIndent=10, bulletFontSize=8))
            flow.append(Spacer(1, 4))
            continue

        # paragraph (gather until blank)
        buf = []
        while i < n and lines[i].strip() and not re.match(r"^(#{1,3}\s|\||>|```|---+$|(\-|\d+\.)\s)", lines[i].strip()):
            buf.append(lines[i].strip())
            i += 1
        flow.append(Paragraph(inline(" ".join(buf)), S["body"]))
    return flow


def main():
    src, dst = sys.argv[1], sys.argv[2]
    md = open(src, encoding="utf-8").read()
    S = styles()
    doc = SimpleDocTemplate(dst, pagesize=A4, leftMargin=2.2 * cm, rightMargin=2.2 * cm,
                            topMargin=2 * cm, bottomMargin=2 * cm,
                            title="Praevisa — Technical Briefing")
    doc.build(build(md, S))
    print(f"wrote {dst}")


if __name__ == "__main__":
    main()
