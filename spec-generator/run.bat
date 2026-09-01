@echo off
REM 소스 상태로 바로 실행 (exe 를 만들지 않고 테스트할 때)
setlocal
cd /d "%~dp0"
python -m pip install -r requirements.txt >nul 2>nul
python -m spec_generator %*
