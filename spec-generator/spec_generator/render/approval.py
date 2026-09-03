# -*- coding: utf-8 -*-
"""고객 승인 사양서 조판 — 표지와 본문 양식.

생산 사양서는 도면 양식(굵은 외곽선·표제란)을 쓰지만,
고객에게 나가는 승인 사양서는 깔끔한 영문 문서체로 만든다.
치수는 모두 mm.
"""
from __future__ import annotations

import os

from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfgen.canvas import Canvas

from ..fonts import FONT_BOLD, FONT_REGULAR
from ..model import Meta
from .cover import (FILL, INK, LINE, SOFT, _spaced, _wrap, _x, _y, draw_stamp)

# ── 본문 양식 ────────────────────────────────────────────────
ML, MR = 22.0, 188.0          # 좌우 여백
HEAD_Y = 279.0                # 머리말 선
FOOT_Y = 18.0                 # 꼬리말 선
CONTENT_TOP = 272.0
CONTENT_BOT = 24.0

# ── 표지 ────────────────────────────────────────────────────
C_TOP_RULE = 272.0
C_LOGO_TOP, C_LOGO_H = 256.0, 17.0
C_TITLE_Y = 214.0
C_SUB_Y = 204.0
C_RULE_Y = 196.0
C_INFO_TOP = 188.0
C_INFO_ROW = 11.0
C_REV_TOP = 100.0             # 개정 이력
C_REV_ROW = 7.5
C_APPR_TOP = 56.0             # 고객 승인란
C_APPR_H = 26.0
C_BOTTOM_RULE = 24.0


def _doc_no(m: Meta) -> str:
    return f"{m.dwg_prefix}-{m.dwg_no}" if m.dwg_prefix and m.dwg_no else (m.dwg_no or "")


class ApprovalFrame:
    """본문 각 장의 머리말·꼬리말."""

    def __init__(self, meta: Meta, total_getter=None, page_offset: int = 0):
        self.meta = meta
        self._total = total_getter
        self.page_offset = page_offset

    def __call__(self, canvas: Canvas, doc) -> None:
        c, m = canvas, self.meta
        c.saveState()
        c.setStrokeColor(LINE)
        c.setLineWidth(0.6)
        c.line(_x(ML), _y(HEAD_Y), _x(MR), _y(HEAD_Y))
        c.line(_x(ML), _y(FOOT_Y), _x(MR), _y(FOOT_Y))

        c.setFillColor(SOFT)
        c.setFont(FONT_REGULAR, 8.0)
        c.drawString(_x(ML), _y(HEAD_Y + 2.6), m.company or "")
        no = _doc_no(m)
        if no:
            c.drawRightString(_x(MR), _y(HEAD_Y + 2.6), f"{no}    Rev. {m.revision or 'A'}")

        c.setFont(FONT_REGULAR, 7.6)
        c.drawString(_x(ML), _y(FOOT_Y - 5.0),
                     (m.cover_subtitle or "APPROVAL SPECIFICATION").upper())
        page = canvas.getPageNumber() - self.page_offset
        total = self.meta.page_total or (self._total() if self._total else 0)
        c.drawRightString(_x(MR), _y(FOOT_Y - 5.0),
                          f"Page {page} / {total}" if total else f"Page {page}")
        c.restoreState()


def content_frame_rect():
    return _x(ML), _y(CONTENT_BOT), _x(MR - ML), _y(CONTENT_TOP - CONTENT_BOT)


class ApprovalCover:
    """승인 사양서 표지 — 제품 요약, 개정 이력, 고객 승인란."""

    def __init__(self, meta: Meta, base_dir: str = ""):
        self.meta = meta
        self.base_dir = base_dir or os.getcwd()
        from .frame import _find_logo
        self._logo = _find_logo(meta.logo_path, self.base_dir)

    def __call__(self, canvas: Canvas, doc) -> None:
        c = canvas
        c.saveState()
        self._header(c)
        self._logo_block(c)
        self._title(c)
        self._info(c)
        self._revisions(c)
        self._approval(c)
        self._footer(c)
        c.restoreState()

    def _header(self, c: Canvas) -> None:
        m = self.meta
        c.setFillColor(SOFT)
        c.setFont(FONT_REGULAR, 8.5)
        c.drawString(_x(ML), _y(C_TOP_RULE + 3.0), m.company or "")
        no = _doc_no(m)
        if no:
            c.drawRightString(_x(MR), _y(C_TOP_RULE + 3.0), f"{no}    Rev. {m.revision or 'A'}")
        c.setStrokeColor(INK)
        c.setLineWidth(1.4)
        c.line(_x(ML), _y(C_TOP_RULE), _x(MR), _y(C_TOP_RULE))
        c.setLineWidth(0.5)
        c.line(_x(ML), _y(C_TOP_RULE - 1.6), _x(MR), _y(C_TOP_RULE - 1.6))

    def _logo_block(self, c: Canvas) -> None:
        m = self.meta
        cx = (ML + MR) / 2
        bottom = C_LOGO_TOP - C_LOGO_H
        if self._logo:
            reader, iw, ih = self._logo
            h = C_LOGO_H
            w = h * (iw / float(ih or 1))
            if w > 85.0:
                w, h = 85.0, 85.0 * (ih / float(iw or 1))
            c.drawImage(reader, _x(cx - w / 2), _y(bottom), _x(w), _y(h),
                        mask="auto", preserveAspectRatio=True, anchor="c")
            if m.company:
                c.setFillColor(SOFT)
                c.setFont(FONT_REGULAR, 9.0)
                c.drawCentredString(_x(cx), _y(bottom - 6.5), m.company)
        elif m.company:
            c.setFillColor(INK)
            c.setFont(FONT_BOLD, 20)
            c.drawCentredString(_x(cx), _y(bottom - 2.0), m.company)

    def _title(self, c: Canvas) -> None:
        m = self.meta
        cx = (ML + MR) / 2
        title = (m.cover_subtitle or "APPROVAL SPECIFICATION").upper()
        c.setFillColor(INK)
        size = 25.0
        while size > 13 and pdfmetrics.stringWidth(title, FONT_BOLD, size) > (MR - ML - 8) * mm:
            size -= 1
        c.setFont(FONT_BOLD, size)
        c.drawCentredString(_x(cx), _y(C_TITLE_Y), title)
        c.setFillColor(SOFT)
        _spaced(c, cx, C_SUB_Y, m.doc_kind or "승인 사양서", FONT_REGULAR, 10.5, 3.0)
        c.setStrokeColor(LINE)
        c.setLineWidth(0.7)
        c.line(_x(ML + 40), _y(C_RULE_Y), _x(MR - 40), _y(C_RULE_Y))

    def _info(self, c: Canvas) -> None:
        m = self.meta
        rows = [("Customer", m.customer_en or m.customer or "-"),
                ("Product", m.product_name or "-"),
                ("Application", m.use_name or "-"),
                ("Drawing No.", _doc_no(m) or "-"),
                ("Rated Current", m.rated_current or "-"),
                ("Revision", f"Rev. {m.revision or 'A'}"),
                ("Issued", m.revision_date or "-")]
        top, label_w = C_INFO_TOP, 45.0
        h = C_INFO_ROW * len(rows)
        c.setStrokeColor(LINE)
        c.setLineWidth(0.6)
        c.setFillColor(FILL)
        c.rect(_x(ML), _y(top - h), _x(label_w), _y(h), stroke=0, fill=1)
        c.setFillColor(colors.white)
        c.rect(_x(ML + label_w), _y(top - h), _x(MR - ML - label_w), _y(h), stroke=0, fill=1)
        c.rect(_x(ML), _y(top - h), _x(MR - ML), _y(h), stroke=1, fill=0)
        c.line(_x(ML + label_w), _y(top - h), _x(ML + label_w), _y(top))
        for i, (label, value) in enumerate(rows):
            y = top - C_INFO_ROW * (i + 1)
            if i:
                c.line(_x(ML), _y(y + C_INFO_ROW), _x(MR), _y(y + C_INFO_ROW))
            c.setFillColor(SOFT)
            c.setFont(FONT_REGULAR, 8.2)
            c.drawString(_x(ML + 4), _y(y + 4.0), label)
            c.setFillColor(INK)
            value, size = str(value), 11.0
            room = (MR - ML - label_w - 10) * mm
            while size > 7.0 and pdfmetrics.stringWidth(value, FONT_BOLD, size) > room:
                size -= 0.5
            c.setFont(FONT_BOLD, size)
            c.drawString(_x(ML + label_w + 5), _y(y + 3.7), value)

    def _revisions(self, c: Canvas) -> None:
        m = self.meta
        cols = [("Rev.", 18.0), ("Date", 28.0), ("Contents", 70.0),
                ("Prepared", 25.0), ("Approved", 25.0)]
        rows = list(self.meta_revisions())[:4] or [("A", m.revision_date or "", "Original issue",
                                                    m.drawn.name, m.approved.name)]
        top = C_REV_TOP
        c.setFillColor(SOFT)
        c.setFont(FONT_REGULAR, 7.6)
        c.drawString(_x(ML), _y(top + 2.6), "Revision History")
        h = C_REV_ROW * (len(rows) + 1)
        total_w = sum(w for _, w in cols)
        scale = (MR - ML) / total_w
        widths = [w * scale for _, w in cols]

        c.setStrokeColor(LINE)
        c.setLineWidth(0.6)
        c.setFillColor(FILL)
        c.rect(_x(ML), _y(top - C_REV_ROW), _x(MR - ML), _y(C_REV_ROW), stroke=0, fill=1)
        c.setFillColor(colors.white)
        c.rect(_x(ML), _y(top - h), _x(MR - ML), _y(h - C_REV_ROW), stroke=0, fill=1)
        c.rect(_x(ML), _y(top - h), _x(MR - ML), _y(h), stroke=1, fill=0)
        for i in range(1, len(rows) + 1):
            gy = top - C_REV_ROW * i
            c.line(_x(ML), _y(gy), _x(MR), _y(gy))
        gx = ML
        for w in widths[:-1]:
            gx += w
            c.line(_x(gx), _y(top - h), _x(gx), _y(top))

        c.setFillColor(SOFT)
        c.setFont(FONT_REGULAR, 8.0)
        gx = ML
        for (label, _), w in zip(cols, widths):
            c.drawCentredString(_x(gx + w / 2), _y(top - C_REV_ROW + 2.6), label)
            gx += w
        c.setFont(FONT_REGULAR, 8.4)
        for r, values in enumerate(rows):
            y = top - C_REV_ROW * (r + 2) + 2.6
            gx = ML
            for value, w in zip(values, widths):
                c.setFillColor(INK)
                text = str(value or "")
                size = 8.4
                while size > 5.5 and pdfmetrics.stringWidth(text, FONT_REGULAR, size) > (w - 3) * mm:
                    size -= 0.4
                c.setFont(FONT_REGULAR, size)
                c.drawCentredString(_x(gx + w / 2), _y(y), text)
                gx += w

    def meta_revisions(self):
        """표지에 실을 개정 이력 (문서에서 채워 넣는다)."""
        return getattr(self, "_revs", [])

    def _approval(self, c: Canvas) -> None:
        m = self.meta
        top, bot = C_APPR_TOP, C_APPR_TOP - C_APPR_H
        head_h = 7.5
        groups = [("Braumm", [("Prepared", m.drawn), ("Checked", m.checked),
                              ("Approved", m.approved)]),
                  ("Customer", [("Checked", None), ("Approved", None)])]
        gap = 8.0
        total = MR - ML - gap
        widths = [total * 3 / 5, total * 2 / 5]
        gx = ML
        for (title, cells), gw in zip(groups, widths):
            c.setFillColor(SOFT)
            c.setFont(FONT_REGULAR, 7.6)
            c.drawString(_x(gx), _y(top + 2.4), title)
            c.setStrokeColor(LINE)
            c.setLineWidth(0.6)
            c.setFillColor(FILL)
            c.rect(_x(gx), _y(top - head_h), _x(gw), _y(head_h), stroke=0, fill=1)
            c.setFillColor(colors.white)
            c.rect(_x(gx), _y(bot), _x(gw), _y(C_APPR_H - head_h), stroke=0, fill=1)
            c.rect(_x(gx), _y(bot), _x(gw), _y(C_APPR_H), stroke=1, fill=0)
            c.line(_x(gx), _y(top - head_h), _x(gx + gw), _y(top - head_h))
            cw = gw / len(cells)
            for i, (label, person) in enumerate(cells):
                x0 = gx + cw * i
                if i:
                    c.line(_x(x0), _y(bot), _x(x0), _y(top))
                c.setFillColor(SOFT)
                c.setFont(FONT_REGULAR, 7.4)
                c.drawCentredString(_x(x0 + cw / 2), _y(top - head_h + 2.3), label)
                if person is None:
                    continue                     # 고객이 직접 서명할 빈 칸
                stamped = draw_stamp(c, person, self.base_dir, cx=x0 + cw / 2,
                                     cy=bot + 11.5, max_w=cw - 6.0, max_h=11.0)
                if person.name:
                    c.setFillColor(INK)
                    c.setFont(FONT_REGULAR, 7.4 if stamped else 10.0)
                    c.drawCentredString(_x(x0 + cw / 2),
                                        _y(bot + 3.0 if stamped else bot + 7.5), person.name)
            gx += gw + gap

    def _footer(self, c: Canvas) -> None:
        m = self.meta
        c.setStrokeColor(LINE)
        c.setLineWidth(0.6)
        c.line(_x(ML), _y(C_BOTTOM_RULE), _x(MR), _y(C_BOTTOM_RULE))
        c.setFillColor(SOFT)
        c.setFont(FONT_REGULAR, 6.6)
        y = C_BOTTOM_RULE - 5.0
        for line in _wrap(m.confidential_note, FONT_REGULAR, 6.6, (MR - ML) * mm):
            c.drawCentredString(_x((ML + MR) / 2), _y(y), line)
            y -= 3.4
        if m.footer_code:
            c.setFont(FONT_REGULAR, 6.4)
            c.drawCentredString(_x((ML + MR) / 2), _y(y - 3.0), m.footer_code)
