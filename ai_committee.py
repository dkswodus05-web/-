"""
AI 투자위원회 (Bull / Bear / Judge) — 헤드리스(브라우저·Claude 앱 없이) 버전.

기존에는 Claude 데스크톱 앱(Cowork) 세션이 열려 있어야만 사람(에이전트)이 지표를 읽고
Bull/Bear/Judge 토론을 해서 신호를 냈다. 이 모듈은 그 판단을 Anthropic API 직접 호출로
대체해, 앱이 꺼져 있어도 PC에서 파이썬 프로그램만으로 매일 자동 실행되게 한다.

⚠️ 안전 원칙: API 키가 없거나 호출이 실패하거나 응답 형식이 이상하면
   신호를 지어내지 않고 CommitteeError를 던진다. 호출 측(daily_pipeline.py)은
   이 예외를 받으면 그날은 매매하지 않고 안전 정지해야 한다.
"""
import os
import json
import re

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5")

VALID_SIGNALS = {"BUY", "HOLD", "SELL"}


class CommitteeError(Exception):
    """AI 위원회 판단을 신뢰할 수 없을 때 발생 — 호출 측은 매매하지 않고 안전 정지해야 함."""
    pass


SYSTEM_PROMPT = """당신은 미국 증시 매크로 지표를 분석하는 AI 투자위원회입니다.
Bull(낙관), Bear(비관), Judge(심판) 세 역할을 한 번에 수행합니다.

절차:
1. Bull: 주어진 지표를 근거로 매수(BUY) 의견의 근거를 3~4개 제시.
   각 근거는 1~2문장으로, 어떤 지표의 어떤 수치가 왜(어떤 메커니즘으로) 시장에
   긍정적인지 구체적으로 설명할 것. 단순 나열이 아니라 인과관계를 풀어서 쓸 것.
2. Bear: 같은 지표를 근거로 매도/관망(SELL/HOLD) 의견의 근거를 3~4개 제시.
   Bull과 동일하게 각 근거를 1~2문장으로 구체적 수치와 인과관계를 포함해 설명할 것.
3. Judge: Bull과 Bear를 종합해 최종 신호와 확신도를 결정. 불확실하면 보수적으로 HOLD.
   또한 시장을 5단계 레짐 중 하나로 분류할 것: "공격", "균형", "중립", "방어", "위기".
   (공격=강한 위험선호, 균형=완만한 우상향, 중립=방향성 불분명, 방어=위험 신호 누적, 위기=급락 위험)
   불확실하면 한 단계 보수적인(현금 비중이 큰) 레짐을 택할 것.
   note는 2~3문장으로, 왜 이 신호·레짐·확신도를 택했는지 핵심 논리를 설명할 것.
4. Alpha 브리핑(참고용, 자동매매에 사용되지 않음): 전략 유니버스 종목
   SPY, QQQ, QLD, TQQQ, GLD 각각에 대해 현재 매크로 환경에서의 시각을 1문장으로.
   stance는 "긍정"/"중립"/"부정" 중 하나. 레버리지 ETF(QLD·TQQQ)는 변동성 위험을 반드시 언급.

이 시스템은 투자 자문이 아니라 도구의 출력입니다. 반드시 아래 JSON 형식으로만,
다른 설명 텍스트 없이 응답하세요:
{
  "bull": ["구체적 근거 문장1", "구체적 근거 문장2", "구체적 근거 문장3"],
  "bear": ["구체적 근거 문장1", "구체적 근거 문장2", "구체적 근거 문장3"],
  "signal": "BUY 또는 HOLD 또는 SELL 중 하나",
  "regime": "공격/균형/중립/방어/위기 중 하나",
  "confidence": 0에서 100 사이 정수,
  "note": "Judge의 종합 판단 (2~3문장)",
  "alpha": [
    {"symbol": "SPY", "stance": "긍정/중립/부정", "view": "1문장 시각"},
    {"symbol": "QQQ", "stance": "...", "view": "..."},
    {"symbol": "QLD", "stance": "...", "view": "..."},
    {"symbol": "TQQQ", "stance": "...", "view": "..."},
    {"symbol": "GLD", "stance": "...", "view": "..."}
  ]
}"""


def _build_user_prompt(indicators_payload):
    inds = indicators_payload.get("indicators", {})
    lines = []
    for name, v in inds.items():
        val = v.get("value")
        if val is not None:
            lines.append(f"- {name}: {val} ({v.get('desc', '')})")
        else:
            lines.append(f"- {name}: (데이터 없음)")
    missing = indicators_payload.get("missing", [])
    tail = f"\n(누락 지표: {', '.join(missing)})" if missing else ""
    return "오늘의 미국 증시 매크로 지표:\n" + "\n".join(lines) + tail


def decide(indicators_payload):
    """
    indicators_payload: fred_collector.collect()의 반환값(dict).
    반환: {"signal":..., "confidence":..., "note":..., "bull":[...], "bear":[...]}
    실패 시 CommitteeError를 던진다 (신호를 지어내지 않음).
    """
    if not ANTHROPIC_API_KEY:
        raise CommitteeError("ANTHROPIC_API_KEY가 없습니다 — .env에 키를 넣어야 AI 위원회를 호출할 수 있습니다.")

    try:
        import anthropic
    except ImportError:
        raise CommitteeError("anthropic 패키지가 설치되지 않았습니다 (pip install anthropic).")

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    user_prompt = _build_user_prompt(indicators_payload)

    try:
        resp = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=8192,  # claude-sonnet-5는 답변 전에 내부적으로 생각하는 토큰도
                              # 이 한도 안에서 쓰기 때문에, 레짐+Alpha 브리핑까지 요청하는
                              # 지금 프롬프트에서는 여유 있게 잡아야 JSON이 중간에 잘리지 않는다.
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )
        # 모델이 답변 앞에 "thinking" 블록을 먼저 보낼 수도 있으므로,
        # content[0]으로 단정하지 않고 실제 text 블록들만 골라 이어붙인다.
        text_parts = [b.text for b in resp.content if getattr(b, "type", None) == "text"]
        text = "".join(text_parts).strip()
        if not text:
            raise CommitteeError(f"응답에 text 블록이 없음 (블록 타입: {[getattr(b,'type',None) for b in resp.content]})")
        if getattr(resp, "stop_reason", None) == "max_tokens":
            raise CommitteeError(
                f"응답이 max_tokens({8192}) 한도에 걸려 중간에 잘림 — "
                f"근거 문장을 줄이거나 max_tokens를 더 늘려야 함. 잘린 원문 뒷부분: ...{text[-200:]}"
            )
    except CommitteeError:
        raise
    except Exception as e:
        raise CommitteeError(f"Anthropic API 호출 실패: {e}")

    # 응답이 ```json ... ``` 코드블록으로 감싸져 오는 경우까지 대비해 JSON 부분만 추출
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        raise CommitteeError(f"응답에서 JSON을 찾지 못함: {text[:200]}")

    try:
        data = json.loads(m.group(0))
    except json.JSONDecodeError as e:
        raise CommitteeError(
            f"응답 JSON 파싱 실패: {e} | stop_reason={getattr(resp,'stop_reason',None)} | "
            f"원문 앞부분: {text[:200]} | 원문 뒷부분: ...{text[-200:]}"
        )

    signal = str(data.get("signal", "")).upper()
    if signal not in VALID_SIGNALS:
        raise CommitteeError(f"AI가 알 수 없는 신호를 냄: {data.get('signal')!r}")

    try:
        confidence = int(data.get("confidence"))
    except (TypeError, ValueError):
        raise CommitteeError(f"확신도가 숫자가 아님: {data.get('confidence')!r}")
    if not (0 <= confidence <= 100):
        raise CommitteeError(f"확신도 범위 오류: {confidence}")

    def _clean_points(points):
        """근거 리스트를 안전하게 정리: 문자열만, 항목당 400자, 최대 5개."""
        if not isinstance(points, list):
            return []
        return [str(p)[:400] for p in points[:5]]

    # 레짐 검증 (Phase 7 리밸런싱용) — 잘못된 값이면 신호를 지어내지 않고 안전 정지.
    # 단, REBALANCE_MODE가 꺼져 있으면 레짐이 없어도 기존 방식으로 동작해야 하므로 None 허용.
    import config as _config
    regime = data.get("regime")
    if regime is not None:
        regime = str(regime).strip()
        if regime not in _config.VALID_REGIMES:
            raise CommitteeError(f"AI가 알 수 없는 레짐을 냄: {data.get('regime')!r} (허용: {sorted(_config.VALID_REGIMES)})")
    elif _config.REBALANCE_MODE:
        raise CommitteeError("리밸런싱 모드인데 AI 응답에 regime이 없음 — 안전 정지")

    def _clean_alpha(items):
        """Alpha 브리핑(참고용) 정리: 형식이 이상하면 그 항목만 버린다 — 매매에 안 쓰이므로 관대하게."""
        out = []
        if not isinstance(items, list):
            return out
        for it in items[:10]:
            if not isinstance(it, dict):
                continue
            sym = str(it.get("symbol", "")).upper()[:10]
            stance = str(it.get("stance", "중립"))[:10]
            view = str(it.get("view", ""))[:300]
            if sym and view:
                out.append({"symbol": sym, "stance": stance, "view": view})
        return out

    return {
        "signal": signal,
        "confidence": confidence,
        "note": str(data.get("note", ""))[:500],
        "bull": _clean_points(data.get("bull", [])),
        "bear": _clean_points(data.get("bear", [])),
        "regime": regime,
        "alpha": _clean_alpha(data.get("alpha", [])),
    }
