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
