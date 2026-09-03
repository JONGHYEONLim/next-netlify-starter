# -*- coding: utf-8 -*-
"""외부 자료 가져오기: 도면 파일(PDF/이미지)과 엑셀 붙여넣기."""
from __future__ import annotations

import hashlib
import os
import shutil
import tempfile
from typing import List, Optional

IMAGE_EXT = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tif", ".tiff"}
PDF_EXT = {".pdf"}
SUPPORTED_EXT = IMAGE_EXT | PDF_EXT

_CACHE = os.path.join(tempfile.gettempdir(), "spec_generator_cache")


def cache_dir() -> str:
    os.makedirs(_CACHE, exist_ok=True)
    return _CACHE


def resolve_image(path: str, base_dir: str) -> Optional[str]:
    """상대경로를 풀고, PDF 라면 첫 페이지를 PNG 로 변환한 경로를 돌려준다."""
    if not path:
        return None
    p = path if os.path.isabs(path) else os.path.normpath(os.path.join(base_dir, path))
    if not os.path.exists(p):
        return None
    if os.path.splitext(p)[1].lower() in PDF_EXT:
        return pdf_page_to_png(p, page=0)
    return p


def pdf_page_to_png(pdf_path: str, page: int = 0, dpi: int = 220) -> Optional[str]:
    """PDF 한 페이지를 PNG 로 변환(캐시). PyMuPDF 가 없으면 None."""
    try:
        import pymupdf  # type: ignore
    except ImportError:
        try:
            import fitz as pymupdf  # type: ignore
        except ImportError:
            return None
    st = os.stat(pdf_path)
    key = hashlib.md5(f"{pdf_path}|{st.st_mtime_ns}|{page}|{dpi}".encode()).hexdigest()
    out = os.path.join(cache_dir(), f"{key}.png")
    if os.path.exists(out):
        return out
    with pymupdf.open(pdf_path) as d:
        if page >= d.page_count:
            return None
        d[page].get_pixmap(dpi=dpi).save(out)
    return out


def pdf_page_count(pdf_path: str) -> int:
    try:
        import pymupdf  # type: ignore
    except ImportError:
        try:
            import fitz as pymupdf  # type: ignore
        except ImportError:
            return 0
    with pymupdf.open(pdf_path) as d:
        return d.page_count


def copy_into_project(src: str, project_dir: str, subdir: str = "figures") -> str:
    """도면 파일을 프로젝트 폴더 안으로 복사하고 상대경로를 돌려준다."""
    dest_dir = os.path.join(project_dir, subdir)
    os.makedirs(dest_dir, exist_ok=True)
    name = os.path.basename(src)
    dest = os.path.join(dest_dir, name)
    stem, ext = os.path.splitext(name)
    i = 1
    while os.path.exists(dest) and not _same_file(src, dest):
        dest = os.path.join(dest_dir, f"{stem}_{i}{ext}")
        i += 1
    if not _same_file(src, dest):
        shutil.copy2(src, dest)
    return os.path.relpath(dest, project_dir).replace(os.sep, "/")


def _same_file(a: str, b: str) -> bool:
    try:
        return os.path.exists(b) and os.path.samefile(a, b)
    except OSError:
        return False


def find_default_logo(base_dir: str) -> Optional[str]:
    """로고를 따로 지정하지 않았을 때 자동으로 찾는다.

    1) 문서 파일과 같은 폴더의 logo.png / logo.jpg ...
    2) 프로그램에 함께 들어 있는 assets/logo.*
    """
    import glob as _glob
    from .fonts import bundled_font_dir
    assets = os.path.dirname(bundled_font_dir())
    for d in (base_dir, os.path.join(base_dir, "figures"), assets):
        if not d or not os.path.isdir(d):
            continue
        for ext in (".png", ".jpg", ".jpeg", ".gif", ".bmp"):
            hits = sorted(_glob.glob(os.path.join(d, f"logo{ext}")))
            if hits:
                return hits[0]
    return None


def find_stamp(name: str, explicit: str, base_dir: str) -> Optional[str]:
    """도장·사인 이미지를 찾는다.

    1) 문서에 지정한 경로
    2) 문서 폴더의 stamps/{이름}.png
    3) 프로그램 폴더의 assets/stamps/{이름}.png   ← 한 번 넣어 두면 계속 쓰인다
    """
    if explicit:
        found = resolve_image(explicit, base_dir)
        if found:
            return found
    name = (name or "").strip()
    if not name:
        return None
    from .fonts import bundled_font_dir
    assets = os.path.join(os.path.dirname(bundled_font_dir()), "stamps")
    for d in (os.path.join(base_dir, "stamps"), assets):
        if not os.path.isdir(d):
            continue
        for ext in (".png", ".jpg", ".jpeg", ".gif", ".bmp"):
            cand = os.path.join(d, name + ext)
            if os.path.exists(cand):
                return cand
    return None


def parse_pasted_table(text: str, ncols: int) -> List[List[str]]:
    """엑셀/시트에서 복사한 내용(탭 구분)을 표 행 리스트로 바꾼다.

    - 탭이 없으면 2칸 이상의 공백 또는 콤마로도 나눠 본다.
    - 셀 안의 줄바꿈은 따옴표로 감싸진 경우를 고려해 CSV 로도 시도한다.
    """
    text = (text or "").replace("\r\n", "\n").replace("\r", "\n").strip("\n")
    if not text:
        return []

    rows: List[List[str]] = []
    if "\t" in text:
        rows = [line.split("\t") for line in text.split("\n")]
    else:
        import csv
        import io
        try:
            dialect = csv.Sniffer().sniff(text[:2000], delimiters=",;|")
            rows = [r for r in csv.reader(io.StringIO(text), dialect)]
        except csv.Error:
            rows = [line.split("  ") for line in text.split("\n")]
            rows = [[c.strip() for c in r if c.strip() != ""] for r in rows]

    out: List[List[str]] = []
    for r in rows:
        cells = [(c or "").strip() for c in r]
        if not any(cells):
            continue
        cells = (cells + [""] * ncols)[:ncols]
        out.append(cells)
    return out
