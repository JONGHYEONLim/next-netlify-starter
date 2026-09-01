@echo off
REM ============================================================
REM  생산용 사양서 생성기 - Windows 실행파일(exe) 빌드
REM  Python 3.9 이상이 설치된 PC 에서 이 파일을 더블클릭하세요.
REM  결과물: dist\SpecGenerator.exe  (단일 파일, 설치 불필요)
REM ============================================================
setlocal
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
  echo [오류] Python 을 찾을 수 없습니다. https://www.python.org 에서 설치 후 다시 실행하세요.
  pause & exit /b 1
)

echo [1/3] 필요한 패키지를 설치합니다...
python -m pip install --upgrade pip >nul
python -m pip install -r requirements.txt || goto :err

echo [2/3] 이전 빌드 결과를 정리합니다...
if exist build rmdir /s /q build
if exist dist  rmdir /s /q dist

echo [3/3] exe 를 만듭니다. 몇 분 걸릴 수 있습니다...
python -m PyInstaller --clean --noconfirm SpecGenerator.spec || goto :err

echo.
echo 완료되었습니다:  %cd%\dist\SpecGenerator.exe
echo 이 파일 하나만 복사해서 다른 PC 에서도 바로 쓸 수 있습니다.
pause
exit /b 0

:err
echo.
echo [오류] 빌드에 실패했습니다. 위의 메시지를 확인하세요.
pause
exit /b 1
