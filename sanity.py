"""
계좌 급변 감지 — 브로커(Alpaca)가 일시적으로 잘못된 계좌 상태를 응답할 때
그 데이터로 매매하지 않도록 막는 안전장치.

배경(2026-07-07): Alpaca 페이퍼가 매도 기록 없이 "포지션 없음, 자산=현금"으로
잘못 응답한 사례가 있었다. 그 순간 신호가 BUY였다면 중복 매수가 나갈 뻔했다.

판정 기준 (직전 기록은 상태 Gist의 account_history.json에서 가져온다):
  1. 자산이 직전 정상 기록 대비 ±15% 넘게 급변           → 이상
  2. 직전엔 보유가 있었는데, 매도 기록 없이 보유가 사라짐 → 이상

이상이면: 오늘 매매 전체 중단(매수·매도 모두). "데이터 오류 시 즉시 멈춤" 원칙.
확인이 불가능하면(Gist 미설정·통신 실패 등): 체크 없이 통과 —
이 안전장치가 새로운 단일 장애점이 되면 안 되기 때문 (fail-open).
"""
import json

import publish_status
from trade_logger import log

# 직전 기록 대비 이 비율(±)을 넘는 자산 변동은 "하루 시장 변동"으로 보기 어려움
EQUITY_JUMP_LIMIT = 0.15


def _cleaned_history(history):
    """대시보드와 같은 기준으로 이상치를 거른다:
    앞뒤 기록과 모두 15% 이상 동떨어진 스파이크(과거의 글리치 기록)는 비교 기준에서 제외."""
    out = []
    n = len(history)
    for i, h in enumerate(history):
        try:
            eq = float(h.get("equity") or 0)
        except (TypeError, ValueError):
            continue
        if eq <= 0:
            continue
        prev_eq = next_eq = None
        if i > 0:
            try:
                prev_eq = float(history[i - 1].get("equity") or 0) or None
            except (TypeError, ValueError):
                pass
        if i < n - 1:
            try:
                next_eq = float(history[i + 1].get("equity") or 0) or None
            except (TypeError, ValueError):
                pass
        if prev_eq and next_eq:
            dp = abs(eq - prev_eq) / prev_eq
            dn = abs(eq - next_eq) / next_eq
            if dp > EQUITY_JUMP_LIMIT and dn > EQUITY_JUMP_LIMIT:
                continue
        out.append(h)
    return out


def check_account_sanity(equity, holding_qty):
    """현재 브로커 응답(자산, 보유수량)이 믿을 만한지 직전 기록과 비교.
    반환: (정상여부 bool, 사유 str). 정상이면 True."""
    try:
        existing = publish_status.fetch_existing_files()
        try:
            history = json.loads(existing.get("account_history.json") or "[]")
        except Exception:
            history = []
        try:
            trades = json.loads(existing.get("trade_history.json") or "[]")
        except Exception:
            trades = []
        if not isinstance(history, list) or not history:
            return True, "직전 기록 없음 — 체크 생략"

        cleaned = _cleaned_history(history)
        prev = cleaned[-1] if cleaned else None
        if not prev:
            return True, "비교할 정상 기록 없음 — 체크 생략"

        # 1) 자산 급변
        prev_eq = float(prev.get("equity") or 0)
        if prev_eq > 0 and equity is not None:
            jump = abs(float(equity) - prev_eq) / prev_eq
            if jump > EQUITY_JUMP_LIMIT:
                return False, (f"자산 급변: 직전 ${prev_eq:,.0f} → 현재 ${float(equity):,.0f} "
                               f"({jump * 100:.1f}% 변동, 한도 {EQUITY_JUMP_LIMIT * 100:.0f}%)")

        # 2) 매도 기록 없이 보유 소실
        # (리밸런싱 모드 기록은 holding_qty 대신 holdings 배열을 쓰므로 둘 다 지원)
        prev_qty = float(prev.get("holding_qty") or 0)
        if prev_qty <= 0 and isinstance(prev.get("holdings"), list):
            prev_qty = sum(float(h.get("qty") or 0) for h in prev["holdings"] if isinstance(h, dict))
        if prev_qty > 0 and float(holding_qty or 0) <= 0:
            prev_ts = prev.get("ts") or ""
            sold_since = any(
                t.get("action") == "SELL" and (t.get("ts") or "") >= prev_ts
                for t in trades if isinstance(t, dict)
            )
            if not sold_since:
                return False, f"매도 기록 없이 보유 소실: 직전 {prev_qty}주 → 현재 0주"

        return True, "정상"
    except Exception as e:
        # 체크 자체가 실패하면 매매를 막지 않는다 (fail-open)
        log(f"⚠️ 계좌 급변 감지 체크 실패 — 무시하고 진행: {e}")
        return True, f"체크 실패 — 통과 처리: {e}"
