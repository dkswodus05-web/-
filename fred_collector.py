"""
경제지표 수집기 — 17개 매크로 지표를 공식 출처에서 자동 수집 (지침서 데이터 업그레이드).

지침서: "데이터(현재): AI 웹검색 추정치 → 정확도는 FRED로 업그레이드 예정"
이 파일이 그 업그레이드다. 웹검색 추정치 대신 공식 데이터를 쓴다.

출처 구분 (블로그 jrune 참고):
  - 거시지표(금리·실업률·CPI·연준 등) → FRED (미 연준 공식, API 키 필요·무료)
  - 시장가격(VIX·S&P500 등)          → Yahoo Finance (키 불필요)

⚠️ 안전 원칙 (가장 중요):
   FRED API 키가 없으면 **가짜값을 지어내지 않고 안전 정지**한다.
   (블로그가 경고한 "키 없이 임의 동작하는 프로그램"의 함정을 피한다.)
   값을 못 가져온 지표는 None으로 두고, 신호 단계에서 데이터 부족을 인지하게 한다.

사용법:
   1) https://fred.stlouisfed.org/docs/api/api_key.html 에서 무료 키 발급
   2) .env 에 FRED_API_KEY=발급받은키
   3) python fred_collector.py     → indicators.json 생성

결과(indicators.json) 형식:
   { "collected_at": "...", "indicators": { "장단기_금리차(10Y-2Y)": {"value":0.31,"source":"FRED","series":"T10Y2Y"}, ... },
     "missing": [...], "ok": true/false }
"""
import os
import json
import datetime
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

FRED_API_KEY = os.getenv("FRED_API_KEY", "")
OUT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "indicators.json")

# ── 17개 지표 정의 ─────────────────────────────────────────────
# (이름, 출처, ID, 설명)  source: "FRED" 또는 "YAHOO"
INDICATORS = [
    ("장단기_금리차(10Y-2Y)", "FRED",  "T10Y2Y",        "음수면 경기침체 경고(역전)"),
    ("국채10년_금리",          "FRED",  "DGS10",         "장기 금리 수준"),
    ("국채2년_금리",           "FRED",  "DGS2",          "단기 금리 수준"),
    ("실업률",                 "FRED",  "UNRATE",        "고용 건전성"),
    ("CPI_소비자물가",         "FRED",  "CPIAUCSL",      "인플레이션 수준"),
    ("기대인플레이션(10Y)",    "FRED",  "T10YIE",        "시장 기대 물가"),
    ("연준기준금리",           "FRED",  "FEDFUNDS",      "통화정책 기조"),
    ("하이일드_신용스프레드",  "FRED",  "BAMLH0A0HYM2",  "신용 위험(클수록 위험회피)"),
    ("회사채_신용스프레드",    "FRED",  "BAMLC0A0CM",    "투자등급 신용 위험"),
    ("달러인덱스(광의)",       "FRED",  "DTWEXBGS",      "달러 강세 여부"),
    ("산업생산지수",           "FRED",  "INDPRO",        "실물 경기"),
    ("소매판매",               "FRED",  "RSAFS",         "소비 동향"),
    ("주택착공",               "FRED",  "HOUST",         "부동산 경기"),
    ("M2_통화량",              "FRED",  "M2SL",          "유동성"),
    ("VIX_변동성지수",         "YAHOO", "^VIX",          "공포지수(클수록 위험)"),
    ("S&P500",                 "YAHOO", "^GSPC",         "시장 추세"),
    ("WTI_유가",               "YAHOO", "CL=F",          "원자재·인플레 압력"),
]


def fetch_fred(series_id):
    """FRED API에서 시리즈의 최신 관측값을 반환. 키 없으면 RuntimeError."""
    if not FRED_API_KEY:
        raise RuntimeError("FRED_API_KEY 없음")
    url = (f"https://api.stlouisfed.org/fred/series/observations"
           f"?series_id={series_id}&api_key={FRED_API_KEY}&file_type=json"
           f"&sort_order=desc&limit=10")
    req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(req, timeout=20) as r:
        data = json.load(r)
    for obs in data.get("observations", []):
        if obs["value"] not in (".", "", None):   # FRED는 결측을 "."으로 표시
            return float(obs["value"]), obs["date"]
    return None, None


def fetch_yahoo(symbol):
    """Yahoo Finance에서 최신 종가 반환 (키 불필요)."""
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
           f"?range=5d&interval=1d")
    req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(req, timeout=20) as r:
        data = json.load(r)
    res = data["chart"]["result"][0]
    closes = res["indicators"]["quote"][0]["close"]
    ts = res["timestamp"]
    for c, t in zip(reversed(closes), reversed(ts)):
        if c is not None:
            day = datetime.datetime.utcfromtimestamp(t).strftime("%Y-%m-%d")
            return round(float(c), 2), day
    return None, None


def collect():
    result = {}
    missing = []
    have_fred = bool(FRED_API_KEY)

    for name, source, sid, desc in INDICATORS:
        try:
            if source == "FRED":
                if not have_fred:
                    raise RuntimeError("FRED 키 없음 — 거시지표 수집 불가")
                val, date = fetch_fred(sid)
            else:
                val, date = fetch_yahoo(sid)
        except Exception as e:
            val, date = None, None

        if val is None:
            missing.append(name)
        result[name] = {"value": val, "date": date, "source": source,
                        "series": sid, "desc": desc}

    payload = {
        "collected_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "indicators": result,
        "missing": missing,
        # 거시지표를 하나도 못 받았으면(=FRED 키 문제) ok=False → 신호 단계에서 안전 정지
        "ok": have_fred and len(missing) < len(INDICATORS) // 2,
        "fred_key_present": have_fred,
    }
    return payload


def main():
    payload = collect()
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    got = sum(1 for v in payload["indicators"].values() if v["value"] is not None)
    total = len(payload["indicators"])
    print(f"수집 완료: {got}/{total} 지표 → {os.path.basename(OUT_FILE)}")

    if not payload["fred_key_present"]:
        print("⛔ FRED_API_KEY가 없습니다 — 거시지표를 가져오지 못했습니다.")
        print("   가짜값을 만들지 않고 빈 값으로 둡니다(안전).")
        print("   해결: https://fred.stlouisfed.org/docs/api/api_key.html 에서 무료 발급 → .env에 FRED_API_KEY=...")
    elif payload["missing"]:
        print(f"⚠️ 일부 지표 누락: {', '.join(payload['missing'])}")

    # 받은 값 미리보기
    for name, v in payload["indicators"].items():
        mark = "✅" if v["value"] is not None else "❌"
        val = f"{v['value']}" if v["value"] is not None else "(없음)"
        print(f"  {mark} {name:24s} {val:>12} [{v['source']}]")

    print(f"\nok={payload['ok']}  (신호 시스템은 ok=False면 매매하지 않고 안전 정지)")


if __name__ == "__main__":
    main()
