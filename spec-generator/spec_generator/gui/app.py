# -*- coding: utf-8 -*-
"""생산용 사양서 생성기 - 메인 창."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import datetime as _dt
import tempfile
import tkinter as tk
import traceback
from tkinter import filedialog, messagebox, ttk
from typing import Dict, List, Optional

from .. import approval as approval_mod
from .. import docnumber as dn
from .. import placeholders as ph
from .. import updater
from .. import templates as tpl_pkg
from ..registry import Registry
from ..fonts import active_font_description, register_fonts
from ..importers import SUPPORTED_EXT, copy_into_project
from ..model import (AUDIENCE_LABELS, AUD_BOTH, AUD_CUSTOMER, AUD_INTERNAL,
                     GridRow, KIND_NAMEPLATE, KIND_TABLE, file_is_newer, KIND_IMAGE, KIND_LABELS, KIND_SPEC_TABLE, KIND_TEXT,
                     KIND_VERSION_TABLE, Block, ImageItem, Section, SpecDoc,
                     SpecRow, VersionRow)
from ..render.build import build_approval_pdf, build_both, build_pdf
from .widgets import (FieldGrid, GridEditor, HelpWindow, MultilineDialog,
                      RegistryWindow, UpdateWindow)

from .. import __version__

APP_TITLE = f"Braumm 사양서 생성기  v{__version__}"
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


DEFAULT_PATTERN = "{도번}_Rev{리비전}_{날짜}"


def safe_name(text: str) -> str:
    """파일·폴더 이름으로 쓸 수 없는 글자를 걸러낸다."""
    out = "".join("_" if ch in '\\/:*?"<>|' else ch for ch in (text or "").strip())
    return out.strip(" .") or "무제"


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
        self.editing_approval = False      # False=생산 사양서 구성, True=승인 정형 문구

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
        self.recent_menu = tk.Menu(m, tearoff=0)
        m.add_cascade(label="최근에 연 문서", menu=self.recent_menu)
        m.add_command(label="저장", accelerator="Ctrl+S", command=self.save)
        m.add_command(label="다른 이름으로 저장...", command=self.save_as)
        m.add_separator()
        m.add_command(label="현재 문서를 템플릿으로 저장...", command=self.save_as_template)
        m.add_separator()
        m.add_command(label="끝내기", command=self.on_close)
        bar.add_cascade(label="파일", menu=m)

        o = tk.Menu(bar, tearoff=0)
        o.add_command(label="생산 사양서 미리보기", accelerator="F5", command=self.preview)
        o.add_command(label="고객 승인 사양서 미리보기", accelerator="F6",
                      command=self.preview_approval)
        o.add_command(label="고객에게 나가는 내용 확인...", command=self.show_customer_scope)
        o.add_separator()
        o.add_command(label="고객사 폴더에 저장", accelerator="Ctrl+E",
                      command=self.export_to_customer_folder)
        o.add_command(label="PDF로 내보내기 (위치 지정)...", accelerator="Ctrl+P",
                      command=self.export)
        o.add_separator()
        self.approval_var = tk.BooleanVar(value=bool(self.settings.get("make_approval", True)))
        o.add_checkbutton(label="저장할 때 고객 승인 사양서도 함께 발행",
                          variable=self.approval_var, command=self.toggle_approval_output)
        o.add_separator()
        o.add_command(label="출력 폴더 설정...", command=self.set_output_root)
        o.add_command(label="파일 이름 규칙...", command=self.set_filename_pattern)
        bar.add_cascade(label="출력", menu=o)

        t = tk.Menu(bar, tearoff=0)
        t.add_command(label="최신 템플릿의 추가 항목 가져오기...", accelerator="F8",
                      command=self.pull_template_updates)
        self.update_check_var = tk.BooleanVar(
            value=bool(self.settings.get("check_updates_on_open", True)))
        t.add_checkbutton(label="문서를 열 때 새로 생긴 항목이 있는지 확인",
                          variable=self.update_check_var, command=self.toggle_update_check)
        t.add_separator()
        t.add_command(label="도번 대장 보기...", command=self.show_registry)
        t.add_command(label="쓸 수 있는 자동 입력 항목...", command=self.show_placeholders)
        t.add_separator()
        t.add_command(label="PDF 폰트 지정...", command=self.choose_font)
        t.add_command(label="폰트 설정 초기화", command=self.reset_font)
        bar.add_cascade(label="도구", menu=t)

        h = tk.Menu(bar, tearoff=0)
        h.add_command(label="사용 방법", command=self.show_help)
        h.add_separator()
        h.add_command(label="프로그램 정보", command=self.show_about)
        bar.add_cascade(label="도움말", menu=h)
        self.config(menu=bar)

        self.bind_all("<Control-n>", lambda e: self.new_from_template())
        self.bind_all("<Control-o>", lambda e: self.open_file())
        self.bind_all("<Control-s>", lambda e: self.save())
        self.bind_all("<Control-p>", lambda e: self.export())
        self.bind_all("<Control-e>", lambda e: self.export_to_customer_folder())
        self.bind_all("<F5>", lambda e: self.preview())
        self.bind_all("<F6>", lambda e: self.preview_approval())
        self.bind_all("<F8>", lambda e: self.pull_template_updates())
        self._rebuild_recent_menu()

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

        g0 = ttk.LabelFrame(f, text="도면번호 · 리비전   (여기부터 채우세요)")
        g0.pack(fill="x", padx=10, pady=(10, 6))
        r1 = ttk.Frame(g0)
        r1.pack(fill="x", padx=6, pady=(6, 2))
        self.no_fields = FieldGrid(r1, columns=3)
        self.no_fields.pack(fill="x")
        nf = self.no_fields
        nf.add("customer", "고객사 (한글)", 18)
        nf.add("customer_en", "고객사 (영문)", 18)
        nf.add("family", "제품군", 24, kind="combo", values=dn.family_choices())
        nf.add("rated_current", "정격 전류", 18)
        nf.add("serial", "일련번호", 8)
        nf.add("dwg_no", "도면번호", 22)
        r2 = ttk.Frame(g0)
        r2.pack(fill="x", padx=12, pady=(0, 6))
        ttk.Button(r2, text="도번 자동 생성", command=self.generate_doc_no).pack(side="left")
        ttk.Label(r2, text="  형식:  BR-제품군-고객코드-정격전류-일련번호",
                  foreground="#666").pack(side="left")
        ttk.Separator(r2, orient="vertical").pack(side="left", fill="y", padx=10)
        ttk.Label(r2, text="리비전").pack(side="left")
        self.rev_var = tk.StringVar(value="A")
        ttk.Entry(r2, textvariable=self.rev_var, width=5).pack(side="left", padx=4)
        self.rev_date_var = tk.StringVar()
        ttk.Label(r2, text="발행일").pack(side="left", padx=(6, 2))
        ttk.Entry(r2, textvariable=self.rev_date_var, width=12).pack(side="left")
        ttk.Button(r2, text="▲ 리비전 올리기", command=self.bump_revision).pack(side="left", padx=8)
        self.rev_var.trace_add("write", lambda *a: self.mark_dirty())
        self.rev_date_var.trace_add("write", lambda *a: self.mark_dirty())
        for var in nf.vars.values():
            var.trace_add("write", lambda *a: self.mark_dirty())

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

        cover = ttk.LabelFrame(f, text="표지 (첫 장)")
        cover.pack(fill="x", padx=10, pady=6)
        crow = ttk.Frame(cover)
        crow.pack(fill="x", padx=6, pady=6)
        self.cover_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(crow, text="첫 장에 표지 넣기", variable=self.cover_var).pack(side="left")
        ttk.Label(crow, text="  영문 부제").pack(side="left", padx=(16, 4))
        self.cover_sub_var = tk.StringVar()
        ttk.Entry(crow, textvariable=self.cover_sub_var, width=34).pack(side="left")
        ttk.Label(cover, foreground="#666",
                  text="표지에는 로고, 제품명, 고객사, 도번, 리비전, 승인란이 들어갑니다. "
                       "표지는 쪽 번호에서 제외됩니다.").pack(anchor="w", padx=12, pady=(0, 6))
        self.cover_var.trace_add("write", lambda *a: self.mark_dirty())
        self.cover_sub_var.trace_add("write", lambda *a: self.mark_dirty())

        logo = ttk.LabelFrame(f, text="회사 로고 (표지 · 표제란)")
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

        g2 = ttk.LabelFrame(f, text="작성 · 검토 · 승인   (도장/사인 이미지를 넣을 수 있습니다)")
        g2.pack(fill="x", padx=10, pady=6)
        head = ttk.Frame(g2)
        head.pack(fill="x", padx=8, pady=(6, 0))
        for text, width in (("", 8), ("이름", 18), ("일자", 16), ("도장 / 사인 파일", 40)):
            ttk.Label(head, text=text, width=width).pack(side="left", padx=2)

        self.sign_vars = {}
        for key, label in (("drawn", "작 성"), ("checked", "검 토"),
                           ("renewal", "갱 신"), ("approved", "승 인")):
            row = ttk.Frame(g2)
            row.pack(fill="x", padx=8, pady=2)
            ttk.Label(row, text=label, width=8).pack(side="left", padx=2)
            name = tk.StringVar()
            date = tk.StringVar()
            stamp = tk.StringVar()
            ttk.Entry(row, textvariable=name, width=18).pack(side="left", padx=2)
            ttk.Entry(row, textvariable=date, width=16).pack(side="left", padx=2)
            ttk.Entry(row, textvariable=stamp).pack(side="left", padx=2, fill="x", expand=True)
            ttk.Button(row, text="찾아보기", width=9,
                       command=lambda v=stamp: self.choose_stamp(v)).pack(side="left", padx=2)
            ttk.Button(row, text="지우기", width=7,
                       command=lambda v=stamp: v.set("")).pack(side="left")
            for var in (name, date, stamp):
                var.trace_add("write", lambda *a: self.mark_dirty())
            self.sign_vars[key] = {"name": name, "date": date, "stamp": stamp}

        ttk.Label(g2, foreground="#666", justify="left",
                  text="도장 파일을 비워 두면 assets\\stamps\\{이름}.png 를 자동으로 찾습니다. "
                       "(예: 홍길동.png)\n"
                       "한 번 넣어 두면 그 사람 이름을 쓸 때마다 자동으로 찍힙니다. "
                       "PNG 배경 투명 권장.").pack(anchor="w", padx=12, pady=(2, 8))

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

        for var in list(mf.vars.values()) + list(pf.vars.values()):
            var.trace_add("write", lambda *a: self.mark_dirty())
        self.note_text.bind("<<Modified>>", self._note_modified)

    def _note_modified(self, _e=None):
        if self.note_text.edit_modified():
            self.note_text.edit_modified(False)
            self.mark_dirty()

    def _sections(self):
        """지금 편집 중인 항목 목록."""
        return self.doc.approval_sections if self.editing_approval else self.doc.sections

    def _switch_list(self) -> None:
        want = bool(self.list_mode.get())
        if want == self.editing_approval:
            return
        self._commit_current()
        if want and not self.doc.approval_sections:
            if not messagebox.askyesno(
                    "승인 사양서 정형 문구",
                    "이 문서에는 아직 승인 사양서 정형 문구가 들어 있지 않습니다.\n"
                    "(지금은 프로그램의 표준 문구를 그대로 쓰고 있습니다)\n\n"
                    "표준 문구를 이 문서 안으로 가져와 편집할까요?\n"
                    "가져오면 적용 규격·사용 조건·허용 공차 등을 제품에 맞게 고칠 수 있습니다."):
                self.list_mode.set(0)
                return
            self.doc.approval_sections = approval_mod.default_boilerplate()
            self.mark_dirty()
        self.editing_approval = want
        self._current = None
        self.refresh_section_list(select=0)
        self.mode_hint.configure(
            text=("고객 승인 사양서에만 실리는 정형 문구입니다. "
                  "적용 규격·허용 공차 등을 제품에 맞게 고치세요."
                  if want else
                  "생산 사양서의 구성입니다. 고객에게도 보낼 항목은 [공개 범위] 를 바꾸세요."))

    def _build_sections_tab(self) -> None:
        top = ttk.Frame(self.tab_sections)
        top.pack(fill="x", padx=10, pady=(8, 0))
        self.list_mode = tk.IntVar(value=0)
        ttk.Radiobutton(top, text="생산 사양서 구성", variable=self.list_mode, value=0,
                        command=self._switch_list).pack(side="left")
        ttk.Radiobutton(top, text="승인 사양서 정형 문구 (적용 규격 · 허용 공차 …)",
                        variable=self.list_mode, value=1,
                        command=self._switch_list).pack(side="left", padx=(14, 0))
        self.mode_hint = ttk.Label(
            self.tab_sections, foreground="#666",
            text="생산 사양서의 구성입니다. 고객에게도 보낼 항목은 [공개 범위] 를 바꾸세요.")
        self.mode_hint.pack(anchor="w", padx=12, pady=(2, 0))

        pane = ttk.PanedWindow(self.tab_sections, orient="horizontal")
        pane.pack(fill="both", expand=True, padx=8, pady=(6, 8))

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
        sfg.add("audience", "공개 범위", 22, kind="combo",
                values=[AUDIENCE_LABELS[k] for k in (AUD_INTERNAL, AUD_BOTH, AUD_CUSTOMER)])
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
        ttk.Button(bar, text="생산 미리보기 (F5)", command=self.preview).pack(
            side="right", padx=(4, 10), pady=4)
        ttk.Button(bar, text="승인 미리보기 (F6)", command=self.preview_approval).pack(
            side="right", padx=4, pady=4)
        ttk.Button(bar, text="고객사 폴더에 저장 (Ctrl+E)",
                   command=self.export_to_customer_folder).pack(side="right", padx=4, pady=4)
        ttk.Button(bar, text="저장 (Ctrl+S)", command=self.save).pack(side="right", pady=4)

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
                    "old_dwg_no", "standard", "dwg_code", "dwg_code2",
                    "index", "footer_code", "label_product", "label_use", "label_kind"):
            self.meta_fields.set(key, getattr(m, key))
        self.logo_var.set(m.logo_path)
        self.logo_h_var.set(str(m.logo_height_mm))
        self.cover_var.set(bool(m.cover))
        self.cover_sub_var.set(m.cover_subtitle)
        for key in ("customer", "customer_en", "rated_current", "serial", "dwg_no"):
            self.no_fields.set(key, getattr(m, key))
        self.no_fields.set("family", next(
            (c for c in dn.family_choices() if c.startswith(m.family)), dn.family_choices()[0]))
        self.rev_var.set(m.revision)
        self.rev_date_var.set(m.revision_date)
        for key, vars_ in self.sign_vars.items():
            person = getattr(m, key)
            vars_["name"].set(person.name)
            vars_["date"].set(person.date)
            vars_["stamp"].set(person.stamp)
        self.page_fields.set("page_start", str(m.page_start))
        self.page_fields.set("page_total", str(m.page_total))
        self.page_fields.set("revision_rows", str(m.revision_rows))
        self.note_text.delete("1.0", "end")
        self.note_text.insert("1.0", m.confidential_note)

        self._current = None
        self.editing_approval = False
        if hasattr(self, "list_mode"):
            self.list_mode.set(0)
        self.refresh_section_list(select=0)
        self.mark_dirty(False)

    def collect_meta(self) -> None:
        m = self.doc.meta
        for key in ("product_name", "use_name", "doc_kind", "company", "dwg_prefix",
                    "old_dwg_no", "standard", "dwg_code", "dwg_code2",
                    "index", "footer_code", "label_product", "label_use", "label_kind"):
            setattr(m, key, self.meta_fields.get(key))
        m.logo_path = self.logo_var.get()
        m.logo_height_mm = _float(self.logo_h_var.get(), 8.5)
        m.cover = bool(self.cover_var.get())
        m.cover_subtitle = self.cover_sub_var.get()
        for key in ("customer", "customer_en", "rated_current", "serial", "dwg_no"):
            setattr(m, key, self.no_fields.get(key))
        m.family = dn.family_from_choice(self.no_fields.get("family"))
        m.revision = (self.rev_var.get() or "A").upper()
        m.revision_date = self.rev_date_var.get()
        for key, vars_ in self.sign_vars.items():
            person = getattr(m, key)
            person.name = vars_["name"].get()
            person.date = vars_["date"].get()
            person.stamp = vars_["stamp"].get()
        m.page_start = _int(self.page_fields.get("page_start"), 1)
        m.page_total = _int(self.page_fields.get("page_total"), 0)
        m.revision_rows = max(1, _int(self.page_fields.get("revision_rows"), 5))
        m.confidential_note = self.note_text.get("1.0", "end-1c")

    def refresh_section_list(self, select: Optional[int] = None) -> None:
        keep = select if select is not None else (self.sec_list.curselection() or [None])[0]
        self.sec_list.delete(0, "end")
        sections = self._sections()
        numbers = self.doc.assign_numbers(sections)
        for s in sections:
            head = numbers.get(s.id) or ""
            head = f"{head}." if s.numbered and head else head
            title = "/".join(x for x in (s.title_ko, s.title_en) if x)
            tag = "  ▶고객" if s.to_customer() else ""
            self.sec_list.insert(
                "end", f"{head} {title}   〔{KIND_LABELS.get(s.kind, s.kind)}〕{tag}")
        if sections:
            idx = 0 if keep is None else max(0, min(int(keep), len(sections) - 1))
            self.sec_list.selection_clear(0, "end")
            self.sec_list.selection_set(idx)
            self.sec_list.see(idx)
            self.show_section(sections[idx])
        else:
            self._current = None
            self._clear_body()

    def _on_select_section(self, _e=None) -> None:
        sel = self.sec_list.curselection()
        if not sel:
            return
        section = self._sections()[sel[0]]
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
        self.plate_vars = {}

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
        sfg.set("audience", AUDIENCE_LABELS.get(section.audience, AUDIENCE_LABELS[AUD_INTERNAL]))

        self._clear_body()
        if section.kind == KIND_SPEC_TABLE:
            self._pane_spec(section)
        elif section.kind == KIND_TABLE:
            self._pane_table(section)
        elif section.kind == KIND_NAMEPLATE:
            self._pane_nameplate(section)
        elif section.kind == KIND_VERSION_TABLE:
            self._pane_version(section)
        elif section.kind == KIND_IMAGE:
            self._pane_image(section)
        else:
            self._pane_text(section)
        self._current = section
        self._refresh_tab_counts()

    # ── 항목 종류별 편집 화면 ────────────────────────────────
    # 표 / 도면 / 설명글을 탭으로 나눠 각각 넉넉한 높이를 갖게 한다.
    def _changed(self):
        return lambda: self._commit_current(mark=True)

    def _notebook(self) -> ttk.Notebook:
        nb = ttk.Notebook(self.body_area)
        nb.pack(fill="both", expand=True, padx=4, pady=4)
        self.body_nb = nb
        self._tab_counts = {}       # {탭 index: (기본 라벨, 개수를 세는 함수)}
        return nb

    def _tab(self, nb: ttk.Notebook, label: str, hint: str = "", counter=None) -> ttk.Frame:
        page = ttk.Frame(nb)
        nb.add(page, text=f"  {label}  ")
        if counter is not None:
            self._tab_counts[len(nb.tabs()) - 1] = (label, counter)
        if hint:
            ttk.Label(page, text=hint, foreground="#555", justify="left").pack(
                anchor="w", padx=8, pady=(6, 0))
        return page

    def _refresh_tab_counts(self) -> None:
        """탭 이름에 담긴 개수를 갱신 — 도면이 붙어 있는지 한눈에 보이도록."""
        nb = getattr(self, "body_nb", None)
        if nb is None or not getattr(self, "_tab_counts", None):
            return
        try:
            tabs = nb.tabs()
        except tk.TclError:
            return
        for idx, (label, counter) in self._tab_counts.items():
            if idx >= len(tabs):
                continue
            n = counter()
            nb.tab(tabs[idx], text=f"  {label} ({n})  " if n else f"  {label}  ")

    def _blocks_grid(self, page, section: Section, main: bool) -> GridEditor:
        g = GridEditor(page, columns=[("indent", "들여쓰기", 70), ("marker", "머리기호", 80),
                                      ("ko", "내용", 520), ("en", "영문(선택)", 300)],
                       multiline=("ko", "en"), on_change=self._changed(),
                       tree_height=10 if main else 5,
                       panel_text_height=3 if main else 2)
        g.pack(fill="both", expand=True, padx=8, pady=8)
        g.set_rows([{"indent": str(b.indent), "marker": b.marker, "ko": b.ko, "en": b.en}
                    for b in section.blocks])
        return g

    def _image_grid(self, page, section: Section, main: bool) -> GridEditor:
        g = GridEditor(page, columns=[("path", "파일", 330), ("width_mm", "폭(mm)", 80),
                                      ("rotate", "회전", 60), ("align", "정렬", 70),
                                      ("caption_ko", "도면 설명", 240),
                                      ("caption_en", "설명(영문·선택)", 160)],
                       multiline=("caption_ko", "caption_en"), on_change=self._changed(),
                       extra_buttons=(("＋ 도면 파일 추가...", self._add_image_file),),
                       tree_height=10 if main else 5,
                       panel_text_height=2)
        g.pack(fill="both", expand=True, padx=8, pady=8)
        g.set_rows([{"path": i.path, "width_mm": str(i.width_mm), "rotate": str(i.rotate),
                     "align": i.align, "caption_ko": i.caption_ko,
                     "caption_en": i.caption_en}
                    for i in section.images])
        return g

    IMG_HINT = ("[＋ 도면 파일 추가...] 로 PNG / JPG / PDF 를 고르세요 (PDF 는 첫 페이지 사용).\n"
                "폭(mm) : 0 = 지면에 맞춰 최대 크기 (권장).  숫자를 넣으면 그 폭으로 고정 (최대 170).\n"
                "회전 : 가로로 긴 도면은 90 을 넣으면 세로 지면에 두 배 가까이 크게 들어갑니다.")
    BLK_HINT = ("한 줄에 한 문장씩 적습니다. 영문 칸은 비워 두어도 됩니다. "
                "들여쓰기 0~3 단계, 머리기호는 (1) ① · 등을 그대로 넣으세요.")

    def _pane_text(self, section: Section) -> None:
        nb = self._notebook()
        self.blocks_editor = self._blocks_grid(self._tab(nb, "본문", self.BLK_HINT), section, True)
        self.image_editor = self._image_grid(self._tab(nb, "첨부 도면", self.IMG_HINT,
                                                counter=lambda: len(self.image_editor.get_rows()) if self.image_editor else 0), section, False)

    def _pane_spec(self, section: Section) -> None:
        nb = self._notebook()
        page = self._tab(nb, "사양표",
                         "엑셀에서 [항목 / 항목(영문) / 사양 / 비고] 4열을 복사한 뒤 "
                         "[엑셀에서 붙여넣기] 를 누르면 한 번에 채워집니다.\n"
                         "‘공개’ 칸은 이 항목이 고객용일 때만 뜻이 있습니다 — "
                         "고객에게 감출 줄만 ‘생산용만’ 으로 바꾸세요.")
        g = GridEditor(page, columns=[("item_ko", "항목", 175),
                                      ("item_en", "항목(영문·선택)", 140),
                                      ("spec", "사양", 300), ("remark", "비고", 210),
                                      ("audience", "공개", 70)],
                       multiline=("spec", "remark"), on_change=self._changed(),
                       tree_height=11, panel_text_height=3)
        g.pack(fill="both", expand=True, padx=8, pady=8)
        g.set_rows([{"item_ko": r.item_ko, "item_en": r.item_en, "spec": r.spec,
                     "remark": r.remark,
                     "audience": AUDIENCE_LABELS.get(r.audience, AUDIENCE_LABELS[AUD_BOTH])}
                    for r in section.rows])
        self.rows_editor = g
        self.image_editor = self._image_grid(self._tab(nb, "첨부 도면", self.IMG_HINT,
                                                counter=lambda: len(self.image_editor.get_rows()) if self.image_editor else 0), section, False)
        self.blocks_editor = self._blocks_grid(
            self._tab(nb, "표 위 설명글", self.BLK_HINT), section, False)

    def _pane_table(self, section: Section) -> None:
        """자유 표 — 열 이름과 열 수를 직접 정한다 (자재 리스트 등)."""
        nb = self._notebook()
        page = self._tab(nb, "표",
                         "열 이름을  |  로 나눠 적고 [열 적용] 을 누르면 표의 열이 바뀝니다.\n"
                         "열 너비는 비워 두면 고르게 나눕니다 (본문 폭 170mm 기준).")
        head = ttk.Frame(page)
        head.pack(fill="x", padx=8, pady=(4, 0))
        ttk.Label(head, text="열 이름").grid(row=0, column=0, sticky="e", padx=(0, 4))
        self.grid_headers_var = tk.StringVar(value=" | ".join(section.headers or ["No.", "항목", "내용"]))
        ttk.Entry(head, textvariable=self.grid_headers_var).grid(row=0, column=1, sticky="ew", pady=2)
        ttk.Label(head, text="열 너비(mm)").grid(row=1, column=0, sticky="e", padx=(0, 4))
        self.grid_widths_var = tk.StringVar(
            value=" | ".join(str(w) for w in section.col_widths_mm))
        ttk.Entry(head, textvariable=self.grid_widths_var).grid(row=1, column=1, sticky="ew", pady=2)
        ttk.Button(head, text="열 적용", command=self._apply_grid_headers).grid(
            row=0, column=2, rowspan=2, padx=6)
        head.columnconfigure(1, weight=1)

        headers = section.headers or ["No.", "항목", "내용"]
        cols = [(f"c{i}", h, 150) for i, h in enumerate(headers)]
        cols.append(("audience", "공개", 70))
        g = GridEditor(page, columns=cols,
                       multiline=tuple(f"c{i}" for i in range(len(headers))),
                       on_change=self._changed(), tree_height=11, panel_text_height=2)
        g.pack(fill="both", expand=True, padx=8, pady=8)
        g.set_rows([{**{f"c{i}": r.cell(i) for i in range(len(headers))},
                     "audience": AUDIENCE_LABELS.get(r.audience, AUDIENCE_LABELS[AUD_BOTH])}
                    for r in section.grid])
        self.rows_editor = g
        self._grid_cols = len(headers)

        self.image_editor = self._image_grid(
            self._tab(nb, "첨부 도면", self.IMG_HINT,
                      counter=lambda: len(self.image_editor.get_rows()) if self.image_editor else 0),
            section, False)
        self.blocks_editor = self._blocks_grid(
            self._tab(nb, "표 위 설명글", self.BLK_HINT), section, False)

    NAMEPLATE_KEYS = [
        ("width_mm", "문서에 넣을 폭(mm)", 115.0),
        ("aspect", "가로/세로 비", 1.93),
        ("x", "글자 시작 X (%)", 8.0),
        ("y", "글자 시작 Y (%)", 24.0),
        ("line", "줄 간격 (%)", 9.0),
        ("size", "글자 크기 (%)", 6.5),
        ("label_w", "라벨 칸 너비 (%)", 40.0),
    ]

    def _pane_nameplate(self, section: Section) -> None:
        """명판 — 값을 적으면 명판 도안 위에 찍힌다."""
        nb = self._notebook()
        page = self._tab(nb, "명판 내용",
                         "라벨을 비우면 제목 줄이 됩니다. 크기배율 1.5 처럼 적으면 그 줄만 커집니다.\n"
                         "{제품명} {도번} {리비전} 같은 자동 입력 항목도 쓸 수 있습니다.")
        g = GridEditor(page, columns=[("c0", "라벨 / Label", 200),
                                      ("c1", "값 / Value", 380),
                                      ("c2", "크기배율", 80),
                                      ("audience", "공개", 70)],
                       multiline=("c1",), on_change=self._changed(),
                       tree_height=10, panel_text_height=2)
        g.pack(fill="both", expand=True, padx=8, pady=8)
        g.set_rows([{"c0": r.cell(0), "c1": r.cell(1), "c2": r.cell(2) or "1.0",
                     "audience": AUDIENCE_LABELS.get(r.audience, AUDIENCE_LABELS[AUD_BOTH])}
                    for r in section.grid])
        self.rows_editor = g
        self._grid_cols = 3

        lay = self._tab(nb, "배치",
                        "명판 안에서 글자가 놓이는 자리입니다. 값은 명판 크기에 대한 % 입니다.\n"
                        "줄이 많아 넘치면 글자 크기를 자동으로 줄여 맞춥니다.")
        box = ttk.Frame(lay)
        box.pack(fill="x", padx=12, pady=10)
        self.plate_vars = {}
        for row, (key, label, default) in enumerate(self.NAMEPLATE_KEYS):
            ttk.Label(box, text=label, width=22).grid(row=row, column=0, sticky="e", pady=3)
            var = tk.StringVar(value=str(section.layout.get(key, default)))
            ttk.Entry(box, textvariable=var, width=12).grid(row=row, column=1, sticky="w", padx=6)
            var.trace_add("write", lambda *a: self._commit_current(mark=True))
            self.plate_vars[key] = var
        ttk.Label(lay, foreground="#666", justify="left",
                  text="바탕 그림(명판 도안)을 [첨부 도면] 에 넣으면 그 위에 값만 찍힙니다.\n"
                       "넣지 않으면 테두리 + 로고 + 제조사 표기를 그려 기본 명판을 만듭니다.").pack(
            anchor="w", padx=12)

        self.image_editor = self._image_grid(
            self._tab(nb, "첨부 도면", "명판 도안(바탕 그림)을 여기에 넣으세요.",
                      counter=lambda: len(self.image_editor.get_rows()) if self.image_editor else 0),
            section, False)
        self.blocks_editor = self._blocks_grid(
            self._tab(nb, "설명글", self.BLK_HINT), section, False)

    def _apply_grid_headers(self) -> None:
        """열 이름·너비를 바꾸고 표 편집기를 다시 그린다."""
        section = self._current
        if section is None:
            return
        headers = [h.strip() for h in self.grid_headers_var.get().split("|")]
        headers = [h for h in headers if h] or ["항목"]
        widths: list = []
        for part in self.grid_widths_var.get().split("|"):
            part = part.strip()
            if part:
                widths.append(_float(part, 0.0))
        if len(widths) != len(headers):
            widths = []            # 개수가 안 맞으면 고르게 나눈다

        self._commit_current()
        section.headers = headers
        section.col_widths_mm = widths
        for row in section.grid:   # 열 수가 바뀌면 칸 수를 맞춰 준다
            cells = list(row.cells)[:len(headers)]
            cells += [""] * (len(headers) - len(cells))
            row.cells = cells
        self.mark_dirty()
        self.show_section(section)

    def _pane_image(self, section: Section) -> None:
        nb = self._notebook()
        self.image_editor = self._image_grid(self._tab(nb, "도면", self.IMG_HINT,
                                               counter=lambda: len(self.image_editor.get_rows()) if self.image_editor else 0), section, True)
        self.blocks_editor = self._blocks_grid(
            self._tab(nb, "도면 위 설명글", self.BLK_HINT), section, False)

    def _pane_version(self, section: Section) -> None:
        top = ttk.Frame(self.body_area)
        top.pack(fill="x", padx=6, pady=(6, 0))
        self.extra_fields = FieldGrid(top, columns=1)
        self.extra_fields.pack(fill="x")
        self.extra_fields.add("part_no", "파트번호 표기 (◇ 파트번호 : ○○)", 20)
        self.extra_fields.set("part_no", section.part_no)
        self.extra_fields.vars["part_no"].trace_add(
            "write", lambda *a: self._commit_current(mark=True))

        nb = self._notebook()
        page = self._tab(nb, "개정 이력",
                         "기본정보 탭의 [▲ 리비전 올리기] 를 쓰면 이 표에 자동으로 한 줄이 기록됩니다.")
        g = GridEditor(page, columns=[("rev", "리비전", 70), ("author", "작성자", 90),
                                      ("date", "발행일", 110),
                                      ("changed_ko", "변경 내용", 420),
                                      ("changed_en", "변경 내용(영문·선택)", 240)],
                       multiline=("changed_ko", "changed_en"), on_change=self._changed(),
                       tree_height=11, panel_text_height=3)
        g.pack(fill="both", expand=True, padx=8, pady=8)
        g.set_rows([{"rev": r.rev, "author": r.author, "date": r.date,
                     "changed_ko": r.changed_ko, "changed_en": r.changed_en}
                    for r in section.versions])
        self.rows_editor = g
        self.blocks_editor = self._blocks_grid(
            self._tab(nb, "표 위 설명글", self.BLK_HINT), section, False)

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
            rows.append({"path": rel, "width_mm": "0", "rotate": "0", "align": "CENTER",
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
        s.audience = next((k for k, v in AUDIENCE_LABELS.items() if v == sfg.get("audience")),
                          AUD_INTERNAL)

        if self.blocks_editor is not None:
            s.blocks = _blocks_from(self.blocks_editor.get_rows())
        if self.image_editor is not None:
            s.images = [ImageItem(r.get("path", ""), _float(r.get("width_mm"), 0.0),
                                  90 if str(r.get("rotate", "")).strip() == "90" else 0,
                                  r.get("caption_ko", ""), r.get("caption_en", ""),
                                  (r.get("align") or "CENTER").upper())
                        for r in self.image_editor.get_rows() if r.get("path")]
        if self.rows_editor is not None:
            rows = self.rows_editor.get_rows()
            if s.kind in (KIND_TABLE, KIND_NAMEPLATE):
                n = getattr(self, "_grid_cols", len(s.headers) or 1)
                s.grid = [GridRow([r.get(f"c{i}", "") for i in range(n)],
                                  next((k for k, v in AUDIENCE_LABELS.items()
                                        if v == r.get("audience")), AUD_BOTH))
                          for r in rows]
            elif s.kind == KIND_SPEC_TABLE:
                s.rows = [SpecRow(r.get("item_ko", ""), r.get("item_en", ""),
                                  r.get("spec", ""), r.get("remark", ""),
                                  next((k for k, v in AUDIENCE_LABELS.items()
                                        if v == r.get("audience")), AUD_BOTH))
                          for r in rows]
            elif s.kind == KIND_VERSION_TABLE:
                s.versions = [VersionRow(r.get("rev", ""), r.get("author", ""),
                                         r.get("date", ""), r.get("changed_ko", ""),
                                         r.get("changed_en", "")) for r in rows]
                if self.extra_fields:
                    s.part_no = self.extra_fields.get("part_no")
        if s.kind == KIND_NAMEPLATE and getattr(self, "plate_vars", None):
            layout = {}
            for key, _, default in self.NAMEPLATE_KEYS:
                layout[key] = _float(self.plate_vars[key].get(), default)
            s.layout = layout
        if mark:
            self.mark_dirty()
            self._refresh_list_labels()
            self._refresh_tab_counts()

    def _refresh_list_labels(self) -> None:
        sel = self.sec_list.curselection()
        idx = sel[0] if sel else None
        sections = self._sections()
        numbers = self.doc.assign_numbers(sections)
        for i, s in enumerate(sections):
            head = numbers.get(s.id) or ""
            head = f"{head}." if s.numbered and head else head
            title = "/".join(x for x in (s.title_ko, s.title_en) if x)
            tag = "  ▶고객" if s.to_customer() else ""
            label = f"{head} {title}   〔{KIND_LABELS.get(s.kind, s.kind)}〕{tag}"
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
        pos = (sel[0] + 1) if sel else len(self._sections())
        section = Section(kind=kind, title_ko="새 항목")
        if kind == KIND_TEXT:
            section.blocks = [Block(indent=1)]
        elif kind == KIND_SPEC_TABLE:
            section.rows = [SpecRow()]
        elif kind == KIND_TABLE:
            section.headers = ["No.", "품명 / Name", "사양 / Specifications"]
            section.col_widths_mm = [14.0, 56.0, 100.0]
            section.grid = [GridRow(["1", "", ""])]
        elif kind == KIND_NAMEPLATE:
            section.headers = ["라벨 / Label", "값 / Value", "크기배율"]
            section.layout = {k: v for k, _, v in App.NAMEPLATE_KEYS}
            section.grid = [GridRow(["", "제품명", "1.5"]), GridRow(["Model", "", "1.0"])]
        elif kind == KIND_VERSION_TABLE:
            section.versions = [VersionRow()]
        self._sections().insert(pos, section)
        self.refresh_section_list(select=pos)
        self.mark_dirty()

    def duplicate_section(self) -> None:
        self._commit_current()
        sel = self.sec_list.curselection()
        if not sel:
            return
        import copy
        s = copy.deepcopy(self._sections()[sel[0]])
        s.id = os.urandom(4).hex()
        self._sections().insert(sel[0] + 1, s)
        self.refresh_section_list(select=sel[0] + 1)
        self.mark_dirty()

    def delete_section(self) -> None:
        sel = self.sec_list.curselection()
        if not sel:
            return
        if not messagebox.askyesno("확인", "선택한 항목을 삭제할까요?"):
            return
        self._current = None
        del self._sections()[sel[0]]
        self.refresh_section_list(select=max(0, sel[0] - 1))
        self.mark_dirty()

    def move_section(self, delta: int) -> None:
        self._commit_current()
        sel = self.sec_list.curselection()
        if not sel:
            return
        sections = self._sections()
        i, j = sel[0], sel[0] + delta
        if not (0 <= j < len(sections)):
            return
        sections[i], sections[j] = sections[j], sections[i]
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
        doc.template = "reactor"
        if not doc.approval_sections:
            doc.approval_sections = approval_mod.default_boilerplate()
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
        newer = file_is_newer(path)
        if newer:
            messagebox.showwarning(
                "새 버전에서 만든 문서",
                "이 문서는 지금 쓰는 것보다 새 버전의 프로그램에서 만들어졌습니다.\n"
                "열어는 보겠지만 일부 내용이 빠질 수 있습니다.\n"
                "가능하면 프로그램을 최신판으로 바꿔 주세요.")
        try:
            self.load_doc(SpecDoc.load(path))
            self.remember_recent(path)
            self.set_status(f"열었습니다: {path}")
        except Exception as exc:
            messagebox.showerror("열기 실패", f"{exc}")
            return
        self.after(150, self.check_template_updates)

    def save(self) -> bool:
        if not self.doc.source_path:
            return self.save_as()
        return self._write(self.doc.source_path)

    def save_as(self) -> bool:
        self._commit_current()
        self.collect_meta()
        folder = self.customer_dir()
        try:
            os.makedirs(folder, exist_ok=True)
        except OSError:
            folder = self.output_root()
        path = filedialog.asksaveasfilename(title="다른 이름으로 저장", defaultextension=".spec.json",
                                            initialdir=folder,
                                            initialfile=self.output_basename() + ".spec.json",
                                            filetypes=FILETYPES)
        return self._write(path) if path else False

    def remember_recent(self, path: str) -> None:
        recent = [p for p in self.settings.get("recent", []) if p != path]
        recent.insert(0, path)
        self.settings["recent"] = recent[:12]
        save_settings(self.settings)
        self._rebuild_recent_menu()

    def _rebuild_recent_menu(self) -> None:
        menu = self.recent_menu
        menu.delete(0, "end")
        recent = [p for p in self.settings.get("recent", []) if os.path.exists(p)]
        if not recent:
            menu.add_command(label="(최근에 연 문서가 없습니다)", state="disabled")
            return
        for path in recent:
            label = f"{os.path.basename(path)}   —   {os.path.dirname(path)}"
            menu.add_command(label=label, command=lambda p=path: self._open_recent(p))
        menu.add_separator()
        menu.add_command(label="목록 지우기", command=self._clear_recent)

    def _open_recent(self, path: str) -> None:
        if self._confirm_discard():
            self.open_path(path)

    def _clear_recent(self) -> None:
        self.settings["recent"] = []
        save_settings(self.settings)
        self._rebuild_recent_menu()

    def _write(self, path: str) -> bool:
        self._commit_current()
        self.collect_meta()
        try:
            self.doc.save(path)
        except OSError as exc:
            messagebox.showerror("저장 실패", f"{exc}")
            return False
        self.mark_dirty(False)
        self.register_current()
        self.remember_recent(path)
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
    # ── 저장 위치 · 파일 이름 ────────────────────────────────
    def output_root(self) -> str:
        return self.settings.get("output_root") or os.path.join(
            os.path.expanduser("~"), "Documents", "Braumm 사양서")

    def customer_dir(self) -> str:
        """{출력 폴더}/{고객사} — 고객사가 비면 출력 폴더 그대로."""
        m = self.doc.meta
        customer = m.customer or m.customer_en
        root = self.output_root()
        return os.path.join(root, safe_name(customer)) if customer else root

    def approval_basename(self) -> str:
        return self.output_basename() + "_APPROVAL"

    def output_basename(self) -> str:
        m = self.doc.meta
        doc_no = f"{m.dwg_prefix}-{m.dwg_no}" if m.dwg_prefix and m.dwg_no else (m.dwg_no or "사양서")
        pattern = self.settings.get("filename_pattern") or DEFAULT_PATTERN
        name = (pattern
                .replace("{도번}", doc_no)
                .replace("{리비전}", m.revision or "A")
                .replace("{날짜}", _dt.date.today().strftime("%Y%m%d"))
                .replace("{발행일}", (m.revision_date or "").replace("-", ""))
                .replace("{고객사}", m.customer or m.customer_en)
                .replace("{제품명}", m.product_name))
        return safe_name(name)

    def set_output_root(self) -> None:
        path = filedialog.askdirectory(title="사양서를 모아 둘 폴더를 고르세요",
                                       initialdir=self.output_root())
        if not path:
            return
        self.settings["output_root"] = path
        save_settings(self.settings)
        self.set_status(f"출력 폴더: {path}   (고객사별 하위 폴더가 자동으로 만들어집니다)")

    def set_filename_pattern(self) -> None:
        dlg = MultilineDialog(
            self, "PDF 파일 이름 규칙",
            self.settings.get("filename_pattern") or DEFAULT_PATTERN)
        if dlg.result is None:
            return
        self.settings["filename_pattern"] = dlg.result.strip().splitlines()[0] if dlg.result.strip() else DEFAULT_PATTERN
        save_settings(self.settings)
        self.set_status(f"파일 이름 예시: {self.output_basename()}.pdf")

    def export_to_customer_folder(self) -> None:
        """고객사 폴더에 곧바로 저장한다(파일 이름 자동)."""
        self._commit_current()
        self.collect_meta()
        if not self.doc.meta.dwg_no:
            if messagebox.askyesno("도번 없음",
                                   "아직 도번이 없습니다.\n지금 자동으로 발급할까요?"):
                self.generate_doc_no()
                self.collect_meta()
        folder = self.customer_dir()
        try:
            os.makedirs(folder, exist_ok=True)
        except OSError as exc:
            messagebox.showerror("폴더 생성 실패", f"{folder}\n{exc}")
            return
        path = os.path.join(folder, self.output_basename() + ".pdf")
        appr_path = os.path.join(folder, self.approval_basename() + ".pdf")
        also_approval = bool(self.settings.get("make_approval", True))

        exists = [p for p in ([path] + ([appr_path] if also_approval else []))
                  if os.path.exists(p)]
        if exists and not messagebox.askyesno(
                "덮어쓰기", "같은 이름의 파일이 이미 있습니다.\n\n"
                + "\n".join(os.path.basename(p) for p in exists) + "\n\n덮어쓸까요?"):
            return

        made = self._make_pdf(path, approval_path=appr_path if also_approval else None)
        if not made:
            return
        self.register_current()
        names = "\n".join(os.path.basename(p) for p in made)
        self.set_status(f"저장했습니다: {folder}  ({len(made)}개 파일)")
        if messagebox.askyesno("완료", f"저장했습니다.\n\n{folder}\n{names}\n\n폴더를 열어볼까요?"):
            open_with_os(folder)

    def _make_pdf(self, out_path: str, approval_path: Optional[str] = None):
        """생산 사양서를, approval_path 가 있으면 고객 승인 사양서까지 만든다."""
        self._commit_current()
        self.collect_meta()
        font = self.settings.get("font_path")
        try:
            self.set_status("PDF 생성 중...")
            if approval_path:
                made = list(build_both(self.doc, out_path, approval_path, font))
            else:
                made = [build_pdf(self.doc, out_path, font)]
            self.set_status(f"PDF 생성 완료 ({len(made)}개)  (폰트: {active_font_description()})")
            return made if approval_path else made[0]
        except Exception as exc:
            traceback.print_exc()
            messagebox.showerror("PDF 생성 실패", f"{exc}\n\n자세한 내용은 콘솔을 확인하세요.")
            self.set_status("PDF 생성 실패")
            return None

    def preview_approval(self) -> None:
        """고객 승인 사양서만 따로 미리보기."""
        self._commit_current()
        self.collect_meta()
        if not approval_mod.customer_sections(self.doc):
            messagebox.showinfo(
                "고객 승인 사양서",
                "고객에게 나갈 항목이 하나도 없습니다.\n\n"
                "‘② 문서 구성’ 에서 항목을 고른 뒤 [공개 범위] 를\n"
                "‘생산 + 고객’ 으로 바꿔 주세요.\n\n"
                "기본값은 ‘생산용만’ 이라 표시하지 않은 항목은 나가지 않습니다.")
            return
        if not getattr(self, "_preview_dir", None):
            self._preview_dir = tempfile.mkdtemp(prefix="specgen_preview_")
        tmp = os.path.join(self._preview_dir,
                           f"승인사양서_{safe_name(self.doc.meta.dwg_no or 'spec')}.pdf")
        try:
            build_approval_pdf(approval_mod.build_doc(self.doc), tmp,
                               self.settings.get("font_path"), source=self.doc)
        except Exception as exc:
            traceback.print_exc()
            messagebox.showerror("승인 사양서 생성 실패", f"{exc}")
            return
        open_with_os(tmp)
        self.set_status(f"고객 승인 사양서 미리보기: {tmp}")

    def show_customer_scope(self) -> None:
        self._commit_current()
        self.collect_meta()
        messagebox.showinfo("고객에게 나가는 내용", approval_mod.summary(self.doc))

    def toggle_approval_output(self) -> None:
        self.settings["make_approval"] = bool(self.approval_var.get())
        save_settings(self.settings)

    def preview(self) -> None:
        # 공용 임시 폴더에 예측 가능한 이름으로 쓰지 않도록, 이 실행 전용 폴더를 쓴다
        if not getattr(self, "_preview_dir", None):
            self._preview_dir = tempfile.mkdtemp(prefix="specgen_preview_")
        tmp = os.path.join(self._preview_dir,
                           f"미리보기_{safe_name(self.doc.meta.dwg_no or 'spec')}.pdf")
        if self._make_pdf(tmp):
            open_with_os(tmp)

    def export(self) -> None:
        self._commit_current()
        self.collect_meta()
        folder = self.customer_dir()
        os.makedirs(folder, exist_ok=True)
        path = filedialog.asksaveasfilename(title="PDF로 내보내기", defaultextension=".pdf",
                                            initialdir=folder,
                                            initialfile=self.output_basename() + ".pdf",
                                            filetypes=[("PDF", "*.pdf")])
        if not path:
            return
        appr = None
        if self.settings.get("make_approval", True) and approval_mod.customer_sections(self.doc):
            stem = os.path.splitext(path)[0]
            appr = stem + "_APPROVAL.pdf"
        made = self._make_pdf(path, approval_path=appr)
        if made and messagebox.askyesno(
                "완료", "저장했습니다.\n\n"
                + "\n".join(os.path.basename(p) for p in (made if appr else [made]))
                + "\n\n생산 사양서를 지금 열어볼까요?"):
            open_with_os(path)

    # ── 도구 ────────────────────────────────────────────────
    def registry(self) -> Registry:
        return Registry(self.output_root())

    def generate_doc_no(self) -> None:
        """도번 대장을 보고 다음 번호를 자동으로 발급한다."""
        self.collect_meta()
        m = self.doc.meta
        if not m.customer_en.strip():
            messagebox.showinfo(
                "도번 발급",
                "고객사(영문)를 먼저 입력해 주세요.\n\n"
                "고객코드는 영문명에서 자동으로 만들어집니다.\n"
                "  Hyundai Electric → HYU      LS Electric → LSE\n"
                "이미 쓰던 고객이면 예전에 준 코드를 그대로 씁니다.")
            return
        if m.dwg_no and not messagebox.askyesno(
                "도번 발급",
                f"이미 도번이 있습니다.\n\n    {m.dwg_prefix}-{m.dwg_no}\n\n"
                "새 번호를 발급할까요?\n"
                "(설계 변경이라면 새 번호가 아니라 [▲ 리비전 올리기] 를 쓰세요)"):
            return

        reg = self.registry()
        number = reg.issue(m.family, m.customer_en, m.customer,
                           m.rated_current, m.product_name)
        if not reg.save():
            messagebox.showwarning(
                "도번 대장",
                f"번호는 만들었지만 대장을 저장하지 못했습니다.\n\n{reg.path}\n\n"
                "출력 폴더에 쓸 수 있는지 확인해 주세요. "
                "대장이 저장되지 않으면 다음에 같은 번호가 또 나올 수 있습니다.")
        prefix, rest = dn.split(number)
        self.no_fields.set("dwg_no", rest)
        self.meta_fields.set("dwg_prefix", prefix)
        code = rest.split("-")[1] if "-" in rest else ""
        if not self.rev_var.get().strip():
            self.rev_var.set("A")
        if not self.rev_date_var.get().strip():
            self.rev_date_var.set(_dt.date.today().isoformat())
        self.mark_dirty()
        self.set_status(f"도번 발급: {number}   (고객코드 {code}, 대장 {reg.count()}건)")

    def show_registry(self) -> None:
        RegistryWindow(self, self.registry())

    def register_current(self) -> None:
        """저장·출력할 때 대장에 현재 문서 정보를 갱신해 둔다."""
        m = self.doc.meta
        if not m.dwg_no:
            return
        reg = self.registry()
        number = f"{m.dwg_prefix}-{m.dwg_no}" if m.dwg_prefix else m.dwg_no
        reg.record(number, family=m.family, customer=m.customer, customer_en=m.customer_en,
                   rated_current=m.rated_current, product=m.product_name,
                   revision=m.revision, file=self.doc.source_path)
        if m.customer_en:
            reg.customer_code(m.customer_en, m.customer)
        reg.save()

    def bump_revision(self) -> None:
        """리비전을 한 단계 올리고 개정 이력에 한 줄 남긴다."""
        self._commit_current()
        self.collect_meta()
        current = self.doc.meta.revision or "A"
        nxt = dn.next_revision(current)
        dlg = MultilineDialog(self, f"Rev.{current} → Rev.{nxt}  변경 내용을 적어 주세요", "")
        if dlg.result is None:
            return
        note = dlg.result.strip()
        if not note:
            messagebox.showinfo("리비전", "변경 내용을 적어야 이력에 남길 수 있습니다.")
            return
        today = _dt.date.today().isoformat()
        self.rev_var.set(nxt)
        self.rev_date_var.set(today)

        author = self.doc.meta.drawn.name or self.doc.meta.checked.name or ""
        target = next((s for s in self.doc.sections if s.kind == KIND_VERSION_TABLE), None)
        if target is None:
            target = Section(kind=KIND_VERSION_TABLE, title_ko="개정 이력",
                             page_break_before=True)
            self.doc.sections.append(target)
        # 비어 있는 줄이 있으면 거기에, 없으면 새 줄로
        row = VersionRow(nxt, author, today, note, "")
        empty = next((i for i, r in enumerate(target.versions)
                      if not (r.rev or r.date or r.changed_ko)), None)
        if empty is None:
            target.versions.append(row)
        else:
            target.versions[empty] = row
        self.collect_meta()
        self._current = None
        self.refresh_section_list()
        self.mark_dirty()
        self.set_status(f"Rev.{current} → Rev.{nxt} 로 올리고 개정 이력에 기록했습니다.")

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

    def choose_stamp(self, var: tk.StringVar) -> None:
        path = filedialog.askopenfilename(
            title="도장 / 사인 이미지 선택",
            initialdir=self._stamp_dir(),
            filetypes=[("이미지", "*.png *.jpg *.jpeg *.gif *.bmp"), ("모든 파일", "*.*")])
        if path:
            var.set(path)

    @staticmethod
    def _stamp_dir() -> str:
        from ..fonts import bundled_font_dir
        d = os.path.join(os.path.dirname(bundled_font_dir()), "stamps")
        return d if os.path.isdir(d) else os.path.expanduser("~")

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

    def toggle_update_check(self) -> None:
        self.settings["check_updates_on_open"] = bool(self.update_check_var.get())
        save_settings(self.settings)

    def _update_plan(self):
        """지금 문서에 템플릿의 새 항목이 얼마나 빠져 있는지 살펴본다."""
        names = tpl_pkg.template_names()
        if not names:
            return None
        name = self.doc.template if self.doc.template in names else names[0]
        try:
            return updater.plan(self.doc, tpl_pkg.load_template(name))
        except Exception:
            return None

    def check_template_updates(self) -> None:
        """예전에 저장한 문서를 열었을 때, 그 뒤로 생긴 항목을 알려 준다.

        저장된 문서를 열자마자 마음대로 고치지는 않는다. 무엇이 들어오는지
        먼저 보여 주고, 가져올지 말지는 쓰는 사람이 정한다.
        """
        if not self.settings.get("check_updates_on_open", True):
            return
        p = self._update_plan()
        if not p:
            return
        titles = [c.label for c in p.changes if c.kind == updater.ADD_SECTION]
        self.set_status(
            f"새로 생긴 항목 {len(p.changes)}건을 가져올 수 있습니다. "
            "[도구 → 최신 템플릿의 추가 항목 가져오기] 또는 F8")
        lines = ["이 문서를 저장한 뒤에 프로그램에 새로 생긴 항목이 있습니다.",
                 "예전 문서에도 그대로 가져올 수 있습니다.",
                 "",
                 f"가져올 수 있는 것: {updater.summary(p)}"]
        if titles:
            head = ", ".join(titles[:8])
            if len(titles) > 8:
                head += f" 외 {len(titles) - 8}건"
            lines += ["", f"새 항목: {head}"]
        lines += ["",
                  "이미 적어 두신 값은 절대 덮어쓰지 않고, 빠진 것만 더합니다.",
                  "가져온 뒤에는 저장을 눌러야 문서에 남습니다.",
                  "",
                  "지금 가져올까요?"]
        if messagebox.askyesno("새로 생긴 항목이 있습니다", "\n".join(lines)):
            self.pull_template_updates()

    def pull_template_updates(self) -> None:
        """예전에 만든 문서에 템플릿의 새 항목·새 줄을 가져온다."""
        self._commit_current()
        self.collect_meta()
        names = tpl_pkg.template_names()
        if not names:
            messagebox.showinfo("가져오기", "쓸 수 있는 템플릿이 없습니다.")
            return
        win = UpdateWindow(self, self.doc, names, tpl_pkg.load_template,
                           updater.plan, updater.apply,
                           current_template=self.doc.template or names[0])
        if win.applied:
            self._current = None
            self.refresh_section_list()
            self.mark_dirty()
            self.set_status(f"템플릿에서 {win.applied}건을 가져왔습니다. 확인 후 저장하세요.")
        else:
            self.set_status("가져온 항목이 없습니다.")

    def show_placeholders(self) -> None:
        messagebox.showinfo(
            "자동 입력 항목",
            "표나 본문에 아래처럼 적어 두면, PDF 를 만들 때 "
            "① 기본정보에 입력한 값으로 자동으로 바뀝니다.\n"
            "표준 템플릿의 '기본 사양' 표에는 이미 들어가 있습니다.\n\n"
            + ph.help_lines())

    def show_about(self) -> None:
        messagebox.showinfo(
            "프로그램 정보",
            f"Braumm 사양서 생성기\n\n"
            f"판 번호 : v{__version__}\n"
            f"PDF 폰트 : {active_font_description()}\n"
            f"설정 파일 : {SETTINGS}\n"
            f"출력 폴더 : {self.output_root()}\n\n"
            "무엇이 바뀌었는지는 CHANGELOG.md 를 보세요.")

    def show_help(self) -> None:
        HelpWindow(self)

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
