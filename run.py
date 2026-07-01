"""
Signal Trader 실행 진입점 (Alpaca 모의투자)

사용법:
  python run.py BUY 72        # 신호 BUY, 확신도 72로 실행
  python run.py SELL 80       # 전량 청산
  python run.py HOLD          # 동작 없음

종목 바꾸기 (둘 다 지원):
  ACTIVE_SYMBOL=QQQ python run.py BUY 65    # QQQ로 매매
  (또는 .env에서 ACTIVE_SYMBOL=SPY / QQQ)

기본은 DRY_RUN=true → 실제 주문 안 나가고 로그만 출력(안전).
실제 모의주문 테스트는 .env에서 DRY_RUN=false + Alpaca 페이퍼 API 키 설정 후.
"""
import sys
from executor import execute_signal


def main():
    signal = sys.argv[1] if len(sys.argv) > 1 else "HOLD"
    try:
        confidence = int(sys.argv[2]) if len(sys.argv) > 2 else 50
    except ValueError:
        confidence = 50
    execute_signal(signal, confidence)


if __name__ == "__main__":
    main()
