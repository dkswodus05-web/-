"""
리스크 관리 게이트 — 신호가 나와도 여기를 통과해야 주문이 나갑니다.
AI가 틀려도 계좌가 망가지지 않게 막는 가장 중요한 층.
"""
import config


class RiskDecision:
    def __init__(self, allow, reason, notional=0.0):
        self.allow = allow
        self.reason = reason
        self.notional = notional


def daily_pl(account):
    """당일 손익률. (현재자산 - 전일종가자산) / 전일종가자산"""
    le = account.get("last_equity") or account.get("equity")
    if not le:
        return 0.0
    return (account["equity"] - le) / le


def check_buy(account, confidence):
    """매수 진입을 허용할지 결정."""
    # 1) 킬 스위치
    if config.KILL_SWITCH:
        return RiskDecision(False, "킬 스위치 ON — 모든 매수 정지")

    # 2) 확신도 임계값
    if confidence < config.MIN_CONFIDENCE:
        return RiskDecision(False, f"확신도 {confidence} < 기준 {config.MIN_CONFIDENCE} — 매수 보류")

    # 3) 일일 손실 한도
    pl = daily_pl(account)
    if pl <= -config.DAILY_LOSS_LIMIT:
        return RiskDecision(False, f"당일 손익 {pl*100:.1f}% — 손실 한도({config.DAILY_LOSS_LIMIT*100:.0f}%) 도달, 매수 정지")

    # 4) 포지션 사이징
    sym = config.SYMBOLS.get(config.ACTIVE_SYMBOL, {})
    pct = min(sym.get("target_pct", 0.20), config.MAX_POSITION_PCT)
    notional = account["equity"] * pct
    if notional < 1:
        return RiskDecision(False, "주문 금액이 너무 작음")

    return RiskDecision(True, f"통과 — 자산의 {pct*100:.0f}% (${notional:,.0f}) 매수", notional)


def check_sell(account):
    """청산(리스크 축소)은 항상 허용 — 위험을 줄이는 행동은 막지 않는다."""
    return RiskDecision(True, "청산 허용 (리스크 축소는 상시 허용)")
