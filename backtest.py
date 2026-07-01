"""
백테스트 (Phase 5) — 실거래 전 필수.

질문: "신호 기반 보유↔현금 스위칭 전략이 단순 매수후보유(Buy&Hold)보다 나은가?
       낙폭(MDD)은 견딜 만한가?"

이 엔진은 두 부분으로 나뉜다.
  1) 백테스트 코어: 날짜별 가격 + 날짜별 신호(BUY/HOLD/SELL)를 받아
     '보유 ↔ 현금' 스위칭을 시뮬레이션하고 성과 지표를 계산.
  2) 신호 생성기: 매크로 17개 지표의 과거값을 매일 재현하기 어렵기 때문에,
     같은 '보유↔현금 스위칭' 성격의 대표 전략(200일 이동평균 추세추종)을
     기본 제공한다. 매크로 신호의 과거 시퀀스가 생기면 그걸 넣어 그대로 비교 가능.

데이터: spy.csv  (헤더: date,adjclose)  — 배당조정 종가.

⚠️ 백테스트는 과거일 뿐 미래 수익을 보장하지 않는다. 거래비용·슬리피지·세금은
   단순화돼 있고, 신호 생성기는 미래 데이터를 쓰지 않도록(look-ahead 방지) 설계했다.
"""
import csv
import os
import sys

DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "spy.csv")

# 거래 비용 가정 (보유→현금 또는 현금→보유 전환 1회당, 비율). 0.0005 = 0.05%
COST_PER_SWITCH = 0.0005


def download_prices(symbol="SPY", years=10, path=DATA_FILE):
    """spy.csv가 없으면 Yahoo Finance에서 배당조정 종가를 받아 저장 (키 불필요)."""
    import json, datetime, time
    from urllib.request import Request, urlopen
    p2 = int(time.time())
    p1 = p2 - years * 365 * 24 * 3600
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
           f"?period1={p1}&period2={p2}&interval=1d")
    req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(req, timeout=30) as r:
        d = json.load(r)
    res = d["chart"]["result"][0]
    ts = res["timestamp"]
    adj = res["indicators"]["adjclose"][0]["adjclose"]
    rows = [(datetime.datetime.utcfromtimestamp(t).strftime("%Y-%m-%d"), round(a, 4))
            for t, a in zip(ts, adj) if a is not None]
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "adjclose"])
        w.writerows(rows)
    print(f"⬇ {symbol} 데이터 {len(rows)}일치 다운로드 → {os.path.basename(path)}")
    return path


def load_prices(path=DATA_FILE):
    if not os.path.exists(path):
        print(f"데이터 파일이 없어 다운로드합니다: {os.path.basename(path)}")
        download_prices(path=path)
    dates, prices = [], []
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            dates.append(row["date"])
            prices.append(float(row["adjclose"]))
    return dates, prices


# ---------------------------------------------------------------------------
# 신호 생성기들 — 각각 [날짜별 신호 리스트]를 반환 (BUY/HOLD/SELL)
# look-ahead 방지: i일 신호는 i일까지의 데이터만 사용.
# ---------------------------------------------------------------------------
def signals_sma_trend(prices, window=200):
    """추세추종: 종가가 N일 이동평균 위면 BUY(보유), 아래면 SELL(현금).
    매크로 신호의 '보유↔현금 스위칭'과 같은 성격의 대표 전략."""
    sig = []
    for i in range(len(prices)):
        if i < window:
            sig.append("HOLD")  # 평균 계산 전 구간은 관망
            continue
        sma = sum(prices[i - window + 1 : i + 1]) / window
        sig.append("BUY" if prices[i] > sma else "SELL")
    return sig


def signals_from_list(records, dates):
    """외부 신호(예: 매크로 위원회 결과)를 날짜에 매핑.
    records: {date: "BUY"|"HOLD"|"SELL"} dict. 없는 날짜는 직전 신호 유지."""
    sig, last = [], "HOLD"
    for d in dates:
        if d in records:
            last = records[d].upper()
        sig.append(last)
    return sig


# ---------------------------------------------------------------------------
# 5단계 레짐 전략 (moket.kr 참고) — 100%/0% 두 칸 대신 비중을 5단계로.
#   공격 → 균형 → 중립 → 방어 → 위기  (위험할수록 현금 비중↑)
# 백테스트에서 검증된 '중간' 비중 세트가 기본값.
# ---------------------------------------------------------------------------
REGIME_WEIGHTS = {"공격": 1.00, "균형": 0.90, "중립": 0.65, "방어": 0.30, "위기": 0.00}


def _sma(prices, i, w):
    if i < w - 1:
        return None
    return sum(prices[i - w + 1 : i + 1]) / w


def regime_of(prices, i):
    """50일·200일 이동평균과 50일선 기울기로 시장을 5단계로 분류."""
    s50, s200 = _sma(prices, i, 50), _sma(prices, i, 200)
    if s50 is None or s200 is None:
        return "중립"
    px = prices[i]
    above200, above50 = px > s200, px > s50
    s50_up = (s50 > _sma(prices, i - 20, 50)) if i >= 70 else True
    if above200 and above50 and s50_up:
        return "공격"
    if above200 and above50:
        return "균형"
    if above200 and not above50:
        return "중립"
    if not above200 and above50:
        return "방어"
    return "위기"


def weights_regime(prices):
    """날짜별 목표 주식비중(0.0~1.0) 리스트를 반환."""
    return [REGIME_WEIGHTS[regime_of(prices, i)] for i in range(len(prices))]


def run_backtest_weighted(prices, target_weights, band=0.05,
                          cost=COST_PER_SWITCH, start_cash=100000.0):
    """목표비중 기반 시뮬. 현재비중과 목표 차이가 band 미만이면 매매를 건너뛴다
    (거래비용 최적화 = 불필요한 잦은 매매 방지). 어제 비중으로 오늘 체결."""
    cash = start_cash
    shares = 0.0
    trades = 0
    equity = []
    for i in range(len(prices)):
        px = prices[i]
        val = cash + shares * px
        cur_w = (shares * px) / val if val > 0 else 0.0
        if i > 0:
            tgt = target_weights[i - 1]
            if abs(tgt - cur_w) >= band:           # 밴드 밖일 때만 리밸런싱
                diff = val * tgt - shares * px
                if abs(diff) > val * 0.001:
                    cash -= diff + abs(diff) * cost
                    shares += diff / px
                    trades += 1
        equity.append(cash + shares * px)
    return equity, trades


# ---------------------------------------------------------------------------
# 백테스트 코어
# ---------------------------------------------------------------------------
def run_backtest(dates, prices, signals, cost=COST_PER_SWITCH, start_cash=100000.0):
    """
    보유↔현금 스위칭 시뮬.
      BUY  → 현금이면 전량 매수(보유 전환)
      SELL → 보유면 전량 매도(현금 전환)
      HOLD → 유지
    신호는 당일 종가로 판단하고 '다음 날 종가'에 체결(look-ahead 방지).
    반환: equity 곡선(list), 거래 횟수.
    """
    equity = []          # 매일의 포트폴리오 평가액
    cash = start_cash
    shares = 0.0
    holding = False
    trades = 0

    for i in range(len(prices)):
        price = prices[i]
        # 1) 먼저 어제 신호에 따른 체결 (오늘 종가로)
        if i > 0:
            want = signals[i - 1]
            if want == "BUY" and not holding:
                cash *= (1 - cost)
                shares = cash / price
                cash = 0.0
                holding = True
                trades += 1
            elif want == "SELL" and holding:
                cash = shares * price * (1 - cost)
                shares = 0.0
                holding = False
                trades += 1
        # 2) 오늘 평가액 기록
        equity.append(cash + shares * price)

    return equity, trades


def buy_and_hold(prices, start_cash=100000.0):
    shares = start_cash / prices[0]
    return [shares * p for p in prices]


# ---------------------------------------------------------------------------
# 성과 지표
# ---------------------------------------------------------------------------
def metrics(equity, dates):
    start, end = equity[0], equity[-1]
    total_ret = end / start - 1

    years = max((len(equity) / 252.0), 1e-9)
    cagr = (end / start) ** (1 / years) - 1

    # 최대 낙폭 (MDD)
    peak = equity[0]
    mdd = 0.0
    for v in equity:
        peak = max(peak, v)
        mdd = min(mdd, v / peak - 1)

    # 일간 수익률 → 변동성, 샤프(무위험 0 가정)
    rets = [equity[i] / equity[i - 1] - 1 for i in range(1, len(equity))]
    n = len(rets)
    mean = sum(rets) / n if n else 0.0
    var = sum((r - mean) ** 2 for r in rets) / n if n else 0.0
    std = var ** 0.5
    sharpe = (mean / std * (252 ** 0.5)) if std > 0 else 0.0

    return {
        "total_return": total_ret,
        "cagr": cagr,
        "mdd": mdd,
        "sharpe": sharpe,
    }


def pct(x):
    return f"{x*100:+.1f}%"


def print_report(name, equity, dates, trades=None):
    m = metrics(equity, dates)
    print(f"  [{name}]")
    print(f"    총수익률  : {pct(m['total_return'])}")
    print(f"    연평균(CAGR): {pct(m['cagr'])}")
    print(f"    최대낙폭(MDD): {pct(m['mdd'])}")
    print(f"    샤프지수  : {m['sharpe']:.2f}")
    if trades is not None:
        print(f"    거래횟수  : {trades}회")
    return m


def main():
    dates, prices = load_prices()
    print(f"📊 백테스트 데이터: {dates[0]} ~ {dates[-1]} ({len(dates)}일, 약 {len(dates)/252:.1f}년)\n")

    # 1) 벤치마크: 단순 매수후보유
    bh = buy_and_hold(prices)
    mb = print_report("Buy & Hold (벤치마크)", bh, dates)
    print()

    # 2) 전략: 200일 이동평균 추세추종 (보유↔현금 스위칭의 대표)
    window = int(sys.argv[1]) if len(sys.argv) > 1 else 200
    sigs = signals_sma_trend(prices, window=window)
    eq, trades = run_backtest(dates, prices, sigs)
    ms = print_report(f"신호전략 (SMA{window} 추세추종, 100/0%)", eq, dates, trades)
    print()

    # 2-b) 5단계 레짐 전략 (비중 차등 + 거래비용 밴드)
    rw = weights_regime(prices)
    eq5, tr5 = run_backtest_weighted(prices, rw, band=0.05)
    mr = print_report("5단계 레짐 (비중 차등 + 밴드5%)", eq5, dates, tr5)
    print(f"    비중표    : 공격100 균형90 중립65 방어30 위기0 (%)")
    print()

    # 3) 비교 결론
    print("=" * 48)
    better_ret = ms["total_return"] > mb["total_return"]
    less_dd = ms["mdd"] > mb["mdd"]  # mdd는 음수, 클수록(0에 가까울수록) 낙폭 작음
    print("📋 비교 결론")
    print(f"  수익률: 전략 {pct(ms['total_return'])} vs B&H {pct(mb['total_return'])}"
          f" → {'전략 우위' if better_ret else 'B&H 우위'}")
    print(f"  낙폭  : 전략 {pct(ms['mdd'])} vs B&H {pct(mb['mdd'])}"
          f" → {'전략이 낙폭 더 적음(방어적)' if less_dd else 'B&H가 낙폭 더 적음'}")
    print(f"  샤프  : 전략 {ms['sharpe']:.2f} vs B&H {mb['sharpe']:.2f}"
          f" → {'전략 우위' if ms['sharpe'] > mb['sharpe'] else 'B&H 우위'}")
    print()
    print("  ⚠️ 과거 성과는 미래를 보장하지 않습니다. 거래비용·세금·슬리피지는 단순화됨.")
    print("  ⚠️ 이 결과가 나쁘면 실거래로 가지 않는 것이 정답입니다 (지침서 Phase 5).")


if __name__ == "__main__":
    main()
