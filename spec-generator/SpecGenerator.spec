# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 빌드 설정.  build.bat 이 이 파일을 사용한다."""
import os

datas = [
    ("spec_generator/templates/*.spec.json", "spec_generator/templates"),
    ("assets/fonts", "assets/fonts"),
]

hiddenimports = [
    "reportlab.pdfbase._fontdata_enc_winansi",
    "reportlab.pdfbase._fontdata_enc_macroman",
    "reportlab.pdfbase._fontdata_widths_helvetica",
    "reportlab.pdfbase.cidfonts",
    "reportlab.graphics.barcode",
    "PIL._tkinter_finder",
]

a = Analysis(
    ["run_app.py"],
    pathex=[os.path.abspath(".")],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["numpy", "matplotlib", "pytest"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="SpecGenerator",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=False,          # 콘솔 창 없이 실행
    disable_windowed_traceback=False,
    icon=None,
)
