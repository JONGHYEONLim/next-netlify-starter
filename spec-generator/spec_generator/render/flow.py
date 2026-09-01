# -*- coding: utf-8 -*-
"""섹션 → platypus flowable 변환."""
from __future__ import annotations

import os
from typing import List, Optional

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (Image, KeepTogether, Paragraph, Spacer, Table,
                               TableStyle)
from reportlab.platypus.flowables import HRFlowable

from ..fonts import FONT_BOLD, FONT_REGULAR
from ..model import KIND_IMAGE, KIND_SPEC_TABLE, KIND_TEXT, KIND_VERSION_TABLE, Section

CONTENT_W_MM = 170.0
INDENT_STEP_MM = 9.0

SPEC_HEADERS = ["항  목", "사  양", "비  고"]
SPEC_WIDTHS = [37.0, 74.0, 59.0]
VER_HEADERS = ["리비전", "작성자", "발행일", "변  경  내  용"]
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


# 렌더링 한 번 동안 쓰이는 치환표. build_pdf 가 채워 넣는다.
_CTX: dict = {}


def set_context(ctx: dict) -> None:
    global _CTX
    _CTX = ctx or {}


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


def _images(section: Section, styles, base_dir: str) -> List:
    from ..importers import resolve_image
    out: List = []
    for item in section.images:
        path = resolve_image(item.path, base_dir)
        if not path or not os.path.exists(path):
            out.append(Paragraph(_esc(f"[이미지를 찾을 수 없습니다: {item.path}]"), styles["caption"]))
            continue
        try:
            img = Image(path)
            ratio = img.imageHeight / float(img.imageWidth or 1)
            w = min(float(item.width_mm or 150.0), CONTENT_W_MM) * mm
            img.drawWidth, img.drawHeight = w, w * ratio
            img.hAlign = (item.align or "CENTER").upper()
            out.append(img)
        except Exception as exc:  # 손상된 이미지도 문서 생성을 막지 않는다
            out.append(Paragraph(_esc(f"[이미지 오류: {item.path} — {exc}]"), styles["caption"]))
            continue
        cap = "<br/>".join(_esc(x) for x in (item.caption_ko, item.caption_en) if x)
        if cap:
            out.append(Spacer(1, 1.5 * mm))
            out.append(Paragraph(cap, styles["caption"]))
        out.append(Spacer(1, 3 * mm))
    return out


__all__ = ["make_styles", "section_flowables", "CONTENT_W_MM", "HRFlowable"]
