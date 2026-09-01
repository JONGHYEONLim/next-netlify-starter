# -*- coding: utf-8 -*-
"""생산용 사양서 데이터 모델 / Data model for the production specification document.

문서 한 건은 JSON 파일 하나(.spec.json)로 저장된다.
- meta     : 도면 표제란(title block)에 들어가는 공통 정보
- sections : 본문을 구성하는 항목들. 종류(kind)에 따라 표/본문/도면/판수관리표로 렌더링된다.
"""
from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List

SCHEMA_VERSION = 1

# 섹션 종류
KIND_TEXT = "text"                    # 번호 항목 + 본문(일/영 병기)
KIND_SPEC_TABLE = "spec_table"        # 항목/사양/비고 3열 표
KIND_VERSION_TABLE = "version_table"  # 판수관리표
KIND_IMAGE = "image"                  # 도면/그림

KIND_LABELS = {
    KIND_TEXT: "본문 항목",
    KIND_SPEC_TABLE: "사양표",
    KIND_IMAGE: "도면/그림",
    KIND_VERSION_TABLE: "판수관리표",
}


def _new_id() -> str:
    return uuid.uuid4().hex[:8]


@dataclass
class Person:
    """표제란의 DRAWN / CHECKED / RENEWAL 한 줄."""
    date: str = ""
    name: str = ""


@dataclass
class Meta:
    product_name: str = ""        # 製品名称 / DESCRIPTION
    use_name: str = ""            # 用途名称 / USE NAME
    doc_kind: str = "생산 사양서"   # 문서 종류
    dwg_prefix: str = "BR"        # 도면번호 접두
    dwg_no: str = ""              # 도면번호
    old_dwg_no: str = ""          # OLD DWG.NO.
    dwg_code: str = ""            # DWG CODE 좌측 칸
    dwg_code2: str = ""           # DWG CODE 우측 칸
    standard: str = "STANDARD"
    index: str = ""
    company: str = "Braumm"
    logo_path: str = ""           # 표제란에 넣을 로고 이미지(PNG/JPG). 비우면 자동 탐색
    logo_height_mm: float = 8.5
    label_product: str = "제품명"   # 좌측 세로 표제란 라벨
    label_use: str = "용도"
    label_kind: str = "문서종류"
    drawn: Person = field(default_factory=Person)
    checked: Person = field(default_factory=Person)
    renewal: Person = field(default_factory=Person)
    approved: str = ""
    footer_code: str = ""         # 용지 좌측 하단 코드 (예: A4V-21_DOC _03)
    confidential_note: str = (
        "본 문서 및 여기에 포함된 정보는 Braumm 의 자산입니다. "
        "Braumm 의 서면 동의 없이 복제, 복사, 대여하거나 제3자에게 "
        "어떠한 방법으로도 공개할 수 없으며, 승인된 생산 목적 외에는 "
        "사용할 수 없습니다."
    )
    page_start: int = 1           # 첫 페이지에 찍히는 PAGE 번호
    page_total: int = 0           # 0 이면 실제 생성 페이지 수로 자동 계산
    revision_rows: int = 5        # 좌측 REVISIONS 빈 칸 수


@dataclass
class Block:
    """본문 한 줄(문단). 한국어(필수) 아래에 영문(선택)을 병기한다."""
    indent: int = 1     # 0=제목과 같은 위치, 1,2,3... 단계별 들여쓰기
    marker: str = ""    # "(1)", "①" 등 머리기호
    ko: str = ""
    en: str = ""


@dataclass
class SpecRow:
    """사양표 한 행. spec/remark 는 줄바꿈으로 여러 줄 입력 가능."""
    item_ko: str = ""
    item_en: str = ""
    spec: str = ""
    remark: str = ""


@dataclass
class VersionRow:
    rev: str = ""
    version: str = ""
    date: str = ""
    changed_ko: str = ""
    changed_en: str = ""


@dataclass
class ImageItem:
    path: str = ""
    width_mm: float = 150.0
    caption_ko: str = ""
    caption_en: str = ""
    align: str = "CENTER"   # LEFT / CENTER / RIGHT


@dataclass
class Section:
    id: str = field(default_factory=_new_id)
    kind: str = KIND_TEXT
    numbered: bool = True         # True 면 1. 2. 3. 자동 번호
    no_override: str = ""         # 번호를 직접 지정할 때
    bullet: str = ""              # 번호 대신 쓸 기호 (예: "○")
    title_ko: str = ""
    title_en: str = ""
    underline: bool = True
    page_break_before: bool = False
    note: str = ""                # 제목 오른쪽 또는 아래에 붙는 ※ 주기
    blocks: List[Block] = field(default_factory=list)
    rows: List[SpecRow] = field(default_factory=list)
    versions: List[VersionRow] = field(default_factory=list)
    images: List[ImageItem] = field(default_factory=list)
    part_no: str = ""             # 판수관리표의 <PartNo. P1> 표기
    headers: List[str] = field(default_factory=list)          # 표 머리글(비우면 기본값)
    col_widths_mm: List[float] = field(default_factory=list)  # 표 열 너비(비우면 기본값)

    def display_name(self) -> str:
        head = self.no_override or self.bullet or ""
        title = " / ".join(x for x in (self.title_ko, self.title_en) if x)
        label = f"{head} {title}".strip() or KIND_LABELS.get(self.kind, self.kind)
        return f"[{KIND_LABELS.get(self.kind, self.kind)}] {label}"


@dataclass
class SpecDoc:
    schema: int = SCHEMA_VERSION
    meta: Meta = field(default_factory=Meta)
    sections: List[Section] = field(default_factory=list)
    source_path: str = ""   # 저장 경로(직렬화 제외). 상대 이미지 경로 해석 기준.

    # ---------- 직렬화 ----------
    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d.pop("source_path", None)
        return d

    def save(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)
        self.source_path = os.path.abspath(path)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "SpecDoc":
        meta_d = dict(d.get("meta") or {})
        for key in ("drawn", "checked", "renewal"):
            meta_d[key] = Person(**_pick(meta_d.get(key) or {}, Person))
        meta = Meta(**_pick(meta_d, Meta))

        sections: List[Section] = []
        for sd in d.get("sections") or []:
            sd = dict(sd)
            sd["blocks"] = [Block(**_pick(b, Block)) for b in sd.get("blocks") or []]
            sd["rows"] = [SpecRow(**_pick(r, SpecRow)) for r in sd.get("rows") or []]
            sd["versions"] = [VersionRow(**_pick(r, VersionRow)) for r in sd.get("versions") or []]
            sd["images"] = [ImageItem(**_pick(i, ImageItem)) for i in sd.get("images") or []]
            sections.append(Section(**_pick(sd, Section)))
        return cls(schema=int(d.get("schema", SCHEMA_VERSION)), meta=meta, sections=sections)

    @classmethod
    def load(cls, path: str) -> "SpecDoc":
        with open(path, "r", encoding="utf-8") as f:
            doc = cls.from_dict(json.load(f))
        doc.source_path = os.path.abspath(path)
        return doc

    # ---------- 편의 ----------
    def base_dir(self) -> str:
        return os.path.dirname(self.source_path) if self.source_path else os.getcwd()

    def assign_numbers(self) -> Dict[str, str]:
        """번호가 붙는 섹션에 1,2,3... 을 매긴다. {section.id: '4'} 형태로 반환."""
        out: Dict[str, str] = {}
        n = 0
        for s in self.sections:
            if not s.numbered:
                out[s.id] = s.no_override or s.bullet
                continue
            if s.no_override:
                out[s.id] = s.no_override
                # 수동 번호가 숫자면 그 뒤부터 이어서 자동 채번
                if s.no_override.strip().rstrip(".").isdigit():
                    n = int(s.no_override.strip().rstrip("."))
                continue
            n += 1
            out[s.id] = str(n)
        return out


# v1 에서 일본어 병기용으로 쓰던 키 → 현재 한국어 키
_LEGACY_KEYS = {
    "ja": "ko", "item_ja": "item_ko", "changed_ja": "changed_ko",
    "caption_ja": "caption_ko", "title_ja": "title_ko",
}


def _pick(d: Dict[str, Any], klass) -> Dict[str, Any]:
    """알 수 없는 키는 버리고 dataclass 가 받는 필드만 남긴다(하위호환)."""
    names = {f for f in klass.__dataclass_fields__}
    out: Dict[str, Any] = {}
    for k, v in d.items():
        k = _LEGACY_KEYS.get(k, k)
        if k in names and k not in out:
            out[k] = v
    return out
