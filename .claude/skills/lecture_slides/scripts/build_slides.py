#!/usr/bin/env python3
"""
Render a slide deck PDF (16:9, dark theme) from a JSON spec.

Usage:
    python build_slides.py <slides.json> <output.pdf>

The JSON format is documented in ../reference/slide_spec.md.

Text is fitted automatically: font size shrinks within readable limits.
Glossary and review-question slides paginate on their own. If a content
slide still does not fit at the smallest readable size, the script reports
OVERFLOW for that slide and exits with code 2. Split that slide into two
and run again.

Inline formatting in any text field: **bold**, *italic*, `code`.
"""

import json
import re
import sys
from pathlib import Path

from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph

# ---------------------------------------------------------------------------
# Page geometry (points). 960 x 540 is 13.33 x 7.5 in, standard 16:9.
# ---------------------------------------------------------------------------
W, H = 960, 540
MARGIN_X = 64
CONTENT_W = W - 2 * MARGIN_X
TITLE_TOP = H - 52
CONTENT_BOTTOM = 66
FOOTER_Y = 28

# ---------------------------------------------------------------------------
# Dark theme
# ---------------------------------------------------------------------------
BG = HexColor("#12151b")
SURFACE = HexColor("#1c212a")
SURFACE_2 = HexColor("#242a35")
TEXT = HexColor("#e9ecf1")
MUTED = HexColor("#9aa4b2")
ACCENT = HexColor("#5cc8ff")
ACCENT_2 = HexColor("#f5b942")
RULE = HexColor("#2e3542")

# Readable size limits for a shared handout deck
BODY_MAX, BODY_MIN = 24, 15
TITLE_MAX, TITLE_MIN = 32, 24


# ---------------------------------------------------------------------------
# Fonts: prefer a Unicode TTF so symbols and accented names render.
# ---------------------------------------------------------------------------
FONT_CANDIDATES = [
    {  # Linux
        "regular": "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "bold": "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "italic": "/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf",
        "bolditalic": "/usr/share/fonts/truetype/dejavu/DejaVuSans-BoldOblique.ttf",
        "mono": "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    },
    {  # macOS
        "regular": "/System/Library/Fonts/Supplemental/Arial.ttf",
        "bold": "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "italic": "/System/Library/Fonts/Supplemental/Arial Italic.ttf",
        "bolditalic": "/System/Library/Fonts/Supplemental/Arial Bold Italic.ttf",
        "mono": "/System/Library/Fonts/Supplemental/Courier New.ttf",
    },
    {  # Windows
        "regular": "C:/Windows/Fonts/arial.ttf",
        "bold": "C:/Windows/Fonts/arialbd.ttf",
        "italic": "C:/Windows/Fonts/ariali.ttf",
        "bolditalic": "C:/Windows/Fonts/arialbi.ttf",
        "mono": "C:/Windows/Fonts/cour.ttf",
    },
]

FONT, FONT_B, FONT_I, FONT_BI, MONO = (
    "Helvetica", "Helvetica-Bold", "Helvetica-Oblique", "Helvetica-BoldOblique", "Courier",
)


def register_fonts():
    global FONT, FONT_B, FONT_I, FONT_BI, MONO
    for cand in FONT_CANDIDATES:
        if all(Path(p).exists() for p in cand.values()):
            pdfmetrics.registerFont(TTFont("Deck", cand["regular"]))
            pdfmetrics.registerFont(TTFont("Deck-Bold", cand["bold"]))
            pdfmetrics.registerFont(TTFont("Deck-Italic", cand["italic"]))
            pdfmetrics.registerFont(TTFont("Deck-BoldItalic", cand["bolditalic"]))
            pdfmetrics.registerFont(TTFont("Deck-Mono", cand["mono"]))
            pdfmetrics.registerFontFamily(
                "Deck", normal="Deck", bold="Deck-Bold",
                italic="Deck-Italic", boldItalic="Deck-BoldItalic",
            )
            FONT, FONT_B, FONT_I, FONT_BI, MONO = (
                "Deck", "Deck-Bold", "Deck-Italic", "Deck-BoldItalic", "Deck-Mono",
            )
            return
    print("Note: no Unicode TTF found, using built-in Helvetica (limited symbol support).")


# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------
def md(text) -> str:
    """Escape text for reportlab markup and convert **bold**, *italic*, `code`."""
    s = str(text or "")
    s = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    s = re.sub(r"`([^`]+)`", lambda m: f'<font name="{MONO}">{m.group(1)}</font>', s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    s = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<i>\1</i>", s)
    return s.replace("\n", "<br/>")


def style(size, color=TEXT, font=None, leading=1.28, align=TA_LEFT, **kw):
    return ParagraphStyle(
        "s", fontName=font or FONT, fontSize=size, leading=size * leading,
        textColor=color, alignment=align, **kw,
    )


def para(text, st):
    return Paragraph(md(text), st)


def height_of(p, width):
    return p.wrap(width, 10_000)[1]


# ---------------------------------------------------------------------------
# Bullet blocks
# ---------------------------------------------------------------------------
def normalize_bullets(items):
    out = []
    for b in items or []:
        if isinstance(b, str):
            out.append({"text": b, "sub": []})
        else:
            out.append({"text": b.get("text", ""), "sub": b.get("sub", []) or []})
    return out


def bullet_paras(items, size, color=TEXT, marker="•", marker_color=ACCENT):
    """Return list of (paragraph, space_after) for top-level bullets and sub-bullets."""
    items = normalize_bullets(items)
    top = style(size, color, leftIndent=size * 1.25, bulletIndent=0,
                bulletFontName=FONT_B, bulletFontSize=size, bulletColor=marker_color)
    sub_size = max(size - 3, 12)
    sub = style(sub_size, MUTED, leftIndent=size * 1.25 + sub_size * 1.3,
                bulletIndent=size * 1.25, bulletFontName=FONT,
                bulletFontSize=sub_size, bulletColor=MUTED)
    gap = size * 0.55
    out = []
    for i, b in enumerate(items):
        m = marker if marker != "#" else f"{i + 1}."
        out.append([Paragraph(md(b["text"]), top, bulletText=m), gap if not b["sub"] else size * 0.25])
        for j, s in enumerate(b["sub"]):
            last = j == len(b["sub"]) - 1
            out.append([Paragraph(md(s), sub, bulletText="–"), gap if last else sub_size * 0.2])
    if out:
        out[-1][1] = 0
    return out


def block_height(paras, width):
    return sum(height_of(p, width) + gap for p, gap in paras)


def draw_block(c, paras, x, y_top, width):
    y = y_top
    for p, gap in paras:
        h = height_of(p, width)
        p.drawOn(c, x, y - h)
        y -= h + gap
    return y


# ---------------------------------------------------------------------------
# Chrome: background, title, footer
# ---------------------------------------------------------------------------
class Deck:
    def __init__(self, spec):
        self.spec = spec
        self.footer_left = spec.get("course") or spec.get("title", "")
        self.pages = []      # list of callables(c, page_no, total)
        self.problems = []   # overflow messages

    def background(self, c):
        c.setFillColor(BG)
        c.rect(0, 0, W, H, stroke=0, fill=1)

    def footer(self, c, page_no, total):
        c.setStrokeColor(RULE)
        c.setLineWidth(0.8)
        c.line(MARGIN_X, FOOTER_Y + 16, W - MARGIN_X, FOOTER_Y + 16)
        c.setFont(FONT, 10)
        c.setFillColor(MUTED)
        c.drawString(MARGIN_X, FOOTER_Y, self.footer_left[:90])
        c.drawRightString(W - MARGIN_X, FOOTER_Y, f"{page_no} / {total}")

    def title_para(self, title, label):
        for size in range(TITLE_MAX, TITLE_MIN - 1, -2):
            p = Paragraph(md(title), style(size, TEXT, FONT_B, leading=1.15))
            if height_of(p, CONTENT_W) <= size * 1.15 * 2 + 1:
                return p
        self.problems.append(f"{label}: title is too long (keep it under ~2 lines).")
        return p

    def draw_title(self, c, title, label, kicker=None):
        """Draw slide title; return y where content may start."""
        y = TITLE_TOP
        if kicker:
            c.setFont(FONT_B, 11)
            c.setFillColor(ACCENT)
            c.drawString(MARGIN_X, y - 11, kicker.upper())
            y -= 22
        p = self.title_para(title, label)
        h = height_of(p, CONTENT_W)
        p.drawOn(c, MARGIN_X, y - h)
        y -= h + 12
        c.setFillColor(ACCENT)
        c.rect(MARGIN_X, y, 56, 4, stroke=0, fill=1)
        return y - 26

    def content_top(self, title, label, kicker=None):
        """Content start y without drawing (for measurement)."""
        y = TITLE_TOP - (22 if kicker else 0)
        y -= height_of(self.title_para(title, label), CONTENT_W) + 12
        return y - 26

    # -----------------------------------------------------------------------
    # Slide builders (each appends one or more page callables)
    # -----------------------------------------------------------------------
    def add_title_slide(self):
        s = self.spec

        def draw(c, n, total):
            self.background(c)
            c.setFillColor(ACCENT)
            c.rect(0, 0, 10, H, stroke=0, fill=1)
            y = H * 0.62
            if s.get("course"):
                c.setFont(FONT_B, 14)
                c.setFillColor(ACCENT)
                c.drawString(MARGIN_X, y + 40, s["course"].upper())
            p = None
            for size in range(46, 29, -2):
                p = Paragraph(md(s.get("title", "Lecture")), style(size, TEXT, FONT_B, leading=1.12))
                if height_of(p, CONTENT_W) <= size * 1.12 * 2 + 1:
                    break
            h = height_of(p, CONTENT_W)
            p.drawOn(c, MARGIN_X, y - h + 20)
            y = y - h
            if s.get("subtitle"):
                sp = para(s["subtitle"], style(22, MUTED))
                sh = height_of(sp, CONTENT_W)
                sp.drawOn(c, MARGIN_X, y - sh)
                y -= sh + 10
            meta = "  ·  ".join(x for x in [s.get("author"), s.get("date")] if x)
            if meta:
                c.setFont(FONT, 14)
                c.setFillColor(MUTED)
                c.drawString(MARGIN_X, 80, meta)

        self.pages.append(draw)

    def add_section(self, slide, label):
        def draw(c, n, total):
            self.background(c)
            c.setFillColor(SURFACE)
            c.rect(0, 0, W, H, stroke=0, fill=1)
            c.setFillColor(ACCENT)
            c.rect(MARGIN_X, H / 2 + 40, 56, 4, stroke=0, fill=1)
            p = para(slide.get("title", ""), style(40, TEXT, FONT_B, leading=1.12))
            h = height_of(p, CONTENT_W)
            p.drawOn(c, MARGIN_X, H / 2 + 24 - h)
            if slide.get("subtitle"):
                sp = para(slide["subtitle"], style(20, MUTED))
                sp.wrap(CONTENT_W, 200)
                sp.drawOn(c, MARGIN_X, H / 2 - h - 20 - height_of(sp, CONTENT_W) + 20)
            self.footer(c, n, total)

        self.pages.append(draw)

    def fit_bullets(self, items, width, avail, label, marker="•", marker_color=ACCENT, extra=None):
        """Find the largest size where bullets (+ optional extra height fn) fit."""
        for size in range(BODY_MAX, BODY_MIN - 1, -1):
            paras = bullet_paras(items, size, marker=marker, marker_color=marker_color)
            need = block_height(paras, width) + (extra(size) if extra else 0)
            if need <= avail:
                return size, paras
        self.problems.append(f"{label}: content does not fit at {BODY_MIN}pt. Split this slide.")
        return BODY_MIN, bullet_paras(items, BODY_MIN, marker=marker, marker_color=marker_color)

    def note_para(self, note, size):
        return para(note, style(max(size - 4, 13), TEXT, leading=1.3))

    def add_bullets(self, slide, label, kicker=None, marker="•", marker_color=ACCENT):
        title = slide.get("title", "")
        note = slide.get("note")
        top = self.content_top(title, label, kicker)
        avail = top - CONTENT_BOTTOM
        note_w = CONTENT_W - 40

        def note_h(size):
            return height_of(self.note_para(note, size), note_w) + 28 + 18 if note else 0

        size, paras = self.fit_bullets(slide.get("bullets", []), CONTENT_W, avail, label,
                                       marker, marker_color, note_h if note else None)

        def draw(c, n, total):
            self.background(c)
            y = self.draw_title(c, title, label, kicker)
            y = draw_block(c, paras, MARGIN_X, y, CONTENT_W)
            if note:
                np_ = self.note_para(note, size)
                nh = height_of(np_, note_w)
                box_h = nh + 28
                box_y = max(CONTENT_BOTTOM, y - 18 - box_h)
                c.setFillColor(SURFACE_2)
                c.roundRect(MARGIN_X, box_y, CONTENT_W, box_h, 6, stroke=0, fill=1)
                c.setFillColor(ACCENT_2)
                c.rect(MARGIN_X, box_y, 5, box_h, stroke=0, fill=1)
                np_.drawOn(c, MARGIN_X + 24, box_y + 14)
            self.footer(c, n, total)

        self.pages.append(draw)

    def add_two_column(self, slide, label):
        title = slide.get("title", "")
        left, right = slide.get("left", {}), slide.get("right", {})
        gap = 36
        col_w = (CONTENT_W - gap) / 2
        avail = self.content_top(title, label) - CONTENT_BOTTOM

        chosen = None
        for size in range(BODY_MAX - 2, BODY_MIN - 1, -1):
            cols = []
            for col in (left, right):
                head = para(col.get("heading", ""), style(size + 2, ACCENT, FONT_B))
                body = bullet_paras(col.get("bullets", []), size)
                cols.append((head, body))
            need = max(height_of(h, col_w - 32) + 14 + block_height(b, col_w - 32) for h, b in cols) + 36
            if need <= avail:
                chosen = cols, need
                break
        if not chosen:
            self.problems.append(f"{label}: columns do not fit at {BODY_MIN}pt. Shorten or split.")
            chosen = cols, avail

        cols, need = chosen

        def draw(c, n, total):
            self.background(c)
            y = self.draw_title(c, title, label)
            for i, (head, body) in enumerate(cols):
                x = MARGIN_X + i * (col_w + gap)
                c.setFillColor(SURFACE)
                c.roundRect(x, y - need, col_w, need, 8, stroke=0, fill=1)
                hh = height_of(head, col_w - 32)
                head.drawOn(c, x + 16, y - 18 - hh)
                draw_block(c, body, x + 16, y - 18 - hh - 14, col_w - 32)
            self.footer(c, n, total)

        self.pages.append(draw)

    def add_definition(self, slide, label):
        title = slide.get("title", "Definition")
        term = para(slide.get("term", ""), style(30, ACCENT, FONT_B, leading=1.15))
        avail = self.content_top(title, label) - CONTENT_BOTTOM
        inner_w = CONTENT_W - 64
        chosen = None
        for size in range(BODY_MAX + 2, BODY_MIN - 1, -1):
            defn = para(slide.get("definition", ""), style(size, TEXT, leading=1.35))
            ex = para("**Example:** " + slide["example"], style(size - 3, MUTED, leading=1.35)) \
                if slide.get("example") else None
            need = height_of(term, inner_w) + 16 + height_of(defn, inner_w) + 48 + \
                (height_of(ex, inner_w) + 20 if ex else 0)
            if need <= avail:
                chosen = defn, ex, need
                break
        if not chosen:
            self.problems.append(f"{label}: definition is too long. Shorten it or use a bullets slide.")
            chosen = defn, ex, avail
        defn, ex, need = chosen

        def draw(c, n, total):
            self.background(c)
            y = self.draw_title(c, title, label)
            c.setFillColor(SURFACE)
            c.roundRect(MARGIN_X, y - need, CONTENT_W, need, 8, stroke=0, fill=1)
            c.setFillColor(ACCENT)
            c.rect(MARGIN_X, y - need, 6, need, stroke=0, fill=1)
            yy = y - 24
            th = height_of(term, inner_w)
            term.drawOn(c, MARGIN_X + 32, yy - th)
            yy -= th + 16
            dh = height_of(defn, inner_w)
            defn.drawOn(c, MARGIN_X + 32, yy - dh)
            yy -= dh + 20
            if ex:
                ex.drawOn(c, MARGIN_X + 32, yy - height_of(ex, inner_w))
            self.footer(c, n, total)

        self.pages.append(draw)

    def add_code(self, slide, label):
        title = slide.get("title", "")
        lines = (slide.get("code") or "").rstrip("\n").split("\n")
        caption = slide.get("caption")
        avail = self.content_top(title, label) - CONTENT_BOTTOM - (34 if caption else 0)
        size = None
        for s in range(18, 10, -1):
            longest = max(pdfmetrics.stringWidth(l, MONO, s) for l in lines) if lines else 0
            if len(lines) * s * 1.4 + 36 <= avail and longest <= CONTENT_W - 48:
                size = s
                break
        if size is None:
            self.problems.append(f"{label}: code block too long or too wide. Trim or split it.")
            size = 11

        def draw(c, n, total):
            self.background(c)
            y = self.draw_title(c, title, label)
            box_h = len(lines) * size * 1.4 + 36
            c.setFillColor(SURFACE)
            c.roundRect(MARGIN_X, y - box_h, CONTENT_W, box_h, 8, stroke=0, fill=1)
            c.setFont(MONO, size)
            c.setFillColor(TEXT)
            yy = y - 18 - size
            for line in lines:
                c.drawString(MARGIN_X + 24, yy, line)
                yy -= size * 1.4
            if caption:
                cp = para(caption, style(15, MUTED))
                cp.wrap(CONTENT_W, 100)
                cp.drawOn(c, MARGIN_X, y - box_h - 14 - height_of(cp, CONTENT_W))
            self.footer(c, n, total)

        self.pages.append(draw)

    # ---- paginated slides --------------------------------------------------
    def paginate(self, rows, title, label, row_height, kicker=None):
        """Split rows into pages that fit; return list of row lists."""
        avail = self.content_top(title + " (cont.)", label, kicker) - CONTENT_BOTTOM
        pages, cur, used = [], [], 0
        for r in rows:
            h = row_height(r)
            if h > avail:
                self.problems.append(f"{label}: one entry is taller than a full slide. Shorten it.")
            if cur and used + h > avail:
                pages.append(cur)
                cur, used = [], 0
            cur.append(r)
            used += h
        if cur:
            pages.append(cur)
        return pages

    def add_glossary(self, slide, label):
        title = slide.get("title", "Glossary")
        terms = slide.get("terms", [])
        term_w, gap = 230, 28
        def_w = CONTENT_W - term_w - gap
        size = 17

        def row(t):
            tp = para(t.get("term", ""), style(size, ACCENT, FONT_B))
            dp = para(t.get("definition", ""), style(size, TEXT, leading=1.3))
            return tp, dp, max(height_of(tp, term_w), height_of(dp, def_w)) + 22

        rows = [row(t) for t in terms]
        pages = self.paginate(rows, title, label, lambda r: r[2])
        for i, chunk in enumerate(pages):
            ttl = title if i == 0 else f"{title} (cont.)"

            def draw(c, n, total, chunk=chunk, ttl=ttl):
                self.background(c)
                y = self.draw_title(c, ttl, label)
                for j, (tp, dp, h) in enumerate(chunk):
                    if j % 2 == 0:
                        c.setFillColor(SURFACE)
                        c.rect(MARGIN_X - 12, y - h + 4, CONTENT_W + 24, h, stroke=0, fill=1)
                    tp.drawOn(c, MARGIN_X, y - 7 - height_of(tp, term_w))
                    dp.drawOn(c, MARGIN_X + term_w + gap, y - 7 - height_of(dp, def_w))
                    y -= h
                self.footer(c, n, total)

            self.pages.append(draw)

    def add_questions(self, slide, label, answers_out):
        title = slide.get("title", "Review Questions")
        qs = slide.get("questions", [])
        size = 19
        num_w = 36

        def row(item):
            q = item if isinstance(item, str) else item.get("q", "")
            p = para(q, style(size, TEXT, leading=1.3))
            return p, height_of(p, CONTENT_W - num_w) + 20

        rows = [(i + 1, *row(q)) for i, q in enumerate(qs)]
        pages = self.paginate(rows, title, label, lambda r: r[2])
        for i, chunk in enumerate(pages):
            ttl = title if i == 0 else f"{title} (cont.)"

            def draw(c, n, total, chunk=chunk, ttl=ttl):
                self.background(c)
                y = self.draw_title(c, ttl, label)
                for num, p, h in chunk:
                    c.setFillColor(ACCENT)
                    c.circle(MARGIN_X + 12, y - 12, 13, stroke=0, fill=1)
                    c.setFillColor(BG)
                    c.setFont(FONT_B, 13)
                    c.drawCentredString(MARGIN_X + 12, y - 16.5, str(num))
                    p.drawOn(c, MARGIN_X + num_w, y - height_of(p, CONTENT_W - num_w))
                    y -= h
                self.footer(c, n, total)

            self.pages.append(draw)

        for i, q in enumerate(qs):
            if isinstance(q, dict) and q.get("answer"):
                answers_out.append((i + 1, q["answer"]))

    def add_answer_key(self, answers):
        title = "Answer Key"
        size = 16
        num_w = 36

        def row(a):
            p = para(a[1], style(size, MUTED, leading=1.3))
            return a[0], p, height_of(p, CONTENT_W - num_w) + 16

        rows = [row(a) for a in answers]
        pages = self.paginate(rows, title, "Answer Key", lambda r: r[2])
        for i, chunk in enumerate(pages):
            ttl = title if i == 0 else f"{title} (cont.)"

            def draw(c, n, total, chunk=chunk, ttl=ttl):
                self.background(c)
                y = self.draw_title(c, ttl, "Answer Key")
                for num, p, h in chunk:
                    c.setFont(FONT_B, size)
                    c.setFillColor(ACCENT)
                    c.drawString(MARGIN_X, y - size, f"{num}.")
                    p.drawOn(c, MARGIN_X + num_w, y - height_of(p, CONTENT_W - num_w))
                    y -= h
                self.footer(c, n, total)

            self.pages.append(draw)

    # -----------------------------------------------------------------------
    def build(self, out_path):
        self.add_title_slide()
        answers = []
        for idx, slide in enumerate(self.spec.get("slides", []), 1):
            t = slide.get("type", "bullets")
            label = f"Slide {idx} ({t}: {slide.get('title', '')[:40]!r})"
            if t == "section":
                self.add_section(slide, label)
            elif t == "bullets":
                self.add_bullets(slide, label)
            elif t == "two_column":
                self.add_two_column(slide, label)
            elif t == "definition":
                self.add_definition(slide, label)
            elif t == "code":
                self.add_code(slide, label)
            elif t == "takeaways":
                slide = {**slide, "title": slide.get("title", "Key Takeaways")}
                self.add_bullets(slide, label, kicker="Summary", marker="✓", marker_color=ACCENT_2)
            elif t == "questions":
                self.add_questions(slide, label, answers)
            elif t == "glossary":
                self.add_glossary(slide, label)
            else:
                self.problems.append(f"{label}: unknown slide type {t!r}.")
        if answers and self.spec.get("answer_key", True):
            self.add_answer_key(answers)

        c = canvas.Canvas(str(out_path), pagesize=(W, H))
        c.setTitle(self.spec.get("title", "Lecture slides"))
        if self.spec.get("author"):
            c.setAuthor(self.spec["author"])
        total = len(self.pages)
        for n, draw in enumerate(self.pages, 1):
            draw(c, n, total)
            c.showPage()
        c.save()
        return total


def main():
    if len(sys.argv) != 3:
        sys.exit("Usage: python build_slides.py <slides.json> <output.pdf>")
    spec = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    out = Path(sys.argv[2])
    out.parent.mkdir(parents=True, exist_ok=True)

    register_fonts()
    deck = Deck(spec)
    total = deck.build(out)
    print(f"Wrote {out} ({total} pages)")
    if deck.problems:
        print("\nOVERFLOW / LAYOUT PROBLEMS. Fix these in the JSON and run again:")
        for p in deck.problems:
            print(f"  - {p}")
        sys.exit(2)


if __name__ == "__main__":
    main()
