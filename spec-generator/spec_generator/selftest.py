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
    from .__main__ import force_utf8_console
    force_utf8_console()
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

    @check("템플릿의 새 항목을 예전 문서가 가져온다")
    def _():
        from . import updater
        from .model import Section, SpecRow, KIND_SPEC_TABLE
        old = templates.load_template("reactor")
        for sec in old.sections:
            sec.key = ""                                  # 예전 파일에는 key 가 없다
        removed = old.sections.pop(7)                     # 그때는 없던 항목
        basic = next(s for s in old.sections if s.title_ko == "기본 사양")
        keep = "사용자가 적어 둔 값"
        basic.rows[4].spec = keep
        dropped_item = basic.rows.pop(3).item_ko          # 그때는 없던 줄
        mine = Section(title_ko="우리 공장 특기사항")
        old.sections.append(mine)

        tpl = templates.load_template("reactor")
        tpl.sections.append(Section(kind=KIND_SPEC_TABLE, key="_new",
                                    title_ko="나중에 생긴 항목",
                                    rows=[SpecRow("새 줄", "", "", "")]))
        p = updater.plan(old, tpl)
        assert p, "가져올 것을 하나도 찾지 못했습니다"
        updater.apply(old, p.changes)

        titles = [s.title_ko for s in old.sections]
        assert removed.title_ko in titles, "빠져 있던 항목이 복구되지 않았습니다"
        assert "나중에 생긴 항목" in titles, "새로 생긴 항목이 들어오지 않았습니다"
        assert "우리 공장 특기사항" in titles, "사용자가 만든 항목이 사라졌습니다"
        basic2 = next(s for s in old.sections if s.title_ko == "기본 사양")
        assert any(r.item_ko == dropped_item for r in basic2.rows), "표의 줄이 복구되지 않았습니다"
        assert any(r.spec == keep for r in basic2.rows), "사용자가 적은 값이 덮어써졌습니다"
        assert not updater.plan(old, tpl), "두 번 실행하면 중복으로 들어갑니다"

    @check("예전 판으로 저장한 문서가 자재 리스트까지 되찾는다")
    def _():
        from . import updater, approval
        # v1.0 무렵의 문서: 그때는 '구조 및 부품 · 명판 · 자재 리스트' 가 없었다.
        늦게_생긴 = ("parts", "nameplate", "materials")
        old = templates.load_template("reactor")
        old.sections = [s for s in old.sections if s.key not in 늦게_생긴]
        old.schema, old.app_version = 1, "1.0"
        tpl = templates.load_template("reactor")

        p = updater.plan(old, tpl)
        찾음 = {c.label for c in p.changes if c.kind == updater.ADD_SECTION}
        assert "자재 리스트" in 찾음, f"자재 리스트를 찾지 못했습니다: {찾음}"
        updater.apply(old, p.changes)

        keys = [s.key for s in old.sections]
        assert keys == [s.key for s in tpl.sections], f"항목 순서가 템플릿과 다릅니다: {keys}"
        mat = next(s for s in old.sections if s.key == "materials")
        assert mat.grid, "자재 리스트가 빈 채로 들어왔습니다"
        assert "제조사 / Manufacturer" in mat.headers, "제조사 열이 빠졌습니다"
        assert mat.to_customer(), "자재 리스트가 고객 승인서로 나가지 않습니다"
        assert any(s.key == "materials" for s in approval.customer_sections(old)), \
            "승인 사양서에 자재 리스트가 담기지 않았습니다"

    @check("업데이트한 문서도 PDF 가 나온다")
    def _(out=out):
        from . import updater
        doc = SpecDoc.load(files[-1])
        updater.apply(doc, updater.plan(doc, templates.load_template("reactor")).changes)
        build_pdf(doc, os.path.join(out, "updated.pdf"))

    @check("표지가 붙고, 쪽 번호에서는 빠진다")
    def _(out=out):
        doc = SpecDoc.load(files[-1])
        doc.meta.cover = False
        a = build_pdf(doc, os.path.join(out, "nocover.pdf"))
        n_without = _pages(a)
        doc.meta.cover = True
        b = build_pdf(doc, os.path.join(out, "cover.pdf"))
        n_with = _pages(b)
        if n_without < 0:
            return                                  # 페이지를 셀 수 없는 환경
        assert n_with == n_without + 1, f"표지가 한 장 늘지 않았습니다 ({n_without} → {n_with})"
        try:
            import pymupdf
        except ImportError:
            return
        with pymupdf.open(b) as d:
            first = d[1].get_text()
            last = d[d.page_count - 1].get_text()
        assert "PAGE" in first, "내용 첫 장에 표제란이 없습니다"
        total = str(n_without)
        assert total in last, f"마지막 장의 전체 쪽수가 {total} 가 아닙니다"

    @check("도면 크기 옵션(자동 최대 · 90도 회전)이 동작한다")
    def _(out=out):
        from .render.flow import FitImage
        from reportlab.lib.units import mm as MM
        doc = SpecDoc.load(files[-1])
        path = None
        for s in doc.sections:
            for item in s.images:
                from .importers import resolve_image
                path = resolve_image(item.path, doc.base_dir())
                if path:
                    break
            if path:
                break
        assert path, "예제에 도면이 없습니다"

        avail_w, avail_h = 170 * MM, 230 * MM
        plain = FitImage(path, 0, "CENTER")
        w1, h1 = plain.wrap(avail_w, avail_h)
        turned = FitImage(path, 0, "CENTER", rotate=90)
        w2, h2 = turned.wrap(avail_w, avail_h)
        fixed = FitImage(path, 80, "CENTER")
        w3, _ = fixed.wrap(avail_w, avail_h)

        assert w1 <= avail_w + 1 and h1 <= avail_h + 1, "자동 크기가 지면을 넘습니다"
        assert abs(w3 - 80 * MM) < 1, "폭을 지정했는데 그 폭이 아닙니다"
        assert w2 * h2 > w1 * h1, "90도 회전이 더 크게 넣지 못했습니다"

    @check("고객 승인 사양서에 생산용 내용이 새어 나가지 않는다")
    def _(out=out):
        # 가장 중요한 검사.
        # '생산용만' 으로 표시한 내용 중, 승인 템플릿의 정형 문구나 고객 공개 항목에는
        # 없는 말(= 그 항목에서만 나오는 말)이 고객 문서에 나타나면 누출이다.
        from . import approval as approval_mod
        from .model import goes_to_customer
        from .render.build import build_approval_pdf

        def words_of(sections):
            out_ = []
            for sec in sections:
                out_.append(sec.title_ko)
                out_.append(sec.title_en)
                out_ += [r.item_ko for r in sec.rows]
                out_ += [r.spec for r in sec.rows]
                out_ += [b.ko for b in sec.blocks]
                for gr in sec.grid:                 # 자유 표 칸도 빠짐없이
                    out_ += list(gr.cells)
            return out_

        def flat(t):
            return " ".join(str(t or "").split())

        def squash(t):
            """공백을 모두 지운다 — 좁은 칸에서 줄바꿈된 글자도 잡기 위해."""
            return "".join(str(t or "").split())

        doc = SpecDoc.load(files[-1])
        tpl = templates.load_template(approval_mod.TEMPLATE_NAME)

        internal = [s for s in doc.sections if not s.to_customer()]
        secret = set()
        for sec in internal:
            texts = [sec.title_ko] + [r.item_ko for r in sec.rows] + \
                    [r.spec for r in sec.rows] + [b.ko for b in sec.blocks]
            for gr in sec.grid:
                texts += list(gr.cells)
            for t in texts:
                if len(flat(t)) >= 3:
                    secret.add(flat(t))
        for sec in doc.sections:                    # 고객 항목 안의 '생산용만' 줄
            if not sec.to_customer():
                continue
            for r in sec.rows:
                if not goes_to_customer(r.audience) and len(flat(r.item_ko)) >= 3:
                    secret.add(flat(r.item_ko))
            for gr in sec.grid:
                if goes_to_customer(gr.audience):
                    continue
                for t in gr.cells:
                    if len(flat(t)) >= 3:
                        secret.add(flat(t))

        # 승인 템플릿·고객 공개 항목에 원래 있는 말은 누출이 아니다.
        # 허용 목록은 검사 대상 함수(customer_sections)를 거치지 않고
        # 문서에서 직접 계산한다 — 그 함수가 망가져도 검사가 무력화되지 않게.
        allowed = "".join(squash(t) for t in
                          words_of(tpl.sections)
                          + words_of([x for x in doc.sections if x.to_customer()]))
        secret = {t for t in secret if squash(t) not in allowed}
        assert secret, "검사할 '생산용 전용' 문구를 찾지 못했습니다"

        pdf = build_approval_pdf(approval_mod.build_doc(doc),
                                 os.path.join(out, "approval_leak.pdf"), source=doc)
        try:
            import pymupdf
        except ImportError:
            return
        with pymupdf.open(pdf) as d:
            text = "".join(squash(p.get_text()) for p in d)
        leaked = sorted(t for t in secret if squash(t) in text)
        assert not leaked, ("고객 문서에 생산용 내용이 실렸습니다: "
                            + ", ".join(leaked[:6]))

    @check("고객 승인 사양서에 기본 내용은 들어간다")
    def _(out=out):
        from . import approval as approval_mod
        from .render.build import build_approval_pdf
        doc = SpecDoc.load(files[-1])
        a = approval_mod.build_doc(doc)
        assert a.sections, "승인 사양서가 비었습니다"
        pdf = build_approval_pdf(a, os.path.join(out, "approval_ok.pdf"), source=doc)
        try:
            import pymupdf
        except ImportError:
            return
        with pymupdf.open(pdf) as d:
            text = " ".join(" ".join(p.get_text().split()) for p in d)
        for must in ("APPROVAL", "Applicable Standards", "Tolerances", "Rev."):
            assert must in text, f"승인 사양서에 '{must}' 가 없습니다"

    @check("자유 표(자재 리스트)가 승인 사양서에 실리고, 감춘 줄은 빠진다")
    def _(out=out):
        from . import approval as approval_mod
        from .model import AUD_INTERNAL, GridRow, KIND_TABLE
        from .render.build import build_approval_pdf

        doc = SpecDoc.load(files[-1])
        target = next((s for s in doc.sections if s.kind == KIND_TABLE and s.to_customer()), None)
        assert target is not None, "고객에게 나가는 자유 표가 없습니다"
        assert target.headers, "자유 표에 열 이름이 없습니다"

        shown = "ZZSHOWN"
        hidden = "ZZHIDDEN"
        n = len(target.headers)
        target.grid.append(GridRow([shown] + [""] * (n - 1)))
        target.grid.append(GridRow([hidden] + [""] * (n - 1), AUD_INTERNAL))

        pdf = build_approval_pdf(approval_mod.build_doc(doc),
                                 os.path.join(out, "grid.pdf"), source=doc)
        try:
            import pymupdf
        except ImportError:
            return
        with pymupdf.open(pdf) as d:
            text = "".join("".join(p.get_text().split()) for p in d)
        assert shown in text, "자유 표의 줄이 승인 사양서에 실리지 않았습니다"
        assert hidden not in text, "감춘 줄이 승인 사양서에 실렸습니다"

    @check("'고객용만' 으로 표시한 항목·줄은 생산 사양서에 안 나온다")
    def _(out=out):
        from .model import (AUD_CUSTOMER, AUD_INTERNAL, GridRow, Section,
                            SpecRow, KIND_SPEC_TABLE, KIND_TABLE)
        from .render.build import build_pdf

        doc = SpecDoc.load(files[-1])
        표시 = {"항목": "ZZCUSTONLYSEC", "사양표줄": "ZZCUSTONLYROW",
               "자유표줄": "ZZCUSTONLYCELL", "생산": "ZZINTERNALROW"}

        # ① 항목 전체를 '고객용만' 으로
        doc.sections.append(Section(kind=KIND_SPEC_TABLE, audience=AUD_CUSTOMER,
                                    title_ko=표시["항목"],
                                    rows=[SpecRow("보증", "2년", "", "")]))
        # ② 사양표 안의 한 줄만 '고객용만'
        table = next(s for s in doc.sections
                     if s.kind == KIND_SPEC_TABLE and s.audience != AUD_CUSTOMER)
        table.rows.append(SpecRow(표시["사양표줄"], "고객에게만", "", "", AUD_CUSTOMER))
        table.rows.append(SpecRow(표시["생산"], "생산에만", "", "", AUD_INTERNAL))
        # ③ 자유 표 안의 한 줄만 '고객용만'
        grid = next(s for s in doc.sections if s.kind == KIND_TABLE)
        n = len(grid.headers) or 3
        grid.grid.append(GridRow([표시["자유표줄"]] + [""] * (n - 1), AUD_CUSTOMER))

        pdf = build_pdf(doc, os.path.join(out, "internal_only.pdf"))
        try:
            import pymupdf
        except ImportError:
            return
        with pymupdf.open(pdf) as d:
            text = "".join("".join(p.get_text().split()) for p in d)
        for 이름, 값 in 표시.items():
            if 이름 == "생산":
                assert 값 in text, "생산용 줄이 생산 사양서에서 빠졌습니다"
            else:
                assert 값 not in text, f"'고객용만' 인 {이름} 이 생산 사양서에 나왔습니다"

    @check("생산 사양서의 항목 번호가 '고객용만' 을 건너뛰고 이어진다")
    def _(out=out):
        from .model import AUD_CUSTOMER, Block, Section, internal_sections

        doc = SpecDoc.load(files[-1])
        doc.sections.insert(1, Section(audience=AUD_CUSTOMER, title_ko="고객 전용 안내",
                                       blocks=[Block(ko="고객에게만 드리는 말씀")]))
        kept = internal_sections(doc)
        assert all(s.title_ko != "고객 전용 안내" for s in kept)
        numbers = [doc.assign_numbers(kept)[s.id] for s in kept if s.numbered]
        assert numbers == [str(i + 1) for i in range(len(numbers))], \
            f"번호가 이어지지 않습니다: {numbers[:6]}"

    @check("명판에 적은 값이 도안 위에 찍힌다")
    def _(out=out):
        from . import approval as approval_mod
        from .model import KIND_NAMEPLATE
        from .render.build import build_approval_pdf

        doc = SpecDoc.load(files[-1])
        plate = next((s for s in doc.sections if s.kind == KIND_NAMEPLATE), None)
        assert plate is not None, "명판 항목이 없습니다"

        marker = "ZZPLATE-26-0001"
        for row in plate.grid:
            if row.cell(0):
                row.cells[1] = marker
                break
        pdf = build_approval_pdf(approval_mod.build_doc(doc),
                                 os.path.join(out, "plate.pdf"), source=doc)
        try:
            import pymupdf
        except ImportError:
            return
        with pymupdf.open(pdf) as d:
            text = "".join("".join(p.get_text().split()) for p in d)
        assert marker.replace(" ", "") in text, "명판에 적은 값이 찍히지 않았습니다"

    @check("명판 글자가 도안 밖으로 넘치지 않는다")
    def _():
        from reportlab.lib.units import mm as MM
        from .render.flow import NamePlate

        # 줄을 아주 많이 넣어도 안쪽에 들어가야 한다
        rows = [("", "제목", 1.6)] + [(f"항목{i}", f"값{i}", 1.0) for i in range(14)]
        plate = NamePlate(rows, {"width_mm": 110, "aspect": 1.93}, None, ".")
        w, h = plate.wrap(170 * MM, 240 * MM)
        used = h * plate.cfg["y"] / 100.0 + plate._body_fraction() * h * plate._shrink
        limit = h * (1.0 - plate.BOTTOM_MARGIN) + 0.5
        assert used <= limit, f"명판 글자가 넘칩니다 ({used:.1f} > {limit:.1f})"
        assert plate._shrink <= 1.0

    @check("승인 사양서 정형 문구를 문서에서 고칠 수 있다")
    def _(out=out):
        from . import approval as approval_mod
        from .render.build import build_approval_pdf
        doc = SpecDoc.load(files[-1])
        doc.approval_sections = approval_mod.default_boilerplate()
        assert doc.approval_sections, "표준 정형 문구를 가져오지 못했습니다"

        changed = "± 7.5 % (검사용)"
        added = "9. 검사용으로 더한 줄"
        for sec in doc.approval_sections:
            if sec.key == "tolerance":
                sec.rows[0].spec = changed
                sec.rows.append(type(sec.rows[0])("9. Extra", "", added, ""))
            if sec.key == "standards":
                sec.rows.append(type(sec.rows[0])("IEC 61800-5-1", "", "Drive systems", ""))

        pdf = build_approval_pdf(approval_mod.build_doc(doc),
                                 os.path.join(out, "approval_edited.pdf"), source=doc)
        try:
            import pymupdf
        except ImportError:
            return
        with pymupdf.open(pdf) as d:
            text = " ".join(" ".join(p.get_text().split()) for p in d)
        assert changed in text, "고친 공차 값이 반영되지 않았습니다"
        assert added in text, "더한 줄이 반영되지 않았습니다"
        assert "IEC 61800-5-1" in text, "더한 규격이 반영되지 않았습니다"
        assert "여기에 생산 사양서" not in text, "슬롯 표시가 인쇄되었습니다"

    @check("문서에 심은 정형 문구가 저장·복원된다")
    def _(out=out):
        from . import approval as approval_mod
        doc = SpecDoc.load(files[-1])
        doc.approval_sections = approval_mod.default_boilerplate()
        doc.approval_sections[0].title_ko = "고친 제목"
        p = os.path.join(out, "with_approval.spec.json")
        doc.save(p)
        again = SpecDoc.load(p)
        assert len(again.approval_sections) == len(doc.approval_sections)
        assert again.approval_sections[0].title_ko == "고친 제목"

    @check("승인란 높이가 도장 유무와 상관없이 같다")
    def _():
        from .render import approval as ar, cover as cv
        # 도장 칸 · 이름 칸 · 일자 칸을 고정 높이로 잡아 두었는지
        assert cv.APPROVAL_H == (cv.APPROVAL_HEAD_H + cv.APPROVAL_STAMP_H
                                 + cv.APPROVAL_NAME_H + cv.APPROVAL_DATE_H)
        assert ar.C_APPR_H == (ar.C_APPR_HEAD_H + ar.C_APPR_STAMP_H + ar.C_APPR_NAME_H)
        assert cv.APPROVAL_NAME_SIZE > 0 and ar.C_APPR_NAME_SIZE > 0

    @check("판 번호가 붙어 있다")
    def _():
        import re as _re
        from . import __version__
        assert _re.fullmatch(r"\d+\.\d+", __version__), f"판 번호 형식이 이상합니다: {__version__}"
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        log = os.path.join(here, "CHANGELOG.md")
        if os.path.exists(log):
            text = open(log, encoding="utf-8").read()
            assert f"v{__version__}" in text, f"CHANGELOG 에 v{__version__} 항목이 없습니다"

    @check("항목의 기본 공개 범위는 '생산용만' 이다")
    def _():
        from .model import AUD_INTERNAL, Section, SpecRow
        assert Section().audience == AUD_INTERNAL, "새 항목이 기본으로 고객에게 나갑니다"
        assert SpecRow().audience == "both"

    @check("도장·사인 이미지가 승인란에 들어간다")
    def _(out=out):
        from PIL import Image, ImageDraw
        from .importers import find_stamp
        from .model import Person

        stamps = os.path.join(out, "stamps")
        os.makedirs(stamps, exist_ok=True)
        for who in ("홍길동", "김철수"):
            im = Image.new("RGBA", (200, 200), (0, 0, 0, 0))
            ImageDraw.Draw(im).ellipse([6, 6, 194, 194], outline=(200, 30, 30, 255), width=10)
            im.save(os.path.join(stamps, who + ".png"))

        # 이름만으로 stamps 폴더에서 찾아진다
        assert find_stamp("홍길동", "", out), "이름으로 도장을 찾지 못했습니다"
        assert not find_stamp("없는사람", "", out), "없는 도장을 찾았다고 합니다"
        explicit = os.path.join(stamps, "김철수.png")
        assert find_stamp("아무개", explicit, out) == explicit, "지정한 경로를 쓰지 않았습니다"

        doc = SpecDoc.load(files[-1])
        doc.source_path = os.path.join(out, "stamped.spec.json")
        doc.meta.drawn = Person("2026-01-01", "홍길동", "")
        doc.meta.approved = Person("2026-01-03", "김철수", explicit)
        pdf = build_pdf(doc, os.path.join(out, "stamped.pdf"))
        assert os.path.getsize(pdf) > 2000

        doc.meta.drawn = Person("2026-01-01", "이름만있음", "")
        doc.meta.approved = Person("", "깨진도장", os.path.join(out, "없는파일.png"))
        build_pdf(doc, os.path.join(out, "stamped2.pdf"))   # 없는 파일이어도 죽지 않는다

    @check("승인란이 예전 파일(문자열)에서도 읽힌다")
    def _():
        import json as _json
        raw = _json.loads(open(files[-1], encoding="utf-8").read())
        raw["meta"]["approved"] = "박영희"          # v2 까지의 저장 형식
        doc = SpecDoc.from_dict(raw)
        assert doc.meta.approved.name == "박영희", doc.meta.approved
        assert doc.meta.approved.stamp == ""

    @check("한글 출력이 서유럽/한국어 코덱 콘솔에서도 죽지 않는다")
    def _():
        # Windows 콘솔은 기본 코덱이 cp1252/cp949 라, 한글을 그냥 print 하면 죽는다.
        # 실제로 이 문제로 CI 빌드가 끊긴 적이 있어 회귀 검사로 남긴다.
        import io
        from .__main__ import force_utf8_console
        saved = sys.stdout
        sys.stdout = io.TextIOWrapper(io.BytesIO(), encoding="cp1252", errors="strict")
        try:
            force_utf8_console()
            print("통과 · 한글 출력 확인 ★")
        finally:
            sys.stdout = saved

    @check("바깥으로 나가는 코드가 없다 (로컬 전용)")
    def _():
        import re
        root = os.path.dirname(os.path.abspath(__file__))
        bad = re.compile(r"\b(socket|urllib|requests|httplib|ftplib|smtplib|telnetlib)\b"
                         r"|\beval\s*\(|\bexec\s*\(|\bpickle\b|shell\s*=\s*True")
        hits = []
        for dirpath, _, names in os.walk(root):
            for n in names:
                if not n.endswith(".py") or n == "selftest.py":   # 이 파일의 검사 패턴 자체는 제외
                    continue
                fp = os.path.join(dirpath, n)
                for i, line in enumerate(open(fp, encoding="utf-8"), 1):
                    if line.lstrip().startswith("#"):
                        continue
                    if bad.search(line):
                        hits.append(f"{n}:{i}")
        assert not hits, "네트워크/위험 호출이 발견되었습니다: " + ", ".join(hits)

    print()
    for name in _PASS:
        print(f"  통과   {name}")
    for name, err in _FAIL:
        print(f"  실패   {name}\n         {err.splitlines()[0]}")
    print(f"\n  {len(_PASS)}건 통과, {len(_FAIL)}건 실패\n")
    if _FAIL:
        print("  ※ 실패한 항목이 있으면 예전 문서가 안 열리거나 기능이 깨진 상태입니다.")
        for name, err in _FAIL:
            print(f"\n--- {name} ---\n{err}")
    return 1 if _FAIL else 0


if __name__ == "__main__":
    sys.exit(run())
