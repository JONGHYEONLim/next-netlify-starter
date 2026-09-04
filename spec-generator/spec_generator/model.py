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
from typing import Any, Dict, List, Optional

SCHEMA_VERSION = 2

# ── 파일 호환 정책 ──────────────────────────────────────────
#  · 필드는 "추가" 만 한다. 지우거나 이름을 바꿀 때는 반드시 _LEGACY_KEYS 에 남긴다.
#  · 모르는 키는 조용히 무시한다(옛 버전 프로그램이 새 파일을 열어도 죽지 않게).
#  · 구조가 바뀌면 _MIGRATIONS 에 변환 함수를 추가하고 SCHEMA_VERSION 을 올린다.
#  · tests/fixtures 에 각 버전의 실제 파일을 얼려 두고 selftest 로 계속 검증한다.

# 공개 범위 — 어떤 문서에 실릴지
AUD_INTERNAL = "internal"   # 생산 사양서에만 (기본값 — 실수로 새어 나가지 않게)
AUD_CUSTOMER = "customer"   # 고객 승인 사양서에만
AUD_BOTH = "both"           # 양쪽 모두

AUDIENCE_LABELS = {
    AUD_INTERNAL: "생산용만",
    AUD_BOTH: "생산 + 고객",
    AUD_CUSTOMER: "고객용만",
}


def goes_to_customer(audience: str) -> bool:
    return audience in (AUD_CUSTOMER, AUD_BOTH)


def goes_to_internal(audience: str) -> bool:
    return audience in (AUD_INTERNAL, AUD_BOTH)


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
    """작성 / 검토 / 승인 한 사람.

    stamp 에 도장·사인 이미지(PNG 권장, 배경 투명)를 지정하면 표지 승인란에 찍힌다.
    비워 두면 이름으로 stamps 폴더에서 자동으로 찾는다.
    """
    date: str = ""
    name: str = ""
    stamp: str = ""     # 도장/사인 이미지 경로. 비우면 이름으로 자동 탐색


@dataclass
class Meta:
    product_name: str = ""        # 製品名称 / DESCRIPTION
    use_name: str = ""            # 用途名称 / USE NAME
    doc_kind: str = "생산 사양서"   # 문서 종류
    dwg_prefix: str = "BR"        # 도면번호 접두
    dwg_no: str = ""              # 도면번호 (접두 뒤 부분)
    customer: str = ""            # 고객사 (한글, 폴더명·표기용)
    customer_en: str = ""         # 고객사 (영문, 도번 생성용)
    family: str = "RA"            # 제품군 코드 (docnumber.FAMILIES)
    serial: str = "01"            # 도번 일련번호
    rated_current: str = ""       # 도번 생성에 쓰는 정격전류
    revision: str = "A"           # 리비전 — 도번은 그대로 두고 이것만 올린다
    revision_date: str = ""       # 해당 리비전 발행일
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
    approved: Person = field(default_factory=Person)
    footer_code: str = ""         # 용지 좌측 하단 코드 (예: A4V-21_DOC _03)
    confidential_note: str = (
        "본 문서 및 여기에 포함된 정보는 Braumm 의 자산입니다. "
        "Braumm 의 서면 동의 없이 복제, 복사, 대여하거나 제3자에게 "
        "어떠한 방법으로도 공개할 수 없으며, 승인된 생산 목적 외에는 "
        "사용할 수 없습니다."
    )
    cover: bool = True            # 첫 장에 표지를 넣을지
    cover_subtitle: str = "PRODUCTION SPECIFICATION"
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
    audience: str = AUD_BOTH   # 고객용 항목 안에서는 기본으로 함께 나간다


@dataclass
class VersionRow:
    rev: str = ""
    author: str = ""
    date: str = ""
    changed_ko: str = ""
    changed_en: str = ""


@dataclass
class ImageItem:
    path: str = ""
    width_mm: float = 0.0      # 0 = 지면에 맞춰 최대 크기
    rotate: int = 0            # 0 또는 90 — 가로로 긴 도면을 세로 지면에 크게 넣을 때
    caption_ko: str = ""
    caption_en: str = ""
    align: str = "CENTER"   # LEFT / CENTER / RIGHT


@dataclass
class Section:
    id: str = field(default_factory=_new_id)
    key: str = ""                 # 템플릿과 짝을 맞추는 고정 이름 (업데이트 반영용)
    audience: str = AUD_INTERNAL  # 기본은 생산용만 — 고객에게 보낼 것만 따로 지정한다
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

    def to_customer(self) -> bool:
        return goes_to_customer(self.audience)

    def customer_copy(self) -> "Section":
        """고객용 사본 — 내부용으로 표시된 표의 줄은 빼고 복사한다."""
        import copy as _copy
        out = _copy.deepcopy(self)
        out.rows = [r for r in out.rows if goes_to_customer(r.audience)]
        return out

    def display_name(self) -> str:
        head = self.no_override or self.bullet or ""
        title = " / ".join(x for x in (self.title_ko, self.title_en) if x)
        label = f"{head} {title}".strip() or KIND_LABELS.get(self.kind, self.kind)
        return f"[{KIND_LABELS.get(self.kind, self.kind)}] {label}"


@dataclass
class SpecDoc:
    schema: int = SCHEMA_VERSION
    app_version: str = ""      # 이 파일을 마지막으로 저장한 프로그램 판
    template: str = ""         # 이 문서를 시작할 때 쓴 템플릿 이름
    meta: Meta = field(default_factory=Meta)
    sections: List[Section] = field(default_factory=list)
    # 고객 승인 사양서의 정형 문구(적용 규격·사용 조건·허용 공차 등).
    # 문서 안에 들어 있으므로 제품마다 값을 고치거나 항목을 더할 수 있다.
    # 비어 있으면 프로그램에 들어 있는 승인 템플릿을 그대로 쓴다.
    approval_sections: List[Section] = field(default_factory=list)
    source_path: str = ""   # 저장 경로(직렬화 제외). 상대 이미지 경로 해석 기준.

    # ---------- 직렬화 ----------
    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d.pop("source_path", None)
        return d

    def save(self, path: str) -> None:
        from . import __version__
        self.schema = SCHEMA_VERSION
        self.app_version = __version__
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)
        self.source_path = os.path.abspath(path)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "SpecDoc":
        d = migrate(dict(d or {}))
        meta_d = dict(d.get("meta") or {})
        # v2 까지 approved 는 이름 문자열이었다 → Person 으로 올린다
        if isinstance(meta_d.get("approved"), str):
            meta_d["approved"] = {"name": meta_d["approved"]}
        for key in ("drawn", "checked", "renewal", "approved"):
            meta_d[key] = Person(**_pick(meta_d.get(key) or {}, Person))
        meta = Meta(**_pick(meta_d, Meta))

        def _sections(key: str) -> List[Section]:
            out: List[Section] = []
            for sd in d.get(key) or []:
                sd = dict(sd)
                sd["blocks"] = [Block(**_pick(b, Block)) for b in sd.get("blocks") or []]
                sd["rows"] = [SpecRow(**_pick(r, SpecRow)) for r in sd.get("rows") or []]
                sd["versions"] = [VersionRow(**_pick(r, VersionRow))
                                  for r in sd.get("versions") or []]
                sd["images"] = [ImageItem(**_pick(i, ImageItem)) for i in sd.get("images") or []]
                out.append(Section(**_pick(sd, Section)))
            return out

        return cls(schema=SCHEMA_VERSION, app_version=str(d.get("app_version") or ""),
                   template=str(d.get("template") or ""), meta=meta,
                   sections=_sections("sections"),
                   approval_sections=_sections("approval_sections"))

    @classmethod
    def load(cls, path: str) -> "SpecDoc":
        with open(path, "r", encoding="utf-8") as f:
            doc = cls.from_dict(json.load(f))
        doc.source_path = os.path.abspath(path)
        return doc

    # ---------- 편의 ----------
    def base_dir(self) -> str:
        return os.path.dirname(self.source_path) if self.source_path else os.getcwd()

    def assign_numbers(self, sections: Optional[List[Section]] = None) -> Dict[str, str]:
        """번호가 붙는 섹션에 1,2,3... 을 매긴다. {section.id: '4'} 형태로 반환."""
        out: Dict[str, str] = {}
        n = 0
        for s in (self.sections if sections is None else sections):
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
    "caption_ja": "caption_ko", "title_ja": "title_ko", "version": "author",
}


def _migrate_1_to_2(d: Dict[str, Any]) -> Dict[str, Any]:
    """v1(일영 병기) → v2(한국어). 키 이름 변경은 _LEGACY_KEYS 가 처리하므로
    여기서는 v1 에만 있던 기본값을 손봐 준다."""
    meta = d.setdefault("meta", {})
    meta.setdefault("revision", "A")
    meta.setdefault("family", "RA")
    meta.setdefault("serial", "01")
    if not meta.get("customer") and meta.get("use_name"):
        pass          # 용도명에 고객사가 섞여 있을 수 있으나 임의로 나누지 않는다
    return d


_MIGRATIONS = {1: _migrate_1_to_2}


def migrate(d: Dict[str, Any]) -> Dict[str, Any]:
    """옛 버전 파일을 현재 구조로 올린다. 미래 버전 파일도 최선을 다해 읽는다."""
    version = int(d.get("schema") or 1)
    while version < SCHEMA_VERSION:
        fn = _MIGRATIONS.get(version)
        if fn is None:
            break
        d = fn(d)
        version += 1
    d["schema"] = SCHEMA_VERSION
    return d


def file_is_newer(path: str) -> int:
    """이 프로그램보다 새 버전에서 만든 파일이면 그 schema 번호를, 아니면 0."""
    try:
        with open(path, encoding="utf-8") as f:
            version = int(json.load(f).get("schema") or 1)
    except (OSError, ValueError, TypeError):
        return 0
    return version if version > SCHEMA_VERSION else 0


def _pick(d: Dict[str, Any], klass) -> Dict[str, Any]:
    """알 수 없는 키는 버리고 dataclass 가 받는 필드만 남긴다(하위호환)."""
    names = {f for f in klass.__dataclass_fields__}
    out: Dict[str, Any] = {}
    for k, v in d.items():
        k = _LEGACY_KEYS.get(k, k)
        if k in names and k not in out:
            out[k] = v
    return out
