"""
The one set of building blocks every PDF report is made from.

  - embedded OFL fonts only (IBM Plex Sans + Plex Mono, vendored in ./fonts, sha256 recorded); the document never references a base-14 font
  - restrained palette: ink + one table-header colour; status colours live only inside badges, result cells and the coverage bar
  - A4, 18 mm margins, a fixed 174 mm grid, column presets per table type (no auto widths), every cell a sanitised, escaped Paragraph
  - running header and two-line footer on every page, "Page X of Y"
  - a closed status vocabulary with one precedence (BLOCKED > FAIL > UNKNOWN > WARN > PASS) and `assert_reconciled`
  - deterministic output: `render_bytes` fixes reportlab's invariant mode and SOURCE_DATE_EPOCH (from the run's `generated_at`); there is no clock here
  - metadata and outline bookmarks; the canonical inputs JSON is written next to each PDF
"""
from __future__ import annotations

import calendar
import hashlib
import io
import json
import os
import re
import threading
import time
from contextlib import contextmanager
from pathlib import Path

from reportlab.graphics.shapes import Drawing, Rect, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import CondPageBreak, LongTable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.pdf.run_context import COMPLETED, new_run_context
from app.pdf.text import esc

TEMPLATE_VERSION = "3.0"
ENGINE_VERSION = "1.0.0"
FONT_DIR = Path(__file__).parent / "fonts"
SANS, SANS_BOLD, SANS_ITALIC, SANS_BOLDITALIC = "Plex", "Plex-Bold", "Plex-Italic", "Plex-BoldItalic"
MONO, MONO_BOLD = "PlexMono", "PlexMono-Bold"
_FONT_FILES = {SANS: "IBMPlexSans-Regular.ttf", SANS_BOLD: "IBMPlexSans-Bold.ttf", SANS_ITALIC: "IBMPlexSans-Italic.ttf", SANS_BOLDITALIC: "IBMPlexSans-BoldItalic.ttf",
               MONO: "IBMPlexMono-Regular.ttf", MONO_BOLD: "IBMPlexMono-Bold.ttf"}

PAGE_W, PAGE_H = A4
MARGIN = 18 * mm                                                     # every side
FRAME_PAD = 6                                                        # reportlab's default Frame padding; the document margins are reduced by it
CONTENT_W = PAGE_W - 2 * MARGIN                                      # 174 mm
CONTENT_MM = 174
ROWS_PER_TABLE = 200
CHUNK_ABOVE = 1000                                                   # more rows than this are cut in chunks of ROWS_PER_TABLE
LONGTABLE_ABOVE = 50
MAX_CELL_CHARS = 600
MAX_CELL_LINES = 12                                                  # a cell taller than this is truncated, so a row is never taller than the frame

# ── palette (B2) ──────────────────────────────────────────────────────────────
INK = colors.HexColor("#1F2933")
MUTED = colors.HexColor("#5B6770")
RULE = colors.HexColor("#D5DBE1")
HEADER_FILL = colors.HexColor("#1F3A5F")
ZEBRA = colors.HexColor("#F5F7FA")
PASS, WARN, FAIL, UNKNOWN, BLOCKED, TEMPLATE = "PASS", "WARN", "FAIL", "UNKNOWN", "BLOCKED", "TEMPLATE ISSUE"
PRECEDENCE = (BLOCKED, FAIL, UNKNOWN, WARN, TEMPLATE, PASS)   # worst wins; a template issue ranks below WARN and above PASS
STATUS_FILL = {PASS: "#E6F4EA", WARN: "#FFF4E0", FAIL: "#FDE7E7", UNKNOWN: "#ECEBFA", BLOCKED: "#2B2B2B", TEMPLATE: "#EEF0F2"}
STATUS_TEXT = {PASS: "#1E6B34", WARN: "#8A5300", FAIL: "#A61B1B", UNKNOWN: "#3F3A8C", BLOCKED: "#FFFFFF", TEMPLATE: "#4A5560"}
STATUS_LABEL = {PASS: "All recorded checks passed", WARN: "Warnings — action required", FAIL: "Failed — see exceptions", UNKNOWN: "Checks incomplete", BLOCKED: "Blocked"}
SEVERITIES = ("critical", "high", "medium", "low", "info")


def TS(cmds: list) -> TableStyle:
    """A TableStyle that also sets the table's own font to the embedded one (reportlab's default is Helvetica, which would be referenced from the PDF)."""
    return TableStyle([("FONTNAME", (0, 0), (-1, -1), SANS)] + list(cmds))


def plural(n, word: str, many: str | None = None) -> str:
    """"1 file", "3 files", "0 files"."""
    return f"{n} {word if n == 1 else (many or word + 's')}"


def _c(hexstr):
    return colors.HexColor(hexstr)


def _ink(status):
    """Text colour for a status shown on a light surface (BLOCKED's own text is white, so on a light surface it uses the ink colour)."""
    return INK if status == BLOCKED else _c(STATUS_TEXT[status])


# ── column presets (mm, each sums to the 174 mm frame) ───────────────────────
COLUMNS = {
    "kv": (46, 128),
    "metric": (112, 62),
    "two": (50, 124),
    "three": (46, 66, 62),
    "signoff": (44, 44, 44, 42),
    "overflow": (12, 50, 112),
    "package": (74, 100),                                   # File | sha256 (64 characters in mono 7 pt on ONE line)
    "sample": (30, 90, 24, 30),                             # Item | Observation | Severity | Status
}


class ReportIntegrityError(ValueError):
    """The inputs contradict themselves (counts that do not add up, an unknown status); nothing is rendered from them."""


# ── fonts ─────────────────────────────────────────────────────────────────────
_fonts_lock = threading.Lock()
_fonts_ready = False
_glyphs: set | None = None


def register_fonts() -> None:
    global _fonts_ready, _glyphs
    with _fonts_lock:
        if _fonts_ready:
            return
        for name, filename in _FONT_FILES.items():
            pdfmetrics.registerFont(TTFont(name, str(FONT_DIR / filename)))
        pdfmetrics.registerFontFamily(SANS, normal=SANS, bold=SANS_BOLD, italic=SANS_ITALIC, boldItalic=SANS_BOLDITALIC)
        pdfmetrics.registerFontFamily(MONO, normal=MONO, bold=MONO_BOLD, italic=MONO, boldItalic=MONO_BOLD)
        _glyphs = set(pdfmetrics.getFont(SANS).face.charToGlyph) & set(pdfmetrics.getFont(MONO).face.charToGlyph)
        # reportlab's own defaults (canvas, drawings) name a base-14 font; point them at the embedded one so no base-14 font is ever referenced
        from reportlab import rl_config
        from reportlab.graphics import shapes
        rl_config.canvas_basefontname = SANS
        shapes.STATE_DEFAULTS["fontName"] = SANS
        _fonts_ready = True


def font_hashes() -> dict:
    """{file name: sha256} of the vendored fonts, recorded in the inputs so a re-render can prove it used the same fonts."""
    return {_FONT_FILES[n]: hashlib.sha256((FONT_DIR / _FONT_FILES[n]).read_bytes()).hexdigest() for n in sorted(_FONT_FILES)}


def font_hash() -> str:
    return hashlib.sha256(json.dumps(font_hashes(), sort_keys=True).encode()).hexdigest()


# ── text helpers ──────────────────────────────────────────────────────────────
def natural_key(value) -> list:
    """Sort key that orders f2 before f10 and never compares a str with an int."""
    return [(0, int(p), "") if p.isdigit() else (1, 0, p.lower()) for p in re.split(r"(\d+)", str(value)) if p != ""]


def clean(value) -> str:
    """Text for the page: control characters dropped, and any character the embedded fonts have no glyph for (emoji, Hebrew ...) shown as '?', never as a box."""
    register_fonts()
    text = "" if value is None else str(value)
    out = []
    for ch in text:
        o = ord(ch)
        if ch == "\n" or o in _glyphs:
            out.append(ch)
        elif o >= 32 and o != 0x200B:
            out.append("?")
    return "".join(out)


ZWSP = "​"
_BREAK_AFTER = re.compile(r"([/._\-:])")
_LONG_HEX = re.compile(r"(sha256:)?[0-9a-fA-F]{32,}")


def is_path_like(token: str) -> bool:
    """A file path or URL: a token with a "/" that is not a ratio ("3/4"), a fraction word ("and/or", "N/A") or a hash."""
    if "/" not in token or _LONG_HEX.fullmatch(token) or not re.search(r"[A-Za-z]", token):
        return False
    return len(token) >= 40 or "." in token or token.count("/") >= 2 or len(token) >= 12


def _width_pt(token: str, font: str, size: float) -> float:
    from reportlab.pdfbase.pdfmetrics import stringWidth
    return stringWidth(token, font, size)


def breakable(text: str, min_len: int = 40, avail_pt: float | None = None, font: str | None = None, size: float = 8.5) -> str:
    """Break opportunities (zero-width spaces) after / . _ - : in a PATH or URL, so reportlab can only wrap it at a separator, never in the middle of a segment.
    Applied to a path that is long (40+ characters) or, when the cell's usable width is known (`avail_pt`), to any path that does not fit on one line of it. A path that fits,
    a hash, a plain name or a ratio is left whole, with nothing invisible in it, so it reads and copies as written."""
    out = []
    for token in re.split(r"(\s+)", text):
        if token and not token.isspace() and "/" in token and not _LONG_HEX.fullmatch(token):
            needs = len(token) >= min_len or (avail_pt is not None and is_path_like(token) and _width_pt(token, font or SANS, size) > avail_pt)
            if needs:
                token = _BREAK_AFTER.sub(lambda m: m.group(1) + ZWSP, token)
        out.append(token)
    return "".join(out)


def mono(value, size: float = 8, wrap: bool = True, avail_pt: float | None = None) -> str:
    """Markup for a path / id / hash / rule id / command in the embedded mono face. wrap=False keeps it unbroken (a hash in a sign-off)."""
    text = clean(value)
    return f"<font name='{MONO}' size='{size}'>{esc(breakable(text, avail_pt=avail_pt, font=MONO, size=size) if wrap else text)}</font>"


def short_hash(digest: str, n: int = 16) -> str:
    return str(digest).replace("sha256:", "")[:n]


PLACEHOLDER = re.compile(r"\[(COMPLETE MANUALLY|VERIFY)[^\]]*\]")


class Overflow:
    """Collects the full text of every truncated cell so it can be printed in an appendix ("… (full text: Appendix E, row 3)")."""

    def __init__(self, letter: str = "E"):
        self.letter = letter
        self.items: list = []

    def add(self, where: str, full: str) -> int:
        self.items.append((where, full))
        return len(self.items)

    def flowables(self) -> list:
        if not self.items:
            return []
        rows = [["#", "Where", "Full text"]] + [[i + 1, w, t[:3000]] for i, (w, t) in enumerate(self.items)]
        return heading(f"Appendix {self.letter}. Full text of truncated cells") + table(rows, "overflow", split_in_row=True, num_cols=(0,))


def _limit(width_mm: float, size: float = 8.5) -> int:
    per_line = max(8, int(width_mm * 2.83465 / (size * 0.78)))
    return min(MAX_CELL_CHARS, per_line * MAX_CELL_LINES)


# ── styles ────────────────────────────────────────────────────────────────────
def _style(name, **kw) -> ParagraphStyle:
    base = dict(fontName=SANS, fontSize=9.5, leading=13, textColor=INK, splitLongWords=1)
    base.update(kw)
    return ParagraphStyle(name, **base)


_styles_cache: dict | None = None


def styles() -> dict:
    global _styles_cache
    register_fonts()
    if _styles_cache is None:
        _styles_cache = {
            "title": _style("H1", fontName=SANS_BOLD, fontSize=20, leading=24, spaceAfter=4),
            "subtitle": _style("Subtitle", fontSize=10, leading=14, textColor=MUTED, spaceAfter=10),
            "h2": _style("H2", fontName=SANS_BOLD, fontSize=13, leading=16, spaceBefore=14, spaceAfter=6),
            "h3": _style("H3", fontName=SANS_BOLD, fontSize=10.5, leading=13, spaceBefore=8, spaceAfter=3),
            "body": _style("Body", spaceAfter=5),
            "small": _style("Small", fontSize=8.5, leading=11.5, textColor=MUTED, spaceAfter=3),
            "bullet": _style("Bullet", leftIndent=10, bulletIndent=2, spaceAfter=1.5, bulletFontName=SANS),
            "placeholder": _style("Placeholder", fontName=SANS_ITALIC, textColor=MUTED, spaceAfter=5),
            "cell": _style("Cell", fontSize=8.5, leading=11, alignment=TA_LEFT),
            "cell_num": _style("CellNum", fontSize=8.5, leading=11, alignment=TA_RIGHT),
            "cell_ph": _style("CellPh", fontName=SANS_ITALIC, fontSize=8.5, leading=11, textColor=MUTED),
            "cell_head": _style("CellHead", fontName=SANS_BOLD, fontSize=8.5, leading=11, textColor=colors.white),
            "badge": _style("Badge", fontName=SANS_BOLD, fontSize=8, leading=10, alignment=TA_CENTER),
            "score_n": _style("ScoreN", fontName=SANS_BOLD, fontSize=20, leading=24, alignment=TA_CENTER),
            "score_l": _style("ScoreL", fontSize=8.5, leading=11, textColor=MUTED, alignment=TA_CENTER),
        }
    return _styles_cache


# ── status model (B3) ─────────────────────────────────────────────────────────
def worst(*statuses: str) -> str:
    """The worst of the given statuses by precedence BLOCKED > FAIL > UNKNOWN > WARN > PASS. An unknown status is an error, never a pass."""
    found = list(statuses)
    for s in found:
        if s not in PRECEDENCE:
            raise ReportIntegrityError(f"unknown status {s!r}")
    return next((p for p in PRECEDENCE if p in found), UNKNOWN)


def rank(status: str) -> int:
    return PRECEDENCE.index(status)


def category_to_badge(status: str) -> str:
    return {"pass": PASS, "ran": PASS, "warn": WARN, "fail": FAIL, "blocked": BLOCKED}.get(str(status), UNKNOWN)


def assert_reconciled(total: int, parts: dict, what: str = "counts") -> None:
    """The parts add up to the total, asserted before anything is rendered."""
    added = sum(int(v) for v in parts.values())
    if added != int(total):
        raise ReportIntegrityError(f"{what} do not reconcile: {' + '.join(f'{k} {v}' for k, v in parts.items())} = {added}, but the total is {total}")


# ── flowables ─────────────────────────────────────────────────────────────────
def P(text, style="body") -> Paragraph:
    """A paragraph from PLAIN text (cleaned, escaped, long tokens made breakable). A bracketed placeholder ("[COMPLETE MANUALLY ...]") takes the placeholder style."""
    text = "" if text is None else str(text)
    if style == "body" and PLACEHOLDER.fullmatch(text.strip()):
        style = "placeholder"
    return Paragraph(esc(breakable(clean(text))), styles()[style])


def PM(markup, style="body") -> Paragraph:
    return Paragraph(markup, styles()[style])


def heading(text: str, level: int = 2) -> list:
    """A section heading (H2) or sub-heading (H3). H2 is a PDF bookmark. `compose` keeps it with the flowables that follow."""
    p = Paragraph(esc(clean(text)), styles()[f"h{level}"])
    if level == 2:
        p._outline = (clean(text)[:90], 0)
    return [p]


def bullets(items, style="bullet") -> list:
    return [Paragraph(esc(breakable(clean(i))), styles()[style], bulletText="•") for i in items]


def badge(status: str, width_mm: float = 34) -> Table:
    """A text badge in a restrained rounded rectangle; the only place status colour sits outside a result cell."""
    t = Table([[Paragraph(f"<font color='{STATUS_TEXT[status]}'>{esc(status)}</font>", styles()["badge"])]], colWidths=[width_mm * mm], rowHeights=[6 * mm], hAlign="LEFT")
    t.setStyle(TS([("BACKGROUND", (0, 0), (-1, -1), _c(STATUS_FILL[status])), ("ROUNDEDCORNERS", [2, 2, 2, 2]), ("BOX", (0, 0), (-1, -1), 0.5, _ink(status)),
                           ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 1), ("BOTTOMPADDING", (0, 0), (-1, -1), 1)]))
    return t


def _need(data: list, widths_pt: list, nrows: int, pad_x: float = 8, pad_y: float = 6) -> float:
    """Height of the first `nrows` rows, measured on the cell paragraphs (never by wrapping the Table, which would replace its cells with lists)."""
    total = 0.0
    for row in data[:nrows]:
        total += max((c.wrap(w - pad_x, 100000)[1] if hasattr(c, "wrap") else 11) for c, w in zip(row, widths_pt)) + pad_y
    return total


def _widths(preset_or_widths, ncols: int) -> list:
    widths = COLUMNS[preset_or_widths] if isinstance(preset_or_widths, str) else tuple(preset_or_widths)
    if len(widths) != ncols:
        raise ReportIntegrityError(f"column preset has {len(widths)} widths for {ncols} columns")
    scale = CONTENT_MM / float(sum(widths))
    return [w * scale for w in widths]


def table(rows: list, columns, *, header: bool = True, mono_cols: tuple = (), status_col: int | None = None, num_cols: tuple = (), status_map: dict | None = None,
          overflow: Overflow | None = None, where: str = "table", split_in_row: bool = False) -> list:
    """The one table builder. Every cell is a Paragraph in an embedded font with cleaned, escaped text; widths come from a preset that sums to the frame; the header repeats;
    more than LONGTABLE_ABOVE rows use LongTable; more than CHUNK_ABOVE rows are cut in chunks of ROWS_PER_TABLE. A cell over MAX_CELL_CHARS (or too tall) is truncated
    with a pointer to the overflow appendix. A status_col cell gets the result colours (text from STATUS_* or via status_map). Numbers right-aligned, text left."""
    if not rows:
        return []
    st = styles()
    ncols = len(rows[0])
    widths_mm = _widths(columns, ncols)
    head, body = (rows[0], rows[1:]) if header else (None, rows)
    def status_of(v):
        s = (status_map or {}).get(str(v), str(v).upper())
        if s not in STATUS_FILL:                                                    # "PASS — No findings (...)": the leading status colours the cell
            lead = s.split(" — ")[0]
            s = lead if lead in STATUS_FILL else s
        return s

    def cell(value, col, row_no, is_head=False):
        if hasattr(value, "wrap"):
            return value
        text = "" if value is None else str(value)
        if not is_head and not text.strip():
            text = "Not recorded"                    # an empty or missing value is never printed as a blank cell
        if is_head:
            return Paragraph(esc(clean(text)), st["cell_head"])
        if len(text) > _limit(widths_mm[col]):
            n = overflow.add(f"{where}, row {row_no}, column {col + 1}", text) if overflow else 0
            ref = f"full text: Appendix {overflow.letter}, row {n}" if overflow else "truncated"
            text = text[: _limit(widths_mm[col]) - 45].rstrip() + f"… ({ref})"
        if status_col == col and status_of(text) in STATUS_FILL:
            s = status_of(text)
            ink = "#1F2933" if s == BLOCKED else STATUS_TEXT[s]
            return Paragraph(f"<font name='{SANS_BOLD}' color='{ink}'>{esc(clean(text))}</font>", st["cell"])
        avail = widths_mm[col] * mm - 8                      # usable width: the cell padding is 4 pt each side
        if col in mono_cols:
            return Paragraph(mono(text, avail_pt=avail), st["cell"])
        if PLACEHOLDER.fullmatch(text.strip()):
            return Paragraph(esc(clean(text)), st["cell_ph"])
        return Paragraph(esc(breakable(clean(text), avail_pt=avail, font=SANS, size=8.5)), st["cell_num"] if col in num_cols else st["cell"])

    chunk_size = ROWS_PER_TABLE if len(body) > CHUNK_ABOVE else max(len(body), 1)
    chunks = [body[i:i + chunk_size] for i in range(0, len(body), chunk_size)] or [[]]
    out: list = []
    numbered = 0
    for chunk in chunks:
        data = ([[cell(v, c, 0, True) for c, v in enumerate(head)]] if head else []) + [[cell(v, c, numbered + i + 1) for c, v in enumerate(r)] for i, r in enumerate(chunk)]
        numbered += len(chunk)
        cls = LongTable if len(data) > LONGTABLE_ABOVE else Table
        t = cls(data, colWidths=[w * mm for w in widths_mm], repeatRows=1 if head else 0, splitByRow=1, splitInRow=1 if split_in_row else 0)
        first = 1 if head else 0
        cmds = [("GRID", (0, 0), (-1, -1), 0.5, RULE), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]
        if head:
            cmds.append(("BACKGROUND", (0, 0), (-1, 0), HEADER_FILL))
        if len(data) > first:
            cmds.append(("ROWBACKGROUNDS", (0, first), (-1, -1), [colors.white, ZEBRA]))
        if status_col is not None:
            for i, r in enumerate(chunk, first):
                s = status_of(r[status_col])
                if s in STATUS_FILL:
                    cmds.append(("BACKGROUND", (status_col, i), (status_col, i), _c(STATUS_FILL[s])))
        t.setStyle(TS(cmds))
        # what must stay together with the heading above: the header row and the first two body rows
        t._need_h = _need(data, [w * mm for w in widths_mm], first + 2)
        out += [t, Spacer(1, 3 * mm)]
    return out


def key_value(pairs: list, mono_values: tuple = ()) -> list:
    """The cover info table: label / value, no header row. Values whose label is in `mono_values` are set in the mono face."""
    st = styles()
    data = [[Paragraph(esc(clean(k)), st["cell"]), Paragraph(mono(v if str(v if v is not None else "").strip() else "Not recorded") if k in mono_values
                                                               else esc(breakable(clean(v if str(v if v is not None else "").strip() else "Not recorded"))), st["cell"])] for k, v in pairs]
    t = Table(data, colWidths=[w * mm for w in _widths("kv", 2)], splitByRow=1)
    t.setStyle(TS([("LINEBELOW", (0, 0), (-1, -1), 0.5, RULE), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                           ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 4)]))
    t._need_h = _need(data, [w * mm for w in _widths("kv", 2)], 3, pad_x=4)
    return [t, Spacer(1, 4 * mm)]


def scorecard(title: str, cards: list) -> list:
    """A titled row of tiles: [(label, count, status)] side by side. The count takes the status text colour; the tile stays neutral."""
    st = styles()
    w = CONTENT_W / len(cards)
    inner = [Table([[Paragraph(f"<font color='{'#1F2933' if s == BLOCKED else STATUS_TEXT[s]}'>{int(n)}</font>", st["score_n"])], [Paragraph(esc(label), st["score_l"])]],
                   colWidths=[w - 16], style=TS([])) for label, n, s in cards]
    t = Table([inner], colWidths=[w] * len(cards))
    t.setStyle(TS([("BOX", (0, 0), (-1, -1), 0.5, RULE), ("INNERGRID", (0, 0), (-1, -1), 0.5, RULE), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                           ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
    t._need_h = 24 * 2.835 + 12                                                    # number (24 pt leading) + label + padding
    return heading(title, 3) + [t, Spacer(1, 3 * mm)]


def stacked_bar(segments: list, caption: str = "") -> Drawing:
    """One stacked coverage bar drawn as native vector graphics, counts printed in and beside the segments. segments = [(label, count, status)]."""
    register_fonts()
    h, bar_h, legend_y = 40, 14, 6
    d = Drawing(CONTENT_W, h)
    total = sum(max(0, int(c)) for _l, c, _s in segments)
    w = float(CONTENT_W)
    if total == 0:
        d.add(Rect(0, h - bar_h - 2, w, bar_h, fillColor=ZEBRA, strokeColor=RULE, strokeWidth=0.5))
        d.add(String(4, h - bar_h + 1, "No files recorded", fontName=SANS, fontSize=8, fillColor=MUTED))
    else:
        x = 0.0
        for _label, count, status in segments:
            count = max(0, int(count))
            if not count:
                continue
            seg_w = w * count / total
            d.add(Rect(x, h - bar_h - 2, seg_w, bar_h, fillColor=_c(STATUS_FILL[status]), strokeColor=_ink(status), strokeWidth=0.8))
            if seg_w > 16:
                d.add(String(x + seg_w / 2, h - bar_h + 2, str(count), fontName=SANS_BOLD, fontSize=8.5, fillColor=_ink(status) if status != BLOCKED else colors.white, textAnchor="middle"))
            x += seg_w
    lx = 0.0
    for label, count, status in segments:
        d.add(Rect(lx, legend_y, 7, 7, fillColor=_c(STATUS_FILL[status]), strokeColor=_ink(status), strokeWidth=0.8))
        text = f"{label}: {int(count)}"
        d.add(String(lx + 10, legend_y + 0.5, text, fontName=SANS, fontSize=8, fillColor=INK))
        lx += 10 + pdfmetrics.stringWidth(text, SANS, 8) + 14
    if caption:
        d.add(String(w, legend_y + 0.5, caption, fontName=SANS, fontSize=8, fillColor=MUTED, textAnchor="end"))
    return d


# ── canonical inputs / hash ───────────────────────────────────────────────────
def canonical(inputs):
    """JSON round trip with sorted keys: what is rendered is exactly what is stored next to the PDF, and dict order can never matter."""
    return json.loads(inputs_json(inputs))


def inputs_json(inputs) -> str:
    return json.dumps(inputs, sort_keys=True, default=str, ensure_ascii=False, separators=(",", ":"))


def inputs_hash(inputs) -> str:
    return hashlib.sha256(inputs_json(inputs).encode("utf-8")).hexdigest()


def _epoch(generated_at: str | None) -> int:
    try:
        return calendar.timegm(time.strptime(str(generated_at).rstrip("Z")[:19], "%Y-%m-%dT%H:%M:%S"))
    except (ValueError, TypeError):
        return 946684800                                                           # 2000-01-01, reportlab's own invariant date


_render_lock = threading.Lock()


@contextmanager
def _deterministic(epoch: int):
    """SOURCE_DATE_EPOCH is process-global, so renders are serialised while it is set."""
    with _render_lock:
        old = os.environ.get("SOURCE_DATE_EPOCH")
        os.environ["SOURCE_DATE_EPOCH"] = str(epoch)
        try:
            yield
        finally:
            if old is None:
                os.environ.pop("SOURCE_DATE_EPOCH", None)
            else:
                os.environ["SOURCE_DATE_EPOCH"] = old


# ── document ──────────────────────────────────────────────────────────────────
def _keep_closing_together(story: list) -> list:
    """If the story ends with a paragraph (a closing note) after a table, the heading, the table and the note are kept together (reportlab splits the group itself when it is
    longer than a page), so the last page never holds a lone paragraph and the heading is never left behind. The spacers between the members go."""
    real = [i for i, f in enumerate(story) if not isinstance(f, (Spacer, CondPageBreak))]
    if len(real) < 3 or not isinstance(story[real[-1]], Paragraph) or not isinstance(story[real[-2]], Table):
        return story
    chain, k = [real[-1], real[-2]], len(real) - 3
    while k >= 0:                                                           # back to (and including) the nearest heading
        chain.append(real[k])
        if isinstance(story[real[k]], Paragraph) and getattr(story[real[k]].style, "name", "") in ("H2", "H3"):
            break
        k -= 1
    first = min(chain)
    for i in chain[1:]:
        story[i].keepWithNext = 1
    return [f for i, f in enumerate(story) if not (first <= i < real[-1] and isinstance(f, (Spacer, CondPageBreak)))]


def compose(story: list) -> list:
    """Keep every H2 / H3 with what follows it: a CondPageBreak sized to the heading plus the next flowable (a table: its header and first two rows) goes before it,
    so a heading never ends a page and a table never leaves only its header behind."""
    story = _keep_closing_together(list(story))
    out: list = []
    for i, f in enumerate(story):
        if isinstance(f, Paragraph) and getattr(f.style, "name", "") in ("H2", "H3"):
            need = f.wrap(CONTENT_W, 100000)[1] + f.style.spaceBefore + f.style.spaceAfter
            taken = 0
            for nxt in story[i + 1:]:
                if isinstance(nxt, (Spacer, CondPageBreak)):
                    continue
                if hasattr(nxt, "_need_h"):
                    need += nxt._need_h
                    break
                is_heading = isinstance(nxt, Paragraph) and getattr(nxt.style, "name", "") in ("H2", "H3")
                need += (nxt.wrap(CONTENT_W, 100000)[1] + (nxt.style.spaceBefore + nxt.style.spaceAfter if is_heading else 0)) if hasattr(nxt, "wrap") else 20
                taken += 0 if is_heading else 1
                if taken >= 2:
                    break
            out.append(CondPageBreak(need + 4))
        out.append(f)
    return out


class Document(SimpleDocTemplate):
    """SimpleDocTemplate that adds an outline entry for every H2 made by `heading()`."""

    def afterFlowable(self, flowable):
        outline = getattr(flowable, "_outline", None)
        if outline:
            self._seq = getattr(self, "_seq", 0) + 1
            key = f"sec{self._seq}"
            self.canv.bookmarkPage(key)
            self.canv.addOutlineEntry(outline[0], key, level=outline[1], closed=0)


def _canvas_class(meta: dict):
    class _Canvas(Canvas):
        """Two-pass canvas: pages are held until the total is known, so the footer can say "Page X of Y". The initial font is an embedded one (no Helvetica)."""

        def __init__(self, *a, **k):
            k["initialFontName"] = SANS
            super().__init__(*a, **k)
            self._held: list = []
            self.setProducer(f"ReportLab {meta['reportlab']}")

        def showPage(self):
            self._held.append(dict(self.__dict__))
            self._startPage()

        def save(self):
            total = len(self._held)
            for state in self._held:
                self.__dict__.update(state)
                _chrome(self, self._pageNumber, total, meta)
                super().showPage()
            super().save()
    return _Canvas


def fit(text: str, font: str, size: float, width: float) -> str:
    """The text cut to `width` points with a trailing "…" (never mid-way through anything but a plain character: it is drawn text, not markup)."""
    if pdfmetrics.stringWidth(text, font, size) <= width:
        return text
    while text and pdfmetrics.stringWidth(text + "…", font, size) > width:
        text = text[:-1]
    return text.rstrip() + "…"


def _chrome(c: Canvas, page: int, total: int, meta: dict) -> None:
    """Header: title left, project name + mono project id right, a 0.5 pt rule. Footer line 1: reference · run · inputs hash (mono) and Page X of Y; line 2: generator."""
    c.saveState()
    c.setStrokeColor(RULE)
    c.setLineWidth(0.5)
    y = PAGE_H - 10 * mm
    c.setFillColor(INK)
    c.setFont(SANS_BOLD, 8.5)
    c.drawString(MARGIN, y, meta["title"])
    title_w = pdfmetrics.stringWidth(meta["title"], SANS_BOLD, 8.5)
    c.setFont(MONO, 7.5)
    c.setFillColor(MUTED)
    right = PAGE_W - MARGIN
    room = right - MARGIN - title_w - 14                                    # what is left of the line for the project name and id
    pid = fit(meta["project_id"], MONO, 7.5, min(room * 0.45, 62 * mm))
    c.drawRightString(right, y, pid)
    c.setFont(SANS, 8)
    name_room = room - pdfmetrics.stringWidth(pid, MONO, 7.5) - 8
    if name_room > 24:
        c.drawRightString(right - pdfmetrics.stringWidth(pid, MONO, 7.5) - 8, y, fit(meta["project"], SANS, 8, name_room))
    c.line(MARGIN, y - 3 * mm, right, y - 3 * mm)
    c.line(MARGIN, 16.5 * mm, right, 16.5 * mm)
    c.setFont(MONO, 7.5)
    c.drawString(MARGIN, 12.5 * mm, f"{meta['doc_id']} · run {meta['run8']} · inputs sha256:{meta['hash'][:12]}")
    c.setFont(SANS, 7.5)
    c.drawRightString(right, 12.5 * mm, f"Page {page} of {total}")
    c.drawString(MARGIN, 8.5 * mm, f"Generated by report engine v{ENGINE_VERSION} · template v{TEMPLATE_VERSION} · automated report")
    c.restoreState()


def render_bytes(story: list, *, title: str, project: str, project_id: str, doc_id: str, subject: str, author: str, run_context: dict | None, inputs) -> bytes:
    """The one place a PDF is made. A pure function of its arguments: no clock, no random ids, so the same story and inputs give byte-identical output."""
    import reportlab
    register_fonts()
    ctx = run_context or new_run_context()
    digest = inputs_hash(inputs)
    meta = {"title": clean(title), "project": clean(project), "project_id": clean(project_id), "doc_id": doc_id, "run8": str(ctx["run_id"])[:8], "hash": digest,
            "reportlab": reportlab.Version}
    buf = io.BytesIO()
    with _deterministic(_epoch(ctx.get("generated_at"))):
        doc = Document(buf, pagesize=A4, leftMargin=MARGIN - FRAME_PAD, rightMargin=MARGIN - FRAME_PAD, topMargin=MARGIN - FRAME_PAD, bottomMargin=MARGIN - FRAME_PAD,
                       invariant=1, title=clean(title), author=clean(author), subject=clean(subject), creator=f"report_kit v{TEMPLATE_VERSION}",
                       keywords=clean(f"{project_id}; {ctx['run_id']}; {doc_id}"))
        doc.build(compose(story), canvasmaker=_canvas_class(meta))
    return buf.getvalue()


def write_pdf(path: str, data: bytes, inputs) -> str:
    """The PDF, and the canonical inputs JSON next to it (<name>.inputs.json): anyone can re-render from it and compare hashes."""
    Path(path).write_bytes(data)
    Path(path[:-4] + ".inputs.json").write_text(inputs_json(inputs), encoding="utf-8")
    return path


def is_completed(ctx: dict | None) -> bool:
    return (ctx or {}).get("run_outcome", COMPLETED) == COMPLETED


def walk_text(flowables) -> list:
    """The plain text of every paragraph in a story (tables and nested tables included), in order."""
    out: list = []

    def walk(node):
        if isinstance(node, (list, tuple)):
            for n in node:
                walk(n)
            return
        if hasattr(node, "getPlainText"):
            out.append(node.getPlainText())
        for row in getattr(node, "_cellvalues", None) or []:
            for cell in row:
                walk(cell)
    for f in flowables:
        walk(f)
    return out
