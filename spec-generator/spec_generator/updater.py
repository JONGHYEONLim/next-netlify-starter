# -*- coding: utf-8 -*-
"""이미 만들어 둔 문서에 템플릿의 새 항목을 반영한다.

프로그램을 업데이트해서 표준 템플릿에 항목이나 표의 줄이 늘어나면,
예전에 저장해 둔 문서도 그 변화를 가져올 수 있어야 한다.

원칙 (안전이 먼저):
  · **더하기만 한다.** 이미 적어 둔 값은 절대 덮어쓰지 않고, 지우지도 않는다.
  · 사용자가 손수 추가한 항목·줄은 그대로 둔다.
  · 무엇이 들어올지 먼저 보여 주고, 하나씩 골라서 적용한다.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .model import (KIND_SPEC_TABLE, Block, Section, SpecDoc, SpecRow)

# 어떤 변화인지
ADD_SECTION = "section"     # 새 항목(장) 추가
ADD_ROW = "row"             # 사양표에 줄 추가
ADD_BLOCK = "block"         # 본문에 문구 추가
FILL_VALUE = "fill"         # 비어 있는 칸에 템플릿 기본값(자동 입력 항목 등) 채우기

KIND_LABEL = {
    ADD_SECTION: "새 항목",
    ADD_ROW: "표에 줄 추가",
    ADD_BLOCK: "본문 문구 추가",
    FILL_VALUE: "빈 칸 채우기",
}


@dataclass
class Change:
    kind: str
    label: str                  # 목록에 보일 한 줄
    where: str                  # 어느 항목에 적용되는지
    payload: Any = None
    index: int = 0              # 삽입 위치
    target_id: str = ""         # 대상 섹션의 id


@dataclass
class Plan:
    changes: List[Change] = field(default_factory=list)

    def __bool__(self) -> bool:
        return bool(self.changes)


def _match(doc: SpecDoc, tpl_section: Section) -> Optional[Section]:
    """템플릿 항목에 대응하는 문서 항목을 찾는다. key 우선, 없으면 제목으로."""
    if tpl_section.key:
        for s in doc.sections:
            if s.key and s.key == tpl_section.key:
                return s
    title = (tpl_section.title_ko or "").strip()
    if title:
        for s in doc.sections:
            if not s.key and (s.title_ko or "").strip() == title:
                return s
    return None


def _norm(text: str) -> str:
    return " ".join((text or "").split())


def plan(doc: SpecDoc, template: SpecDoc) -> Plan:
    """문서와 템플릿을 견주어 '더하면 좋을 것들' 목록을 만든다."""
    out: List[Change] = []
    insert_at = len(doc.sections)          # 짝이 없는 항목을 넣을 자리
    after = ""                             # 바로 앞에 오는(짝이 맞은) 항목 이름

    for tpl in template.sections:
        found = _match(doc, tpl)
        if found is None:
            new = copy.deepcopy(tpl)
            new.id = Section().id
            out.append(Change(
                ADD_SECTION,
                f"{tpl.title_ko or '(제목 없음)'}",
                f"'{after}' 뒤에 추가" if after else "문서 맨 앞에 추가",
                payload=new, index=insert_at))
            continue

        insert_at = doc.sections.index(found) + 1
        after = found.title_ko or ""
        if not found.key and tpl.key:
            found.key = tpl.key            # 다음부터 확실히 짝이 맞도록 조용히 붙여 준다

        where = found.title_ko or "(제목 없음)"

        if tpl.kind == KIND_SPEC_TABLE and found.kind == KIND_SPEC_TABLE:
            have = {_norm(r.item_ko) for r in found.rows}
            for i, row in enumerate(tpl.rows):
                if _norm(row.item_ko) and _norm(row.item_ko) not in have:
                    out.append(Change(ADD_ROW, row.item_ko, where,
                                      payload=copy.deepcopy(row), index=i,
                                      target_id=found.id))
            # 비어 있는 칸에 템플릿 기본값 채우기 (자동 입력 항목 등)
            tpl_by_item = {_norm(r.item_ko): r for r in tpl.rows}
            for r in found.rows:
                t = tpl_by_item.get(_norm(r.item_ko))
                if t and t.spec and not (r.spec or "").strip():
                    out.append(Change(FILL_VALUE, f"{r.item_ko} → {t.spec}", where,
                                      payload=(r.item_ko, t.spec), target_id=found.id))

        have_blocks = {(_norm(b.marker), _norm(b.ko)) for b in found.blocks}
        for b in tpl.blocks:
            if not _norm(b.ko) and not _norm(b.en):
                continue
            if (_norm(b.marker), _norm(b.ko)) not in have_blocks:
                out.append(Change(ADD_BLOCK, b.ko or b.en, where,
                                  payload=copy.deepcopy(b), target_id=found.id))

    return Plan(out)


def apply(doc: SpecDoc, changes: List[Change]) -> int:
    """고른 변화를 문서에 반영한다. 반영한 건수를 돌려준다."""
    by_id: Dict[str, Section] = {s.id: s for s in doc.sections}
    done = 0

    # 표·본문 먼저 (섹션 인덱스가 흔들리지 않게)
    for c in changes:
        target = by_id.get(c.target_id)
        if target is None:
            continue
        if c.kind == ADD_ROW:
            pos = min(c.index, len(target.rows))
            target.rows.insert(pos, c.payload)
            done += 1
        elif c.kind == ADD_BLOCK:
            target.blocks.append(c.payload)
            done += 1
        elif c.kind == FILL_VALUE:
            item, value = c.payload
            for r in target.rows:
                if _norm(r.item_ko) == _norm(item) and not (r.spec or "").strip():
                    r.spec = value
                    done += 1
                    break

    # 새 항목은 나중에. 같은 자리에 들어갈 것들은 묶어서 한 번에,
    # 자리는 뒤에서부터 채워야 앞쪽 위치가 밀리지 않는다.
    groups: Dict[int, List[Section]] = {}
    for c in changes:
        if c.kind == ADD_SECTION:
            groups.setdefault(c.index, []).append(c.payload)
    for anchor in sorted(groups, reverse=True):
        at = min(anchor, len(doc.sections))
        doc.sections[at:at] = groups[anchor]
        done += len(groups[anchor])
    return done


def summary(p: Plan) -> str:
    if not p:
        return "추가할 것이 없습니다. 이미 최신 구성입니다."
    counts: Dict[str, int] = {}
    for c in p.changes:
        counts[c.kind] = counts.get(c.kind, 0) + 1
    return ", ".join(f"{KIND_LABEL[k]} {v}건" for k, v in counts.items())
