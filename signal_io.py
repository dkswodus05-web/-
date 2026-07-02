"""
신호 입출력 모듈 — 대시보드와 트레이더를 잇는 다리 (Phase 3).

대시보드(브라우저)가 낸 판단을 signal.json 파일로 주고받습니다.
사람이 BUY/HOLD/SELL과 확신도 숫자를 손으로 옮겨적지 않아도
트레이더가 이 파일을 읽어 그대로 실행합니다.

signal.json 형식:
{
  "signal": "BUY",          # BUY / HOLD / SELL
  "confidence": 72,         # 0~100
  "symbol": "SPY",          # (선택) SPY / QQQ
  "created_at": "2026-06-26T08:30:00",  # ISO 시각
  "note": "..."             # (선택) Judge 요약 등 메모
}

⚠️ 안전 원칙: 파일이 없거나 형식이 이상하거나 너무 오래된 신호면
   '동작 없음(HOLD)'으로 안전하게 처리합니다. (AI가 틀려도 계좌가 안 터지게)
"""
import os
import json
import datetime

# signal.json은 이 모듈과 같은 폴더에 둡니다.
SIGNAL_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "signal.json")

VALID_SIGNALS = {"BUY", "HOLD", "SELL"}

# 신호가 이 시간보다 오래되면 신뢰하지 않고 HOLD 처리 (분)
MAX_AGE_MINUTES = 60 * 24  # 24시간 (일 1회 매매 주기에 맞춤)


class SignalError(Exception):
    """신호 파일이 없거나 형식/신선도 검증에 실패하면 발생."""
    pass


def write_signal(signal, confidence, symbol=None, note="", bull=None, bear=None):
    """신호를 signal.json으로 저장 (대시보드 대신 코드로 만들 때 사용).
    bull/bear: (선택) AI 위원회의 낙관/비관 근거 문자열 리스트. IDE의 토론 근거 표시에 쓰인다."""
    signal = (signal or "HOLD").upper()
    if signal not in VALID_SIGNALS:
        raise SignalError(f"알 수 없는 신호: {signal} (BUY/HOLD/SELL 중 하나여야 함)")
    try:
        confidence = int(confidence)
    except (TypeError, ValueError):
        raise SignalError(f"확신도가 숫자가 아닙니다: {confidence!r}")
    if not (0 <= confidence <= 100):
        raise SignalError(f"확신도 범위 오류: {confidence} (0~100)")

    data = {
        "signal": signal,
        "confidence": confidence,
        "created_at": datetime.datetime.now().isoformat(timespec="seconds"),
    }
    if symbol:
        data["symbol"] = str(symbol).upper()
    if note:
        data["note"] = str(note)
    if bull:
        data["bull"] = [str(x) for x in bull]
    if bear:
        data["bear"] = [str(x) for x in bear]

    with open(SIGNAL_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return data


def read_signal(path=None, max_age_minutes=MAX_AGE_MINUTES):
    """
    signal.json을 읽고 검증해서 (signal, confidence, data) 반환.
    문제가 있으면 SignalError를 던집니다 — 호출 측에서 잡아 안전 정지하세요.
    """
    path = path or SIGNAL_FILE

    if not os.path.exists(path):
        raise SignalError(f"신호 파일이 없습니다: {path}")

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise SignalError(f"신호 파일 형식 오류(JSON 파싱 실패): {e}")

    if not isinstance(data, dict):
        raise SignalError("신호 파일이 객체(JSON object) 형식이 아닙니다")

    # 신호 값 검증
    signal = str(data.get("signal", "")).upper()
    if signal not in VALID_SIGNALS:
        raise SignalError(f"신호 값 오류: {data.get('signal')!r} (BUY/HOLD/SELL 중 하나여야 함)")

    # 확신도 검증
    try:
        confidence = int(data.get("confidence", 0))
    except (TypeError, ValueError):
        raise SignalError(f"확신도가 숫자가 아닙니다: {data.get('confidence')!r}")
    if not (0 <= confidence <= 100):
        raise SignalError(f"확신도 범위 오류: {confidence} (0~100)")

    # 신선도 검증 — 오래된 신호로 매매하지 않기
    created = data.get("created_at")
    if created:
        try:
            ts = datetime.datetime.fromisoformat(created)
            age_min = (datetime.datetime.now() - ts).total_seconds() / 60
            if age_min > max_age_minutes:
                raise SignalError(
                    f"신호가 너무 오래됨: {age_min/60:.1f}시간 전 생성 "
                    f"(허용 {max_age_minutes/60:.0f}시간) — 신선한 신호 아님"
                )
            if age_min < -5:  # 미래 시각이면 시계 오류 의심
                raise SignalError(f"신호 생성 시각이 미래입니다: {created}")
        except ValueError:
            raise SignalError(f"created_at 시각 형식 오류: {created!r}")

    return signal, confidence, data
