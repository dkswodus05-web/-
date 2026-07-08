"""
텔레그램 알림 — 매일 파이프라인 결과·에러를 폰으로 보내주는 소식통.

설정 (환경변수, Railway Variables 또는 .env):
  TELEGRAM_BOT_TOKEN : @BotFather 에서 봇 만들면 주는 토큰
  TELEGRAM_CHAT_ID   : 내 대화방 ID (봇에게 아무 말이나 보낸 뒤
                       https://api.telegram.org/bot<토큰>/getUpdates 에서 chat.id 확인)

설계 원칙:
  - 알림은 부가 기능. 토큰이 없거나 전송이 실패해도 파이프라인을 절대 막지 않는다.
  - 표준 라이브러리만 사용 (추가 패키지 설치 불필요).
"""
import os
import json
from urllib.request import Request, urlopen

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()


def enabled():
    return bool(BOT_TOKEN and CHAT_ID)


def send(text):
    """텔레그램으로 메시지 전송. 성공 True / 실패·미설정 False. 예외를 밖으로 던지지 않는다."""
    if not enabled():
        return False
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = json.dumps({
            "chat_id": CHAT_ID,
            "text": text[:4000],          # 텔레그램 한도(4096자) 안전 마진
        }).encode("utf-8")
        req = Request(url, data=payload, headers={"Content-Type": "application/json"})
        with urlopen(req, timeout=15) as r:
            return json.load(r).get("ok", False)
    except Exception:
        return False


_DIR = os.path.dirname(os.path.abspath(__file__))

# 브리핑에 보여줄 주요 지표 (indicators.json의 키 일부와 부분 일치)
_KEY_INDICATORS = ["장단기_금리차", "VIX", "S&P500", "나스닥", "연준기준금리",
                   "기대인플레이션", "하이일드", "실업률"]


def _read_json(filename):
    try:
        with open(os.path.join(_DIR, filename), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def notify_result(result):
    """오늘의 결과를 블로그식 '데일리 브리핑'으로 전송.
    signal.json(토론 내용)과 indicators.json(지표)을 읽어 살을 붙인다."""
    if not enabled() or not isinstance(result, dict):
        return False
    sig = result.get("signal", "?")
    conf = result.get("confidence", "?")
    emoji = "🔄" if str(sig).startswith("REBAL") else {"BUY": "🟢", "HOLD": "🟡", "SELL": "🔴"}.get(sig, "⚪")
    signal_data = _read_json("signal.json") or {}
    ind_data = _read_json("indicators.json") or {}

    lines = [f"{emoji} Signal Invest Pro — 데일리 브리핑",
             f"⚖️ 신호: {sig} (확신도 {conf}) · {result.get('mode', '?')}"]
    if signal_data.get("regime"):
        lines[-1] += f" · 레짐 {signal_data['regime']}"
    if signal_data.get("note"):
        lines.append(f"📝 판결: {signal_data['note'][:400]}")

    # 주요 지표
    inds = ind_data.get("indicators") or {}
    picked = []
    for want in _KEY_INDICATORS:
        for name, v in inds.items():
            if want in name and isinstance(v, dict) and v.get("value") is not None:
                picked.append(f"· {name}: {v['value']}")
                break
    if picked:
        lines.append("\n📊 주요 지표")
        lines.extend(picked)

    # Bull / Bear 토론
    for key, head in (("bull", "🐂 낙관(Bull)"), ("bear", "🐻 비관(Bear)")):
        points = signal_data.get(key) or []
        if points:
            lines.append(f"\n{head}")
            lines.extend(f"· {str(p)[:300]}" for p in points[:4])

    # 주문 / 계좌
    lines.append("\n💼 실행 결과")
    action = result.get("action")
    trades = result.get("trades")
    if trades:
        for t in trades:
            lines.append(f"주문: {t.get('action')} {t.get('symbol')} ${t.get('notional')} — {t.get('status')}")
    elif action in ("BUY", "SELL"):
        lines.append(f"주문: {action} {result.get('symbol')} ${result.get('notional')} — {result.get('status')}")
    else:
        lines.append(f"주문: 없음 ({result.get('detail') or '유지'})")

    if result.get("equity") is not None:
        eq, cash = result.get("equity"), result.get("cash")
        qty = result.get("holding_qty")
        lines.append(f"계좌: 평가 ${eq:,.2f} · 현금 ${cash:,.2f}" if isinstance(eq, (int, float)) and isinstance(cash, (int, float))
                     else f"계좌: 평가 {eq} · 현금 {cash}")
        holdings = result.get("holdings")
        if isinstance(holdings, list) and holdings:
            # 리밸런싱 모드: 보유 종목 전체를 비중과 함께 표시
            for h in holdings:
                try:
                    lines.append(f"보유: {h.get('symbol')} {float(h.get('qty') or 0):,.3f}주 "
                                 f"(${float(h.get('market_value') or 0):,.0f} · {float(h.get('weight') or 0)*100:.1f}%)")
                except (TypeError, ValueError):
                    lines.append(f"보유: {h.get('symbol')} {h.get('qty')}주")
        elif qty:
            lines.append(f"보유: {result.get('symbol')} {qty}주")
    return send("\n".join(lines))


def notify_error(stage, message):
    """안전 정지·오류 알림. stage: 어느 단계에서 멈췄는지."""
    return send(f"⛔ Signal Invest Pro — 안전 정지\n단계: {stage}\n사유: {str(message)[:500]}")


if __name__ == "__main__":
    # 수동 테스트: python telegram_notifier.py
    if not enabled():
        print("TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID 가 설정되지 않았습니다.")
    else:
        ok = send("✅ 텔레그램 연동 테스트 — Signal Invest Pro")
        print("전송 성공" if ok else "전송 실패 (토큰/chat_id 확인)")
