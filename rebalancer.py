"""
멀티에셋 레짐 리밸런싱 실행기 (Phase 7).

기존 executor.py(단일 종목 보유↔현금 스위칭)를 대체하는 것이 아니라 별도 경로다.
config.REBALANCE_MODE=true일 때만 daily_pipeline이 이쪽을 탄다.

동작:
  AI 위원회가 낸 레짐(공격·균형·중립·방어·위기) → config.REGIME_WEIGHTS의 목표 비중
  → 현재 보유 비중과 비교 → 밴드(REBALANCE_BAND)를 벗어난 종목만 매매.

원칙 (기존 리스크 게이트 계승):
  - 매도(비중 축소·유니버스 미포함 정리)는 항상 허용 — 위험을 줄이는 행동은 막지 않는다.
  - 매수(비중 확대)는 킬스위치 OFF + 확신도 기준 + 일일 손실 한도를 모두 통과해야 한다.
  - 종목별 상한 = min(UNIVERSE의 max_pct, MAX_POSITION_PCT).
  - 계좌·포지션 조회 실패 시 매매하지 않고 안전 정지.
"""
import time
import config
import telegram_notifier
from broker import Broker
from risk import daily_pl
from sanity import check_account_sanity
from trade_logger import log

MIN_ORDER_NOTIONAL = 10.0  # 이보다 작은 주문은 스킵 (의미 없는 잔돈 매매 방지)


def _base_result(regime, confidence, mode):
    return {
        "strategy": "REBALANCE",
        "regime": regime,
        "signal": f"REBAL({regime})",   # 기존 기록 형식과의 호환용 표기
        "confidence": confidence,
        "symbol": None,
        "action": "NONE",
        "status": "UNKNOWN",
        "detail": "",
        "equity": None,
        "cash": None,
        "holding_qty": 0.0,
        "notional": 0.0,
        "mode": mode,
        "holdings": [],   # [{symbol, qty, market_value, weight}]
        "trades": [],     # [{symbol, action, notional, status, detail}]
    }


def _buys_allowed(account, confidence):
    """매수(비중 확대) 허용 여부 — 기존 리스크 게이트와 동일한 3중 검사."""
    if config.KILL_SWITCH:
        return False, "킬 스위치 ON — 모든 매수 정지"
    if confidence < config.MIN_CONFIDENCE:
        return False, f"확신도 {confidence} < 기준 {config.MIN_CONFIDENCE} — 매수 보류(매도만 수행)"
    pl = daily_pl(account)
    if pl <= -config.DAILY_LOSS_LIMIT:
        return False, f"당일 손익 {pl*100:.1f}% — 손실 한도 도달, 매수 정지(매도만 수행)"
    return True, "매수 허용"


def _snapshot_holdings(positions, equity):
    out = []
    for sym, p in sorted(positions.items()):
        w = (p["market_value"] / equity) if equity else 0.0
        out.append({"symbol": sym, "qty": p["qty"], "market_value": round(p["market_value"], 2),
                    "weight": round(w, 4)})
    return out


def execute_rebalance(regime, confidence):
    mode = "DRY-RUN(시뮬)" if config.DRY_RUN else ("PAPER(모의투자)" if config.PAPER else "⚠️ LIVE(실거래)")
    result = _base_result(regime, confidence, mode)

    if regime not in config.VALID_REGIMES:
        log(f"⛔ 알 수 없는 레짐: {regime!r} — 안전 정지(매매 안 함)")
        result["status"] = "INVALID_REGIME"
        result["detail"] = f"알 수 없는 레짐: {regime!r}"
        return result

    log(f"===== 리밸런싱 | 레짐={regime} 확신도={confidence} | {mode} =====")

    # 1) 계좌·보유 조회 (실패 시 안전 정지, 휴장 여부와 무관하게 먼저 조회)
    try:
        broker = Broker()
        account = broker.get_account()
        positions = broker.get_positions()
    except Exception as e:
        log(f"⛔ 계좌/포지션 조회 실패 — 안전 정지: {e}")
        result["status"] = "ACCOUNT_ERROR"
        result["detail"] = str(e)
        return result

    equity = account["equity"]
    result["equity"] = equity
    result["cash"] = account["cash"]
    result["holdings"] = _snapshot_holdings(positions, equity)

    pl = daily_pl(account)
    log(f"계정 상태: 자산 ${equity:,.0f} | 현금 ${account['cash']:,.0f} | 당일손익 {pl*100:+.2f}%")
    if positions:
        for h in result["holdings"]:
            log(f"보유: {h['symbol']} {h['qty']}주 (${h['market_value']:,.0f}, {h['weight']*100:.1f}%)")
    else:
        log("보유: 없음 (전량 현금)")

    # 1.5) 계좌 급변 감지 (2026-07-07 Alpaca 글리치 대응) — executor와 동일한 안전장치.
    # 브로커 응답이 직전 기록과 크게 어긋나면 그 데이터로는 리밸런싱하지 않는다.
    total_qty = sum(float(p.get("qty") or 0) for p in positions.values())
    sane, why = check_account_sanity(equity, total_qty)
    if not sane:
        log(f"⛔ 계좌 급변 감지 — 브로커 데이터 신뢰 불가, 오늘 리밸런싱 중단: {why}")
        result["status"] = "SANITY_BLOCKED"
        result["detail"] = f"계좌 급변 감지 — 리밸런싱 중단: {why}"
        # 의심스러운 스냅샷은 기록하지 않는다 (히스토리·대시보드 오염 방지)
        result["equity"] = None
        result["cash"] = None
        result["holdings"] = []
        telegram_notifier.notify_error(
            "계좌 급변 감지",
            f"{why}\n오늘 리밸런싱을 중단했습니다. Alpaca 계좌를 직접 확인해보세요. "
            f"(브로커 일시 오류라면 다음 실행에서 자동 복구됩니다)")
        return result

    # 2) 장 마감이면 주문 보류 (보유 현황은 위에서 이미 기록됨)
    if not broker.is_market_open():
        log("⏸ 미국 정규장 마감 — 리밸런싱 보류 (다음 개장 때 실행)")
        result["status"] = "MARKET_CLOSED"
        result["detail"] = "미국 정규장 마감 — 리밸런싱 보류"
        return result

    # 3) 목표 비중 계산 (종목별 상한 적용)
    targets = {}
    for sym, w in config.REGIME_WEIGHTS[regime].items():
        cap = min(config.UNIVERSE.get(sym, {}).get("max_pct", 0.0), config.MAX_POSITION_PCT)
        targets[sym] = min(w, cap)
    log("목표 비중: " + ", ".join(f"{s} {w*100:.0f}%" for s, w in targets.items())
        + f" | 현금 {max(0.0, 1 - sum(targets.values()))*100:.0f}%")

    allowed, gate_reason = _buys_allowed(account, confidence)
    log(f"🛡 리스크 게이트(매수): {'✅ ' if allowed else '⛔ '}{gate_reason}")

    # 4) 매매 계획 수립
    sells, buys = [], []   # (symbol, notional, 사유)  notional=None이면 전량 청산
    held_syms = set(positions.keys())

    # 4-1) 유니버스에 없는 보유 종목 → 전량 정리 (항상 허용)
    for sym in sorted(held_syms):
        if sym not in config.UNIVERSE:
            sells.append((sym, None, "전략 유니버스 미포함 → 포지션 정리"))

    # 4-2) 유니버스 종목: 현재 비중 vs 목표 비중
    for sym in sorted(set(targets) | (held_syms & set(config.UNIVERSE))):
        cur_mv = positions.get(sym, {}).get("market_value", 0.0)
        cur_w = cur_mv / equity if equity else 0.0
        tgt_w = targets.get(sym, 0.0)
        diff = tgt_w - cur_w
        if tgt_w == 0.0 and cur_mv > 0:
            sells.append((sym, None, f"레짐 {regime}에서 목표 0% → 전량 정리"))
        elif diff <= -config.REBALANCE_BAND:
            sells.append((sym, -diff * equity, f"비중 축소 {cur_w*100:.1f}%→{tgt_w*100:.0f}%"))
        elif diff >= config.REBALANCE_BAND:
            buys.append((sym, diff * equity, f"비중 확대 {cur_w*100:.1f}%→{tgt_w*100:.0f}%"))
        else:
            log(f"↔ {sym}: 현재 {cur_w*100:.1f}% ≈ 목표 {tgt_w*100:.0f}% (밴드 {config.REBALANCE_BAND*100:.0f}%p 이내) — 유지")

    # 5) 매도 먼저 실행 (리스크 축소 우선, 매수 현금 확보)
    def _record(sym, action, notional, status, detail):
        result["trades"].append({"symbol": sym, "action": action,
                                 "notional": round(notional, 2) if notional else None,
                                 "status": status, "detail": detail})

    for sym, notional, reason in sells:
        try:
            if notional is None:
                r = broker.liquidate(sym)
                log(f"🔴 전량 매도 {sym}: {reason} → {r}")
                _record(sym, "SELL", positions.get(sym, {}).get("market_value"), str(r.get("status")), reason)
            else:
                if notional < MIN_ORDER_NOTIONAL:
                    log(f"↔ {sym}: 매도 금액 ${notional:,.0f} 너무 작음 — 스킵")
                    continue
                r = broker.sell_notional(sym, notional)
                log(f"🔴 부분 매도 {sym} ${notional:,.0f}: {reason} → {r}")
                _record(sym, "SELL", notional, str(r.get("status")), reason)
        except Exception as e:
            log(f"⛔ 매도 실패 {sym} (계속 진행): {e}")
            _record(sym, "SELL", notional, "FAILED", str(e))

    # 6) 매수 실행 (게이트 통과 시에만, 매도 반영된 현금 한도 내에서)
    if buys and allowed:
        if sells and not config.DRY_RUN:
            time.sleep(2)  # 매도 체결·현금 반영 대기
            try:
                account = broker.get_account()
            except Exception as e:
                log(f"⛔ 매도 후 계좌 재조회 실패 — 매수 중단(안전 정지): {e}")
                buys = []
        cash_avail = account["cash"] * 0.98  # 체결가 변동 여유 2%
        total_buy = sum(n for _, n, _ in buys)
        scale = min(1.0, cash_avail / total_buy) if total_buy > 0 else 0.0
        if scale < 1.0:
            log(f"현금 한도로 매수 규모 축소: 계획 ${total_buy:,.0f} → 가용 ${cash_avail:,.0f} (x{scale:.2f})")
        for sym, notional, reason in buys:
            n = notional * scale
            if n < MIN_ORDER_NOTIONAL:
                log(f"↔ {sym}: 매수 금액 ${n:,.0f} 너무 작음 — 스킵")
                continue
            try:
                r = broker.buy_notional(sym, n)
                log(f"🟢 매수 {sym} ${n:,.0f}: {reason} → {r}")
                _record(sym, "BUY", n, str(r.get("status")), reason)
            except Exception as e:
                log(f"⛔ 매수 실패 {sym} — 이후 매수 중단(안전 정지): {e}")
                _record(sym, "BUY", n, "FAILED", str(e))
                break
    elif buys and not allowed:
        for sym, notional, reason in buys:
            log(f"⛔ 매수 보류 {sym} (${notional:,.0f}): {gate_reason}")
            _record(sym, "BUY", notional, "BLOCKED", gate_reason)

    # 7) 매매 후 상태 재조회 → 결과에 최종 보유 반영
    if result["trades"] and not config.DRY_RUN:
        try:
            time.sleep(2)
            account = broker.get_account()
            positions = broker.get_positions()
            result["equity"] = account["equity"]
            result["cash"] = account["cash"]
            result["holdings"] = _snapshot_holdings(positions, account["equity"])
        except Exception as e:
            log(f"⚠️ 매매 후 상태 재조회 실패(주문 자체는 이미 처리됨): {e}")

    executed = [t for t in result["trades"] if t["status"] not in ("BLOCKED", "FAILED")]
    result["action"] = "REBALANCE" if executed else "NONE"
    result["status"] = "OK" if executed else ("NO_TRADES" if not result["trades"] else "PARTIAL")
    result["detail"] = f"레짐 {regime} — 매매 {len(executed)}건 실행" if executed else f"레짐 {regime} — 매매 없음"
    log(f"===== 리밸런싱 완료: {result['detail']} =====\n")
    return result
