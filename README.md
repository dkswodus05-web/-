# Signal Trader (Alpaca 모의투자)

AI 투자위원회가 낸 신호(BUY / HOLD / SELL)를 받아 **리스크 게이트를 거쳐** Alpaca 모의투자 계좌에서 ETF를 매매하는 모듈입니다. SPY / QQQ 둘 다 지원합니다.

> ⚠️ **이건 학습·검증용입니다.** 표시되는 동작은 투자 권유가 아니며, 자동매매는 실제 손실을 낼 수 있습니다. 반드시 모의투자(Paper)로 충분히 검증하고, 실거래는 본인 책임 하에 신중히 결정하세요.

---

## 동작 방식

ETF 하나에 대해 **'보유 ↔ 현금'** 을 신호로 스위칭합니다.

| 신호 | 동작 |
|------|------|
| **BUY** | 미보유면 매수(자산의 일정 %), 이미 보유면 유지 |
| **HOLD** | 아무것도 안 함 |
| **SELL** | 보유 중이면 전량 청산 |

매수는 항상 **리스크 게이트**를 통과해야 실행됩니다:
- 킬 스위치 OFF
- 신호 확신도 ≥ 기준값(기본 60)
- 당일 손실이 한도(기본 -2%) 미도달
- 포지션 사이징 (SPY 30% / QQQ 25%, 상한 30%)

매도(청산)는 리스크 축소이므로 항상 허용됩니다.

---

## 설치

```bash
pip install -r requirements.txt
cp .env.example .env      # 그리고 .env 파일을 열어 키 입력
```

Alpaca 페이퍼 키 발급: https://app.alpaca.markets/ → 가입 → **Paper** 계정으로 전환 → API Keys 생성

FRED 키 발급(무료): https://fred.stlouisfed.org/docs/api/api_key.html → `.env`에 `FRED_API_KEY=...`

---

## 경제지표 수집 (FRED + Yahoo) — 데이터 업그레이드

웹검색 추정치 대신 **공식 데이터**로 17개 매크로 지표를 수집합니다.

```bash
python fred_collector.py     # FRED+Yahoo에서 수집 → indicators.json 생성
```

- 거시지표(금리·실업률·CPI·연준·신용스프레드 등) → **FRED** (미 연준 공식)
- 시장가격(VIX·S&P500·유가) → **Yahoo Finance** (키 불필요)

> ⚠️ FRED 키가 없으면 **가짜값을 만들지 않고 안전 정지**합니다(`ok:false`). 신호 시스템은 이 경우 매매하지 않습니다. "키 없이 임의 동작하는 프로그램"의 함정을 피하기 위한 안전장치입니다.

---

## 실행

```bash
# DRY_RUN=true (기본): 실제 주문 없이 시뮬레이션 로그만
python run.py BUY 72
python run.py SELL 80
python run.py HOLD

# 종목 바꾸기
ACTIVE_SYMBOL=QQQ python run.py BUY 65
```

실제 모의주문을 Alpaca에 보내 테스트하려면 `.env`에서 `DRY_RUN=false` + 키 설정 후 같은 명령을 실행하세요.

모든 기록은 `trades.log` 에 남습니다.

---

## 브리핑 대시보드와 연결하기 (Phase 3 — 완료)

손으로 숫자를 옮겨적는 대신 **`signal.json` 파일**로 신호가 흐릅니다.

1. `export_signal.html`을 브라우저로 연다 → 신호/확신도/종목 입력 → **signal.json 저장**
2. 저장한 `signal.json`을 이 폴더(트레이더와 같은 곳)에 둔다
3. 다음을 실행:

```bash
python run_from_signal.py            # 같은 폴더의 signal.json 읽어 자동 실행
python run_from_signal.py 경로/signal.json   # 다른 위치 지정
```

`signal.json` 형식:

```json
{ "signal": "BUY", "confidence": 72, "symbol": "SPY",
  "created_at": "2026-06-26T08:30:00", "note": "금리차 안정 + VIX 하락" }
```

**안전장치**: 파일이 없거나·형식 오류·24시간 넘은 오래된 신호면 매매하지 않고 안전 정지합니다.
직접 숫자로 실행하던 `python run.py BUY 72` 방식도 그대로 쓸 수 있습니다.

---

## 백테스트 (Phase 5 — 실거래 전 필수)

과거 데이터로 "이 전략이 단순 매수후보유(Buy&Hold)보다 나은가, 낙폭은 견딜 만한가"를 숫자로 확인합니다.

```bash
python backtest.py          # SMA200 추세추종 vs Buy&Hold
python backtest.py 150      # 이동평균 기간 바꿔 민감도 확인
```

`spy.csv`가 없으면 Yahoo Finance에서 자동으로 받습니다(키 불필요).

**최근 10년 SPY 결과 (2016-06 ~ 2026-06):**

| 지표 | Buy&Hold | 신호전략(SMA200) | 5단계 레짐 |
|------|----------|------------------|-----------|
| 총수익률 | +324% | +146% | +150% |
| 연평균(CAGR) | +15.6% | +9.4% | +9.6% |
| 최대낙폭(MDD) | **-33.7%** | -24.2% | **-22.0%** |
| 샤프지수 | 0.90 | 0.83 | **0.91** |
| 거래횟수 | - | 51회 | 194회 |

**해석:** 강한 상승장이었던 지난 10년에는 그냥 들고 있는 Buy&Hold가 절대수익은 더 컸습니다. 하지만 신호전략은 **낙폭을 줄이고(위험 대비 수익 = 샤프는 더 높음)** 방어적으로 움직였습니다. 즉 "더 많이 벌기"보다 "덜 다치기"에 강점이 있는 전략입니다.

**5단계 레짐 전략** (moket.kr 참고로 추가)은 BUY/현금 2칸 대신 시장을 공격·균형·중립·방어·위기 5단계로 나눠 주식비중을 100/90/65/30/0%로 차등합니다. 기존 2칸보다 수익은 같으면서 낙폭은 더 작고 샤프는 더 높았습니다. **거래비용 밴드**(목표비중과 차이가 5% 미만이면 매매 스킵)로 불필요한 잦은 매매도 줄였습니다(547회→194회).

> ⚠️ 위 신호는 매크로 위원회가 아니라 같은 '보유↔현금 스위칭' 성격의 대표 전략(이동평균 추세추종)으로 검증한 것입니다. 매크로 신호의 과거 시퀀스가 모이면 `signals_from_list()`에 넣어 동일하게 비교할 수 있습니다. **과거 성과는 미래를 보장하지 않으며, 결과가 나쁘면 실거래로 가지 않는 것이 정답입니다.**

---

## 파일 구조

```
signal_trader/
├─ config.py           설정·리스크 파라미터 (여기만 바꾸면 동작 변경)
├─ broker.py           Alpaca 연결·주문 (DRY_RUN이면 패키지 없이도 동작)
├─ risk.py             리스크 게이트 (확신도·손실한도·포지션 사이징)
├─ executor.py         신호 → 안전장치 → 주문 오케스트레이션
├─ trade_logger.py     콘솔 + trades.log 기록
├─ run.py              실행 진입점 (CLI: python run.py BUY 72)
├─ signal_io.py        신호 JSON 읽기/쓰기·검증 (Phase 3)
├─ run_from_signal.py  signal.json 읽어 자동 실행 (Phase 3)
├─ export_signal.html  브라우저에서 signal.json 내보내기 (Phase 3)
├─ backtest.py         과거 데이터 백테스트 (Phase 5)
├─ requirements.txt
└─ .env.example
```

---

## 다음 단계 (로드맵)

1. ✅ 신호 시스템 (대시보드)
2. ✅ 모의투자 주문 모듈 (이 폴더)
3. ✅ 대시보드 ↔ 트레이더 연결 다리 (signal.json + run_from_signal.py)
4. ✅ 자동 스케줄링 (평일 아침 8시 자동 실행)
5. ✅ **백테스트** — 과거 데이터로 신호 검증 (backtest.py)
6. ⬜ (선택) 소액 실거래

**5번 백테스트 없이 실거래로 가지 마세요.** 신호가 실제로 수익을 내는지 과거 데이터로 확인하는 게 안전장치보다도 먼저입니다.
