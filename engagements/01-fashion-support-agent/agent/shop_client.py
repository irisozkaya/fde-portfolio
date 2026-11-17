"""Thin HTTP client for the shop API. Paths are relative so a FastAPI TestClient can stand in for httpx."""
import httpx


class ShopError(Exception):
    def __init__(self, status: int, payload: dict):
        super().__init__(f"shop returned {status}: {payload}")
        self.status = status
        self.payload = payload


class ShopClient:
    def __init__(self, base_url: str, http: httpx.Client | None = None):
        self.http = http or httpx.Client(base_url=base_url, timeout=10)

    def _request(self, method: str, path: str, **kwargs):
        r = self.http.request(method, path, **kwargs)
        if r.status_code >= 400:
            try:
                payload = r.json()
            except ValueError:
                payload = {}
            if not isinstance(payload, dict) or "error" not in payload:
                payload = {"error": "shop_rejected", "details": payload}
            raise ShopError(r.status_code, payload)
        return r.json()

    def lookup_order(self, order_no: str, verification: str) -> dict:
        return self._request("POST", "/orders/lookup", json={"order_no": order_no, "verification": verification})

    def start_return(self, order_no: str, verification: str, line_nos: list[int], reason: str) -> dict:
        return self._request("POST", "/returns", json={"order_no": order_no, "verification": verification,
                                                        "line_nos": line_nos, "reason": reason})

    def search_products(self, query: str, category: str | None = None, size: str | None = None) -> list[dict]:
        params = {"q": query} | ({"category": category} if category else {}) | ({"size": size} if size else {})
        return self._request("GET", "/products/search", params=params)

    def get_size_chart(self, category: str) -> dict:
        return self._request("GET", f"/size-chart/{category}")

    def get_policy(self) -> dict:
        return self._request("GET", "/policy")

    def create_ticket(self, reason: str, summary: str, order_no: str | None = None,
                      customer_email: str | None = None) -> dict:
        return self._request("POST", "/tickets", json={"reason": reason, "summary": summary,
                                                        "order_no": order_no, "customer_email": customer_email})
