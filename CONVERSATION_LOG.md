# Signal Invest Pro — 작업 기록 (대화 요약)

> 지금까지 함께 만든 것들과 현재 상태를 정리한 문서입니다.

## 프로젝트 한 줄 요약
AI가 미국 증시 매크로 지표를 분석해 BUY/HOLD/SELL 신호를 내고, 리스크 게이트를 거쳐 Alpaca 모의계좌에서 SPY/QQQ를 자동매매하는 시스템. **현재는 DRY_RUN(연습 모드)라 실제 돈은 움직이지 않음.**

---

## 지금까지 완성한 것 (Phase별)

| Phase | 내용 | 산출물 | 상태 |
|-------|------|--------|------|
| 1 | 신호 시스템 (AI 투자위원회) | (대시보드) | ✅ |
| 2 | 모의투자 주문 모듈 + 안전장치 | config.py, broker.py, risk.py, executor.py, run.py | ✅ |
| 3 | 신호 ↔ 트레이더 연결 | signal_io.py, run_from_signal.py, export_signal.html | ✅ |
| 4 | 매일 아침 8시 자동 실행 | 스케줄 등록됨 (signal-invest-daily) | ✅ |
| 5 | 백테스트 (과거 10년 검증) | backtest.py, spy.csv | ✅ |
| 6 | 실거래 준비 (안전장치 실증) | SAFETY_CHECKLIST.md | ✅ 준비완료 |
| 확장 | FRED 공식 데이터 수집기 | fred_collector.py | ✅ |
| 확장 | 종합 대시보드 | dashboard_pro.html | ✅ |
| 확장 | 추천 페이지 (ZEZE 스타일) | signal_page.html | ✅ |
| 확장 | 수익률 대시보드 | dashboard.html | ✅ |
| 확장 | 통합 트레이딩 IDE | algotu_ide.html → index.html | ✅ |
| 확장 | Claude 앱 없이 도는 로컬 프로그램 | daily_pipeline.py, ai_committee.py, run_daily_pipeline.bat | ✅ |
| 확장 | 클라우드 24시간 자동화 (PC 꺼도 됨) | Railway 배포 (Cron, 평일 8시) | ✅ |
| 확장 | IDE 실시간 연동 (아무 브라우저·모바일) | publish_status.py(Gist 공유) + index.html 자동 fetch | ✅ |
| 확장 | IDE 공개 웹 호스팅 (링크로 누구나 열람) | Railway 2번째 서비스 (web-production-34a77.up.railway.app) | ✅ |

---

## 2026-07-01 세션 — Claude 앱 의존성 제거 & 클라우드 전환

**동기**: 자동매매가 PC/Claude 앱이 켜져 있을 때만 돌던 구조라, "PC가 어차피 켜져 있어야 한다면 아예 독립 프로그램으로 만들자"는 문제의식에서 시작.

**한 일**:
1. **로컬 독립 프로그램화** — `ai_committee.py`(Anthropic API 직접 호출로 Bull/Bear/Judge 재현) + `daily_pipeline.py`(전체 파이프라인 한 번에 실행) 작성. Windows 작업 스케줄러(`schtasks`)로 평일 8시 자동 실행 등록.
   - 도중 발견/수정한 버그: Windows 콘솔이 cp949라 이모지 로그에서 크래시 → `trade_logger.py`에 UTF-8 강제 인코딩 추가.
2. **GitHub 연동** — GitHub Desktop으로 저장소 생성·업로드 (`.env`는 `.gitignore`로 안전하게 제외 확인).
3. **Railway 클라우드 배포** — 같은 코드를 Railway Cron 서비스로 배포해 PC 없이도 24시간 자동 실행되게 함.
   - 겪은 이슈: Railpack이 시작 명령을 못 찾아 빌드 실패 → `Procfile` 추가로 해결. 파이썬 버전 이슈 대비 `.python-version` 고정.
   - Cron 스케줄: `0 23 * * 0-4` (UTC) = 한국시간 평일 오전 8시.
   - 실제 Anthropic API 호출로 Bull/Bear/Judge 판단이 정상 동작하는 것까지 로그로 확인.
4. **중복 실행 정리** — 클라우드가 안정화된 뒤, 기존 Cowork 스케줄(`signal-invest-daily`)은 비활성화. 로컬 Windows 작업 스케줄러도 삭제 권장.
5. **IDE ↔ Railway 실시간 연동** — `publish_status.py`가 매 실행 결과(signal.json/indicators.json/trades.log)를 GitHub Gist에 자동 업로드하고, `algotu_ide.html`(→ `index.html`로 개편)이 그 Gist를 fetch로 읽어와 자동 표시하도록 구현.
6. **공개 웹 호스팅** — Railway에 두 번째 서비스(`sincere-stillness` 프로젝트, `web-production-34a77.up.railway.app`)를 추가해 `python -m http.server`로 `index.html`을 상시 호스팅. Gist ID를 코드에 기본값으로 박아둬서 로그인·연동 절차 없이 링크만 열면 바로 오늘의 신호가 보임 (모바일 대응 CSS 포함).
7. **버그 수정** — Anthropic 응답에 thinking 블록이 먼저 올 때 `content[0].text`가 깨지는 문제 발견 → 실제 text 블록만 골라 처리하도록 `ai_committee.py` 수정.

**결과**: 이제 신호 생성·매매 파이프라인이 Claude 데스크톱 앱과 완전히 무관하게 Railway에서 단독으로 매일 자동 실행되며, 그 결과를 PC/모바일 아무 브라우저에서나 공개 링크로 확인할 수 있음. 여전히 DRY_RUN 기본값, 실거래 전환은 본인 판단.

---

## 주요 검증 결과

**백테스트 (2016~2026, SPY 10년):**
- Buy&Hold: 수익 +324%, 최대낙폭 -33.7%, 샤프 0.90
- 5단계 레짐 전략: 수익 +150%, 최대낙폭 **-22.0%**, 샤프 **0.91**
- → "더 벌기"보다 "덜 다치기"에 강한 전략

**안전장치 실증 (전부 통과):**
- 킬스위치 → 매수 차단, 청산은 허용 ✅
- 일일 손실한도 -2% → 매수 차단 ✅
- 정규장 마감 → 주문 보류 ✅
- 확신도 60 미만 / 오래된 신호 / 파일오류 → 안전 정지 ✅

**FRED 데이터 수집:** 17개 지표 전부 공식 데이터로 수집 확인 (키 연동 완료)

---

## 재연님이 직접 해야 할 일 (실거래 전)
1. Alpaca 페이퍼(가짜돈) 키 발급 → .env에 입력 → DRY_RUN=false로 며칠 테스트
2. 킬스위치 실제로 눌러 멈추는지 확인
3. 페이퍼로 수 주 무사 운영
4. 잃어도 되는 최소 금액만
→ 자세한 절차는 AUTO_TRADING_GUIDE.md, SAFETY_CHECKLIST.md 참고

**⚠️ 실거래 전환(PAPER=False)은 본인 판단·본인 책임. AI는 대신 하지 않음.**

---

## 남은 작업 (원하실 때)
- 텔레그램 알림 봇 (신호·체결·에러를 폰으로)
- ~~24시간 클라우드 서버 배포~~ ✅ 완료 (Railway)

---

## 참고: 화면 파일들 사용법
- `index.html` (구 `algotu_ide.html`) — 통합 IDE (계좌·신호·지표·로그 한 화면). **공개 웹**: web-production-34a77.up.railway.app 로 접속하면 로컬 파일 없이 바로 최신 상태를 볼 수 있음 (모바일 포함)
- `dashboard_pro.html` — 종합 대시보드
- `signal_page.html` — 오늘의 추천 카드
- `dashboard.html` — 수익률 추이
- `export_signal.html` — 신호 수동 입력
→ 로컬에서 열 때는 signal.json / indicators.json / trades.log 를 직접 불러오거나, 상단 "🔗 연동"으로 Gist 주소를 넣으면 표시됨

### 고지
개인 학습·기록용. 투자 권유가 아니며 자동매매는 실제 손실 가능. 모든 판단과 책임은 본인에게 있음.
