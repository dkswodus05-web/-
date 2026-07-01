"""
일일 자동매매 파이프라인 — Claude 데스크톱 앱(Cowork) 없이 단독으로 도는 프로그램.

흐름:
  지표 수집(FRED+Yahoo) → AI 투자위원회(Anthropic API) → signal.json 기록
  → 리스크 게이트 → (DRY_RUN/Paper/Live) 주문 실행 → trades.log 기록

Windows 작업 스케줄러가 매일 아침 이 파일 하나만 실행하면 전체 파이프라인이 돕니다.
Claude 앱이 꺼져 있어도 동작합니다 — PC와 파이썬만 켜져 있으면 됩니다.

⚠️ 이건 투자 자문이 아닙니다. 기본값은 DRY_RUN(실주문 없음)입니다.
   config.py의 DRY_RUN / PAPER 값은 SAFETY_CHECKLIST.md를 통과하기 전까지 바꾸지 마세요.
"""
import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
import fred_collector
import ai_committee
import publish_status
from signal_io import write_signal, SignalError
from executor import execute_signal
from trade_logger import log, LOG_FILE


def _publish_current_state():
    """지금까지 만들어진 결과(신호/지표/로그)를 Gist에 올려 IDE에서 볼 수 있게 한다.
    실패해도 조용히 넘어간다 — 상태 공유는 부가 기능일 뿐 본 파이프라인을 막으면 안 됨."""
    try:
        sig_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "signal.json")
        signal_txt = open(sig_path, encoding="utf-8").read() if os.path.exists(sig_path) else None
    except Exception:
        signal_txt = None
    try:
        ind_txt = open(fred_collector.OUT_FILE, encoding="utf-8").read() if os.path.exists(fred_collector.OUT_FILE) else None
    except Exception:
        ind_txt = None
    try:
        log_txt = open(LOG_FILE, encoding="utf-8").read() if os.path.exists(LOG_FILE) else None
        if log_txt:
            log_txt = "\n".join(log_txt.splitlines()[-300:])  # 최근 300줄만
    except Exception:
        log_txt = None
    publish_status.publish(signal_txt, ind_txt, log_txt)


def main():
    log("========== 일일 파이프라인 시작 ==========")

    # 1) 지표 수집 (FRED 공식 + Yahoo, 키 없으면 가짜값 없이 안전 정지)
    try:
        payload = fred_collector.collect()
        with open(fred_collector.OUT_FILE, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
    except Exception as e:
        log(f"⛔ 지표 수집 실패 — 안전 정지: {e}")
        return

    got = sum(1 for v in payload["indicators"].values() if v["value"] is not None)
    total = len(payload["indicators"])
    log(f"📊 지표 수집: {got}/{total} (ok={payload['ok']})")

    if not payload["ok"]:
        log("⛔ 공식 데이터(FRED) 부족 — 신호를 지어내지 않고 오늘은 안전 정지합니다.")
        log("   (해결: .env에 FRED_API_KEY 입력)")
        return

    # 2) AI 투자위원회 (Bull/Bear/Judge) — Anthropic API 직접 호출
    try:
        decision = ai_committee.decide(payload)
    except ai_committee.CommitteeError as e:
        log(f"⛔ AI 위원회 판단 실패 — 안전 정지(매매 안 함): {e}")
        return

    log(f"🐂 Bull: {'; '.join(decision['bull']) if decision['bull'] else '(없음)'}")
    log(f"🐻 Bear: {'; '.join(decision['bear']) if decision['bear'] else '(없음)'}")
    log(f"⚖️ Judge: {decision['signal']} (확신도 {decision['confidence']}) — {decision['note']}")

    # 3) signal.json 기록 (Phase 3 다리 재사용)
    try:
        write_signal(
            decision["signal"], decision["confidence"],
            symbol=config.ACTIVE_SYMBOL, note=decision["note"],
        )
    except SignalError as e:
        log(f"⛔ signal.json 기록 실패 — 안전 정지: {e}")
        return

    # 4) 리스크 게이트 → 주문 실행 (Phase 2 재사용, DRY_RUN 기본)
    execute_signal(decision["signal"], decision["confidence"])

    log("========== 일일 파이프라인 종료 ==========\n")


if __name__ == "__main__":
    try:
        main()
    finally:
        # 성공하든 중간에 안전 정지하든, 지금까지의 상태는 항상 공유 시도
        _publish_current_state()
