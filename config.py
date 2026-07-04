"""
설정 파일 — 여기 값만 바꾸면 동작이 달라집니다.
⚠️ 안전 기본값: DRY_RUN=true(실주문 X), PAPER=True(모의계좌). 검증 전까지 절대 바꾸지 마세요.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ===== 계정 / 실행 모드 =====
ALPACA_API_KEY = os.getenv("ALPACA_API_KEY", "")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY", "")

PAPER = True   # ⚠️ 모의투자 계좌. 실거래로 바꾸지 말 것 (충분한 검증 + 본인 책임 하에만)
DRY_RUN = os.getenv("DRY_RUN", "true").lower() == "true"  # true면 실제 주문 없이 시뮬레이션만

# ===== 매매 대상 (SPY / QQQ 둘 다 설정됨) =====
SYMBOLS = {
    "SPY": {"name": "S&P 500",    "target_pct": 0.30},  # 자산의 30%까지 매수
    "QQQ": {"name": "Nasdaq 100", "target_pct": 0.25},  # 변동성 커서 비중 낮춤
}
ACTIVE_SYMBOL = os.getenv("ACTIVE_SYMBOL", "SPY").upper()

# ===== 리스크 파라미터 (시스템의 핵심) =====
MIN_CONFIDENCE = 60       # Judge 확신도가 이 값 미만이면 매수하지 않음
DAILY_LOSS_LIMIT = 0.02   # 당일 -2% 손실 도달 시 그날 매수 정지
MAX_POSITION_PCT = 0.30   # 한 종목 최대 비중 상한
ALLOW_EXTENDED_HOURS = False  # 정규장만 거래
KILL_SWITCH = False       # True로 두면 모든 매수 즉시 정지 (긴급 스위치)

# ===== 멀티에셋 레짐 리밸런싱 (Phase 7) =====
# True면 단일 종목 스위칭 대신, 아래 유니버스를 레짐별 목표 비중으로 리밸런싱한다.
# ⚠️ 안전 기본값 false — DRY_RUN 검증 후 Railway 환경변수 REBALANCE_MODE=true로 켠다.
REBALANCE_MODE = os.getenv("REBALANCE_MODE", "false").lower() == "true"

# 전략 유니버스 — 여기 있는 종목만 사고판다.
# 유니버스에 없는 종목을 보유 중이면 리밸런싱 때 전량 정리한다(원본 블로그 방식).
# ⚠️ QLD(2배)·TQQQ(3배)는 레버리지 ETF — 수익도 손실도 증폭됨. 본인 결정으로 포함(2026-07-04).
UNIVERSE = {
    "SPY":  {"name": "S&P 500",    "max_pct": 0.40, "leveraged": False},
    "QQQ":  {"name": "Nasdaq 100", "max_pct": 0.35, "leveraged": False},
    "QLD":  {"name": "Nasdaq 2x",  "max_pct": 0.25, "leveraged": True},
    "TQQQ": {"name": "Nasdaq 3x",  "max_pct": 0.15, "leveraged": True},
    "GLD":  {"name": "Gold",       "max_pct": 0.20, "leveraged": False},
}

# 레짐별 목표 비중 (합계가 1보다 작으면 나머지는 현금).
# backtest.py의 5단계 레짐(공격·균형·중립·방어·위기) 사상과 동일 — 위험할수록 현금 증가,
# 레버리지는 공격 레짐에서만 소폭 허용.
REGIME_WEIGHTS = {
    "공격": {"SPY": 0.30, "QQQ": 0.25, "QLD": 0.20, "TQQQ": 0.10, "GLD": 0.05},  # 위험자산 90%
    "균형": {"SPY": 0.30, "QQQ": 0.20, "QLD": 0.10, "GLD": 0.10},                # 70%
    "중립": {"SPY": 0.25, "QQQ": 0.15, "GLD": 0.10},                             # 50%
    "방어": {"SPY": 0.15, "GLD": 0.15},                                          # 30%
    "위기": {"GLD": 0.10},                                                       # 10% (거의 전량 현금)
}
VALID_REGIMES = set(REGIME_WEIGHTS.keys())

# 리밸런싱 밴드: 목표 비중과 현재 비중의 차이가 이 값 미만이면 매매하지 않는다.
# (불필요한 잦은 매매 방지 — 백테스트에서 거래를 547회→194회로 줄였던 그 장치)
REBALANCE_BAND = 0.05
