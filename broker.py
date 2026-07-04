"""
Alpaca 브로커 래퍼.
DRY_RUN=true일 때는 alpaca 패키지 없이도 동작(시뮬). false일 때만 실제 Alpaca에 연결.
"""
import config


class Broker:
    def __init__(self):
        self.client = None
        if not config.DRY_RUN:
            if not config.ALPACA_API_KEY or not config.ALPACA_SECRET_KEY:
                raise RuntimeError("API 키가 없습니다. .env에 ALPACA_API_KEY / ALPACA_SECRET_KEY를 넣으세요.")
            from alpaca.trading.client import TradingClient
            self.client = TradingClient(
                config.ALPACA_API_KEY, config.ALPACA_SECRET_KEY, paper=config.PAPER
            )

    def get_account(self):
        if config.DRY_RUN:
            # 시뮬용 가상 계정 ($100,000 시작)
            return {"equity": 100000.0, "last_equity": 100000.0, "cash": 100000.0}
        a = self.client.get_account()
        return {
            "equity": float(a.equity),
            "last_equity": float(a.last_equity),
            "cash": float(a.cash),
        }

    def get_position_qty(self, symbol):
        """보유 수량 반환. 포지션이 정말 없으면 0.
        ⚠️ '포지션 없음(404)'과 그 외 진짜 오류(인증·네트워크·API 변경 등)를 구분해서,
           후자는 조용히 0으로 삼키지 않고 로그에 남긴다. 안 그러면 실제로는 보유 중인데도
           조회가 실패해서 '보유 없음'으로 잘못 표시되는 문제가 원인도 모른 채 반복된다."""
        if config.DRY_RUN:
            return 0.0
        try:
            pos = self.client.get_open_position(symbol)
            return float(pos.qty)
        except Exception as e:
            msg = str(e).lower()
            is_no_position = "position does not exist" in msg or "404" in msg
            if not is_no_position:
                try:
                    from trade_logger import log
                    log(f"⚠️ 포지션 조회 중 예상 밖 오류(일단 보유 없음으로 처리) — 원인 확인 필요: {e}")
                except Exception:
                    pass
            return 0.0

    def get_positions(self):
        """전체 보유 포지션 반환: {심볼: {"qty": 수량, "market_value": 평가금액}}.
        멀티에셋 리밸런싱(Phase 7)에서 현재 비중 계산에 사용.
        조회 실패는 조용히 삼키지 않고 예외를 올린다 — 보유 현황을 모르면 매매하면 안 됨."""
        if config.DRY_RUN:
            return {}
        out = {}
        for pos in self.client.get_all_positions():
            out[str(pos.symbol).upper()] = {
                "qty": float(pos.qty),
                "market_value": float(pos.market_value),
            }
        return out

    def is_market_open(self):
        if config.DRY_RUN:
            return True
        return bool(self.client.get_clock().is_open)

    def buy_notional(self, symbol, notional):
        """금액(달러) 기준 시장가 매수. 소수점 주식 자동 처리."""
        if config.DRY_RUN:
            return {"status": "DRY_RUN", "side": "buy", "symbol": symbol, "notional": round(notional, 2)}
        from alpaca.trading.requests import MarketOrderRequest
        from alpaca.trading.enums import OrderSide, TimeInForce
        req = MarketOrderRequest(
            symbol=symbol,
            notional=round(notional, 2),
            side=OrderSide.BUY,
            time_in_force=TimeInForce.DAY,
        )
        order = self.client.submit_order(order_data=req)
        return {"status": str(order.status), "id": str(order.id), "symbol": symbol, "notional": round(notional, 2)}

    def sell_notional(self, symbol, notional):
        """금액(달러) 기준 시장가 부분 매도. 리밸런싱에서 비중 축소에 사용."""
        if config.DRY_RUN:
            return {"status": "DRY_RUN", "side": "sell", "symbol": symbol, "notional": round(notional, 2)}
        from alpaca.trading.requests import MarketOrderRequest
        from alpaca.trading.enums import OrderSide, TimeInForce
        req = MarketOrderRequest(
            symbol=symbol,
            notional=round(notional, 2),
            side=OrderSide.SELL,
            time_in_force=TimeInForce.DAY,
        )
        order = self.client.submit_order(order_data=req)
        return {"status": str(order.status), "id": str(order.id), "symbol": symbol, "notional": round(notional, 2)}

    def liquidate(self, symbol):
        """해당 종목 전량 매도(청산)."""
        if config.DRY_RUN:
            return {"status": "DRY_RUN", "side": "sell_all", "symbol": symbol}
        order = self.client.close_position(symbol)
        return {"status": str(order.status), "id": str(order.id), "symbol": symbol}
