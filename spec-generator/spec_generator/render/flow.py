# -*- coding: utf-8 -*-
"""섹션 → platypus flowable 변환."""
from __future__ import annotations

import os
from typing import List, Optional

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (Image, KeepTogether, Paragraph, Spacer, Table,
                               TableStyle)
from reportlab.platypus.flowables import Flowable
from reportlab.platypus.flowables import HRFlowable

from ..fonts import FONT_BOLD, FONT_REGULAR
from ..model import (KIND_IMAGE, KIND_NAMEPLATE, KIND_SPEC_TABLE, KIND_TABLE,
                     KIND_TEXT, KIND_VERSION_TABLE, Section)

CONTENT_W_MM = 170.0
INDENT_STEP_MM = 9.0

SPEC_HEADERS = ["항  목", "사  양", "비  고"]
SPEC_WIDTHS = [37.0, 74.0, 59.0]
VER_HEADERS = ["리비전", "작성자", "발행일", "변  경  내  용"]
GRID_HEADERS = ["No.", "항목", "내용"]
VER_WIDTHS = [16.0, 20.0, 24.0, 110.0]


def make_styles():
    base = ParagraphStyle("base", fontName=FONT_REGULAR, fontSize=9.0, leading=12.6,
                          wordWrap="CJK", allowWidows=1, allowOrphans=1)
    return {
        "heading": ParagraphStyle("heading", parent=base, fontName=FONT_BOLD,
                                  fontSize=10.0, leading=14.0, spaceBefore=0, spaceAfter=2),
        "body": ParagraphStyle("body", parent=base, bulletFontName=FONT_REGULAR,
                               bulletFontSize=9.0),
        "cell": ParagraphStyle("cell", parent=base, fontSize=7.9, leading=10.0,
                               alignment=TA_CENTER),
        "cell_l": ParagraphStyle("cell_l", parent=base, fontSize=7.9, leading=10.0,
                                 alignment=TA_LEFT),
        "cell_h": ParagraphStyle("cell_h", parent=base, fontSize=8.2, leading=10.8,
                                 alignment=TA_CENTER),
        "caption": ParagraphStyle("caption", parent=base, fontSize=8.0, leading=10.4,
                                  alignment=TA_CENTER),
    }


# 렌더링 한 번 동안 쓰이는 치환표와 표제 정보. build_pdf 가 채워 넣는다.
_CTX: dict = {}
_META: dict = {}


def set_context(ctx: dict, meta=None) -> None:
    global _CTX, _META
    _CTX = ctx or {}
    _META = {"meta": meta} if meta is not None else {}


def _esc(text: str) -> str:
    from ..placeholders import apply as _apply
    text = _apply(text or "", _CTX)
    return (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def _multiline(text: str) -> str:
    return _esc(text).replace("\n", "<br/>")


def section_flowables(section: Section, number: str, styles, base_dir: str) -> List:
    """섹션 하나를 flowable 리스트로."""
    out: List = []
    head = _heading(section, number, styles)
    body = _body(section, styles, base_dir)

    if head is not None:
        # 제목이 페이지 끝에 홀로 남지 않도록 첫 본문과 묶는다.
        if body:
            out.append(KeepTogether([head] + body[:1]))
            out.extend(body[1:])
        else:
            out.append(head)
    else:
        out.extend(body)
    out.append(Spacer(1, 5 * mm))
    return out


def _heading(section: Section, number: str, styles) -> Optional[Paragraph]:
    title = "/".join(x for x in (section.title_ko, section.title_en) if x)
    if not title:
        return None
    prefix = ""
    if section.numbered:
        prefix = f"{number}. " if number else ""
    elif section.bullet:
        prefix = f"{section.bullet}"
    label = _esc(prefix + title)
    text = f"<u>{label}</u>" if section.underline else label
    if section.note:
        text += f'&nbsp;&nbsp;&nbsp;&nbsp;<font size="9">{_esc(section.note)}</font>'
    return Paragraph(text, styles["heading"])


def _body(section: Section, styles, base_dir: str) -> List:
    """어떤 종류의 항목이든 [설명글] → [표] → [첨부 도면] 순서로 쌓는다.

    덕분에 '요크코어 사이즈 + 도면' 처럼 표와 도면이 함께 있는 항목을
    하나로 관리할 수 있다.
    """
    out: List = []
    if section.kind == KIND_VERSION_TABLE:
        out.extend(_version_table(section, styles))
    elif section.kind == KIND_NAMEPLATE:
        out.extend(_text_blocks(section, styles))
        out.extend(_nameplate(section, styles, base_dir))
        return out
    elif section.kind == KIND_TABLE:
        out.extend(_text_blocks(section, styles))
        if section.grid:
            if out:
                out.append(Spacer(1, 2 * mm))
            out.append(_free_table(section, styles))
    elif section.kind == KIND_IMAGE:
        out.extend(_text_blocks(section, styles))
    else:
        out.extend(_text_blocks(section, styles))
        if section.kind == KIND_SPEC_TABLE and section.rows:
            if out:
                out.append(Spacer(1, 2 * mm))
            out.append(_spec_table(section, styles))
    if section.images:
        if out:
            out.append(Spacer(1, 4 * mm))
        out.extend(_images(section, styles, base_dir))
    return out


def _text_blocks(section: Section, styles) -> List:
    out: List = []
    for b in section.blocks:
        indent = max(0, b.indent) * INDENT_STEP_MM * mm
        st = ParagraphStyle(f"b{id(b)}", parent=styles["body"],
                            leftIndent=indent + (7 * mm if b.marker else 0),
                            bulletIndent=indent,
                            spaceAfter=1.5)
        if b.ko:
            out.append(Paragraph(_multiline(b.ko), st,
                                 bulletText=b.marker or None))
        if b.en:
            st_en = ParagraphStyle(f"e{id(b)}", parent=st, spaceAfter=4)
            out.append(Paragraph(_multiline(b.en), st_en,
                                 bulletText=None if b.ko else (b.marker or None)))
        if not b.ko and not b.en:
            out.append(Spacer(1, 3 * mm))
    return out


def _widths(section: Section, default: List[float]) -> List[float]:
    w = [float(x) for x in section.col_widths_mm] if section.col_widths_mm else list(default)
    if len(w) != len(default):
        w = list(default)
    scale = CONTENT_W_MM / sum(w)
    return [x * scale * mm for x in w]


def _spec_table(section: Section, styles) -> Table:
    headers = section.headers or SPEC_HEADERS
    data = [[Paragraph(_multiline(h), styles["cell_h"]) for h in headers]]
    for r in section.rows:
        item = "<br/>".join(_esc(x) for x in (r.item_ko, r.item_en) if x)
        data.append([
            Paragraph(item, styles["cell"]),
            Paragraph(_multiline(r.spec), styles["cell"]),
            Paragraph(_multiline(r.remark), styles["cell_l"]),
        ])
    t = Table(data, colWidths=_widths(section, SPEC_WIDTHS), repeatRows=1)
    t.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 1.9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1.9),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
    ]))
    return t


def _version_table(section: Section, styles) -> List:
    out: List = []
    out.extend(_text_blocks(section, styles))
    if section.part_no:
        st = ParagraphStyle("partno", parent=styles["body"], spaceBefore=3, spaceAfter=2,
                            leftIndent=INDENT_STEP_MM * mm)
        out.append(Paragraph(_esc(f"◇ 파트번호 : {section.part_no}"), st))

    headers = section.headers or VER_HEADERS
    data = [[Paragraph(_multiline(h), styles["cell_h"]) for h in headers]]
    for r in section.versions:
        changed = "<br/>".join(_esc(x) for x in (r.changed_ko, r.changed_en) if x)
        data.append([
            Paragraph(_esc(r.rev), styles["cell"]),
            Paragraph(_esc(r.author), styles["cell"]),
            Paragraph(_esc(r.date), styles["cell"]),
            Paragraph(changed or "&nbsp;", styles["cell_l"]),
        ])
    t = Table(data, colWidths=_widths(section, VER_WIDTHS), repeatRows=1)
    t.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("MINROWHEIGHTS", (0, 1), (-1, -1), 0),
    ]))
    out.append(t)
    return out


class FitImage(Flowable):
    """남은 지면을 최대한 채우는 그림.

    폭(mm)을 0 으로 두면 **가로 폭과 남은 세로 높이 양쪽에 맞춰** 최대한 크게 넣는다.
    도면은 클수록 현장에서 보기 좋으므로 이 방식을 기본으로 삼는다.
    """

    def __init__(self, path: str, width_mm: float = 0.0, align: str = "CENTER",
                 reserve_mm: float = 0.0, rotate: int = 0):
        super().__init__()
        self.path = path
        self.width_mm = float(width_mm or 0.0)
        self.align = (align or "CENTER").upper()
        self.reserve_mm = reserve_mm      # 캡션 등 아래에 남겨 둘 높이
        self.rotate_deg = 90 if int(rotate or 0) == 90 else 0
        reader = ImageReader(path)
        iw, ih = reader.getSize()
        self._reader = reader
        ratio = (ih / float(iw)) if iw else 1.0
        self._ratio = (1.0 / ratio if ratio else 1.0) if self.rotate_deg else ratio
        self._w = self._h = 0.0

    def wrap(self, availWidth, availHeight):
        max_w = min(availWidth, CONTENT_W_MM * mm)
        if self.width_mm > 0:
            max_w = min(max_w, self.width_mm * mm)
        w = max_w
        h = w * self._ratio
        room = availHeight - self.reserve_mm * mm
        if room > 20 * mm and h > room:       # 세로가 모자라면 높이에 맞춘다
            h = room
            w = h / self._ratio if self._ratio else max_w
        self._w, self._h = w, h
        return w, h

    def draw(self):
        if self.rotate_deg:
            self.canv.saveState()
            self.canv.translate(self._w, 0)
            self.canv.rotate(90)
            self.canv.drawImage(self._reader, 0, 0, self._h, self._w,
                                mask="auto", preserveAspectRatio=True, anchor="c")
            self.canv.restoreState()
        else:
            self.canv.drawImage(self._reader, 0, 0, self._w, self._h,
                                mask="auto", preserveAspectRatio=True, anchor="c")

    def identity(self, maxLen=None):
        return f"FitImage({os.path.basename(self.path)})"


def _free_table(section: Section, styles) -> Table:
    """열 수를 마음대로 정할 수 있는 표 (자재 리스트, 부품 목록 등)."""
    headers = [h for h in (section.headers or GRID_HEADERS)]
    n = len(headers)
    data = [[Paragraph(_multiline(h), styles["cell_h"]) for h in headers]]
    for row in section.grid:
        cells = [row.cell(i) for i in range(n)]
        data.append([Paragraph(_multiline(c) or "&nbsp;",
                               styles["cell"] if i == 0 else styles["cell_l"])
                     for i, c in enumerate(cells)])

    widths = section.col_widths_mm or []
    if len(widths) != n:
        widths = [CONTENT_W_MM / n] * n
    scale = CONTENT_W_MM / sum(widths)
    col_widths = [w * scale * mm for w in widths]

    t = Table(data, colWidths=col_widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("VALIGN", (0, 0), (-1, 0), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 2.0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.0),
        ("LEFTPADDING", (0, 0), (-1, -1), 2.5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2.5),
    ]))
    return t


def _images(section: Section, styles, base_dir: str) -> List:
    from ..importers import resolve_image
    out: List = []
    for item in section.images:
        path = resolve_image(item.path, base_dir)
        if not path or not os.path.exists(path):
            out.append(Paragraph(_esc(f"[이미지를 찾을 수 없습니다: {item.path}]"), styles["caption"]))
            continue
        cap = "<br/>".join(_esc(x) for x in (item.caption_ko, item.caption_en) if x)
        try:
            img = FitImage(path, item.width_mm, item.align,
                           reserve_mm=10.0 if cap else 4.0, rotate=item.rotate)
            img.hAlign = (item.align or "CENTER").upper()
            out.append(img)
        except Exception as exc:  # 손상된 이미지도 문서 생성을 막지 않는다
            out.append(Paragraph(_esc(f"[이미지 오류: {item.path} — {exc}]"), styles["caption"]))
            continue
        if cap:
            out.append(Spacer(1, 1.5 * mm))
            out.append(Paragraph(cap, styles["caption"]))
        out.append(Spacer(1, 3 * mm))
    return out


__all__ = ["make_styles", "section_flowables", "CONTENT_W_MM", "HRFlowable"]


# ── 명판 ────────────────────────────────────────────────────
NAMEPLATE_DEFAULTS = {
    "width_mm": 110.0,   # 문서에 넣을 명판 폭
    "aspect": 1.93,      # 바탕 그림이 없을 때의 가로/세로 비
    "x": 8.0,            # 글자 시작 위치 (폭의 %)
    "y": 24.0,           # 글자 시작 위치 (높이의 %, 위에서부터)
    "line": 9.0,         # 줄 간격 (높이의 %)
    "size": 6.5,         # 글자 크기 (높이의 %)
    "label_w": 40.0,     # 라벨 칸 너비 (폭의 %)
}


class NamePlate(Flowable):
    """명판 도안.

    · 바탕 그림(images[0])을 넣으면 그 위에 값만 찍는다.
    · 바탕 그림이 없으면 테두리 + 로고 + 제조사 표기를 그려 명판 모양을 만든다.
    배치는 layout 의 백분율 값으로 조절한다(가로 폭·높이 기준).
    """

    def __init__(self, rows, layout, meta, base_dir, background=None, logo=None):
        super().__init__()
        self.rows = rows                 # [(라벨, 값, 크기배율), ...]
        self.cfg = dict(NAMEPLATE_DEFAULTS)
        self.cfg.update({k: float(v) for k, v in (layout or {}).items()
                         if isinstance(v, (int, float, str)) and str(v).strip() != ""})
        self.meta = meta
        self.base_dir = base_dir
        self.bg = background
        self.logo = logo
        self._w = self._h = 0.0

    BOTTOM_MARGIN = 0.14          # 아래쪽 제조사 표기를 위해 비워 두는 비율
    _shrink = 1.0

    def _body_fraction(self) -> float:
        """줄들이 차지하는 높이 — 명판 높이에 대한 비율."""
        line = self.cfg["line"] / 100.0
        base = self.cfg["size"] / 100.0
        return sum(max(line, base * (scale or 1.0) * 1.35) for _, _, scale in self.rows)

    def wrap(self, availWidth, availHeight):
        w = min(self.cfg["width_mm"] * mm, availWidth, CONTENT_W_MM * mm)
        if self.bg is not None:
            iw, ih = self.bg[1], self.bg[2]
            ratio = (ih / float(iw)) if iw else (1.0 / self.cfg["aspect"])
        else:
            ratio = 1.0 / max(self.cfg["aspect"], 0.2)

        # 글자 크기·줄 간격이 모두 명판 높이의 비율이므로, 명판을 키워도
        # 글자가 같이 커진다. 따라서 넘칠 때는 글자를 줄여서 맞춘다.
        avail = max(1.0 - self.cfg["y"] / 100.0 - self.BOTTOM_MARGIN, 0.05)
        body = self._body_fraction()
        self._shrink = min(1.0, avail / body) if body > 0 else 1.0

        self._w, self._h = w, w * ratio
        return self._w, self._h

    def draw(self):
        c, w, h = self.canv, self._w, self._h
        if self.bg is not None:
            c.drawImage(self.bg[0], 0, 0, w, h, mask="auto",
                        preserveAspectRatio=True, anchor="c")
        else:
            self._draw_blank(c, w, h)
        self._draw_values(c, w, h)

    # ── 바탕 그림이 없을 때의 기본 명판 ──────────────────────
    def _draw_blank(self, c, w, h) -> None:
        c.saveState()
        c.setFillColorRGB(1, 1, 1)
        c.rect(0, 0, w, h, stroke=0, fill=1)
        c.setStrokeColorRGB(0.35, 0.35, 0.40)
        c.setLineWidth(1.0)
        c.rect(0, 0, w, h, stroke=1, fill=0)

        if self.logo is not None:                 # 좌측 상단 로고
            reader, iw, ih = self.logo
            lh = h * 0.20
            lw = lh * (iw / float(ih or 1))
            if lw > w * 0.30:
                lw = w * 0.30
                lh = lw * (ih / float(iw or 1))
            c.drawImage(reader, w * 0.05, h - h * 0.06 - lh, lw, lh,
                        mask="auto", preserveAspectRatio=True, anchor="nw")

        company = self.meta.company or ""         # 우측 하단 제조사
        c.setFillColorRGB(0.1, 0.1, 0.12)
        base = max(h * 0.055, 4.0)
        c.setFont(FONT_REGULAR, base)
        c.drawRightString(w * 0.95, h * 0.16, "Manufacturer")
        c.setFont(FONT_BOLD, base)
        c.drawRightString(w * 0.95, h * 0.16 - base * 1.25, company)
        site = str(self.cfg.get("site", "") or getattr(self.meta, "website", "") or "")
        if site:
            c.setFont(FONT_REGULAR, base)
            c.drawRightString(w * 0.95, h * 0.16 - base * 2.7, site)
        c.restoreState()

    # ── 입력한 값 찍기 ───────────────────────────────────────
    def _draw_values(self, c, w, h) -> None:
        cfg = self.cfg
        x = w * cfg["x"] / 100.0
        y = h - h * cfg["y"] / 100.0
        line = h * cfg["line"] / 100.0 * self._shrink
        base = h * cfg["size"] / 100.0 * self._shrink
        label_w = w * cfg["label_w"] / 100.0

        c.saveState()
        c.setFillColorRGB(0.05, 0.05, 0.07)
        for label, value, scale in self.rows:
            if not (label or value):
                y -= line
                continue
            size = max(base * (scale or 1.0), 3.0)
            if label:
                c.setFont(FONT_REGULAR, size)
                c.drawString(x, y - size, label)
                c.setFont(FONT_BOLD, size)
                c.drawString(x + label_w, y - size, value)
            else:                                  # 라벨이 없으면 제목 줄
                c.setFont(FONT_BOLD, size)
                c.drawString(x, y - size, value)
            y -= max(line, size * 1.35)
        c.restoreState()

    def identity(self, maxLen=None):
        return "NamePlate"


def _nameplate(section: Section, styles, base_dir: str) -> List:
    from ..importers import resolve_image
    from .frame import _find_logo

    from ..placeholders import apply as _sub
    rows = []
    for r in section.grid:
        try:
            scale = float(r.cell(2) or 1.0)
        except ValueError:
            scale = 1.0
        # 명판도 {제품명} {도번} 같은 자동 입력 항목을 쓸 수 있어야 한다
        rows.append((_sub(r.cell(0), _CTX), _sub(r.cell(1), _CTX), scale))

    background = None
    if section.images:
        path = resolve_image(section.images[0].path, base_dir)
        if path and os.path.exists(path):
            try:
                reader = ImageReader(path)
                iw, ih = reader.getSize()
                background = (reader, iw, ih)
            except Exception:
                background = None
    layout = dict(section.layout or {})
    if section.images and section.images[0].width_mm:
        layout.setdefault("width_mm", section.images[0].width_mm)

    plate = NamePlate(rows, layout, _META.get("meta"), base_dir, background,
                      _find_logo(_META["meta"].logo_path, base_dir) if _META.get("meta") else None)
    plate.hAlign = "CENTER"
    return [plate]
