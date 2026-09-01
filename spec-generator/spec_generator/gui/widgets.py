# -*- coding: utf-8 -*-
"""GUI 공용 위젯: 표 편집기, 여러 줄 입력 대화상자."""
from __future__ import annotations

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
    """행 추가/삭제/이동과 엑셀 붙여넣기를 지원하는 간단한 표 편집기."""

    def __init__(self, master, columns: Sequence[Tuple[str, str, int]],
                 multiline: Sequence[str] = (),
                 on_change: Optional[Callable[[], None]] = None,
                 extra_buttons: Sequence[Tuple[str, Callable[[], None]]] = ()):
        super().__init__(master)
        self.columns = list(columns)          # (key, 표시이름, 너비px)
        self.keys = [c[0] for c in self.columns]
        self.multiline = set(multiline)
        self.on_change = on_change
        self._rows: List[Dict[str, str]] = []
        self._editor: Optional[tk.Widget] = None

        bar = ttk.Frame(self)
        bar.pack(fill="x", pady=(0, 4))
        for label, cmd in (("행 추가", self.add_row), ("위로", lambda: self.move(-1)),
                           ("아래로", lambda: self.move(1)), ("행 삭제", self.delete_row)):
            ttk.Button(bar, text=label, width=8, command=cmd).pack(side="left", padx=2)
        ttk.Separator(bar, orient="vertical").pack(side="left", fill="y", padx=6)
        ttk.Button(bar, text="엑셀에서 붙여넣기", command=self.paste_clipboard).pack(side="left", padx=2)
        ttk.Button(bar, text="전체 비우기", command=self.clear).pack(side="left", padx=2)
        for label, cmd in extra_buttons:
            ttk.Button(bar, text=label, command=cmd).pack(side="left", padx=2)

        wrap = ttk.Frame(self)
        wrap.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(wrap, columns=self.keys, show="headings", selectmode="browse")
        for key, label, width in self.columns:
            self.tree.heading(key, text=label)
            self.tree.column(key, width=width, minwidth=40, stretch=True, anchor="w")
        vs = ttk.Scrollbar(wrap, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")

        self.tree.bind("<Double-1>", self._begin_edit)
        self.tree.bind("<Return>", self._begin_edit)
        self.tree.bind("<Configure>", lambda e: self._cancel_edit())
        self.tree.bind("<MouseWheel>", lambda e: self._cancel_edit(), add="+")

        ttk.Label(self, text="셀을 더블클릭하면 수정할 수 있습니다. 여러 줄은 ⏎ 로 표시됩니다.",
                  foreground="#666").pack(anchor="w", pady=(3, 0))

    # ── 데이터 ──────────────────────────────────────────────
    def set_rows(self, rows: List[Dict[str, str]]) -> None:
        self._cancel_edit()
        self._rows = [dict(r) for r in rows]
        self._refresh()

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

    def _changed(self) -> None:
        if self.on_change:
            self.on_change()

    # ── 버튼 동작 ────────────────────────────────────────────
    def _selected_index(self) -> Optional[int]:
        sel = self.tree.selection()
        return int(sel[0]) if sel else None

    def add_row(self) -> None:
        idx = self._selected_index()
        pos = len(self._rows) if idx is None else idx + 1
        self._rows.insert(pos, {k: "" for k in self.keys})
        self._refresh(pos)
        self._changed()

    def delete_row(self) -> None:
        idx = self._selected_index()
        if idx is None:
            return
        del self._rows[idx]
        self._refresh(idx - 1)
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

    # ── 셀 편집 ─────────────────────────────────────────────
    def _cancel_edit(self) -> None:
        if self._editor is not None:
            self._editor.destroy()
            self._editor = None

    def _begin_edit(self, event=None) -> str:
        self._cancel_edit()
        if event is not None and getattr(event, "type", None) is not None and event.num == 1:
            row_id = self.tree.identify_row(event.y)
            col_id = self.tree.identify_column(event.x)
        else:
            sel = self.tree.selection()
            row_id, col_id = (sel[0] if sel else ""), "#1"
        if not row_id or not col_id:
            return "break"
        col_index = int(col_id.replace("#", "")) - 1
        if not (0 <= col_index < len(self.keys)):
            return "break"
        key = self.keys[col_index]
        idx = int(row_id)
        value = str(self._rows[idx].get(key, ""))

        if key in self.multiline or "\n" in value:
            dlg = MultilineDialog(self, self.columns[col_index][1], value)
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
