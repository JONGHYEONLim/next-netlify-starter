# -*- coding: utf-8 -*-
"""실행 진입점.

  python -m spec_generator                     GUI 실행
  python -m spec_generator file.spec.json      해당 문서를 열고 GUI 실행
  python -m spec_generator build in.spec.json -o out.pdf     GUI 없이 PDF 생성
  python -m spec_generator templates           사용 가능한 템플릿 목록
"""
from __future__ import annotations

import argparse
import os
import sys


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)

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
