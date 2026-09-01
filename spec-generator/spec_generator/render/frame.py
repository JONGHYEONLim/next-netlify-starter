# -*- coding: utf-8 -*-
"""A4 도면 양식(외곽선·좌측 표제란·하단 표제란)을 캔버스에 직접 그린다.

치수는 모두 mm 단위 상수다. 양식을 손보고 싶으면 아래 상수만 고치면 된다.
표제란 하단에는 회사 로고를 넣을 수 있다(Meta.logo_path).
"""
from __future__ import annotations

import os
from typing import Optional

from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfgen.canvas import Canvas

from ..fonts import FONT_BOLD, FONT_REGULAR
from ..model import Meta

# ── 용지 / 외곽 ──────────────────────────────────────────────
PAGE_W, PAGE_H = 210.0, 297.0
OUT_L, OUT_R, OUT_B, OUT_T = 7.0, 200.0, 7.0, 290.0

# ── 좌측 세로 표제란 ─────────────────────────────────────────
STRIP_X = 25.5              # 본문 영역과 나누는 세로 굵은 선
LS_X0, LS_X1 = 11.5, 24.0   # 제품명/용도명/도면종류 박스
LS_TOP, LS_SEP, LS_BOT = 288.0, 234.0, 218.0
NOTE_TOP, NOTE_BOT = 198.0, 127.0   # 기밀 문구(세로쓰기) 영역
REV_TOP, REV_BOT = 103.0, OUT_B     # REVISIONS 영역
REV_LABEL_H = 6.5

# ── 하단 표제란 ─────────────────────────────────────────────
TB_TOP, TB_BOT = 40.0, OUT_B
TB_MID_X = 120.3            # 좌(승인란) / 우(도면번호) 분할
TB_ROW_H = 5.2              # DATE/NAME 행 높이
TB_COMPANY_TOP = TB_BOT + 12.2
TB_COL = (25.5, 35.9, 53.1, 70.3, 89.7, TB_MID_X)   # 좌측 표 열 경계
TB_LBL_X = 126.2            # 우측 세로 라벨(DWG CODE / DRAWING NO.) 우측 경계
TB_PAGE_X = 184.8           # PAGE/INDEX 열 시작
TB_PAGE_LBL_X = 191.5
TB_OLD_Y = 13.1             # OLD DWG.NO. 띠 상단
TB_CODE_Y = 34.5            # DWG CODE 점선 박스 하단
TB_PAGE_Y1, TB_PAGE_Y2 = 37.0, 28.0
TB_INDEX_Y = 19.1

THIN, THICK = 0.35, 1.1


def _x(v: float) -> float:
    return v * mm


def _y(v: float) -> float:
    return v * mm


class FrameDrawer:
    """SimpleDocTemplate 의 onPage 콜백으로 쓰인다."""

    def __init__(self, meta: Meta, total_pages_getter=None, base_dir: str = ""):
        self.meta = meta
        self._total = total_pages_getter
        self.base_dir = base_dir or os.getcwd()
        self._logo = _find_logo(meta.logo_path, self.base_dir)

    # ── public ──────────────────────────────────────────────
    def __call__(self, canvas: Canvas, doc) -> None:
        canvas.saveState()
        canvas.setStrokeColorRGB(0, 0, 0)
        canvas.setFillColorRGB(0, 0, 0)
        self._outer(canvas)
        self._left_strip(canvas)
        self._title_block(canvas, page_index=canvas.getPageNumber())
        self._footer_code(canvas)
        canvas.restoreState()

    # ── parts ───────────────────────────────────────────────
    def _outer(self, c: Canvas) -> None:
        c.setLineWidth(THIN)
        c.rect(_x(OUT_L), _y(OUT_B), _x(OUT_R - OUT_L), _y(OUT_T - OUT_B))
        c.setLineWidth(THICK)
        c.rect(_x(STRIP_X), _y(OUT_B), _x(OUT_R - STRIP_X), _y(OUT_T - OUT_B))

    def _left_strip(self, c: Canvas) -> None:
        m = self.meta
        c.setLineWidth(THIN)
        # 제품명 / 용도명 / 도면종류 3열
        c.rect(_x(LS_X0), _y(LS_BOT), _x(LS_X1 - LS_X0), _y(LS_TOP - LS_BOT))
        w = (LS_X1 - LS_X0) / 3.0
        for i in (1, 2):
            gx = LS_X0 + w * i
            c.line(_x(gx), _y(LS_BOT), _x(gx), _y(LS_TOP))
        c.line(_x(LS_X0), _y(LS_SEP), _x(LS_X1), _y(LS_SEP))

        labels = (m.label_product, m.label_use, m.label_kind)
        values = (m.product_name, m.use_name, m.doc_kind)
        for i, (lab, val) in enumerate(zip(labels, values)):
            cx = LS_X0 + w * (i + 0.5)
            _vtext(c, cx, LS_SEP + 1.5, val, FONT_REGULAR, 7.2, anchor="start")
            _vtext(c, cx, LS_BOT + 1.5, lab, FONT_BOLD, 6.6, anchor="start")

        # 기밀 문구 (세로쓰기, 여러 줄)
        if m.confidential_note:
            _vparagraph(c, LS_X0, LS_X1, NOTE_BOT, NOTE_TOP, m.confidential_note,
                        FONT_REGULAR, 5.0, leading=6.0)

        # REVISIONS
        c.rect(_x(OUT_L), _y(REV_BOT), _x(LS_X1 - OUT_L), _y(REV_TOP - REV_BOT))
        c.line(_x(OUT_L), _y(REV_BOT + REV_LABEL_H), _x(LS_X1), _y(REV_BOT + REV_LABEL_H))
        _ctext(c, (OUT_L + LS_X1) / 2, REV_BOT + 2.0, "REVISIONS", FONT_BOLD, 6.0)
        rows = max(1, int(self.meta.revision_rows))
        top, bot = REV_TOP, REV_BOT + REV_LABEL_H
        rh = (top - bot) / rows
        for i in range(1, rows):
            gy = bot + rh * i
            c.line(_x(OUT_L), _y(gy), _x(LS_X1), _y(gy))
        for gx in (11.5, 16.0, 20.0):
            c.line(_x(gx), _y(bot), _x(gx), _y(top))

    def _title_block(self, c: Canvas, page_index: int) -> None:
        m = self.meta
        c.setLineWidth(THIN)
        c.line(_x(STRIP_X), _y(TB_TOP), _x(OUT_R), _y(TB_TOP))
        c.line(_x(TB_MID_X), _y(TB_BOT), _x(TB_MID_X), _y(TB_TOP))

        self._approval_table(c)
        self._drawing_no_block(c, page_index)
        _ = m

    def _approval_table(self, c: Canvas) -> None:
        m = self.meta
        rows = [("", "DATE", "NAME"), ("DRAWN", m.drawn.date, m.drawn.name),
                ("CHECKED", m.checked.date, m.checked.name),
                ("RENEWAL", m.renewal.date, m.renewal.name)]
        top = TB_TOP
        # 가로선
        for i in range(len(rows) + 1):
            gy = top - TB_ROW_H * i
            c.line(_x(TB_COL[0]), _y(gy), _x(TB_COL[-1]), _y(gy))
        c.line(_x(TB_COL[0]), _y(TB_COMPANY_TOP), _x(TB_COL[-1]), _y(TB_COMPANY_TOP))
        # 세로선
        bot_rows = top - TB_ROW_H * len(rows)
        for gx in TB_COL[1:-1]:
            c.line(_x(gx), _y(bot_rows), _x(gx), _y(top))
        c.line(_x(TB_COL[3]), _y(TB_COMPANY_TOP), _x(TB_COL[3]), _y(bot_rows))
        c.line(_x(TB_COL[4]), _y(TB_COMPANY_TOP), _x(TB_COL[4]), _y(bot_rows))
        # 좌상단 사선
        c.line(_x(TB_COL[0]), _y(top), _x(TB_COL[1]), _y(top - TB_ROW_H))

        for r, (lab, d, n) in enumerate(rows):
            cy = top - TB_ROW_H * (r + 1) + 1.5
            if lab:
                _ctext(c, (TB_COL[0] + TB_COL[1]) / 2, cy, lab, FONT_REGULAR, 6.4)
            _ctext(c, (TB_COL[1] + TB_COL[2]) / 2, cy, d, FONT_REGULAR, 7.0)
            _ctext(c, (TB_COL[2] + TB_COL[3]) / 2, cy, n, FONT_REGULAR, 7.4)
        _ctext(c, (TB_COL[3] + TB_COL[4]) / 2, top - TB_ROW_H + 1.5, "APPROVED", FONT_REGULAR, 6.6)
        _ctext(c, (TB_COL[3] + TB_COL[4]) / 2,
               (bot_rows + top - TB_ROW_H) / 2 - 1.4, m.approved, FONT_REGULAR, 9.0)
        self._company_cell(c, TB_COL[0], TB_COL[-1], TB_BOT, TB_COMPANY_TOP)

    def _company_cell(self, c: Canvas, x0: float, x1: float, y0: float, y1: float) -> None:
        """회사 로고(있으면)와 회사명을 표제란 하단 칸에 배치한다."""
        m = self.meta
        cy = (y0 + y1) / 2
        if not self._logo:
            _ctext(c, (x0 + x1) / 2, cy - 2.1, m.company, FONT_BOLD, 12.0)
            return

        path, iw, ih = self._logo
        h = min(float(m.logo_height_mm or 8.5), (y1 - y0) - 2.5)
        w = h * (iw / float(ih or 1))
        max_w = (x1 - x0) - 6.0
        if w > max_w:
            w, h = max_w, max_w * (ih / float(iw or 1))

        if m.company:
            # 로고를 왼쪽에, 회사명을 남은 칸 가운데에
            lx = x0 + 4.0
            c.drawImage(path, _x(lx), _y(cy - h / 2), _x(w), _y(h),
                        mask="auto", preserveAspectRatio=True, anchor="c")
            _ctext(c, (lx + w + x1) / 2, cy - 2.1, m.company, FONT_BOLD, 12.0)
        else:
            c.drawImage(path, _x((x0 + x1 - w) / 2), _y(cy - h / 2), _x(w), _y(h),
                        mask="auto", preserveAspectRatio=True, anchor="c")

    def _drawing_no_block(self, c: Canvas, page_index: int) -> None:
        m = self.meta
        c.line(_x(TB_LBL_X), _y(TB_BOT), _x(TB_LBL_X), _y(TB_TOP))
        c.line(_x(TB_LBL_X), _y(TB_CODE_Y), _x(TB_PAGE_X), _y(TB_CODE_Y))
        c.line(_x(TB_LBL_X), _y(TB_OLD_Y), _x(TB_PAGE_X), _y(TB_OLD_Y))
        c.line(_x(TB_PAGE_X), _y(TB_BOT), _x(TB_PAGE_X), _y(TB_TOP))

        _vtext_mid(c, (TB_MID_X + TB_LBL_X) / 2, (TB_CODE_Y + TB_TOP) / 2, "DWG CODE",
                   FONT_REGULAR, 4.8)
        _vtext_mid(c, (TB_MID_X + TB_LBL_X) / 2, (TB_OLD_Y + TB_CODE_Y) / 2, "DRAWING NO.",
                   FONT_REGULAR, 5.6)

        # DWG CODE 점선 박스 2개
        c.saveState()
        c.setDash(2, 2)
        c.rect(_x(TB_LBL_X + 1.5), _y(TB_CODE_Y + 0.8), _x(26.0), _y(4.0))
        c.rect(_x(TB_LBL_X + 30.5), _y(TB_CODE_Y + 0.8),
               _x(TB_PAGE_X - 1.5 - (TB_LBL_X + 30.5)), _y(4.0))
        c.restoreState()
        _ctext(c, TB_LBL_X + 14.5, TB_CODE_Y + 2.1, m.dwg_code, FONT_REGULAR, 7.0)
        _ctext(c, (TB_LBL_X + 30.5 + TB_PAGE_X - 1.5) / 2, TB_CODE_Y + 2.1,
               m.dwg_code2, FONT_REGULAR, 7.0)

        # 도면번호 (크게, 칸을 넘치면 자동으로 줄인다)
        mid_y = (TB_OLD_Y + TB_CODE_Y) / 2 - 3.2
        if m.dwg_prefix:
            _ctext(c, TB_LBL_X + 12.0, mid_y, m.dwg_prefix, FONT_BOLD, 20.0)
            no_x0, no_x1 = TB_LBL_X + 20.0, TB_PAGE_X
        else:
            no_x0, no_x1 = TB_LBL_X, TB_PAGE_X
        _fit_text(c, (no_x0 + no_x1) / 2, mid_y, m.dwg_no, FONT_BOLD, 20.0,
                  max_width=(no_x1 - no_x0) - 4.0, min_size=8.0)

        # OLD DWG.NO. 띠
        c.line(_x(TB_LBL_X + 12.0), _y(TB_BOT), _x(TB_LBL_X + 12.0), _y(TB_OLD_Y))
        c.line(_x(TB_LBL_X + 44.0), _y(TB_BOT), _x(TB_LBL_X + 44.0), _y(TB_OLD_Y))
        _ctext(c, TB_LBL_X + 6.0, TB_BOT + 3.2, "OLD", FONT_REGULAR, 4.2)
        _ctext(c, TB_LBL_X + 6.0, TB_BOT + 1.2, "DWG.NO.", FONT_REGULAR, 4.2)
        _ctext(c, TB_LBL_X + 28.0, TB_BOT + 1.8, m.old_dwg_no, FONT_REGULAR, 7.2)
        _ctext(c, (TB_LBL_X + 44.0 + TB_PAGE_X) / 2, TB_BOT + 1.8, m.standard, FONT_REGULAR, 6.6)

        # PAGE / INDEX
        c.line(_x(TB_PAGE_LBL_X), _y(TB_BOT), _x(TB_PAGE_LBL_X), _y(TB_PAGE_Y1))
        c.line(_x(TB_PAGE_X), _y(TB_PAGE_Y1), _x(OUT_R), _y(TB_PAGE_Y1))
        c.line(_x(TB_PAGE_LBL_X), _y(TB_PAGE_Y2), _x(OUT_R), _y(TB_PAGE_Y2))
        c.line(_x(TB_PAGE_X), _y(TB_INDEX_Y), _x(OUT_R), _y(TB_INDEX_Y))
        _vtext_mid(c, (TB_PAGE_X + TB_PAGE_LBL_X) / 2, (TB_INDEX_Y + TB_PAGE_Y1) / 2,
                   "PAGE", FONT_REGULAR, 5.4)
        _vtext_mid(c, (TB_PAGE_X + TB_PAGE_LBL_X) / 2, (TB_BOT + TB_INDEX_Y) / 2,
                   "REV.", FONT_REGULAR, 5.4)

        page_no = self.meta.page_start + page_index - 1
        total = self.meta.page_total or (self._total() if self._total else 0)
        _ctext(c, (TB_PAGE_LBL_X + OUT_R) / 2, (TB_PAGE_Y1 + TB_PAGE_Y2) / 2 - 1.4,
               str(page_no), FONT_REGULAR, 9.0)
        _ctext(c, (TB_PAGE_LBL_X + OUT_R) / 2, (TB_PAGE_Y2 + TB_INDEX_Y) / 2 - 1.4,
               str(total) if total else "", FONT_REGULAR, 9.0)
        _ctext(c, (TB_PAGE_LBL_X + OUT_R) / 2, (TB_INDEX_Y + TB_BOT) / 2 - 1.8,
               self.meta.revision or self.meta.index, FONT_BOLD, 11.0)

    def _footer_code(self, c: Canvas) -> None:
        if self.meta.footer_code:
            c.setFont(FONT_REGULAR, 7.0)
            c.drawString(_x(LS_X1 - 0.5), _y(2.6), self.meta.footer_code)


# ── 텍스트 헬퍼 ──────────────────────────────────────────────
def _ctext(c: Canvas, cx: float, y: float, text: str, font: str, size: float) -> None:
    if not text:
        return
    c.setFont(font, size)
    c.drawCentredString(_x(cx), _y(y), text)


def _vtext(c: Canvas, cx: float, y0: float, text: str, font: str, size: float,
           anchor: str = "start") -> None:
    """세로쓰기(아래→위). cx 는 글자 세로 중심선, y0 는 시작 높이."""
    if not text:
        return
    c.saveState()
    c.translate(_x(cx), _y(y0))
    c.rotate(90)
    c.setFont(font, size)
    c.drawString(0, -size * 0.36, text) if anchor == "start" else c.drawCentredString(0, -size * 0.36, text)
    c.restoreState()


def _fit_text(c: Canvas, cx: float, y: float, text: str, font: str, size: float,
              max_width: float, min_size: float = 6.0) -> None:
    """칸 폭을 넘으면 글자를 줄여서 한 줄에 맞춘다."""
    if not text:
        return
    limit = max_width * mm
    while size > min_size and pdfmetrics.stringWidth(text, font, size) > limit:
        size -= 0.5
    c.setFont(font, size)
    c.drawCentredString(_x(cx), _y(y), text)


def _vtext_mid(c: Canvas, cx: float, cy: float, text: str, font: str, size: float) -> None:
    """세로쓰기하되 cy 를 글자열의 중앙으로 맞춘다."""
    if not text:
        return
    c.saveState()
    c.translate(_x(cx), _y(cy))
    c.rotate(90)
    c.setFont(font, size)
    c.drawCentredString(0, -size * 0.36, text)
    c.restoreState()


def _vparagraph(c: Canvas, x0: float, x1: float, y0: float, y1: float, text: str,
                font: str, size: float, leading: float) -> None:
    """세로쓰기 여러 줄. x0..x1 폭 안에서 오른쪽 줄부터 채운다."""
    max_len = (y1 - y0) * mm
    words, lines, cur = text.split(), [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if pdfmetrics.stringWidth(trial, font, size) > max_len and cur:
            lines.append(cur)
            cur = w
        else:
            cur = trial
    if cur:
        lines.append(cur)

    c.saveState()
    c.setFont(font, size)
    cx = x1 - 1.0
    for line in lines:
        if cx < x0:
            break
        c.saveState()
        c.translate(_x(cx), _y(y0))
        c.rotate(90)
        c.drawString(0, 0, line)
        c.restoreState()
        cx -= leading * 0.353  # pt → mm
    c.restoreState()


def _find_logo(logo_path: str, base_dir: str):
    """로고 파일을 찾아 (경로, 폭, 높이) 를 돌려준다. 없으면 None.

    Meta.logo_path 가 비어 있으면 문서 폴더의 logo.* → 프로그램 assets/logo.* 순으로 찾는다.
    """
    from ..importers import find_default_logo, resolve_image
    path = resolve_image(logo_path, base_dir) if logo_path else find_default_logo(base_dir)
    if not path:
        return None
    try:
        from reportlab.lib.utils import ImageReader
        reader = ImageReader(path)
        w, h = reader.getSize()
        return reader, w, h
    except Exception:
        return None


def content_frame_rect():
    """본문 Frame 의 (x, y, width, height) 를 point 단위로 돌려준다."""
    left, right = STRIP_X + 1.5, OUT_R - 3.0
    bottom, top = TB_TOP + 2.0, OUT_T - 3.0
    return _x(left), _y(bottom), _x(right - left), _y(top - bottom)
