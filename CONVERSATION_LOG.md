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
| 확장 | 통합 트레이딩 IDE | algotu_ide.html | ✅ |

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
- 24시간 클라우드 서버 배포 (컴퓨터 안 켜도 자동 실행)

---

## 참고: 화면 파일들 사용법
- `algotu_ide.html` — 통합 IDE (계좌·신호·지표·로그 한 화면)
- `dashboard_pro.html` — 종합 대시보드
- `signal_page.html` — 오늘의 추천 카드
- `dashboard.html` — 수익률 추이
- `export_signal.html` — 신호 수동 입력
→ 브라우저로 열고 signal.json / indicators.json / trades.log 를 불러오면 표시됨

### 고지
개인 학습·기록용. 투자 권유가 아니며 자동매매는 실제 손실 가능. 모든 판단과 책임은 본인에게 있음.
