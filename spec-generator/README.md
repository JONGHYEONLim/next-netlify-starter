# 생산용 사양서 생성기 (Production Spec Generator)

사양 값과 도면을 넣으면, 생산처에 그대로 넘길 수 있는 **A4 도면 양식 사양서 PDF** 를
만들어 주는 데스크톱 프로그램입니다. 첨부해 주신 `HG564145` (AC Reactor 注文仕様書)
양식을 그대로 재현했습니다.

- 항목 번호(`1.` `2.` `3.` …)와 `PAGE n / N` 은 **자동으로 다시 매겨집니다**
- 사양표는 **엑셀에서 복사 → 붙여넣기** 로 한 번에 채울 수 있습니다
- 도면은 **PNG / JPG / PDF** 를 그대로 얹을 수 있습니다 (PDF 는 첫 페이지를 사용)
- 문서 한 건 = JSON 파일 한 개(`.spec.json`) → 사내에서 복사·재사용·버전관리가 쉽습니다
- 반복되는 정형 문구(시험·검사, 제출서류, 보증조건 등)는 **템플릿**에 들어 있습니다

---

## 1. 바로 쓰기

### Windows 실행파일(exe)
설치가 필요 없는 단일 exe 로 만들 수 있습니다.

```bat
build.bat        :: 더블클릭 → dist\SpecGenerator.exe 생성
```

또는 이 저장소를 GitHub 에 올리면 **Actions → Build Spec Generator** 가
`SpecGenerator.exe` 를 자동으로 빌드해 아티팩트로 올려 줍니다. (빌드는 Windows 러너에서 수행)

### 소스로 실행 (Windows / macOS / Linux)

```bash
pip install -r requirements.txt
python -m spec_generator                       # GUI 실행
python -m spec_generator 파일.spec.json         # 문서를 열면서 실행
```

---

## 2. 사용 순서

1. **① 기본정보(표제란)** — 제품명, 용도명, 도면번호, DRAWN/CHECKED/APPROVED 등 표제란 값을 입력합니다.
2. **② 문서 구성** — 왼쪽 목록에서 항목을 고르고 오른쪽에서 내용을 채웁니다.
   - **본문 항목** : 일본어/영어를 나란히, 들여쓰기 0~3 단계, 머리기호 `(1)` `①` 지원
   - **사양표** : `항목(일)/항목(영)/사양/비고` 4열. 엑셀에서 복사 후 **[엑셀에서 붙여넣기]**
   - **도면/그림** : PNG·JPG·PDF 추가. 폭(mm) 지정 (본문 최대 폭 170mm)
   - **판수관리표** : 개정 이력
3. **F5** 로 미리보기, **Ctrl+P** 로 PDF 내보내기.

문서를 저장(`Ctrl+S`)하면 `.spec.json` 이 생기고, 이후 추가하는 도면 파일은
그 옆의 `figures/` 폴더로 자동 복사되므로 폴더째 주고받으면 됩니다.

### 새 제품 시작하기
`파일 → 표준 템플릿으로 새로 만들기` 를 누르면 6~15번 정형 문구가 채워진 상태로 시작합니다.
자주 쓰는 구성이 따로 있으면 `파일 → 현재 문서를 템플릿으로 저장` 으로 템플릿을 늘려 가세요
(사용자 템플릿은 `~/.spec_generator_templates` 에 저장됩니다).

---

## 3. 명령줄 (일괄 생성용)

```bash
python -m spec_generator build samples/HG564145.spec.json -o HG564145.pdf
python -m spec_generator build in.spec.json --font C:\Windows\Fonts\malgun.ttf
python -m spec_generator templates          # 사용 가능한 템플릿 목록
```

여러 파트를 한꺼번에 뽑을 때는 `.spec.json` 을 복사해 값만 바꾼 뒤 반복 호출하면 됩니다.

---

## 4. 폰트

산출물에 일본어가 들어가므로 CJK 폰트가 필요합니다. 프로그램이 시스템 폰트를 자동으로
찾지만, 일본어와 한글이 **함께** 들어가는 문서라면 `assets/fonts/` 에
`NotoSansCJK` 계열 폰트를 넣어 두는 것을 권합니다 (넣어 두면 최우선 사용, exe 에도 함께 포함됨).
`도구 → PDF 폰트 지정` 으로 그때그때 바꿀 수도 있습니다.

---

## 5. 구조

```
spec-generator/
├─ run_app.py                  실행 진입점 (exe 빌드용)
├─ build.bat / run.bat         Windows 빌드 · 실행
├─ SpecGenerator.spec          PyInstaller 설정
├─ samples/HG564145.spec.json  첨부 도면을 그대로 재현한 예제
├─ assets/fonts/               (선택) 번들 폰트
└─ spec_generator/
   ├─ model.py                 데이터 모델 + JSON 저장/불러오기
   ├─ fonts.py                 CJK 폰트 탐색·등록
   ├─ importers.py             엑셀 붙여넣기 파싱, 도면 PDF→이미지
   ├─ templates/               표준 템플릿(.spec.json)
   ├─ render/
   │  ├─ frame.py              도면 양식(외곽선·좌측/하단 표제란) — 치수는 모두 mm 상수
   │  ├─ flow.py               섹션 → 표·본문·그림 변환
   │  └─ build.py              PDF 조판 (페이지 총수 자동 계산)
   └─ gui/                     Tkinter 화면
```

### 양식을 손보고 싶을 때
표제란 칸 위치·크기는 전부 `render/frame.py` 위쪽의 mm 상수입니다.
표 열 너비·글자 크기는 `render/flow.py` 의 `SPEC_WIDTHS`, `make_styles()` 에 있습니다.

---

## 6. 참고 — 예제 문서에 대해

`samples/HG564145.spec.json` 은 주신 PDF(8페이지 중 2~8페이지)를 그대로 옮긴 것입니다.
**1페이지는 제공되지 않아** 1·2·3번 항목(`適用範囲` / `適用規格` / `使用条件`)은
제목만 있는 빈 자리표시로 넣어 두었습니다. 실제 1페이지를 주시면 그대로 채워 넣겠습니다.
