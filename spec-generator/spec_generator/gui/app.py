# -*- coding: utf-8 -*-
"""생산용 사양서 생성기 - 메인 창."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import tkinter as tk
import traceback
from tkinter import filedialog, messagebox, ttk
from typing import Dict, List, Optional

from .. import templates as tpl_pkg
from ..fonts import active_font_description, register_fonts
from ..importers import SUPPORTED_EXT, copy_into_project
from ..model import (KIND_IMAGE, KIND_LABELS, KIND_SPEC_TABLE, KIND_TEXT,
                     KIND_VERSION_TABLE, Block, ImageItem, Section, SpecDoc,
                     SpecRow, VersionRow)
from ..render.build import build_pdf
from .widgets import FieldGrid, GridEditor

APP_TITLE = "생산용 사양서 생성기"
SETTINGS = os.path.join(os.path.expanduser("~"), ".spec_generator.json")
FILETYPES = [("사양서 프로젝트", "*.spec.json"), ("JSON", "*.json"), ("모든 파일", "*.*")]


def load_settings() -> Dict[str, str]:
    try:
        with open(SETTINGS, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_settings(data: Dict[str, str]) -> None:
    try:
        with open(SETTINGS, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except OSError:
        pass


def open_with_os(path: str) -> None:
    try:
        if sys.platform.startswith("win"):
            os.startfile(path)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
    except Exception:
        pass


class App(tk.Tk):
    def __init__(self, path: Optional[str] = None):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1180x780")
        self.minsize(980, 640)

        self.settings = load_settings()
        self.doc = SpecDoc()
        self._dirty = False
        self._current: Optional[Section] = None

        self._build_menu()
        self._build_body()
        self._build_status()

        if path and os.path.exists(path):
            self.open_path(path)
        else:
            self.new_from_template(silent=True)
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    # ── 화면 구성 ────────────────────────────────────────────
    def _build_menu(self) -> None:
        bar = tk.Menu(self)
        m = tk.Menu(bar, tearoff=0)
        m.add_command(label="표준 템플릿으로 새로 만들기", accelerator="Ctrl+N",
                      command=lambda: self.new_from_template())
        m.add_command(label="빈 문서로 새로 만들기", command=self.new_empty)
        m.add_separator()
        m.add_command(label="열기...", accelerator="Ctrl+O", command=self.open_file)
        m.add_command(label="저장", accelerator="Ctrl+S", command=self.save)
        m.add_command(label="다른 이름으로 저장...", command=self.save_as)
        m.add_separator()
        m.add_command(label="현재 문서를 템플릿으로 저장...", command=self.save_as_template)
        m.add_separator()
        m.add_command(label="끝내기", command=self.on_close)
        bar.add_cascade(label="파일", menu=m)

        o = tk.Menu(bar, tearoff=0)
        o.add_command(label="PDF 미리보기", accelerator="F5", command=self.preview)
        o.add_command(label="PDF로 내보내기...", accelerator="Ctrl+P", command=self.export)
        bar.add_cascade(label="출력", menu=o)

        t = tk.Menu(bar, tearoff=0)
        t.add_command(label="PDF 폰트 지정...", command=self.choose_font)
        t.add_command(label="폰트 설정 초기화", command=self.reset_font)
        bar.add_cascade(label="도구", menu=t)

        h = tk.Menu(bar, tearoff=0)
        h.add_command(label="사용 방법", command=self.show_help)
        bar.add_cascade(label="도움말", menu=h)
        self.config(menu=bar)

        self.bind_all("<Control-n>", lambda e: self.new_from_template())
        self.bind_all("<Control-o>", lambda e: self.open_file())
        self.bind_all("<Control-s>", lambda e: self.save())
        self.bind_all("<Control-p>", lambda e: self.export())
        self.bind_all("<F5>", lambda e: self.preview())

    def _build_body(self) -> None:
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=8, pady=(8, 4))
        self.nb = nb
        self.tab_meta = ttk.Frame(nb)
        self.tab_sections = ttk.Frame(nb)
        nb.add(self.tab_meta, text="  ① 기본정보(표제란)  ")
        nb.add(self.tab_sections, text="  ② 문서 구성  ")
        self._build_meta_tab()
        self._build_sections_tab()

    def _build_meta_tab(self) -> None:
        f = self.tab_meta
        g1 = ttk.LabelFrame(f, text="제품 / 도면")
        g1.pack(fill="x", padx=10, pady=(10, 6))
        self.meta_fields = FieldGrid(g1, columns=2)
        self.meta_fields.pack(fill="x", padx=6, pady=6)
        mf = self.meta_fields
        mf.add("product_name", "제품명", 34)
        mf.add("use_name", "용도 / 고객사", 34)
        mf.add("doc_kind", "문서종류", 34)
        mf.add("company", "회사명", 34)
        mf.add("dwg_prefix", "도면번호 접두", 12)
        mf.add("dwg_no", "도면번호", 20)
        mf.add("old_dwg_no", "구 도면번호", 20)
        mf.add("standard", "STANDARD 표기", 20)
        mf.add("dwg_code", "DWG CODE (좌)", 20)
        mf.add("dwg_code2", "DWG CODE (우)", 20)
        mf.add("index", "INDEX", 12)
        mf.add("footer_code", "용지 하단 코드", 24)
        mf.newline()
        mf.add("label_product", "좌측 라벨 ①", 16)
        mf.add("label_use", "좌측 라벨 ②", 16)
        mf.add("label_kind", "좌측 라벨 ③", 16)

        logo = ttk.LabelFrame(f, text="회사 로고 (표제란 하단)")
        logo.pack(fill="x", padx=10, pady=6)
        row = ttk.Frame(logo)
        row.pack(fill="x", padx=6, pady=6)
        ttk.Label(row, text="로고 파일").pack(side="left", padx=(6, 4))
        self.logo_var = tk.StringVar()
        ttk.Entry(row, textvariable=self.logo_var).pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="찾아보기...", command=self.choose_logo).pack(side="left", padx=4)
        ttk.Button(row, text="지우기", command=lambda: self.logo_var.set("")).pack(side="left")
        ttk.Label(row, text="높이(mm)").pack(side="left", padx=(10, 4))
        self.logo_h_var = tk.StringVar(value="8.5")
        ttk.Entry(row, textvariable=self.logo_h_var, width=6).pack(side="left")
        ttk.Label(logo, foreground="#666",
                  text="비워 두면 문서 파일과 같은 폴더의 logo.png 를 자동으로 사용합니다.").pack(
            anchor="w", padx=12, pady=(0, 6))
        self.logo_var.trace_add("write", lambda *a: self.mark_dirty())
        self.logo_h_var.trace_add("write", lambda *a: self.mark_dirty())

        g2 = ttk.LabelFrame(f, text="표제란 서명")
        g2.pack(fill="x", padx=10, pady=6)
        self.sign_fields = FieldGrid(g2, columns=2)
        self.sign_fields.pack(fill="x", padx=6, pady=6)
        sf = self.sign_fields
        sf.add("drawn_date", "DRAWN 일자", 20)
        sf.add("drawn_name", "DRAWN 이름", 20)
        sf.add("checked_date", "CHECKED 일자", 20)
        sf.add("checked_name", "CHECKED 이름", 20)
        sf.add("renewal_date", "RENEWAL 일자", 20)
        sf.add("renewal_name", "RENEWAL 이름", 20)
        sf.add("approved", "APPROVED", 20)

        g3 = ttk.LabelFrame(f, text="페이지 / 양식")
        g3.pack(fill="x", padx=10, pady=6)
        self.page_fields = FieldGrid(g3, columns=2)
        self.page_fields.pack(fill="x", padx=6, pady=6)
        pf = self.page_fields
        pf.add("page_start", "첫 페이지 번호", 10)
        pf.add("page_total", "전체 페이지 수 (0=자동)", 10)
        pf.add("revision_rows", "REVISIONS 칸 수", 10)

        g4 = ttk.LabelFrame(f, text="좌측 기밀 문구 (세로쓰기)")
        g4.pack(fill="both", expand=True, padx=10, pady=(6, 10))
        self.note_text = tk.Text(g4, height=5, wrap="word")
        self.note_text.pack(fill="both", expand=True, padx=6, pady=6)

        for var in list(mf.vars.values()) + list(sf.vars.values()) + list(pf.vars.values()):
            var.trace_add("write", lambda *a: self.mark_dirty())
        self.note_text.bind("<<Modified>>", self._note_modified)

    def _note_modified(self, _e=None):
        if self.note_text.edit_modified():
            self.note_text.edit_modified(False)
            self.mark_dirty()

    def _build_sections_tab(self) -> None:
        pane = ttk.PanedWindow(self.tab_sections, orient="horizontal")
        pane.pack(fill="both", expand=True, padx=8, pady=8)

        left = ttk.Frame(pane)
        pane.add(left, weight=1)
        ttk.Label(left, text="항목 목록 (문서에 나오는 순서)").pack(anchor="w")
        wrap = ttk.Frame(left)
        wrap.pack(fill="both", expand=True, pady=(2, 4))
        self.sec_list = tk.Listbox(wrap, exportselection=False, activestyle="dotbox")
        vs = ttk.Scrollbar(wrap, orient="vertical", command=self.sec_list.yview)
        hs = ttk.Scrollbar(wrap, orient="horizontal", command=self.sec_list.xview)
        self.sec_list.configure(yscrollcommand=vs.set, xscrollcommand=hs.set)
        self.sec_list.grid(row=0, column=0, sticky="nsew")
        vs.grid(row=0, column=1, sticky="ns")
        hs.grid(row=1, column=0, sticky="ew")
        wrap.rowconfigure(0, weight=1)
        wrap.columnconfigure(0, weight=1)
        self.sec_list.bind("<<ListboxSelect>>", self._on_select_section)

        bar = ttk.Frame(left)
        bar.pack(fill="x")
        self.new_kind = tk.StringVar(value=KIND_LABELS[KIND_TEXT])
        ttk.Combobox(bar, textvariable=self.new_kind, state="readonly", width=12,
                     values=[KIND_LABELS[k] for k in
                             (KIND_TEXT, KIND_SPEC_TABLE, KIND_IMAGE, KIND_VERSION_TABLE)]
                     ).pack(side="left", padx=(0, 4))
        ttk.Button(bar, text="추가", width=5, command=self.add_section).pack(side="left")
        ttk.Button(bar, text="복제", width=5, command=self.duplicate_section).pack(side="left", padx=2)
        ttk.Button(bar, text="삭제", width=5, command=self.delete_section).pack(side="left")
        bar2 = ttk.Frame(left)
        bar2.pack(fill="x", pady=3)
        ttk.Button(bar2, text="▲ 위로", command=lambda: self.move_section(-1)).pack(side="left")
        ttk.Button(bar2, text="▼ 아래로", command=lambda: self.move_section(1)).pack(side="left", padx=4)

        right = ttk.Frame(pane)
        pane.add(right, weight=4)
        head = ttk.LabelFrame(right, text="항목 설정")
        head.pack(fill="x")
        self.sec_fields = FieldGrid(head, columns=2)
        self.sec_fields.pack(fill="x", padx=6, pady=6)
        sfg = self.sec_fields
        sfg.add("title_ko", "제목", 34)
        sfg.add("title_en", "제목(영문·선택)", 34)
        sfg.add("numbered", "번호 자동부여", kind="check")
        sfg.add("no_override", "번호 직접지정", 10)
        sfg.add("bullet", "번호 대신 기호(예: ○)", 10)
        sfg.add("underline", "제목 밑줄", kind="check")
        sfg.add("page_break_before", "이 항목부터 새 페이지", kind="check")
        sfg.add("note", "제목 옆 주기(※)", 40, span=2)
        for var in sfg.vars.values():
            var.trace_add("write", lambda *a: self._commit_current(mark=True))

        self.body_area = ttk.LabelFrame(right, text="내용")
        self.body_area.pack(fill="both", expand=True, pady=(6, 0))
        self.rows_editor: Optional[GridEditor] = None
        self.blocks_editor: Optional[GridEditor] = None
        self.image_editor: Optional[GridEditor] = None
        self.extra_fields: Optional[FieldGrid] = None

    def _build_status(self) -> None:
        bar = ttk.Frame(self)
        bar.pack(fill="x", side="bottom")
        self.status = tk.StringVar(value="준비됨")
        ttk.Label(bar, textvariable=self.status, anchor="w").pack(side="left", padx=10, pady=4)
        ttk.Button(bar, text="PDF 미리보기 (F5)", command=self.preview).pack(side="right", padx=(4, 10), pady=4)
        ttk.Button(bar, text="PDF로 내보내기", command=self.export).pack(side="right", pady=4)

    # ── 상태 ────────────────────────────────────────────────
    def mark_dirty(self, dirty: bool = True) -> None:
        self._dirty = dirty
        name = os.path.basename(self.doc.source_path) if self.doc.source_path else "새 문서"
        self.title(f"{APP_TITLE} — {name}{' *' if dirty else ''}")

    def set_status(self, text: str) -> None:
        self.status.set(text)
        self.update_idletasks()

    # ── 문서 ↔ 화면 ──────────────────────────────────────────
    def load_doc(self, doc: SpecDoc) -> None:
        self.doc = doc
        m = doc.meta
        for key in ("product_name", "use_name", "doc_kind", "company", "dwg_prefix",
                    "dwg_no", "old_dwg_no", "standard", "dwg_code", "dwg_code2",
                    "index", "footer_code", "label_product", "label_use", "label_kind"):
            self.meta_fields.set(key, getattr(m, key))
        self.logo_var.set(m.logo_path)
        self.logo_h_var.set(str(m.logo_height_mm))
        self.sign_fields.set("drawn_date", m.drawn.date)
        self.sign_fields.set("drawn_name", m.drawn.name)
        self.sign_fields.set("checked_date", m.checked.date)
        self.sign_fields.set("checked_name", m.checked.name)
        self.sign_fields.set("renewal_date", m.renewal.date)
        self.sign_fields.set("renewal_name", m.renewal.name)
        self.sign_fields.set("approved", m.approved)
        self.page_fields.set("page_start", str(m.page_start))
        self.page_fields.set("page_total", str(m.page_total))
        self.page_fields.set("revision_rows", str(m.revision_rows))
        self.note_text.delete("1.0", "end")
        self.note_text.insert("1.0", m.confidential_note)

        self._current = None
        self.refresh_section_list(select=0)
        self.mark_dirty(False)

    def collect_meta(self) -> None:
        m = self.doc.meta
        for key in ("product_name", "use_name", "doc_kind", "company", "dwg_prefix",
                    "dwg_no", "old_dwg_no", "standard", "dwg_code", "dwg_code2",
                    "index", "footer_code", "label_product", "label_use", "label_kind"):
            setattr(m, key, self.meta_fields.get(key))
        m.logo_path = self.logo_var.get()
        m.logo_height_mm = _float(self.logo_h_var.get(), 8.5)
        m.drawn.date = self.sign_fields.get("drawn_date")
        m.drawn.name = self.sign_fields.get("drawn_name")
        m.checked.date = self.sign_fields.get("checked_date")
        m.checked.name = self.sign_fields.get("checked_name")
        m.renewal.date = self.sign_fields.get("renewal_date")
        m.renewal.name = self.sign_fields.get("renewal_name")
        m.approved = self.sign_fields.get("approved")
        m.page_start = _int(self.page_fields.get("page_start"), 1)
        m.page_total = _int(self.page_fields.get("page_total"), 0)
        m.revision_rows = max(1, _int(self.page_fields.get("revision_rows"), 5))
        m.confidential_note = self.note_text.get("1.0", "end-1c")

    def refresh_section_list(self, select: Optional[int] = None) -> None:
        keep = select if select is not None else (self.sec_list.curselection() or [None])[0]
        self.sec_list.delete(0, "end")
        numbers = self.doc.assign_numbers()
        for s in self.doc.sections:
            head = numbers.get(s.id) or ""
            head = f"{head}." if s.numbered and head else head
            title = "/".join(x for x in (s.title_ko, s.title_en) if x)
            self.sec_list.insert("end", f"{head} {title}   〔{KIND_LABELS.get(s.kind, s.kind)}〕")
        if self.doc.sections:
            idx = 0 if keep is None else max(0, min(int(keep), len(self.doc.sections) - 1))
            self.sec_list.selection_clear(0, "end")
            self.sec_list.selection_set(idx)
            self.sec_list.see(idx)
            self.show_section(self.doc.sections[idx])
        else:
            self._current = None
            self._clear_body()

    def _on_select_section(self, _e=None) -> None:
        sel = self.sec_list.curselection()
        if not sel:
            return
        section = self.doc.sections[sel[0]]
        if section is self._current:
            return
        self._commit_current()
        self.show_section(section)

    # ── 섹션 편집기 ──────────────────────────────────────────
    def _clear_body(self) -> None:
        for child in self.body_area.winfo_children():
            child.destroy()
        self.rows_editor: Optional[GridEditor] = None
        self.blocks_editor: Optional[GridEditor] = None
        self.image_editor: Optional[GridEditor] = None
        self.extra_fields: Optional[FieldGrid] = None

    def show_section(self, section: Section) -> None:
        self._current = None   # 값 세팅 중 trace 로 되쓰이는 것 방지
        sfg = self.sec_fields
        sfg.set("title_ko", section.title_ko)
        sfg.set("title_en", section.title_en)
        sfg.set("numbered", section.numbered)
        sfg.set("no_override", section.no_override)
        sfg.set("bullet", section.bullet)
        sfg.set("underline", section.underline)
        sfg.set("page_break_before", section.page_break_before)
        sfg.set("note", section.note)

        self._clear_body()
        if section.kind == KIND_SPEC_TABLE:
            self._pane_spec(section)
        elif section.kind == KIND_VERSION_TABLE:
            self._pane_version(section)
        elif section.kind == KIND_IMAGE:
            self._pane_image(section)
        else:
            self._pane_text(section)
        self._current = section

    # ── 항목 종류별 편집 화면 ────────────────────────────────
    def _changed(self):
        return lambda: self._commit_current(mark=True)

    def _blocks_grid(self, parent, section: Section, title: str, hint: str,
                     weight: int) -> GridEditor:
        box = ttk.LabelFrame(parent, text=title)
        if hint:
            ttk.Label(box, text=hint, foreground="#555", justify="left").pack(
                anchor="w", padx=6, pady=(4, 0))
        g = GridEditor(box, columns=[("indent", "들여쓰기", 70), ("marker", "머리기호", 80),
                                     ("ko", "내용", 520), ("en", "영문(선택)", 300)],
                       multiline=("ko", "en"), on_change=self._changed())
        g.pack(fill="both", expand=True, padx=6, pady=6)
        g.set_rows([{"indent": str(b.indent), "marker": b.marker, "ko": b.ko, "en": b.en}
                    for b in section.blocks])
        parent.add(box, weight=weight)
        return g

    def _image_grid(self, parent, section: Section, weight: int) -> GridEditor:
        box = ttk.LabelFrame(parent, text="첨부 도면 (PNG / JPG / PDF)")
        ttk.Label(box, foreground="#555", justify="left",
                  text="PDF 를 넣으면 첫 페이지가 그림으로 들어갑니다. "
                       "폭은 mm 단위이고 본문 최대 폭은 170mm 입니다.").pack(
            anchor="w", padx=6, pady=(4, 0))
        g = GridEditor(box, columns=[("path", "파일", 380), ("width_mm", "폭(mm)", 70),
                                     ("align", "정렬", 80),
                                     ("caption_ko", "도면 설명", 260),
                                     ("caption_en", "설명(영문·선택)", 180)],
                       multiline=("caption_ko", "caption_en"), on_change=self._changed(),
                       extra_buttons=(("도면 파일 추가...", self._add_image_file),))
        g.pack(fill="both", expand=True, padx=6, pady=6)
        g.set_rows([{"path": i.path, "width_mm": str(i.width_mm), "align": i.align,
                     "caption_ko": i.caption_ko, "caption_en": i.caption_en}
                    for i in section.images])
        parent.add(box, weight=weight)
        return g

    def _pane(self) -> ttk.PanedWindow:
        p = ttk.PanedWindow(self.body_area, orient="vertical")
        p.pack(fill="both", expand=True, padx=4, pady=4)
        return p

    def _pane_text(self, section: Section) -> None:
        p = self._pane()
        self.blocks_editor = self._blocks_grid(
            p, section, "본문",
            "한 줄에 한 문장씩. 영문 칸은 비워 두어도 됩니다. "
            "들여쓰기 0~3 단계, 머리기호는 (1) ① · 등을 그대로 넣으세요.", 3)
        self.image_editor = self._image_grid(p, section, 2)

    def _pane_spec(self, section: Section) -> None:
        p = self._pane()
        box = ttk.LabelFrame(p, text="사양표")
        ttk.Label(box, foreground="#555", justify="left",
                  text="엑셀에서 [항목 / 항목(영문) / 사양 / 비고] 4열을 복사한 뒤 "
                       "‘엑셀에서 붙여넣기’ 를 누르면 한 번에 채워집니다.").pack(
            anchor="w", padx=6, pady=(4, 0))
        g = GridEditor(box, columns=[("item_ko", "항목", 200),
                                     ("item_en", "항목(영문·선택)", 160),
                                     ("spec", "사양", 330), ("remark", "비고", 260)],
                       multiline=("spec", "remark"), on_change=self._changed())
        g.pack(fill="both", expand=True, padx=6, pady=6)
        g.set_rows([{"item_ko": r.item_ko, "item_en": r.item_en,
                     "spec": r.spec, "remark": r.remark} for r in section.rows])
        p.add(box, weight=4)
        self.rows_editor = g
        self.blocks_editor = self._blocks_grid(p, section, "표 위에 붙일 설명글 (선택)", "", 1)
        self.image_editor = self._image_grid(p, section, 3)

    def _pane_image(self, section: Section) -> None:
        p = self._pane()
        self.image_editor = self._image_grid(p, section, 4)
        self.blocks_editor = self._blocks_grid(p, section, "도면 위에 붙일 설명글 (선택)", "", 2)

    def _pane_version(self, section: Section) -> None:
        top = ttk.Frame(self.body_area)
        top.pack(fill="x", padx=6, pady=(6, 0))
        self.extra_fields = FieldGrid(top, columns=1)
        self.extra_fields.pack(fill="x")
        self.extra_fields.add("part_no", "파트번호 표기 (◇ 파트번호 : ○○)", 20)
        self.extra_fields.set("part_no", section.part_no)
        self.extra_fields.vars["part_no"].trace_add("write", lambda *a: self._commit_current(mark=True))

        p = self._pane()
        box = ttk.LabelFrame(p, text="개정 이력")
        g = GridEditor(box, columns=[("rev", "개정", 70), ("version", "판수", 70),
                                     ("date", "변경일자", 110),
                                     ("changed_ko", "변경 내용", 460),
                                     ("changed_en", "변경 내용(영문·선택)", 260)],
                       multiline=("changed_ko", "changed_en"), on_change=self._changed())
        g.pack(fill="both", expand=True, padx=6, pady=6)
        g.set_rows([{"rev": r.rev, "version": r.version, "date": r.date,
                     "changed_ko": r.changed_ko, "changed_en": r.changed_en}
                    for r in section.versions])
        p.add(box, weight=4)
        self.rows_editor = g
        self.blocks_editor = self._blocks_grid(p, section, "표 위에 붙일 설명글 (선택)", "", 1)

    def _add_image_file(self) -> None:
        g = self.image_editor
        if g is None:
            return
        paths = filedialog.askopenfilenames(
            title="도면 파일 선택",
            filetypes=[("도면/이미지", " ".join(f"*{e}" for e in sorted(SUPPORTED_EXT))),
                       ("모든 파일", "*.*")])
        if not paths:
            return
        rows = g.get_rows()
        for path in paths:
            try:
                rel = copy_into_project(path, self.doc.base_dir()) if self.doc.source_path else path
            except OSError:
                rel = path
            rows.append({"path": rel, "width_mm": "150", "align": "CENTER",
                         "caption_ko": "", "caption_en": ""})
        g.set_rows(rows)
        self._commit_current(mark=True)
        if not self.doc.source_path:
            self.set_status("문서를 먼저 저장하면 도면 파일이 프로젝트 폴더로 복사됩니다.")

    def _commit_current(self, mark: bool = False) -> None:
        s = self._current
        if s is None:
            return
        sfg = self.sec_fields
        s.title_ko = sfg.get("title_ko")
        s.title_en = sfg.get("title_en")
        s.numbered = bool(sfg.get("numbered"))
        s.no_override = sfg.get("no_override")
        s.bullet = sfg.get("bullet")
        s.underline = bool(sfg.get("underline"))
        s.page_break_before = bool(sfg.get("page_break_before"))
        s.note = sfg.get("note")

        if self.blocks_editor is not None:
            s.blocks = _blocks_from(self.blocks_editor.get_rows())
        if self.image_editor is not None:
            s.images = [ImageItem(r.get("path", ""), _float(r.get("width_mm"), 150.0),
                                  r.get("caption_ko", ""), r.get("caption_en", ""),
                                  (r.get("align") or "CENTER").upper())
                        for r in self.image_editor.get_rows() if r.get("path")]
        if self.rows_editor is not None:
            rows = self.rows_editor.get_rows()
            if s.kind == KIND_SPEC_TABLE:
                s.rows = [SpecRow(r.get("item_ko", ""), r.get("item_en", ""),
                                  r.get("spec", ""), r.get("remark", "")) for r in rows]
            elif s.kind == KIND_VERSION_TABLE:
                s.versions = [VersionRow(r.get("rev", ""), r.get("version", ""),
                                         r.get("date", ""), r.get("changed_ko", ""),
                                         r.get("changed_en", "")) for r in rows]
                if self.extra_fields:
                    s.part_no = self.extra_fields.get("part_no")
        if mark:
            self.mark_dirty()
            self._refresh_list_labels()

    def _refresh_list_labels(self) -> None:
        sel = self.sec_list.curselection()
        idx = sel[0] if sel else None
        numbers = self.doc.assign_numbers()
        for i, s in enumerate(self.doc.sections):
            head = numbers.get(s.id) or ""
            head = f"{head}." if s.numbered and head else head
            title = "/".join(x for x in (s.title_ko, s.title_en) if x)
            label = f"{head} {title}   〔{KIND_LABELS.get(s.kind, s.kind)}〕"
            if self.sec_list.get(i) != label:
                self.sec_list.delete(i)
                self.sec_list.insert(i, label)
        if idx is not None:
            self.sec_list.selection_clear(0, "end")
            self.sec_list.selection_set(idx)

    # ── 섹션 목록 조작 ───────────────────────────────────────
    def add_section(self) -> None:
        self._commit_current()
        kind = next((k for k, v in KIND_LABELS.items() if v == self.new_kind.get()), KIND_TEXT)
        sel = self.sec_list.curselection()
        pos = (sel[0] + 1) if sel else len(self.doc.sections)
        section = Section(kind=kind, title_ko="새 항목")
        if kind == KIND_TEXT:
            section.blocks = [Block(indent=1)]
        elif kind == KIND_SPEC_TABLE:
            section.rows = [SpecRow()]
        elif kind == KIND_VERSION_TABLE:
            section.versions = [VersionRow()]
        self.doc.sections.insert(pos, section)
        self.refresh_section_list(select=pos)
        self.mark_dirty()

    def duplicate_section(self) -> None:
        self._commit_current()
        sel = self.sec_list.curselection()
        if not sel:
            return
        import copy
        s = copy.deepcopy(self.doc.sections[sel[0]])
        s.id = os.urandom(4).hex()
        self.doc.sections.insert(sel[0] + 1, s)
        self.refresh_section_list(select=sel[0] + 1)
        self.mark_dirty()

    def delete_section(self) -> None:
        sel = self.sec_list.curselection()
        if not sel:
            return
        if not messagebox.askyesno("확인", "선택한 항목을 삭제할까요?"):
            return
        self._current = None
        del self.doc.sections[sel[0]]
        self.refresh_section_list(select=max(0, sel[0] - 1))
        self.mark_dirty()

    def move_section(self, delta: int) -> None:
        self._commit_current()
        sel = self.sec_list.curselection()
        if not sel:
            return
        i, j = sel[0], sel[0] + delta
        if not (0 <= j < len(self.doc.sections)):
            return
        self.doc.sections[i], self.doc.sections[j] = self.doc.sections[j], self.doc.sections[i]
        self._current = None
        self.refresh_section_list(select=j)
        self.mark_dirty()

    # ── 파일 ────────────────────────────────────────────────
    def _confirm_discard(self) -> bool:
        if not self._dirty:
            return True
        ans = messagebox.askyesnocancel("저장", "변경 내용을 저장할까요?")
        if ans is None:
            return False
        if ans:
            return self.save()
        return True

    def new_from_template(self, silent: bool = False) -> None:
        if not silent and not self._confirm_discard():
            return
        doc = tpl_pkg.load_template("reactor")
        doc.source_path = ""
        self.load_doc(doc)
        self.set_status("표준 템플릿(리액터 생산 사양서)에서 새 문서를 시작했습니다.")

    def new_empty(self) -> None:
        if not self._confirm_discard():
            return
        doc = SpecDoc()
        doc.sections = [Section(kind=KIND_TEXT, title_ko="적용 범위", title_en="Scope",
                                blocks=[Block(indent=1)])]
        self.load_doc(doc)
        self.set_status("빈 문서를 시작했습니다.")

    def open_file(self) -> None:
        if not self._confirm_discard():
            return
        path = filedialog.askopenfilename(title="사양서 열기", filetypes=FILETYPES)
        if path:
            self.open_path(path)

    def open_path(self, path: str) -> None:
        try:
            self.load_doc(SpecDoc.load(path))
            self.set_status(f"열었습니다: {path}")
        except Exception as exc:
            messagebox.showerror("열기 실패", f"{exc}")

    def save(self) -> bool:
        if not self.doc.source_path:
            return self.save_as()
        return self._write(self.doc.source_path)

    def save_as(self) -> bool:
        name = (self.doc.meta.dwg_no or "사양서") + ".spec.json"
        path = filedialog.asksaveasfilename(title="다른 이름으로 저장", defaultextension=".spec.json",
                                            initialfile=name, filetypes=FILETYPES)
        return self._write(path) if path else False

    def _write(self, path: str) -> bool:
        self._commit_current()
        self.collect_meta()
        try:
            self.doc.save(path)
        except OSError as exc:
            messagebox.showerror("저장 실패", f"{exc}")
            return False
        self.mark_dirty(False)
        self.set_status(f"저장했습니다: {path}")
        return True

    def save_as_template(self) -> None:
        self._commit_current()
        self.collect_meta()
        path = filedialog.asksaveasfilename(
            title="템플릿으로 저장", defaultextension=".spec.json",
            initialdir=tpl_pkg.user_template_dir(), filetypes=FILETYPES)
        if not path:
            return
        try:
            SpecDoc.from_dict(self.doc.to_dict()).save(path)
            self.set_status(f"템플릿으로 저장했습니다: {path}")
        except OSError as exc:
            messagebox.showerror("저장 실패", f"{exc}")

    # ── 출력 ────────────────────────────────────────────────
    def _make_pdf(self, out_path: str) -> Optional[str]:
        self._commit_current()
        self.collect_meta()
        try:
            self.set_status("PDF 생성 중...")
            path = build_pdf(self.doc, out_path, self.settings.get("font_path"))
            self.set_status(f"PDF 생성 완료: {path}  (폰트: {active_font_description()})")
            return path
        except Exception as exc:
            traceback.print_exc()
            messagebox.showerror("PDF 생성 실패", f"{exc}\n\n자세한 내용은 콘솔을 확인하세요.")
            self.set_status("PDF 생성 실패")
            return None

    def preview(self) -> None:
        tmp = os.path.join(tempfile.gettempdir(),
                           f"미리보기_{self.doc.meta.dwg_no or 'spec'}.pdf")
        if self._make_pdf(tmp):
            open_with_os(tmp)

    def export(self) -> None:
        base = f"{self.doc.meta.dwg_prefix}{self.doc.meta.dwg_no}".strip() or "사양서"
        path = filedialog.asksaveasfilename(title="PDF로 내보내기", defaultextension=".pdf",
                                            initialfile=base + ".pdf",
                                            filetypes=[("PDF", "*.pdf")])
        if not path:
            return
        if self._make_pdf(path) and messagebox.askyesno("완료", "PDF를 지금 열어볼까요?"):
            open_with_os(path)

    # ── 도구 ────────────────────────────────────────────────
    def choose_logo(self) -> None:
        path = filedialog.askopenfilename(
            title="회사 로고 선택",
            filetypes=[("이미지", "*.png *.jpg *.jpeg *.gif *.bmp"), ("모든 파일", "*.*")])
        if not path:
            return
        if self.doc.source_path:
            try:
                path = copy_into_project(path, self.doc.base_dir(), subdir=".")
            except OSError:
                pass
        self.logo_var.set(path)

    def choose_font(self) -> None:
        path = filedialog.askopenfilename(
            title="PDF에 사용할 폰트 선택",
            filetypes=[("폰트 파일", "*.ttf *.otf *.ttc"), ("모든 파일", "*.*")])
        if not path:
            return
        self.settings["font_path"] = path
        save_settings(self.settings)
        messagebox.showinfo("폰트", "다음 PDF 생성부터 적용됩니다.\n"
                                    "프로그램을 다시 시작하면 확실하게 반영됩니다.")

    def reset_font(self) -> None:
        self.settings.pop("font_path", None)
        save_settings(self.settings)
        messagebox.showinfo("폰트", "기본 폰트 자동 선택으로 되돌렸습니다.")

    def show_help(self) -> None:
        messagebox.showinfo(
            "사용 방법",
            "1) ‘① 기본정보’ 에서 도면번호·제품명·서명란을 채웁니다.\n"
            "2) ‘② 문서 구성’ 에서 항목을 고르고 내용을 입력합니다.\n"
            "   · 사양표는 엑셀에서 4열을 복사해 붙여넣을 수 있습니다.\n"
            "   · 도면은 ‘도면/그림’ 항목에 PNG/JPG/PDF 를 추가합니다.\n"
            "3) F5 로 미리보기, Ctrl+P 로 PDF 내보내기.\n\n"
            "항목 번호(1. 2. 3. …)와 PAGE n/N 은 자동으로 다시 매겨집니다.\n"
            f"현재 PDF 폰트: {active_font_description()}")

    def on_close(self) -> None:
        self._commit_current()
        if self._confirm_discard():
            self.destroy()


def _blocks_from(rows: List[Dict[str, str]]) -> List[Block]:
    return [Block(_int(r.get("indent"), 1), r.get("marker", ""),
                  r.get("ko", ""), r.get("en", "")) for r in rows]


def _int(value, default: int) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def _float(value, default: float) -> float:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return default


def main(path: Optional[str] = None) -> int:
    register_fonts(load_settings().get("font_path"))
    app = App(path)
    app.mainloop()
    return 0
