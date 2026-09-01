# -*- coding: utf-8 -*-
"""PDF 에 쓸 CJK 폰트 등록.

한국어 UI 로 입력하더라도 산출물에는 일본어/영어가 섞이므로,
한글·가나·한자를 모두 담은 폰트를 우선 찾는다.
찾지 못하면 reportlab 내장 CID 폰트(일본어)로 자동 대체한다.
"""
from __future__ import annotations

import glob
import os
import sys
from typing import List, Optional, Tuple

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.ttfonts import TTFont

FONT_REGULAR = "SpecGen"
FONT_BOLD = "SpecGen-Bold"

# (경로 후보, 폰트 인덱스) — 앞에 있을수록 우선. 한중일+한글 커버리지가 넓은 순.
_CANDIDATES: List[Tuple[str, int]] = [
    # 번들 폰트 (assets/fonts 에 넣어두면 최우선 사용)
    ("<bundled>", 0),
    # Windows
    (r"C:\Windows\Fonts\NotoSansCJKkr-Regular.otf", 0),
    (r"C:\Windows\Fonts\malgun.ttf", 0),
    (r"C:\Windows\Fonts\meiryo.ttc", 0),
    (r"C:\Windows\Fonts\YuGothM.ttc", 0),
    (r"C:\Windows\Fonts\msgothic.ttc", 0),
    # macOS
    ("/System/Library/Fonts/AppleSDGothicNeo.ttc", 0),
    ("/Library/Fonts/Arial Unicode.ttf", 0),
    # Linux
    ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", 0),
    ("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc", 0),
    ("/usr/share/fonts/truetype/nanum/NanumGothic.ttf", 0),
    ("/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc", 0),
    ("/usr/share/fonts/opentype/unifont/unifont_jp.otf", 0),
]

_BOLD_HINTS = {
    "malgun.ttf": "malgunbd.ttf",
    "NotoSansCJKkr-Regular.otf": "NotoSansCJKkr-Bold.otf",
    "NotoSansCJK-Regular.ttc": "NotoSansCJK-Bold.ttc",
    "NanumGothic.ttf": "NanumGothicBold.ttf",
    "msgothic.ttc": None,
}

_registered = False
_active_path: Optional[str] = None


def bundled_font_dir() -> str:
    """PyInstaller 로 묶였을 때와 소스 실행일 때 모두 동작하는 assets/fonts 경로."""
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return os.path.join(base, "assets", "fonts")
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(here, "assets", "fonts")


def _bundled_candidates() -> List[str]:
    d = bundled_font_dir()
    out: List[str] = []
    for pat in ("*.ttf", "*.otf", "*.ttc"):
        out.extend(sorted(glob.glob(os.path.join(d, pat))))
    # Bold 로 보이는 파일은 본문용 후보에서 제외
    return [p for p in out if "bold" not in os.path.basename(p).lower()]


def _try_register(name: str, path: str, index: int = 0) -> bool:
    try:
        if path.lower().endswith(".ttc"):
            pdfmetrics.registerFont(TTFont(name, path, subfontIndex=index))
        else:
            pdfmetrics.registerFont(TTFont(name, path))
        return True
    except Exception:
        return False


def _bold_for(path: str) -> Optional[str]:
    base = os.path.basename(path)
    guess = _BOLD_HINTS.get(base)
    if guess:
        cand = os.path.join(os.path.dirname(path), guess)
        if os.path.exists(cand):
            return cand
    for suffix in ("Bold", "-Bold", "bd", "B"):
        stem, ext = os.path.splitext(path)
        cand = f"{stem}{suffix}{ext}"
        if os.path.exists(cand):
            return cand
    return None


def register_fonts(preferred: Optional[str] = None) -> str:
    """폰트를 등록하고 실제 사용된 경로(또는 CID 폰트명)를 돌려준다."""
    global _registered, _active_path
    if _registered:
        return _active_path or FONT_REGULAR

    order: List[Tuple[str, int]] = []
    if preferred:
        order.append((preferred, 0))
    for path, idx in _CANDIDATES:
        if path == "<bundled>":
            order.extend((p, 0) for p in _bundled_candidates())
        else:
            order.append((path, idx))

    for path, idx in order:
        if not path or not os.path.exists(path):
            continue
        if _try_register(FONT_REGULAR, path, idx):
            bold = _bold_for(path)
            if not (bold and _try_register(FONT_BOLD, bold, idx)):
                pdfmetrics.registerFontFamily(FONT_REGULAR, normal=FONT_REGULAR, bold=FONT_REGULAR)
                _alias_bold_to_regular()
            _registered, _active_path = True, path
            return path

    # 최후 수단: reportlab 내장 일본어 CID 폰트(한글은 표시되지 않음)
    pdfmetrics.registerFont(UnicodeCIDFont("HeiseiKakuGo-W5"))
    _alias(FONT_REGULAR, "HeiseiKakuGo-W5")
    _alias(FONT_BOLD, "HeiseiKakuGo-W5")
    _registered, _active_path = True, "HeiseiKakuGo-W5 (내장 CID, 한글 미지원)"
    return _active_path


def _alias(alias_name: str, real_name: str) -> None:
    font = pdfmetrics.getFont(real_name)
    pdfmetrics.registerFont(_Alias(alias_name, font))


def _alias_bold_to_regular() -> None:
    if FONT_BOLD not in pdfmetrics.getRegisteredFontNames():
        _alias(FONT_BOLD, FONT_REGULAR)


class _Alias:
    """등록된 폰트를 다른 이름으로 재사용하기 위한 얇은 래퍼."""

    def __init__(self, name, font):
        self.__dict__.update(font.__dict__)
        self._real = font
        self.fontName = name

    def __getattr__(self, item):
        return getattr(self._real, item)


def active_font_description() -> str:
    return _active_path or "(미등록)"
