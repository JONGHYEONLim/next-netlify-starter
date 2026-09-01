# -*- coding: utf-8 -*-
"""GUI 공용 위젯: 표 편집기, 여러 줄 입력 대화상자."""
from __future__ import annotations

import os
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable, Dict, List, Optional, Sequence, Tuple

NL_MARK = " ⏎ "


def flat(text: str) -> str:
    """표에 한 줄로 보여주기 위해 줄바꿈을 기호로 바꾼다."""
    return (text or "").replace("\n", NL_MARK)


class MultilineDialog(tk.Toplevel):
    """셀 하나를 여러 줄로 편집하는 창."""

    def __init__(self, master, title: str, value: str):
        super().__init__(master)
        self.title(title)
        self.transient(master)
        self.result: Optional[str] = None
        self.geometry("640x320")

        self.text = tk.Text(self, wrap="word", undo=True)
        self.text.insert("1.0", value or "")
        self.text.pack(fill="both", expand=True, padx=8, pady=(8, 4))
        self.text.focus_set()

        bar = ttk.Frame(self)
        bar.pack(fill="x", padx=8, pady=(0, 8))
        ttk.Label(bar, text="Ctrl+Enter 로 확인").pack(side="left")
        ttk.Button(bar, text="취소", command=self.destroy).pack(side="right")
        ttk.Button(bar, text="확인", command=self._ok).pack(side="right", padx=4)
        self.bind("<Control-Return>", lambda e: self._ok())
        self.bind("<Escape>", lambda e: self.destroy())
        self.grab_set()
        self.wait_window(self)

    def _ok(self):
        self.result = self.text.get("1.0", "end-1c")
        self.destroy()


class GridEditor(ttk.Frame):
    """표 편집기.

    위쪽은 전체를 훑어보는 목록, 아래쪽은 **선택한 행을 입력하는 칸**이다.
    목록에서 행을 클릭하면 아래 입력칸에 값이 뜨고, 거기에 타이핑하면 바로 반영된다.
    (목록의 셀을 더블클릭해서 그 자리에서 고치는 것도 된다.)
    """

    def __init__(self, master, columns: Sequence[Tuple[str, str, int]],
                 multiline: Sequence[str] = (),
                 on_change: Optional[Callable[[], None]] = None,
                 extra_buttons: Sequence[Tuple[str, Callable[[], None]]] = (),
                 tree_height: int = 8, panel_text_height: int = 3):
        super().__init__(master)
        self._panel_text_height = panel_text_height
        self.columns = list(columns)          # (key, 표시이름, 너비px)
        self.keys = [c[0] for c in self.columns]
        self.labels = {c[0]: c[1] for c in self.columns}
        self.multiline = set(multiline)
        self.on_change = on_change
        self._rows: List[Dict[str, str]] = []
        self._editor: Optional[tk.Widget] = None
        self._loading = False
        self._panel: Dict[str, tk.Widget] = {}

        bar = ttk.Frame(self)
        bar.pack(fill="x", pady=(0, 4))
        for label, cmd in (("＋ 행 추가", self.add_row), ("▲", lambda: self.move(-1)),
                           ("▼", lambda: self.move(1)), ("행 삭제", self.delete_row)):
            ttk.Button(bar, text=label, width=9 if len(label) > 2 else 4,
                       command=cmd).pack(side="left", padx=2)
        ttk.Separator(bar, orient="vertical").pack(side="left", fill="y", padx=6)
        ttk.Button(bar, text="엑셀에서 붙여넣기", command=self.paste_clipboard).pack(side="left", padx=2)
        ttk.Button(bar, text="전체 비우기", command=self.clear).pack(side="left", padx=2)
        for label, cmd in extra_buttons:
            ttk.Button(bar, text=label, command=cmd).pack(side="left", padx=2)

        wrap = ttk.Frame(self)
        wrap.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(wrap, columns=self.keys, show="headings",
                                 selectmode="browse", height=tree_height)
        for key, label, width in self.columns:
            self.tree.heading(key, text=label)
            self.tree.column(key, width=width, minwidth=40, stretch=True, anchor="w")
        vs = ttk.Scrollbar(wrap, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")

        self.tree.bind("<Double-1>", self._begin_edit)
        self.tree.bind("<<TreeviewSelect>>", self._load_panel)
        self.tree.bind("<Configure>", lambda e: self._cancel_edit())
        self.tree.bind("<MouseWheel>", lambda e: self._cancel_edit(), add="+")

        self._build_panel()

    # ── 선택한 행 입력칸 ─────────────────────────────────────
    def _build_panel(self) -> None:
        box = ttk.LabelFrame(self, text="  ▼ 선택한 행 입력  —  위 목록에서 행을 고른 뒤 여기에 값을 적으세요  ")
        box.pack(fill="x", pady=(6, 0))
        self.panel_box = box

        singles = [k for k in self.keys if k not in self.multiline]
        multis = [k for k in self.keys if k in self.multiline]

        if singles:
            row = ttk.Frame(box)
            row.pack(fill="x", padx=8, pady=(6, 2))
            for key in singles:
                cell = ttk.Frame(row)
                cell.pack(side="left", fill="x", expand=True, padx=(0, 10))
                ttk.Label(cell, text=self.labels[key]).pack(anchor="w")
                var = tk.StringVar()
                ent = ttk.Entry(cell, textvariable=var)
                ent.pack(fill="x")
                var.trace_add("write", lambda *a, k=key: self._panel_changed(k))
                self._panel[key] = ent
                setattr(ent, "_var", var)

        for key in multis:
            cell = ttk.Frame(box)
            cell.pack(fill="x", padx=8, pady=(2, 2))
            ttk.Label(cell, text=f"{self.labels[key]}   (Enter 로 줄바꿈)").pack(anchor="w")
            txt = tk.Text(cell, height=self._panel_text_height, wrap="word", undo=True)
            txt.pack(fill="x")
            txt.bind("<KeyRelease>", lambda e, k=key: self._panel_changed(k))
            txt.bind("<FocusOut>", lambda e, k=key: self._panel_changed(k))
            self._panel[key] = txt

        self.hint = ttk.Label(box, foreground="#777",
                              text="행을 선택하면 입력할 수 있습니다.  ＋행 추가 로 새 줄을 만드세요.")
        self.hint.pack(anchor="w", padx=8, pady=(2, 6))
        self._set_panel_state("disabled")

    def _set_panel_state(self, state: str) -> None:
        for w in self._panel.values():
            try:
                w.configure(state=state if isinstance(w, tk.Text) else
                            ("normal" if state == "normal" else "disabled"))
            except tk.TclError:
                pass

    def _load_panel(self, _e=None) -> None:
        idx = self._selected_index()
        self._loading = True
        try:
            if idx is None:
                self._set_panel_state("disabled")
                self.hint.configure(text="행을 선택하면 입력할 수 있습니다.  ＋행 추가 로 새 줄을 만드세요.")
                return
            self._set_panel_state("normal")
            self.hint.configure(text=f"{idx + 1}번째 행을 편집하고 있습니다. "
                                     f"(전체 {len(self._rows)}행)")
            row = self._rows[idx]
            for key, w in self._panel.items():
                value = str(row.get(key, ""))
                if isinstance(w, tk.Text):
                    w.delete("1.0", "end")
                    w.insert("1.0", value)
                else:
                    getattr(w, "_var").set(value)
        finally:
            self._loading = False

    def _panel_changed(self, key: str) -> None:
        if self._loading:
            return
        idx = self._selected_index()
        if idx is None:
            return
        w = self._panel[key]
        value = w.get("1.0", "end-1c") if isinstance(w, tk.Text) else getattr(w, "_var").get()
        if self._rows[idx].get(key, "") == value:
            return
        self._rows[idx][key] = value
        self.tree.item(str(idx), values=[flat(str(self._rows[idx].get(k, "")))
                                         for k in self.keys])
        self._changed()

    def focus_panel(self) -> None:
        if self._panel:
            first = self._panel[self.keys[0]]
            try:
                first.focus_set()
            except tk.TclError:
                pass

    # ── 데이터 ──────────────────────────────────────────────
    def set_rows(self, rows: List[Dict[str, str]]) -> None:
        self._cancel_edit()
        self._rows = [dict(r) for r in rows]
        self._refresh(0 if self._rows else None)

    def get_rows(self) -> List[Dict[str, str]]:
        self._cancel_edit()
        return [dict(r) for r in self._rows]

    def _refresh(self, select: Optional[int] = None) -> None:
        self.tree.delete(*self.tree.get_children())
        for i, row in enumerate(self._rows):
            self.tree.insert("", "end", iid=str(i),
                             values=[flat(str(row.get(k, ""))) for k in self.keys])
        if select is not None and self._rows:
            idx = max(0, min(select, len(self._rows) - 1))
            self.tree.selection_set(str(idx))
            self.tree.see(str(idx))
        # 선택 이벤트는 나중에 들어오므로, 입력칸은 여기서 바로 맞춰 둔다
        self._load_panel()

    def _changed(self) -> None:
        if self.on_change:
            self.on_change()

    # ── 버튼 동작 ────────────────────────────────────────────
    def _selected_index(self) -> Optional[int]:
        sel = self.tree.selection()
        if not sel:
            return None
        idx = int(sel[0])
        return idx if 0 <= idx < len(self._rows) else None

    def add_row(self) -> None:
        idx = self._selected_index()
        pos = len(self._rows) if idx is None else idx + 1
        self._rows.insert(pos, {k: "" for k in self.keys})
        self._refresh(pos)
        self._changed()
        self.focus_panel()

    def delete_row(self) -> None:
        idx = self._selected_index()
        if idx is None:
            return
        del self._rows[idx]
        self._refresh(min(idx, len(self._rows) - 1) if self._rows else None)
        self._changed()

    def move(self, delta: int) -> None:
        idx = self._selected_index()
        if idx is None:
            return
        new = idx + delta
        if not (0 <= new < len(self._rows)):
            return
        self._rows[idx], self._rows[new] = self._rows[new], self._rows[idx]
        self._refresh(new)
        self._changed()

    def clear(self) -> None:
        if self._rows and not messagebox.askyesno("확인", "표의 모든 행을 지울까요?", parent=self):
            return
        self._rows = []
        self._refresh()
        self._changed()

    def paste_clipboard(self) -> None:
        from ..importers import parse_pasted_table
        try:
            text = self.clipboard_get()
        except tk.TclError:
            messagebox.showinfo("붙여넣기", "클립보드가 비어 있습니다.", parent=self)
            return
        rows = parse_pasted_table(text, len(self.keys))
        if not rows:
            messagebox.showinfo("붙여넣기", "표로 인식할 내용이 없습니다.", parent=self)
            return
        append = bool(self._rows) and messagebox.askyesno(
            "붙여넣기", f"{len(rows)}행을 인식했습니다.\n기존 행 뒤에 이어붙일까요?\n"
                        "(아니오 = 기존 내용을 지우고 새로 채움)", parent=self)
        cells = [dict(zip(self.keys, r)) for r in rows]
        self._rows = (self._rows + cells) if append else cells
        self._refresh(len(self._rows) - 1)
        self._changed()

    # ── 목록에서 바로 고치기 (더블클릭) ───────────────────────
    def _cancel_edit(self) -> None:
        if self._editor is not None:
            self._editor.destroy()
            self._editor = None

    def _begin_edit(self, event=None) -> str:
        self._cancel_edit()
        if event is None:
            return "break"
        row_id = self.tree.identify_row(event.y)
        col_id = self.tree.identify_column(event.x)
        if not row_id or not col_id:
            return "break"
        col_index = int(col_id.replace("#", "")) - 1
        if not (0 <= col_index < len(self.keys)):
            return "break"
        key = self.keys[col_index]
        idx = int(row_id)
        value = str(self._rows[idx].get(key, ""))

        if key in self.multiline or "\n" in value:
            dlg = MultilineDialog(self, self.labels[key], value)
            if dlg.result is not None:
                self._rows[idx][key] = dlg.result
                self._refresh(idx)
                self._changed()
            return "break"

        bbox = self.tree.bbox(row_id, col_id)
        if not bbox:
            return "break"
        x, y, w, h = bbox
        var = tk.StringVar(value=value)
        entry = ttk.Entry(self.tree, textvariable=var)
        entry.place(x=x, y=y, width=w, height=h)
        entry.focus_set()
        entry.selection_range(0, "end")
        self._editor = entry

        def commit(_e=None):
            self._rows[idx][key] = var.get()
            self._cancel_edit()
            self._refresh(idx)
            self._changed()

        entry.bind("<Return>", commit)
        entry.bind("<FocusOut>", commit)
        entry.bind("<Escape>", lambda e: self._cancel_edit())
        return "break"


class FieldGrid(ttk.Frame):
    """라벨 + 입력칸을 격자로 배치하는 헬퍼."""

    def __init__(self, master, columns: int = 2):
        super().__init__(master)
        self.vars: Dict[str, tk.Variable] = {}
        self._row = 0
        self._col = 0
        self._columns = columns
        for c in range(columns):
            self.columnconfigure(c * 2 + 1, weight=1)

    def add(self, key: str, label: str, width: int = 24, span: int = 1,
            kind: str = "entry", values: Sequence[str] = ()) -> tk.Variable:
        if self._col + span > self._columns:
            self._row += 1
            self._col = 0
        c = self._col * 2
        ttk.Label(self, text=label).grid(row=self._row, column=c, sticky="e", padx=(6, 4), pady=3)
        if kind == "check":
            var: tk.Variable = tk.BooleanVar()
            w: tk.Widget = ttk.Checkbutton(self, variable=var)
        elif kind == "combo":
            var = tk.StringVar()
            w = ttk.Combobox(self, textvariable=var, values=list(values), state="readonly",
                             width=width)
        else:
            var = tk.StringVar()
            w = ttk.Entry(self, textvariable=var, width=width)
        w.grid(row=self._row, column=c + 1, columnspan=span * 2 - 1, sticky="ew",
               padx=(0, 8), pady=3)
        self.vars[key] = var
        self._col += span
        if self._col >= self._columns:
            self._row += 1
            self._col = 0
        return var

    def newline(self) -> None:
        if self._col:
            self._row += 1
            self._col = 0

    def get(self, key: str):
        return self.vars[key].get()

    def set(self, key: str, value) -> None:
        self.vars[key].set(value)


HELP_TEXT = """\
■ 한 건을 만드는 흐름

  1.  파일 → 표준 템플릿으로 새로 만들기
  2.  ① 기본정보 탭에서 고객사·정격전류를 넣고 [도번 자동 생성]
  3.  ② 문서 구성 탭에서 항목을 고르고 값을 입력 (아래 설명 참고)
  4.  F5 로 미리보기
  5.  Ctrl+S 로 저장  →  Ctrl+E 로 고객사 폴더에 PDF 저장


■ 값은 이렇게 넣습니다  ★ 가장 헷갈리는 부분

  표(사양표·개정 이력)는 두 부분으로 되어 있습니다.

    위쪽 = 전체 목록          아래쪽 = "▼ 선택한 행 입력"

  ① 위 목록에서 고칠 줄을 한 번 클릭합니다.
  ② 아래 "선택한 행 입력" 칸에 값을 타이핑합니다.
  ③ 타이핑하는 즉시 위 목록에도 반영됩니다.  저장 버튼은 없습니다.

  · 줄을 새로 만들려면 [＋ 행 추가]
  · 줄 순서는 [▲] [▼], 지우기는 [행 삭제]
  · 목록의 칸을 더블클릭해도 그 자리에서 고칠 수 있습니다.
  · 여러 줄을 쓰려면 아래 입력칸에서 그냥 Enter 를 치세요.
  · 엑셀에 정리해 둔 표가 있으면, 범위를 복사한 뒤
    [엑셀에서 붙여넣기] 를 누르면 한 번에 들어갑니다.


■ 도면 붙이기

  모든 항목 아래에 "첨부 도면" 칸이 있습니다.
  [도면 파일 추가...] 로 PNG / JPG / PDF 를 고르면 됩니다.
  (PDF 는 첫 페이지가 그림으로 들어갑니다)
  폭은 mm 단위이고, 본문에 들어갈 수 있는 최대 폭은 170mm 입니다.

  문서를 한 번 저장해 두면, 이후 추가하는 도면은 문서 옆
  figures 폴더로 자동 복사됩니다. 폴더째 주고받으면 됩니다.


■ 항목 늘리고 줄이기

  왼쪽 목록 아래에서 종류를 고르고 [추가] 를 누르면 새 항목이 생깁니다.
    본문 항목    — 글로 쓰는 지시사항
    사양표       — 항목 / 사양 / 비고 표
    도면/그림    — 도면만 크게
    판수관리표   — 개정 이력
  [복제] 는 비슷한 항목을 만들 때, [▲][▼] 는 순서를 바꿀 때 씁니다.
  번호(1. 2. 3. …)와 PAGE n/N 은 자동으로 다시 매겨집니다.


■ 도번과 리비전

  도번   BR - RA - HYU - 0475 - 01
         │    │    │      │      └ 일련번호
         │    │    │      └ 정격전류
         │    │    └ 고객코드(영문명에서 자동)
         │    └ 제품군
         └ Braumm

  · 도번은 한 번 정하면 바꾸지 않습니다. 제품이 달라지면 새 도번을 땁니다.
  · 설계가 바뀌면 [▲ 리비전 올리기] 를 누릅니다.
    A → B → C 로 올라가고, 변경 내용이 개정 이력 표에 자동으로 기록됩니다.
  · 밖으로 나간 문서를 고쳤다면 반드시 리비전을 올리세요.
    현장에서 구본을 쓰는 사고를 막아 줍니다.


■ 저장과 불러오기

  저장(Ctrl+S)  → .spec.json 파일. 이 파일이 원본입니다.
  열기(Ctrl+O)  → 저장해 둔 .spec.json 을 다시 불러옵니다.
  파일 → 최근에 연 문서 에서 바로 고를 수도 있습니다.

  다음 제품을 만들 때는 비슷한 문서를 열어
  "다른 이름으로 저장" 한 뒤 값만 고치는 것이 가장 빠릅니다.


■ PDF 저장 위치

  출력 → 출력 폴더 설정  에서 사양서를 모아 둘 폴더를 한 번만 정해 두면,
  Ctrl+E 를 누를 때마다

      {출력 폴더} / {고객사} / BR-RA-HYU-0475-01_RevB_20260901.pdf

  형태로 알아서 저장됩니다. 고객사 폴더는 없으면 자동으로 만들어집니다.
  파일 이름 규칙은 출력 → 파일 이름 규칙 에서 바꿀 수 있습니다.
    쓸 수 있는 항목: {도번} {리비전} {날짜} {발행일} {고객사} {제품명}
"""


class HelpWindow(tk.Toplevel):
    """스크롤되는 사용법 창."""

    def __init__(self, master):
        super().__init__(master)
        self.title("사용 방법")
        self.geometry("760x620")
        self.transient(master)

        wrap = ttk.Frame(self)
        wrap.pack(fill="both", expand=True, padx=10, pady=10)
        text = tk.Text(wrap, wrap="word", font=("Malgun Gothic", 10), padx=12, pady=10)
        vs = ttk.Scrollbar(wrap, orient="vertical", command=text.yview)
        text.configure(yscrollcommand=vs.set)
        text.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        text.insert("1.0", HELP_TEXT)
        text.configure(state="disabled")

        ttk.Button(self, text="닫기", command=self.destroy).pack(pady=(0, 10))
        self.bind("<Escape>", lambda e: self.destroy())


class RegistryWindow(tk.Toplevel):
    """도번 대장 — 지금까지 발행한 번호를 훑어보는 창."""

    def __init__(self, master, registry):
        super().__init__(master)
        self.title(f"도번 대장  —  {registry.path}")
        self.geometry("980x560")
        self.transient(master)
        self.registry = registry

        top = ttk.Frame(self)
        top.pack(fill="x", padx=10, pady=(10, 4))
        ttk.Label(top, text=f"발행한 도번 {registry.count()}건").pack(side="left")
        self.q = tk.StringVar()
        ttk.Label(top, text="검색").pack(side="left", padx=(20, 4))
        ent = ttk.Entry(top, textvariable=self.q, width=28)
        ent.pack(side="left")
        self.q.trace_add("write", lambda *a: self._fill())
        ttk.Button(top, text="폴더 열기", command=self._open_folder).pack(side="right")

        cols = [("number", "도번", 190), ("customer", "고객사", 130),
                ("product", "제품명", 200), ("rated_current", "정격전류", 90),
                ("revision", "리비전", 60), ("created", "최초 발행", 100),
                ("updated", "최종 수정", 100)]
        wrap = ttk.Frame(self)
        wrap.pack(fill="both", expand=True, padx=10, pady=4)
        self.tree = ttk.Treeview(wrap, columns=[c[0] for c in cols], show="headings")
        for key, label, width in cols:
            self.tree.heading(key, text=label)
            self.tree.column(key, width=width, anchor="w")
        vs = ttk.Scrollbar(wrap, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")

        codes = ", ".join(f"{v.get('name_ko') or k}={v['code']}"
                          for k, v in sorted(registry.data["customers"].items(),
                                             key=lambda x: x[1]["code"]))
        ttk.Label(self, text="고객코드:  " + (codes or "(아직 없음)"),
                  foreground="#555", wraplength=940, justify="left").pack(
            anchor="w", padx=12, pady=(0, 4))
        ttk.Button(self, text="닫기", command=self.destroy).pack(pady=(0, 10))
        self.bind("<Escape>", lambda e: self.destroy())
        self._fill()

    def _fill(self) -> None:
        self.tree.delete(*self.tree.get_children())
        needle = self.q.get().strip().lower()
        for row in self.registry.rows():
            blob = " ".join(str(v) for v in row.values()).lower()
            if needle and needle not in blob:
                continue
            self.tree.insert("", "end", values=[
                row.get("number", ""), row.get("customer", ""), row.get("product", ""),
                row.get("rated_current", ""), row.get("revision", ""),
                row.get("created", ""), row.get("updated", "")])

    def _open_folder(self) -> None:
        import subprocess
        import sys
        path = self.registry.root
        try:
            if sys.platform.startswith("win"):
                os.startfile(path)          # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
        except Exception:
            pass
