# -*- coding: utf-8 -*-
"""PyInstaller / 직접 실행용 진입 스크립트."""
import multiprocessing
import sys

from spec_generator.__main__ import main

if __name__ == "__main__":
    multiprocessing.freeze_support()
    sys.exit(main())
