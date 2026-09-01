# -*- coding: utf-8 -*-
"""Braumm 도면번호(도번) 체계.

    BR - RA - HYU - 0475 - 01
    │    │    │      │      └ 일련번호 : 같은 고객·같은 정격에서 사양이 다른 제품 구분
    │    │    │      └ 정격전류 4자리 : 475A → 0475
    │    │    └ 고객코드 3자리 : 영문 고객명에서 자동 생성 (Hyundai → HYU)
    │    └ 제품군 2자리 : RA=AC리액터, RD=DC리액터 …
    └ Braumm 고정

원칙
  · 도번은 한 번 부여하면 **절대 바뀌지 않는다**. 제품이 달라지면 새 도번을 딴다.
  · 개정(설계 변경)은 도번이 아니라 **리비전(A → B → C)** 으로 관리한다.
  · 문서·명판 표기는 `BR-RA-HYU-0475-01 Rev.B` 형태.
"""
from __future__ import annotations

import re
from typing import Dict, List, Tuple

PREFIX = "BR"

# 제품군 코드 — 필요하면 여기에 계속 추가하면 된다
FAMILIES: Dict[str, str] = {
    "RA": "AC 리액터 (AC Reactor)",
    "RD": "DC 리액터 (DC Reactor)",
    "RL": "라인 리액터 (Line Reactor)",
    "RZ": "영상 리액터 (Zero-phase Reactor)",
    "CH": "초크 코일 (Choke Coil)",
    "TR": "변압기 (Transformer)",
    "CT": "계기용 변류기 (Current Transformer)",
    "ET": "기타 (Etc.)",
}

_STOPWORDS = {"CO", "LTD", "INC", "CORP", "CORPORATION", "COMPANY", "GROUP",
              "ELECTRIC", "ELECTRONICS", "ENERGY", "SYSTEM", "SYSTEMS", "TECH",
              "TECHNOLOGY", "INDUSTRIAL", "INDUSTRIES", "THE", "AND"}


def customer_code(customer_en: str) -> str:
    """영문 고객명 → 3자리 코드.

    첫 낱말이 3글자 이상이면 그 앞 3글자, 짧으면 다음 낱말의 첫 글자로 채운다.
      Hyundai Electric → HYU     LS Electric → LSE
      LG Energy Solution → LGE   SK → SKX
    """
    words = [w for w in re.split(r"[^A-Za-z0-9]+", (customer_en or "").upper()) if w]
    if not words:
        return "XXX"
    meaningful = [w for w in words if w not in _STOPWORDS] or words

    # 첫 낱말이 3글자 이상이면 그 앞 3글자, 짧으면 뒤 낱말 첫 글자로 채운다
    code = meaningful[0][:3]
    rest = words[words.index(meaningful[0]) + 1:]
    for w in rest:
        if len(code) >= 3:
            break
        code += w[0]
    code = re.sub(r"[^A-Z0-9]", "", code)
    return (code + "XXX")[:3]


def current_code(rated_current: str) -> str:
    """'475 Arms' / '475A' / '1200' → '0475' / '1200'."""
    m = re.search(r"\d+(?:\.\d+)?", str(rated_current or ""))
    if not m:
        return "0000"
    value = int(round(float(m.group())))
    return f"{min(value, 9999):04d}"


def build(family: str, customer_en: str, rated_current: str, serial: str = "01") -> str:
    """전체 도번 문자열을 만든다."""
    fam = (family or "ET").upper()[:2]
    ser = re.sub(r"\D", "", str(serial or "1")) or "1"
    return f"{PREFIX}-{fam}-{customer_code(customer_en)}-{current_code(rated_current)}-{int(ser):02d}"


def split(doc_no: str) -> Tuple[str, str]:
    """표제란에 넣기 위해 'BR' 과 나머지로 나눈다."""
    s = (doc_no or "").strip()
    if s.upper().startswith(PREFIX + "-"):
        return PREFIX, s[len(PREFIX) + 1:]
    return "", s


# ── 리비전 ───────────────────────────────────────────────────
def next_revision(current: str) -> str:
    """A → B → … → Z → AA. 비어 있으면 A."""
    s = re.sub(r"[^A-Za-z]", "", (current or "")).upper()
    if not s:
        return "A"
    chars = list(s)
    i = len(chars) - 1
    while i >= 0:
        if chars[i] != "Z":
            chars[i] = chr(ord(chars[i]) + 1)
            return "".join(chars)
        chars[i] = "A"
        i -= 1
    return "A" + "".join(chars)


def family_choices() -> List[str]:
    return [f"{k}  {v}" for k, v in FAMILIES.items()]


def family_from_choice(choice: str) -> str:
    return (choice or "").split()[0] if choice else "ET"
