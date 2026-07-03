"""
신호 실행기 — 신호를 받아 안전장치를 거쳐 실제 매매로 변환.
전략: ETF 하나에 대해 '들어가 있느냐(보유) / 현금이냐'를 신호로 스위칭.
  BUY  → 미보유면 매수, 보유면 유지
  HOLD → 아무것도 안 함
  SELL → 보유면 전량 청산
"""
import time
import config
from broker import Broker
from risk import check_buy, check_sell, daily_pl
from trade_logger import log


def _refresh_after_trade(broker, symbol, result):
    """매수/매도 주문을 넣은 직후, 계좌·보유수량을 다시 조회해 result에 반영한다.
    주문 전에 읽어둔 계좌 상태를 그대로 쓰면 '방금 산 게 보유현황에 안 보이는' 문제가
    생기므로, 체결이 즉시 반영되도록 잠깐 기다렸다가 다시 읽는다.
    실패해도 조용히 넘어간다 — 이미 주문 자체는 성공했으므로 매매를 막을 이유는 아님."""
    try:
        time.sleep(2)  # Alpaca 체결 반영 시간 대기
        acc = broker.get_account()
        result["equity"] = acc.get("equity")
        result["cash"] = acc.get("cash")
        result["holding_qty"] = broker.get_position_qty(symbol)
    except Exception as e:
        log(f"⚠️ 체결 후 계좌 상태 갱신 실패(주문 자체는 이미 성공): {e}")


def _base_result(signal, confidence, symbol, mode):
    """모든 경로에서 공통으로 채우는 결과 뼈대."""
    return {
        "symbol": symbol,
        "signal": signal,
        "confidence": confidence,
        "action": "NONE",
        "status": "UNKNOWN",
        "detail": "",
        "equity": None,
        "cash": None,
        "holding_qty": 0.0,
        "notional": 0.0,
        "mode": mode,
    }


def execute_signal(signal, confidence):
    signal = (signal or "HOLD").upper()
    symbol = config.ACTIVE_SYMBOL
    mode = "DRY-RUN(시뮬)" if config.DRY_RUN else ("PAPER(모의투자)" if config.PAPER else "⚠️ LIVE(실거래)")
    result = _base_result(signal, confidence, symbol, mode)

    if symbol not in config.SYMBOLS:
        log(f"⛔ 설정 오류: {symbol} 는 등록된 종목이 아닙니다 (SPY/QQQ 중 선택). 중단.")
        result["status"] = "CONFIG_ERROR"
        result["detail"] = f"{symbol} 는 등록된 종목이 아닙니다"
        return result

    log(f"===== 신호 처리 | {symbol}({config.SYMBOLS[symbol]['name']}) | 신호={signal} 확신도={confidence} | {mode} =====")

    try:
        broker = Broker()
        account = broker.get_account()
    except Exception as e:
        # 안전 자동 정지 (블로그의 조건3)
        log(f"⛔ 계정 연결 실패 — 안전 정지: {e}")
        result["status"] = "ACCOUNT_ERROR"
        result["detail"] = str(e)
        return result

    result["equity"] = account.get("equity")
    result["cash"] = account.get("cash")

    pl = daily_pl(account)
    log(f"계정 상태: 자산 ${account['equity']:,.0f} | 현금 ${account['cash']:,.0f} | 당일손익 {pl*100:+.2f}%")

    if not broker.is_market_open():
        log("⏸ 미국 정규장 마감 — 주문 보류 (다음 개장 때 실행)")
        result["status"] = "MARKET_CLOSED"
        result["detail"] = "미국 정규장 마감 — 주문 보류"
        return result

    qty = broker.get_position_qty(symbol)
    holding = qty > 0
    result["holding_qty"] = qty
    log(f"현재 {symbol} 보유: {'있음 (' + str(qty) + '주)' if holding else '없음 (현금)'}")

    if signal == "BUY":
        if holding:
            log("➡ 이미 보유 중 — 추가 매수 없이 유지")
            result["status"] = "ALREADY_HOLDING"
            result["detail"] = "이미 보유 중 — 추가 매수 없이 유지"
            return result
        d = check_buy(account, confidence)
        log(f"🛡 리스크 게이트: {'✅ 허용' if d.allow else '⛔ 차단'} — {d.reason}")
        if d.allow:
            try:
                r = broker.buy_notional(symbol, d.notional)
                log(f"🟢 매수 주문 전송: {r}")
                result["action"] = "BUY"
                result["status"] = "OK"
                result["detail"] = d.reason
                result["notional"] = d.notional
                _refresh_after_trade(broker, symbol, result)
            except Exception as e:
                log(f"⛔ 매수 주문 실패 — 안전 정지: {e}")
                result["status"] = "ORDER_FAILED"
                result["detail"] = str(e)
        else:
            result["status"] = "BLOCKED"
            result["detail"] = d.reason

    elif signal == "SELL":
        if not holding:
            log("➡ 보유 없음 — 매도할 포지션 없음")
            result["status"] = "NO_POSITION"
            result["detail"] = "보유 없음 — 매도할 포지션 없음"
            return result
        d = check_sell(account)
        log(f"🛡 리스크 게이트: ✅ {d.reason}")
        try:
            r = broker.liquidate(symbol)
            log(f"🔴 전량 매도(청산) 전송: {r}")
            result["action"] = "SELL"
            result["status"] = "OK"
            result["detail"] = d.reason
            _refresh_after_trade(broker, symbol, result)
        except Exception as e:
            log(f"⛔ 매도 주문 실패 — 안전 정지: {e}")
            result["status"] = "ORDER_FAILED"
            result["detail"] = str(e)

    else:  # HOLD 또는 알 수 없는 신호
        log("➡ HOLD — 동작 없음")
        result["status"] = "HOLD"
        result["detail"] = "HOLD — 동작 없음"

    log("===== 처리 완료 =====\n")
    return result
