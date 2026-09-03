# -*- coding: utf-8 -*-
"""실행 진입점.

  python -m spec_generator                     GUI 실행
  python -m spec_generator file.spec.json      해당 문서를 열고 GUI 실행
  python -m spec_generator build in.spec.json -o out.pdf     GUI 없이 PDF 생성
  python -m spec_generator templates           사용 가능한 템플릿 목록
  python -m spec_generator selftest            호환성 자체 점검 (예전 문서가 열리는지)
"""
from __future__ import annotations

import argparse
import os
import sys


def force_utf8_console() -> None:
    """Windows 콘솔 기본 코덱(cp1252/cp949)에서 한글 출력이 죽지 않게 한다.

    창 모드로 빌드한 exe 에서는 stdout 이 아예 없을 수 있으므로 조용히 넘어간다.
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError, OSError):
            pass


def main(argv=None) -> int:
    force_utf8_console()
    argv = list(sys.argv[1:] if argv is None else argv)

    if argv and argv[0] == "selftest":
        from .selftest import run
        return run()

    if argv and argv[0] == "templates":
        from . import templates
        for name, path in templates.list_templates().items():
            print(f"{name}\t{path}")
        return 0

    if argv and argv[0] == "build":
        p = argparse.ArgumentParser(prog="spec_generator build")
        p.add_argument("input", help="사양서 프로젝트 파일(.spec.json)")
        p.add_argument("-o", "--output", help="출력 PDF 경로")
        p.add_argument("--font", help="PDF에 사용할 폰트 파일 경로")
        args = p.parse_args(argv[1:])

        from .model import SpecDoc
        from .render.build import build_pdf
        doc = SpecDoc.load(args.input)
        out = args.output or os.path.splitext(os.path.splitext(args.input)[0])[0] + ".pdf"
        print(build_pdf(doc, out, args.font))
        return 0

    from .gui.app import main as gui_main
    return gui_main(argv[0] if argv else None)


if __name__ == "__main__":
    raise SystemExit(main())
