# -*- coding: utf-8 -*-
"""표준 템플릿 로딩.

내장 템플릿은 이 폴더의 *.spec.json,
사용자가 만든 템플릿은 홈 폴더의 .spec_generator_templates 에 둔다.
"""
from __future__ import annotations

import glob
import os
import sys
from typing import Dict, List

from ..model import SpecDoc


def builtin_dir() -> str:
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return os.path.join(base, "spec_generator", "templates")
    return os.path.dirname(os.path.abspath(__file__))


def user_template_dir() -> str:
    d = os.path.join(os.path.expanduser("~"), ".spec_generator_templates")
    os.makedirs(d, exist_ok=True)
    return d


def list_templates() -> Dict[str, str]:
    """{템플릿이름: 경로}. 사용자 템플릿이 같은 이름이면 우선한다."""
    out: Dict[str, str] = {}
    for d in (builtin_dir(), user_template_dir()):
        for path in sorted(glob.glob(os.path.join(d, "*.spec.json"))):
            out[os.path.basename(path)[: -len(".spec.json")]] = path
    return out


def load_template(name: str) -> SpecDoc:
    paths = list_templates()
    path = paths.get(name)
    if not path:
        if not paths:
            return SpecDoc()
        path = next(iter(paths.values()))
    doc = SpecDoc.load(path)
    doc.source_path = ""     # 템플릿을 덮어쓰지 않도록 경로를 비운다
    return doc


def template_names() -> List[str]:
    return sorted(list_templates())
