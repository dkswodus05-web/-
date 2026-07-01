"""
신호 실행기 — 신호를 받아 안전장치를 거쳐 실제 매매로 변환.
전략: ETF 하나에 대해 '들어가 있느냐(보유) / 현금이냐'를 신호로 스위칭.
  BUY  → 미보유면 매수, 보유면 유지
  HOLD → 아무것도 안 함
  SELL → 보유면 전량 청산
"""
import config
from broker import Broker
from risk import check_buy, check_sell, daily_pl
from trade_logger import log


def execute_signal(signal, confidence):
    signal = (signal or "HOLD").upper()
    symbol = config.ACTIVE_SYMBOL

    if symbol not in config.SYMBOLS:
        log(f"⛔ 설정 오류: {symbol} 는 등록된 종목이 아닙니다 (SPY/QQQ 중 선택). 중단.")
        return

    mode = "DRY-RUN(시뮬)" if config.DRY_RUN else ("PAPER(모의투자)" if config.PAPER else "⚠️ LIVE(실거래)")
    log(f"===== 신호 처리 | {symbol}({config.SYMBOLS[symbol]['name']}) | 신호={signal} 확신도={confidence} | {mode} =====")

    try:
        broker = Broker()
        account = broker.get_account()
    except Exception as e:
        # 안전 자동 정지 (블로그의 조건3)
        log(f"⛔ 계정 연결 실패 — 안전 정지: {e}")
        return

    pl = daily_pl(account)
    log(f"계정 상태: 자산 ${account['equity']:,.0f} | 현금 ${account['cash']:,.0f} | 당일손익 {pl*100:+.2f}%")

    if not broker.is_market_open():
        log("⏸ 미국 정규장 마감 — 주문 보류 (다음 개장 때 실행)")
        return

    qty = broker.get_position_qty(symbol)
    holding = qty > 0
    log(f"현재 {symbol} 보유: {'있음 (' + str(qty) + '주)' if holding else '없음 (현금)'}")

    if signal == "BUY":
        if holding:
            log("➡ 이미 보유 중 — 추가 매수 없이 유지")
            return
        d = check_buy(account, confidence)
        log(f"🛡 리스크 게이트: {'✅ 허용' if d.allow else '⛔ 차단'} — {d.reason}")
        if d.allow:
            try:
                r = broker.buy_notional(symbol, d.notional)
                log(f"🟢 매수 주문 전송: {r}")
            except Exception as e:
                log(f"⛔ 매수 주문 실패 — 안전 정지: {e}")

    elif signal == "SELL":
        if not holding:
            log("➡ 보유 없음 — 매도할 포지션 없음")
            return
        d = check_sell(account)
        log(f"🛡 리스크 게이트: ✅ {d.reason}")
        try:
            r = broker.liquidate(symbol)
            log(f"🔴 전량 매도(청산) 전송: {r}")
        except Exception as e:
            log(f"⛔ 매도 주문 실패 — 안전 정지: {e}")

    else:  # HOLD 또는 알 수 없는 신호
        log("➡ HOLD — 동작 없음")

    log("===== 처리 완료 =====\n")
