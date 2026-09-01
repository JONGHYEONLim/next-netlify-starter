# -*- coding: utf-8 -*-
"""도번 대장.

출력 폴더에 `_도번대장.json` 하나를 두고, 지금까지 발행한 도번과
고객사별 코드를 기록한다. 덕분에

  · 고객코드를 사람이 정하지 않아도 되고 (영문명에서 자동, 겹치면 자동 회피)
  · 일련번호가 자동으로 다음 번호로 올라가며
  · "이 고객한테 예전에 뭘 만들었더라" 를 한눈에 볼 수 있다.

공유 폴더(네트워크 드라이브)에 두면 팀이 같은 대장을 쓰게 된다.
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import string
from typing import Dict, List, Optional

from . import docnumber as dn

FILENAME = "_도번대장.json"
SCHEMA = 1


class Registry:
    def __init__(self, root: str):
        self.root = root
        self.path = os.path.join(root, FILENAME)
        self.data: Dict = {"schema": SCHEMA, "customers": {}, "numbers": {}}
        self.load()

    # ── 파일 ────────────────────────────────────────────────
    def load(self) -> None:
        try:
            with open(self.path, encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                self.data.update({k: v for k, v in loaded.items() if k in self.data})
                self.data.setdefault("customers", {})
                self.data.setdefault("numbers", {})
        except (OSError, ValueError):
            pass          # 없거나 깨졌으면 빈 대장으로 시작한다

    def save(self) -> bool:
        try:
            os.makedirs(self.root, exist_ok=True)
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self.path)
            return True
        except OSError:
            return False

    # ── 고객 코드 ────────────────────────────────────────────
    @staticmethod
    def _key(customer_en: str) -> str:
        return " ".join((customer_en or "").upper().split())

    def _candidates(self, customer_en: str) -> List[str]:
        base = dn.customer_code(customer_en)
        letters = [c for c in (customer_en or "").upper() if c in string.ascii_uppercase]
        out = [base]
        for c in letters[2:] + list(string.ascii_uppercase):
            cand = base[:2] + c
            if cand not in out:
                out.append(cand)
        for d in "23456789":
            out.append(base[:2] + d)
        return out

    def customer_code(self, customer_en: str, customer_ko: str = "") -> str:
        """고객사에 코드를 부여한다. 이미 있으면 그대로, 겹치면 자동으로 피한다."""
        key = self._key(customer_en)
        if not key:
            return "XXX"
        customers = self.data["customers"]
        if key in customers:
            entry = customers[key]
            if customer_ko and not entry.get("name_ko"):
                entry["name_ko"] = customer_ko
            return entry["code"]
        taken = {v["code"] for v in customers.values()}
        code = next((c for c in self._candidates(customer_en) if c not in taken), "XXX")
        customers[key] = {"code": code, "name_ko": customer_ko,
                          "registered": _dt.date.today().isoformat()}
        return code

    def customer_of_code(self, code: str) -> str:
        for key, v in self.data["customers"].items():
            if v.get("code") == code:
                return v.get("name_ko") or key
        return ""

    # ── 번호 ────────────────────────────────────────────────
    def next_serial(self, family: str, code: str, rated_current: str) -> str:
        """같은 (제품군·고객·정격) 안에서 다음 일련번호."""
        stem = f"{dn.PREFIX}-{family}-{code}-{dn.current_code(rated_current)}-"
        used = []
        for no in self.data["numbers"]:
            if no.startswith(stem):
                tail = no[len(stem):]
                if tail.isdigit():
                    used.append(int(tail))
        return f"{(max(used) + 1) if used else 1:02d}"

    def issue(self, family: str, customer_en: str, customer_ko: str,
              rated_current: str, product: str = "") -> str:
        """새 도번을 발급하고 대장에 기록한다."""
        self.load()                                   # 공유 폴더 대비 최신 상태로
        code = self.customer_code(customer_en, customer_ko)
        serial = self.next_serial(family, code, rated_current)
        number = f"{dn.PREFIX}-{family}-{code}-{dn.current_code(rated_current)}-{serial}"
        self.record(number, family=family, customer_en=customer_en, customer=customer_ko,
                    rated_current=rated_current, product=product)
        return number

    def record(self, number: str, **info) -> None:
        """이미 있는 도번의 정보를 갱신하거나 새로 등록한다."""
        if not number:
            return
        entry = self.data["numbers"].setdefault(
            number, {"created": _dt.date.today().isoformat()})
        entry.update({k: v for k, v in info.items() if v not in (None, "")})
        entry["updated"] = _dt.date.today().isoformat()

    def lookup(self, number: str) -> Optional[Dict]:
        return self.data["numbers"].get(number)

    def rows(self) -> List[Dict]:
        """대장 보기용 — 도번 오름차순."""
        out = []
        for number, info in sorted(self.data["numbers"].items()):
            row = dict(info)
            row["number"] = number
            out.append(row)
        return out

    def count(self) -> int:
        return len(self.data["numbers"])
