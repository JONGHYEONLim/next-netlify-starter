# BRAUMM 사무 도구 (데스크톱 앱)

견적서 · 거래명세서 · 성적서 · 제품 · 매출을 한 곳에서 처리하는 내부용 데스크톱 앱입니다.
인터넷 없이 내 PC에서 실행되고, 데이터는 이 컴퓨터에만 저장됩니다.

## 사용자용 — 설치해서 쓰기

1. GitHub 저장소의 **Releases** 페이지로 갑니다.
2. 최신 버전의 `BRAUMM Office Setup x.x.x.exe` 를 내려받아 설치합니다.
3. 바탕화면의 **BRAUMM 사무 도구** 아이콘으로 실행합니다.
4. 새 버전이 나오면 앱이 켜질 때 자동으로 감지해 업데이트합니다.

기존 브라우저(아트팩트)에서 쓰던 데이터는 앱으로 자동 이전되지 않습니다.
브라우저 도구의 **[백업]** 으로 JSON을 내려받아, 앱에서 불러오면 됩니다.

## 개발자용 — 직접 실행/빌드하기

사전 준비: [Node.js](https://nodejs.org) 설치 (LTS 버전)

```bash
cd desktop
npm install

# 앱을 바로 실행해서 개발/확인
npm run dev

# 내 PC에서 설치파일(.exe)만 만들어보기 (게시 안 함)
npm run dist        # -> desktop/dist/ 에 생성
```

## 새 버전 배포 (자동 빌드)

코드를 고친 뒤 버전을 올리고 태그를 push 하면, GitHub Actions가
윈도우 설치파일을 자동으로 만들어 **Releases**에 올립니다.

```bash
# 1) desktop/package.json 의 "version" 을 올린다 (예: 1.0.0 -> 1.0.1)
# 2) 태그를 만들어 push
git tag v1.0.1
git push origin v1.0.1
```

또는 GitHub 저장소 **Actions 탭 → Build Desktop App → Run workflow** 로 수동 실행할 수 있습니다.

## 구조

- `main.js` — Electron 메인 프로세스 (창 생성 + 자동 업데이트)
- `renderer/index.html` — 실제 도구 (UI + 로직, 단일 파일)
- 데이터 저장 — 앱 내부 저장소(localStorage). 앱의 **[백업]** 으로 언제든 파일로 내보낼 수 있음
