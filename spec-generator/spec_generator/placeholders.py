# -*- coding: utf-8 -*-
"""문서 안에서 쓸 수 있는 치환 항목.

표제란(기본정보)에 한 번 입력한 값을 본문·표 어디서나 다시 쓸 수 있게 한다.
예) 기본 사양표의 '고객사' 칸에  {고객사}  라고 적어 두면
    PDF 를 만들 때 기본정보에 입력한 고객사 이름으로 바뀐다.
"""
from __future__ import annotations

import datetime as _dt
import re
from typing import Dict

from .model import Meta

# 표시용 설명 (도움말·GUI 안내에 쓴다)
DESCRIPTIONS = {
    "{도번}": "도면번호 전체 (BR-RA-HYU-0475-01)",
    "{리비전}": "현재 리비전 (A, B, …)",
    "{발행일}": "리비전 발행일",
    "{고객사}": "고객사 (한글)",
    "{고객사영문}": "고객사 (영문)",
    "{제품명}": "제품명",
    "{용도}": "용도 / 고객 모델",
    "{정격전류}": "기본정보에 입력한 정격 전류",
    "{제품군}": "제품군 이름 (AC 리액터 …)",
    "{회사명}": "Braumm",
    "{오늘}": "PDF 를 만든 날짜",
}

_PATTERN = re.compile(r"\{[가-힣A-Za-z]+\}")


def build_context(meta: Meta) -> Dict[str, str]:
    from . import docnumber as dn
    doc_no = f"{meta.dwg_prefix}-{meta.dwg_no}" if meta.dwg_prefix and meta.dwg_no else (meta.dwg_no or "")
    return {
        "{도번}": doc_no,
        "{리비전}": meta.revision or "",
        "{발행일}": meta.revision_date or "",
        "{고객사}": meta.customer or "",
        "{고객사영문}": meta.customer_en or "",
        "{제품명}": meta.product_name or "",
        "{용도}": meta.use_name or "",
        "{정격전류}": meta.rated_current or "",
        "{제품군}": dn.FAMILIES.get(meta.family, ""),
        "{회사명}": meta.company or "",
        "{오늘}": _dt.date.today().isoformat(),
    }


def apply(text: str, ctx: Dict[str, str]) -> str:
    """모르는 항목은 손대지 않고 그대로 둔다(오타를 눈에 띄게 하려고)."""
    if not text or "{" not in text:
        return text
    return _PATTERN.sub(lambda m: ctx.get(m.group(), m.group()), text)


def help_lines() -> str:
    width = max(len(k) for k in DESCRIPTIONS)
    return "\n".join(f"  {k.ljust(width)}   {v}" for k, v in DESCRIPTIONS.items())
