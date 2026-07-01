"""
신호 파일 자동 실행 진입점 (Phase 3 — 연결 다리).

대시보드가 만든 signal.json을 읽어, 사람이 숫자를 옮겨적지 않아도
그대로 트레이더(execute_signal)로 흘려보냅니다.

사용법:
  python run_from_signal.py                 # 같은 폴더의 signal.json 읽어 실행
  python run_from_signal.py path/to/signal.json   # 다른 위치 지정

흐름:
  signal.json → read_signal(검증) → execute_signal(리스크 게이트 → 주문)

⚠️ 안전 원칙: 파일이 없거나·형식 오류·오래된 신호면 매매하지 않고 안전 정지합니다.
   기본은 DRY_RUN=true(실주문 없음). config.py에서 바꾸기 전까지 시뮬만 돕니다.
"""
import sys
import config
from signal_io import read_signal, SignalError
from executor import execute_signal
from trade_logger import log


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else None

    try:
        signal, confidence, data = read_signal(path)
    except SignalError as e:
        # 신호를 못 믿겠으면 매매하지 않는다 (안전 정지)
        log(f"⛔ 신호 읽기 실패 — 안전 정지(매매 안 함): {e}")
        return

    note = data.get("note", "")
    src_symbol = data.get("symbol")
    log(f"📥 신호 파일 수신: {signal} (확신도 {confidence})"
        + (f" | 종목 {src_symbol}" if src_symbol else "")
        + (f" | 메모: {note}" if note else ""))

    # signal.json에 종목이 지정돼 있으면 그걸 우선 적용 (없으면 config 기본값)
    if src_symbol:
        src_symbol = str(src_symbol).upper()
        if src_symbol in config.SYMBOLS:
            config.ACTIVE_SYMBOL = src_symbol
        else:
            log(f"⚠️ 신호의 종목 {src_symbol}는 등록되지 않음 — 기본 {config.ACTIVE_SYMBOL} 사용")

    execute_signal(signal, confidence)


if __name__ == "__main__":
    main()
