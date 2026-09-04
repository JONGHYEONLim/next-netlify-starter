# -*- coding: utf-8 -*-
"""SpecDoc → PDF."""
from __future__ import annotations

import io
import os
from typing import List, Optional

from reportlab.lib.pagesizes import A4
from reportlab.platypus import (BaseDocTemplate, Frame, NextPageTemplate,
                                PageBreak, PageTemplate, Spacer)
from reportlab.platypus.doctemplate import ActionFlowable

from ..fonts import register_fonts
from ..model import SpecDoc, internal_sections
from .. import placeholders
from . import approval as approval_render
from . import cover as cover_mod
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
        offset = 1 if meta.cover else 0
        pages = [PageTemplate(
            id="std", frames=[f],
            onPage=frame.FrameDrawer(meta, total_getter, base_dir, page_offset=offset))]
        if meta.cover:
            # 표지는 도면 양식 없이 통짜 한 장. 쪽 번호에서도 빼 준다.
            blank = Frame(0, 0, A4[0], A4[1], id="cover", showBoundary=0)
            pages.insert(0, PageTemplate(id="cover", frames=[blank],
                                         onPage=cover_mod.CoverDrawer(meta, base_dir)))
        self.addPageTemplates(pages)


def _is_filler(f) -> bool:
    """혼자 있으면 아무것도 안 찍히는 flowable(빈 칸·내부 지시)인가."""
    return isinstance(f, (Spacer, ActionFlowable))


def _tidy(body: List) -> List:
    """빈 페이지를 만드는 페이지 넘김을 걷어낸다.

    항목을 골라 싣다 보면(고객용/생산용 분리, 항목 삭제 등) '페이지 넘김' 만
    잇달아 남는 자리가 생긴다. 그대로 두면 아무것도 없는 장이 끼어든다.
      · 앞에 실제 내용이 없는 페이지 넘김은 버린다 (맨 앞 · 넘김 바로 뒤)
      · 맨 끝의 페이지 넘김도 버린다 (마지막에 빈 장이 붙는다)
    """
    out: List = []
    for item in body:
        if isinstance(item, PageBreak):
            j = len(out) - 1
            while j >= 0 and _is_filler(out[j]):
                j -= 1
            if j < 0 or isinstance(out[j], PageBreak):
                continue                      # 앞에 실린 내용이 없다 → 넘길 것이 없다
        out.append(item)
    while out and isinstance(out[-1], PageBreak):
        out.pop()
    return out


def _story(doc: SpecDoc, styles, sections=None):
    """조판할 flowable 목록. sections 를 주면 그것만 싣는다."""
    if sections is None:
        sections = doc.sections
    numbers = doc.assign_numbers(sections)
    base_dir = doc.base_dir()
    body: List = []
    for s in sections:
        if s.page_break_before:
            body.append(PageBreak())
        body.extend(flow.section_flowables(s, numbers.get(s.id, ""), styles, base_dir))
    body = _tidy(body)
    # 표지는 통짜 한 장이라, 표지를 닫는 넘김은 손대지 않고 앞에 붙인다.
    if doc.meta.cover:
        return [Spacer(1, 1), NextPageTemplate("std"), PageBreak()] + body
    return body


class _ApprovalDoc(BaseDocTemplate):
    """고객 승인 사양서용 — 도면 양식 대신 깔끔한 머리말·꼬리말."""

    def __init__(self, target, meta, total_getter, base_dir="", revisions=()):
        super().__init__(target, pagesize=A4,
                         leftMargin=0, rightMargin=0, topMargin=0, bottomMargin=0,
                         title=f"{meta.dwg_prefix}-{meta.dwg_no}".strip("-"),
                         author=meta.company, subject=meta.doc_kind)
        x, y, w, h = approval_render.content_frame_rect()
        f = Frame(x, y, w, h, leftPadding=0, rightPadding=0,
                  topPadding=0, bottomPadding=0, id="content")
        offset = 1 if meta.cover else 0
        pages = [PageTemplate(id="std", frames=[f],
                              onPage=approval_render.ApprovalFrame(meta, total_getter, offset,
                                                                  base_dir))]
        if meta.cover:
            cover = approval_render.ApprovalCover(meta, base_dir)
            cover._revs = list(revisions)
            blank = Frame(0, 0, A4[0], A4[1], id="cover")
            pages.insert(0, PageTemplate(id="cover", frames=[blank], onPage=cover))
        self.addPageTemplates(pages)


def _revision_rows(source: SpecDoc):
    """생산 사양서의 개정 이력 표 → 승인 사양서 표지에 실을 줄."""
    from ..model import KIND_VERSION_TABLE
    for s in source.sections:
        if s.kind != KIND_VERSION_TABLE:
            continue
        rows = [(v.rev, v.date, v.changed_ko or v.changed_en, v.author,
                 source.meta.approved.name)
                for v in s.versions if (v.rev or v.date or v.changed_ko)]
        return list(reversed(rows))
    return []


def build_approval_pdf(doc: SpecDoc, out_path: str, font_path: Optional[str] = None,
                       source: Optional[SpecDoc] = None) -> str:
    """고객 승인 사양서 PDF. doc 은 approval.build_doc() 이 만든 문서."""
    register_fonts(font_path)
    styles = flow.make_styles()
    flow.set_context(placeholders.build_context(doc.meta), doc.meta)
    revisions = _revision_rows(source or doc)

    total = {"n": 0}
    probe = _ApprovalDoc(io.BytesIO(), doc.meta, lambda: 0, doc.base_dir(), revisions)
    probe.build(_story(doc, styles))
    total["n"] = probe.page - (1 if doc.meta.cover else 0)

    out_dir = os.path.dirname(os.path.abspath(out_path))
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    final = _ApprovalDoc(out_path, doc.meta, lambda: total["n"], doc.base_dir(), revisions)
    final.build(_story(doc, styles))
    return os.path.abspath(out_path)


def build_both(doc: SpecDoc, production_path: str, approval_path: str,
               font_path: Optional[str] = None):
    """생산 사양서와 고객 승인 사양서를 한 번에. (생산, 승인) 경로를 돌려준다."""
    from .. import approval as approval_mod
    a = build_pdf(doc, production_path, font_path)
    b = build_approval_pdf(approval_mod.build_doc(doc), approval_path, font_path, source=doc)
    return a, b


def build_pdf(doc: SpecDoc, out_path: str, font_path: Optional[str] = None) -> str:
    """PDF 를 만들고 실제 저장 경로를 돌려준다.

    페이지 총수(PAGE n/N)를 찍기 위해 두 번 조판한다.
    """
    register_fonts(font_path)
    styles = flow.make_styles()
    flow.set_context(placeholders.build_context(doc.meta), doc.meta)

    # '고객용만' 으로 표시한 항목·줄은 생산 사양서에 싣지 않는다.
    sections = internal_sections(doc)

    total = {"n": doc.meta.page_total or 0}
    if not doc.meta.page_total:
        probe = _Doc(io.BytesIO(), doc.meta, lambda: 0, doc.base_dir())
        probe.build(_story(doc, styles, sections))
        content_pages = probe.page - (1 if doc.meta.cover else 0)
        total["n"] = content_pages + max(0, doc.meta.page_start - 1)

    out_dir = os.path.dirname(os.path.abspath(out_path))
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    final = _Doc(out_path, doc.meta, lambda: total["n"], doc.base_dir())
    final.build(_story(doc, styles, sections))
    return os.path.abspath(out_path)
