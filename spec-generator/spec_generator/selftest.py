# -*- coding: utf-8 -*-
"""자체 점검 — `python -m spec_generator selftest`

핵심 목적은 **호환성 보증**이다.
tests/fixtures 에는 각 버전에서 실제로 저장한 문서를 얼려 두었고,
프로그램을 아무리 고쳐도 그 파일들이 계속 열리고 계속 PDF 로 나와야 한다.
CI(GitHub Actions)에서도 매번 이걸 돌린다.
"""
from __future__ import annotations

import glob
import json
import os
import sys
import tempfile
import traceback
from typing import Callable, List, Tuple

_PASS: List[str] = []
_FAIL: List[Tuple[str, str]] = []


def check(name: str):
    def deco(fn: Callable[[], None]):
        try:
            fn()
            _PASS.append(name)
        except Exception as exc:                       # noqa: BLE001
            _FAIL.append((name, f"{exc}\n{traceback.format_exc(limit=3)}"))
        return fn
    return deco


def fixtures_dir() -> str:
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(here, "tests", "fixtures")


def _pages(path: str) -> int:
    try:
        import pymupdf
    except ImportError:
        try:
            import fitz as pymupdf          # type: ignore
        except ImportError:
            return -1                        # 셀 수 없으면 건너뛴다
    with pymupdf.open(path) as d:
        return d.page_count


def run() -> int:
    from .model import SCHEMA_VERSION, SpecDoc
    from .render.build import build_pdf
    from . import docnumber as dn, placeholders as ph, templates
    from .registry import Registry

    out = tempfile.mkdtemp(prefix="specgen_selftest_")
    files = sorted(glob.glob(os.path.join(fixtures_dir(), "*.spec.json")))

    @check("고정 문서(fixture)가 하나 이상 있다")
    def _():
        assert files, f"fixtures 가 비었습니다: {fixtures_dir()}"

    for path in files:
        name = os.path.basename(path)

        @check(f"[{name}] 열린다")
        def _(path=path):
            doc = SpecDoc.load(path)
            assert doc.sections, "항목이 하나도 없습니다"
            assert doc.schema == SCHEMA_VERSION, f"schema 가 {doc.schema} 로 남았습니다"

        @check(f"[{name}] 내용이 살아 있다")
        def _(path=path):
            doc = SpecDoc.load(path)
            texts = []
            for s in doc.sections:
                texts += [s.title_ko] + [b.ko for b in s.blocks]
                texts += [r.item_ko for r in s.rows] + [r.changed_ko for r in s.versions]
            assert any(t.strip() for t in texts), "글자가 전부 비었습니다"

        @check(f"[{name}] PDF 가 만들어진다")
        def _(path=path, out=out):
            doc = SpecDoc.load(path)
            pdf = build_pdf(doc, os.path.join(out, os.path.basename(path) + ".pdf"))
            assert os.path.getsize(pdf) > 2000, "PDF 가 너무 작습니다"
            n = _pages(pdf)
            assert n != 0, "페이지가 0장입니다"

        @check(f"[{name}] 저장했다 다시 열어도 같다")
        def _(path=path, out=out):
            doc = SpecDoc.load(path)
            tmp = os.path.join(out, "roundtrip_" + os.path.basename(path))
            doc.save(tmp)
            again = SpecDoc.load(tmp)
            a, b = doc.to_dict(), again.to_dict()
            a.pop("app_version", None)
            b.pop("app_version", None)
            assert a == b, "저장/불러오기에서 내용이 달라졌습니다"

    @check("모르는 필드가 있어도 열린다 (미래 버전 대비)")
    def _():
        base = json.load(open(files[-1], encoding="utf-8"))
        base["schema"] = SCHEMA_VERSION + 5
        base["미래에추가될항목"] = {"뭔가": 1}
        base["meta"]["아직없는설정"] = "x"
        for s in base["sections"]:
            s["나중에생길필드"] = [1, 2, 3]
        doc = SpecDoc.from_dict(base)
        assert doc.sections, "미래 버전 파일을 읽지 못했습니다"

    @check("표준 템플릿이 열리고 PDF 가 나온다")
    def _():
        for tname in templates.template_names():
            doc = templates.load_template(tname)
            assert doc.sections, f"{tname} 템플릿이 비었습니다"
            build_pdf(doc, os.path.join(out, f"tpl_{tname}.pdf"))

    @check("자동 입력 항목이 치환된다")
    def _():
        from .model import Meta
        m = Meta(customer="현대일렉트릭", product_name="AC Reactor",
                 dwg_prefix="BR", dwg_no="RA-HYU-0475-01", revision="B")
        ctx = ph.build_context(m)
        got = ph.apply("{고객사} / {제품명} / {도번} Rev.{리비전} / {없는항목}", ctx)
        assert got == "현대일렉트릭 / AC Reactor / BR-RA-HYU-0475-01 Rev.B / {없는항목}", got

    @check("도번 규칙이 그대로다")
    def _():
        assert dn.build("RA", "Hyundai Electric", "475 Arms", "1") == "BR-RA-HYU-0475-01"
        assert dn.customer_code("LS Electric") == "LSE"
        assert dn.next_revision("A") == "B" and dn.next_revision("Z") == "AA"

    @check("도번 대장이 번호를 겹치지 않게 준다")
    def _(out=out):
        root = os.path.join(out, "대장")
        reg = Registry(root)
        a = reg.issue("RA", "Hyundai Electric", "현대", "475", "p1")
        b = reg.issue("RA", "Hyundai Electric", "현대", "475", "p2")
        c = reg.issue("RD", "Hyundai Heavy", "현대중", "300", "p3")
        assert a != b and a.endswith("-01") and b.endswith("-02"), (a, b)
        assert c.split("-")[2] != a.split("-")[2], "고객코드 충돌을 피하지 못했습니다"
        assert reg.save(), "대장 저장 실패"
        assert Registry(root).count() == 3

    print()
    for name in _PASS:
        print(f"  통과   {name}")
    for name, err in _FAIL:
        print(f"  실패   {name}\n         {err.splitlines()[0]}")
    print(f"\n  {len(_PASS)}건 통과, {len(_FAIL)}건 실패\n")
    if _FAIL:
        print("  ※ 실패한 항목이 있으면 예전에 저장한 문서가 안 열릴 수 있습니다.")
        for name, err in _FAIL:
            print(f"\n--- {name} ---\n{err}")
    return 1 if _FAIL else 0


if __name__ == "__main__":
    sys.exit(run())
