# -*- coding: utf-8 -*-
"""SpecDoc → PDF."""
from __future__ import annotations

import io
import os
from typing import Optional

from reportlab.lib.pagesizes import A4
from reportlab.platypus import BaseDocTemplate, Frame, PageBreak, PageTemplate

from ..fonts import register_fonts
from ..model import SpecDoc
from .. import placeholders
from . import flow, frame


class _Doc(BaseDocTemplate):
    def __init__(self, target, meta, total_getter, base_dir=""):
        super().__init__(target, pagesize=A4,
                         leftMargin=0, rightMargin=0, topMargin=0, bottomMargin=0,
                         title=f"{meta.dwg_prefix} {meta.dwg_no}".strip(),
                         author=meta.company, subject=meta.doc_kind)
        x, y, w, h = frame.content_frame_rect()
        f = Frame(x, y, w, h, leftPadding=0, rightPadding=0,
                  topPadding=0, bottomPadding=0, id="content")
        self.addPageTemplates([PageTemplate(
            id="std", frames=[f],
            onPage=frame.FrameDrawer(meta, total_getter, base_dir))])


def _story(doc: SpecDoc, styles):
    numbers = doc.assign_numbers()
    base_dir = doc.base_dir()
    story = []
    for i, s in enumerate(doc.sections):
        if s.page_break_before and story:
            story.append(PageBreak())
        story.extend(flow.section_flowables(s, numbers.get(s.id, ""), styles, base_dir))
    return story


def build_pdf(doc: SpecDoc, out_path: str, font_path: Optional[str] = None) -> str:
    """PDF 를 만들고 실제 저장 경로를 돌려준다.

    페이지 총수(PAGE n/N)를 찍기 위해 두 번 조판한다.
    """
    register_fonts(font_path)
    styles = flow.make_styles()
    flow.set_context(placeholders.build_context(doc.meta))

    total = {"n": doc.meta.page_total or 0}
    if not doc.meta.page_total:
        probe = _Doc(io.BytesIO(), doc.meta, lambda: 0, doc.base_dir())
        probe.build(_story(doc, styles))
        total["n"] = probe.page + max(0, doc.meta.page_start - 1)

    out_dir = os.path.dirname(os.path.abspath(out_path))
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    final = _Doc(out_path, doc.meta, lambda: total["n"], doc.base_dir())
    final.build(_story(doc, styles))
    return os.path.abspath(out_path)
