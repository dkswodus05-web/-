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
        """보유 수량 반환. 포지션 없으면 0."""
        if config.DRY_RUN:
            return 0.0
        try:
            pos = self.client.get_open_position(symbol)
            return float(pos.qty)
        except Exception:
            return 0.0

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

    def liquidate(self, symbol):
        """해당 종목 전량 매도(청산)."""
        if config.DRY_RUN:
            return {"status": "DRY_RUN", "side": "sell_all", "symbol": symbol}
        order = self.client.close_position(symbol)
        return {"status": str(order.status), "id": str(order.id), "symbol": symbol}
