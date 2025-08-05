"""MCP Alpaca Trading Server for stock market operations."""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from base_server import BaseMCPServer, create_argument_parser
from typing import Dict, Any, List, Optional
import aiohttp
import json
from datetime import datetime, timedelta
import asyncio


class AlpacaServer(BaseMCPServer):
    """Alpaca trading operations server."""
    
    def __init__(self, port: int = 3012):
        super().__init__("alpaca", port)
        
        # Alpaca configuration
        self.api_key = os.environ.get("ALPACA_API_KEY", "")
        self.secret_key = os.environ.get("ALPACA_SECRET_KEY", "")
        self.base_url = os.environ.get("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")
        self.data_url = "https://data.alpaca.markets"
        
        # Register methods
        self.register_method("get_account", self.get_account)
        self.register_method("get_positions", self.get_positions)
        self.register_method("get_position", self.get_position)
        self.register_method("close_position", self.close_position)
        self.register_method("close_all_positions", self.close_all_positions)
        self.register_method("get_orders", self.get_orders)
        self.register_method("get_order", self.get_order)
        self.register_method("place_order", self.place_order)
        self.register_method("cancel_order", self.cancel_order)
        self.register_method("cancel_all_orders", self.cancel_all_orders)
        self.register_method("get_portfolio_history", self.get_portfolio_history)
        self.register_method("get_market_status", self.get_market_status)
        self.register_method("get_quote", self.get_quote)
        self.register_method("get_bars", self.get_bars)
        self.register_method("get_trades", self.get_trades)
        self.register_method("get_watchlist", self.get_watchlist)
        self.register_method("create_watchlist", self.create_watchlist)
        self.register_method("add_to_watchlist", self.add_to_watchlist)
        self.register_method("remove_from_watchlist", self.remove_from_watchlist)
        
    def _get_headers(self) -> Dict[str, str]:
        """Get API headers."""
        return {
            "APCA-API-KEY-ID": self.api_key,
            "APCA-API-SECRET-KEY": self.secret_key,
            "Accept": "application/json"
        }
        
    async def _make_request(self, method: str, endpoint: str, base_url: str = None,
                          data: Any = None, params: Dict = None) -> Dict[str, Any]:
        """Make Alpaca API request."""
        if not self.api_key or not self.secret_key:
            return {"error": "Alpaca API credentials not configured"}
            
        url = f"{base_url or self.base_url}{endpoint}"
        headers = self._get_headers()
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.request(method, url, headers=headers, json=data, params=params) as response:
                    if response.status == 204:  # No content
                        return {"success": True}
                        
                    result = await response.json()
                    
                    if response.status >= 400:
                        return {"error": result.get("message", f"API error: {response.status}")}
                        
                    return result
                    
        except Exception as e:
            return {"error": str(e)}
            
    async def get_account(self) -> Dict[str, Any]:
        """Get account information."""
        result = await self._make_request("GET", "/v2/account")
        
        if "error" not in result:
            # Format account data
            return {
                "account_number": result.get("account_number"),
                "status": result.get("status"),
                "currency": result.get("currency"),
                "buying_power": float(result.get("buying_power", 0)),
                "cash": float(result.get("cash", 0)),
                "portfolio_value": float(result.get("portfolio_value", 0)),
                "equity": float(result.get("equity", 0)),
                "last_equity": float(result.get("last_equity", 0)),
                "long_market_value": float(result.get("long_market_value", 0)),
                "short_market_value": float(result.get("short_market_value", 0)),
                "pattern_day_trader": result.get("pattern_day_trader"),
                "trading_blocked": result.get("trading_blocked"),
                "transfers_blocked": result.get("transfers_blocked"),
                "account_blocked": result.get("account_blocked"),
                "created_at": result.get("created_at")
            }
        return result
        
    async def get_positions(self) -> Dict[str, Any]:
        """Get all positions."""
        result = await self._make_request("GET", "/v2/positions")
        
        if isinstance(result, list):
            positions = []
            for pos in result:
                positions.append({
                    "symbol": pos["symbol"],
                    "qty": float(pos["qty"]),
                    "side": pos["side"],
                    "market_value": float(pos["market_value"]),
                    "cost_basis": float(pos["cost_basis"]),
                    "unrealized_pl": float(pos["unrealized_pl"]),
                    "unrealized_plpc": float(pos["unrealized_plpc"]),
                    "current_price": float(pos["current_price"]),
                    "avg_entry_price": float(pos["avg_entry_price"])
                })
            return {"positions": positions, "count": len(positions)}
        return result
        
    async def get_position(self, symbol: str) -> Dict[str, Any]:
        """Get position for a specific symbol."""
        return await self._make_request("GET", f"/v2/positions/{symbol}")
        
    async def close_position(self, symbol: str, qty: float = None) -> Dict[str, Any]:
        """Close a position."""
        params = {}
        if qty:
            params["qty"] = qty
        return await self._make_request("DELETE", f"/v2/positions/{symbol}", params=params)
        
    async def close_all_positions(self) -> Dict[str, Any]:
        """Close all positions."""
        return await self._make_request("DELETE", "/v2/positions")
        
    async def get_orders(self, status: str = "all", limit: int = 50) -> Dict[str, Any]:
        """Get orders."""
        params = {"status": status, "limit": limit}
        result = await self._make_request("GET", "/v2/orders", params=params)
        
        if isinstance(result, list):
            orders = []
            for order in result:
                orders.append({
                    "id": order["id"],
                    "symbol": order["symbol"],
                    "qty": float(order["qty"]),
                    "side": order["side"],
                    "type": order["order_type"],
                    "time_in_force": order["time_in_force"],
                    "status": order["status"],
                    "filled_qty": float(order.get("filled_qty", 0)),
                    "filled_avg_price": float(order.get("filled_avg_price", 0)) if order.get("filled_avg_price") else None,
                    "created_at": order["created_at"],
                    "updated_at": order["updated_at"]
                })
            return {"orders": orders, "count": len(orders)}
        return result
        
    async def get_order(self, order_id: str) -> Dict[str, Any]:
        """Get specific order."""
        return await self._make_request("GET", f"/v2/orders/{order_id}")
        
    async def place_order(self, symbol: str, qty: float, side: str, 
                         order_type: str = "market", time_in_force: str = "day",
                         limit_price: float = None, stop_price: float = None,
                         extended_hours: bool = False) -> Dict[str, Any]:
        """Place an order."""
        data = {
            "symbol": symbol,
            "qty": qty,
            "side": side,
            "type": order_type,
            "time_in_force": time_in_force,
            "extended_hours": extended_hours
        }
        
        if order_type == "limit" and limit_price:
            data["limit_price"] = limit_price
        elif order_type == "stop" and stop_price:
            data["stop_price"] = stop_price
        elif order_type == "stop_limit" and limit_price and stop_price:
            data["limit_price"] = limit_price
            data["stop_price"] = stop_price
            
        return await self._make_request("POST", "/v2/orders", data=data)
        
    async def cancel_order(self, order_id: str) -> Dict[str, Any]:
        """Cancel an order."""
        return await self._make_request("DELETE", f"/v2/orders/{order_id}")
        
    async def cancel_all_orders(self) -> Dict[str, Any]:
        """Cancel all orders."""
        return await self._make_request("DELETE", "/v2/orders")
        
    async def get_portfolio_history(self, period: str = "1D", timeframe: str = "1Min") -> Dict[str, Any]:
        """Get portfolio history."""
        params = {"period": period, "timeframe": timeframe}
        result = await self._make_request("GET", "/v2/account/portfolio/history", params=params)
        
        if "error" not in result:
            return {
                "equity": result.get("equity", []),
                "profit_loss": result.get("profit_loss", []),
                "profit_loss_pct": result.get("profit_loss_pct", []),
                "timestamps": result.get("timestamp", []),
                "base_value": result.get("base_value"),
                "timeframe": result.get("timeframe")
            }
        return result
        
    async def get_market_status(self) -> Dict[str, Any]:
        """Get market status."""
        result = await self._make_request("GET", "/v2/clock")
        
        if "error" not in result:
            return {
                "is_open": result.get("is_open"),
                "next_open": result.get("next_open"),
                "next_close": result.get("next_close"),
                "timestamp": result.get("timestamp")
            }
        return result
        
    async def get_quote(self, symbol: str) -> Dict[str, Any]:
        """Get latest quote for a symbol."""
        result = await self._make_request("GET", f"/v2/stocks/{symbol}/quotes/latest",
                                        base_url=self.data_url)
        
        if "quote" in result:
            quote = result["quote"]
            return {
                "symbol": symbol,
                "ask_price": float(quote.get("ap", 0)),
                "ask_size": int(quote.get("as", 0)),
                "bid_price": float(quote.get("bp", 0)),
                "bid_size": int(quote.get("bs", 0)),
                "timestamp": quote.get("t")
            }
        return result
        
    async def get_bars(self, symbol: str, timeframe: str = "1Day", limit: int = 100) -> Dict[str, Any]:
        """Get historical bars."""
        params = {"symbols": symbol, "timeframe": timeframe, "limit": limit}
        result = await self._make_request("GET", "/v2/stocks/bars", 
                                        base_url=self.data_url, params=params)
        
        if "bars" in result and symbol in result["bars"]:
            bars = []
            for bar in result["bars"][symbol]:
                bars.append({
                    "time": bar["t"],
                    "open": float(bar["o"]),
                    "high": float(bar["h"]),
                    "low": float(bar["l"]),
                    "close": float(bar["c"]),
                    "volume": int(bar["v"])
                })
            return {"symbol": symbol, "bars": bars, "count": len(bars)}
        return result
        
    async def get_trades(self, symbol: str, limit: int = 100) -> Dict[str, Any]:
        """Get latest trades."""
        params = {"symbols": symbol, "limit": limit}
        result = await self._make_request("GET", "/v2/stocks/trades",
                                        base_url=self.data_url, params=params)
        
        if "trades" in result and symbol in result["trades"]:
            trades = []
            for trade in result["trades"][symbol]:
                trades.append({
                    "timestamp": trade["t"],
                    "price": float(trade["p"]),
                    "size": int(trade["s"]),
                    "conditions": trade.get("c", [])
                })
            return {"symbol": symbol, "trades": trades, "count": len(trades)}
        return result
        
    async def get_watchlist(self, watchlist_id: str = None) -> Dict[str, Any]:
        """Get watchlist(s)."""
        if watchlist_id:
            endpoint = f"/v2/watchlists/{watchlist_id}"
        else:
            endpoint = "/v2/watchlists"
            
        return await self._make_request("GET", endpoint)
        
    async def create_watchlist(self, name: str, symbols: List[str]) -> Dict[str, Any]:
        """Create a watchlist."""
        data = {"name": name, "symbols": symbols}
        return await self._make_request("POST", "/v2/watchlists", data=data)
        
    async def add_to_watchlist(self, watchlist_id: str, symbol: str) -> Dict[str, Any]:
        """Add symbol to watchlist."""
        data = {"symbol": symbol}
        return await self._make_request("POST", f"/v2/watchlists/{watchlist_id}", data=data)
        
    async def remove_from_watchlist(self, watchlist_id: str, symbol: str) -> Dict[str, Any]:
        """Remove symbol from watchlist."""
        return await self._make_request("DELETE", f"/v2/watchlists/{watchlist_id}/{symbol}")


if __name__ == "__main__":
    parser = create_argument_parser("MCP Alpaca Trading Server")
    args = parser.parse_args()
    
    if not os.environ.get("ALPACA_API_KEY") or not os.environ.get("ALPACA_SECRET_KEY"):
        print("Warning: ALPACA_API_KEY and ALPACA_SECRET_KEY not set.")
        print("Please set these environment variables to use the Alpaca API.")
    
    server = AlpacaServer(port=args.port)
    server.run()