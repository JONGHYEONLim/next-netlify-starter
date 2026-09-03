# -*- coding: utf-8 -*-
"""고객 승인 사양서 만들기.

생산 사양서 한 건에서 **고객에게 나가도 되는 내용만** 뽑아,
영문 정형 문구(승인 사양서 템플릿)와 합쳐 별도의 문서를 만든다.

안전 원칙
  · 항목(Section)의 기본 공개 범위는 "생산용만" 이다.
    새로 만든 항목은 표시하지 않는 한 절대 고객 문서에 실리지 않는다.
  · 표의 줄도 "생산용만" 으로 표시하면 고객 문서에서 빠진다.
  · 이 조립 과정에서 값을 새로 만들어 내지 않는다. 걸러내기만 한다.
"""
from __future__ import annotations

import copy
from typing import List, Optional

from . import templates as tpl_pkg
from .model import (AUD_CUSTOMER, KIND_TEXT, Section, SpecDoc)

SLOT_KEY = "_customer_content"     # 이 자리에 생산 사양서의 고객 공개 항목이 들어간다
TEMPLATE_NAME = "approval"


def customer_sections(doc: SpecDoc) -> List[Section]:
    """생산 사양서에서 고객에게 나갈 항목만 (표의 줄까지 걸러서) 뽑는다."""
    out: List[Section] = []
    for s in doc.sections:
        if not s.to_customer():
            continue
        copy_ = s.customer_copy()
        # 표만 있고 남은 줄이 하나도 없으면서 그림·글도 없으면 뺀다
        if copy_.kind != KIND_TEXT and not (copy_.rows or copy_.images or copy_.blocks):
            continue
        out.append(copy_)
    return out


def build_doc(doc: SpecDoc, template: Optional[SpecDoc] = None) -> SpecDoc:
    """생산 사양서 → 고객 승인 사양서 문서를 만들어 돌려준다(원본은 건드리지 않는다)."""
    tpl = template or tpl_pkg.load_template(TEMPLATE_NAME)

    out = SpecDoc()
    out.source_path = doc.source_path          # 도면·로고 상대경로 기준을 그대로 쓴다
    out.template = TEMPLATE_NAME

    # 표제 정보는 생산 사양서 것을 그대로, 문서 종류만 승인 사양서로
    out.meta = copy.deepcopy(doc.meta)
    out.meta.doc_kind = tpl.meta.doc_kind or "승인 사양서"
    out.meta.cover_subtitle = tpl.meta.cover_subtitle or "APPROVAL SPECIFICATION"
    out.meta.footer_code = tpl.meta.footer_code or doc.meta.footer_code
    out.meta.cover = True

    picked = customer_sections(doc)
    sections: List[Section] = []
    for s in tpl.sections:
        if s.key == SLOT_KEY:
            sections.extend(copy.deepcopy(picked))
            continue
        sections.append(copy.deepcopy(s))
    out.sections = sections
    return out


def summary(doc: SpecDoc) -> str:
    """고객 문서에 실릴 항목을 사람이 읽을 수 있게 요약한다."""
    picked = customer_sections(doc)
    if not picked:
        return ("고객 승인 사양서에 실릴 항목이 없습니다.\n"
                "각 항목의 '공개 범위' 를 '생산 + 고객' 으로 바꿔 주세요.")
    lines = []
    for s in picked:
        detail = []
        if s.rows:
            detail.append(f"표 {len(s.rows)}줄")
        if s.images:
            detail.append(f"도면 {len(s.images)}장")
        suffix = f"  ({', '.join(detail)})" if detail else ""
        lines.append(f"  · {s.title_ko or '(제목 없음)'}{suffix}")
    hidden = [s.title_ko for s in doc.sections if not s.to_customer()]
    text = "고객 승인 사양서에 실리는 항목:\n" + "\n".join(lines)
    if hidden:
        text += "\n\n실리지 않는 항목(생산용만):\n  " + ", ".join(x for x in hidden if x)
    return text
