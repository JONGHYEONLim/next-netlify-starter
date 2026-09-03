# -*- coding: utf-8 -*-
"""사양서 표지 (첫 장).

도면 양식(외곽선·표제란)이 없는 깨끗한 한 장으로, 로고와 문서 정보를 담는다.
치수는 모두 mm. 손보고 싶으면 아래 상수를 고치면 된다.
"""
from __future__ import annotations

import os

from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfgen.canvas import Canvas

from ..fonts import FONT_BOLD, FONT_REGULAR
from ..model import Meta

# ── 배치 ────────────────────────────────────────────────────
L, R = 25.0, 185.0            # 좌우 여백선
TOP_RULE = 268.0              # 상단 굵은 선
LOGO_TOP, LOGO_H = 250.0, 18.0
TITLE_Y = 196.0               # 큰 제목 기준선
SUB_Y = 185.0
MID_RULE = 176.0
INFO_TOP = 164.0              # 정보표 상단
INFO_ROW = 13.0
INFO_LABEL_W = 42.0
APPROVAL_TOP = 74.0           # 승인란 상단
APPROVAL_H = 30.0
BOTTOM_RULE = 34.0

INK = colors.Color(0.10, 0.10, 0.12)
SOFT = colors.Color(0.45, 0.46, 0.50)
LINE = colors.Color(0.72, 0.73, 0.76)
FILL = colors.Color(0.955, 0.957, 0.965)


def _x(v: float) -> float:
    return v * mm


def _y(v: float) -> float:
    return v * mm


class CoverDrawer:
    """첫 페이지에 표지를 그린다 (SimpleDocTemplate 의 onPage 콜백)."""

    def __init__(self, meta: Meta, base_dir: str = ""):
        self.meta = meta
        self.base_dir = base_dir or os.getcwd()
        from .frame import _find_logo
        self._logo = _find_logo(meta.logo_path, self.base_dir)

    def __call__(self, canvas: Canvas, doc) -> None:
        c, m = canvas, self.meta
        c.saveState()
        self._header(c)
        self._logo_and_company(c)
        self._title(c)
        self._info_table(c)
        self._approval(c)
        self._footer(c)
        c.restoreState()

    # ── 각 부분 ─────────────────────────────────────────────
    def _header(self, c: Canvas) -> None:
        m = self.meta
        doc_no = f"{m.dwg_prefix}-{m.dwg_no}" if m.dwg_prefix and m.dwg_no else (m.dwg_no or "")
        c.setFillColor(SOFT)
        c.setFont(FONT_REGULAR, 8.5)
        if doc_no:
            c.drawRightString(_x(R), _y(TOP_RULE + 3.0),
                              f"{doc_no}    Rev. {m.revision or 'A'}")
        c.drawString(_x(L), _y(TOP_RULE + 3.0), m.doc_kind or "")
        c.setStrokeColor(INK)
        c.setLineWidth(1.4)
        c.line(_x(L), _y(TOP_RULE), _x(R), _y(TOP_RULE))
        c.setLineWidth(0.5)
        c.line(_x(L), _y(TOP_RULE - 1.6), _x(R), _y(TOP_RULE - 1.6))

    def _logo_and_company(self, c: Canvas) -> None:
        m = self.meta
        cx = (L + R) / 2
        bottom = LOGO_TOP - LOGO_H
        if self._logo:
            reader, iw, ih = self._logo
            h = LOGO_H
            w = h * (iw / float(ih or 1))
            if w > 90.0:
                w, h = 90.0, 90.0 * (ih / float(iw or 1))
            c.drawImage(reader, _x(cx - w / 2), _y(bottom), _x(w), _y(h),
                        mask="auto", preserveAspectRatio=True, anchor="c")
            if m.company:
                c.setFillColor(SOFT)
                c.setFont(FONT_REGULAR, 9.5)
                c.drawCentredString(_x(cx), _y(bottom - 7.0), m.company)
        elif m.company:
            c.setFillColor(INK)
            c.setFont(FONT_BOLD, 22)
            c.drawCentredString(_x(cx), _y(bottom - 4.0), m.company)

    def _title(self, c: Canvas) -> None:
        m = self.meta
        cx = (L + R) / 2
        title = m.doc_kind or "생산 사양서"
        c.setFillColor(INK)
        size = 30.0
        while size > 16 and pdfmetrics.stringWidth(title, FONT_BOLD, size) > (R - L - 10) * mm:
            size -= 1
        c.setFont(FONT_BOLD, size)
        c.drawCentredString(_x(cx), _y(TITLE_Y), title)

        sub = (m.cover_subtitle or "").strip()
        if sub:
            c.setFillColor(SOFT)
            c.setFont(FONT_REGULAR, 9.5)
            _spaced(c, cx, SUB_Y, sub.upper(), FONT_REGULAR, 9.5, 2.2)

        c.setStrokeColor(LINE)
        c.setLineWidth(0.7)
        c.line(_x(L + 45), _y(MID_RULE), _x(R - 45), _y(MID_RULE))

    def _info_table(self, c: Canvas) -> None:
        m = self.meta
        doc_no = f"{m.dwg_prefix}-{m.dwg_no}" if m.dwg_prefix and m.dwg_no else (m.dwg_no or "-")
        rows = [
            ("제 품 명", m.product_name or "-"),
            ("고 객 사", m.customer or m.customer_en or "-"),
            ("용    도", m.use_name or "-"),
            ("도면번호", doc_no),
            ("리 비 전", f"Rev. {m.revision or 'A'}"),
            ("발 행 일", m.revision_date or "-"),
        ]
        top = INFO_TOP
        h = INFO_ROW * len(rows)
        c.setStrokeColor(LINE)
        c.setLineWidth(0.6)
        c.setFillColor(FILL)
        c.rect(_x(L), _y(top - h), _x(INFO_LABEL_W), _y(h), stroke=0, fill=1)
        c.setFillColor(colors.white)
        c.rect(_x(L + INFO_LABEL_W), _y(top - h), _x(R - L - INFO_LABEL_W), _y(h),
               stroke=0, fill=1)
        c.rect(_x(L), _y(top - h), _x(R - L), _y(h), stroke=1, fill=0)
        c.line(_x(L + INFO_LABEL_W), _y(top - h), _x(L + INFO_LABEL_W), _y(top))

        for i, (label, value) in enumerate(rows):
            y = top - INFO_ROW * (i + 1)
            if i:
                c.setStrokeColor(LINE)
                c.line(_x(L), _y(y + INFO_ROW), _x(R), _y(y + INFO_ROW))
            c.setFillColor(SOFT)
            c.setFont(FONT_REGULAR, 8.6)
            c.drawCentredString(_x(L + INFO_LABEL_W / 2), _y(y + 4.6), label)
            c.setFillColor(INK)
            value = str(value)
            size = 12.0
            room = (R - L - INFO_LABEL_W - 12) * mm
            while size > 7.5 and pdfmetrics.stringWidth(value, FONT_BOLD, size) > room:
                size -= 0.5
            c.setFont(FONT_BOLD, size)
            c.drawString(_x(L + INFO_LABEL_W + 6), _y(y + 4.3), value)

    def _approval(self, c: Canvas) -> None:
        m = self.meta
        cells = [("작 성", m.drawn.name, m.drawn.date),
                 ("검 토", m.checked.name, m.checked.date),
                 ("승 인", m.approved, "")]
        total_w = R - L
        w = total_w / len(cells)
        top, bot = APPROVAL_TOP, APPROVAL_TOP - APPROVAL_H
        head_h = 8.0

        c.setStrokeColor(LINE)
        c.setLineWidth(0.6)
        c.setFillColor(FILL)
        c.rect(_x(L), _y(top - head_h), _x(total_w), _y(head_h), stroke=0, fill=1)
        c.setFillColor(colors.white)
        c.rect(_x(L), _y(bot), _x(total_w), _y(APPROVAL_H - head_h), stroke=0, fill=1)
        c.rect(_x(L), _y(bot), _x(total_w), _y(APPROVAL_H), stroke=1, fill=0)
        c.line(_x(L), _y(top - head_h), _x(R), _y(top - head_h))

        for i, (label, name, date) in enumerate(cells):
            x0 = L + w * i
            if i:
                c.line(_x(x0), _y(bot), _x(x0), _y(top))
            c.setFillColor(SOFT)
            c.setFont(FONT_REGULAR, 8.4)
            c.drawCentredString(_x(x0 + w / 2), _y(top - head_h + 2.6), label)
            if name:
                c.setFillColor(INK)
                c.setFont(FONT_REGULAR, 12)
                c.drawCentredString(_x(x0 + w / 2), _y(bot + 9.5), name)
            if date:
                c.setFillColor(SOFT)
                c.setFont(FONT_REGULAR, 7.6)
                c.drawCentredString(_x(x0 + w / 2), _y(bot + 3.2), date)

    def _footer(self, c: Canvas) -> None:
        m = self.meta
        c.setStrokeColor(LINE)
        c.setLineWidth(0.6)
        c.line(_x(L), _y(BOTTOM_RULE), _x(R), _y(BOTTOM_RULE))
        c.setFillColor(SOFT)
        c.setFont(FONT_REGULAR, 6.6)
        y = BOTTOM_RULE - 5.0
        for line in _wrap(m.confidential_note, FONT_REGULAR, 6.6, (R - L) * mm):
            c.drawCentredString(_x((L + R) / 2), _y(y), line)
            y -= 3.4
        if m.footer_code:
            c.setFont(FONT_REGULAR, 6.4)
            c.drawCentredString(_x((L + R) / 2), _y(y - 3.0), m.footer_code)


# ── 헬퍼 ────────────────────────────────────────────────────
def _spaced(c: Canvas, cx: float, y: float, text: str, font: str, size: float,
            gap: float) -> None:
    """자간을 벌려 가운데 정렬로 그린다."""
    widths = [pdfmetrics.stringWidth(ch, font, size) + gap for ch in text]
    total = sum(widths) - (gap if widths else 0)
    x = _x(cx) - total / 2
    c.setFont(font, size)
    for ch, w in zip(text, widths):
        c.drawString(x, _y(y), ch)
        x += w


def _wrap(text: str, font: str, size: float, width: float):
    words, lines, cur = (text or "").split(), [], ""
    for word in words:
        trial = (cur + " " + word).strip()
        if pdfmetrics.stringWidth(trial, font, size) > width and cur:
            lines.append(cur)
            cur = word
        else:
            cur = trial
    if cur:
        lines.append(cur)
    return lines
