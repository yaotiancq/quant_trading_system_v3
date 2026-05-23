"""Low-level IBKR Web API client boundary.

This module intentionally stays below the normalized brokerage layer. It knows
about IBKR Web API paths, but normalized domain objects are produced in mapping
and brokerage modules before data leaves the adapter boundary.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Protocol
from urllib import error, parse, request

from qts.core import BrokerError
from qts.domain import BrokerConfig


class IBKRClient(Protocol):
    """Small IBKR client surface consumed by `IBKRBrokerage`."""

    def get_account_summary(self, account_id: str) -> dict[str, Any]:
        """Return IBKR account summary payload."""

    def list_positions(self, account_id: str, *, page_id: int = 0) -> list[dict[str, Any]]:
        """Return IBKR position payloads."""

    def submit_order(self, account_id: str, payload: dict[str, Any]) -> Any:
        """Submit an IBKR order ticket payload."""

    def cancel_order(self, account_id: str, order_id: str) -> dict[str, Any]:
        """Cancel an IBKR order."""

    def get_order_status(self, account_id: str, order_id: str) -> dict[str, Any]:
        """Return one IBKR order status payload."""

    def list_orders(self, account_id: str, *, filters: str | None = None) -> list[dict[str, Any]]:
        """Return IBKR order payloads."""

    def close(self) -> None:
        """Release client resources."""


@dataclass(frozen=True)
class IBKRCredentials:
    """Optional IBKR bearer token loaded at the adapter boundary."""

    access_token: str | None = None

    @classmethod
    def from_env(
        cls,
        credential_env_keys: dict[str, str],
        *,
        env_values: dict[str, str] | None = None,
    ) -> "IBKRCredentials":
        env = os.environ if env_values is None else env_values
        token_name = credential_env_keys.get("access_token", "IBKR_ACCESS_TOKEN")
        return cls(access_token=env.get(token_name))


class IBKRAPIError(BrokerError):
    """Raised when IBKR returns an error response or cannot be reached."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        payload: Any = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload


class IBKRTransport(Protocol):
    """HTTP transport used by `IBKRWebAPIClient`."""

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str],
        body: bytes | None = None,
        timeout: float = 30.0,
    ) -> tuple[int, dict[str, str], str]:
        """Return status code, response headers, and decoded body text."""


class UrllibIBKRTransport:
    """Dependency-free HTTP transport built on the Python standard library."""

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str],
        body: bytes | None = None,
        timeout: float = 30.0,
    ) -> tuple[int, dict[str, str], str]:
        req = request.Request(url, data=body, headers=headers, method=method.upper())
        try:
            with request.urlopen(req, timeout=timeout) as response:
                response_body = response.read().decode("utf-8")
                return response.status, dict(response.headers.items()), response_body
        except error.HTTPError as exc:
            response_body = exc.read().decode("utf-8")
            return exc.code, dict(exc.headers.items()), response_body
        except error.URLError as exc:
            raise IBKRAPIError(f"could not reach IBKR API: {exc.reason}") from exc


class IBKRWebAPIClient:
    """Minimal REST client for IBKR Web API / Client Portal style endpoints."""

    def __init__(
        self,
        *,
        base_url: str,
        credentials: IBKRCredentials | None = None,
        transport: IBKRTransport | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.credentials = credentials or IBKRCredentials()
        self.transport = transport or UrllibIBKRTransport()
        self.timeout = timeout

    def get_account_summary(self, account_id: str) -> dict[str, Any]:
        return _ensure_dict(self._request("GET", f"/portfolio/{parse.quote(account_id)}/summary"))

    def list_positions(self, account_id: str, *, page_id: int = 0) -> list[dict[str, Any]]:
        response = self._request(
            "GET",
            f"/portfolio/{parse.quote(account_id)}/positions/{int(page_id)}",
        )
        if isinstance(response, dict) and isinstance(response.get("positions"), list):
            response = response["positions"]
        return _ensure_list(response, "positions")

    def submit_order(self, account_id: str, payload: dict[str, Any]) -> Any:
        return self._request(
            "POST",
            f"/iserver/account/{parse.quote(account_id)}/orders",
            payload=[payload],
        )

    def cancel_order(self, account_id: str, order_id: str) -> dict[str, Any]:
        return _ensure_dict(
            self._request(
                "DELETE",
                f"/iserver/account/{parse.quote(account_id)}/order/{parse.quote(order_id)}",
            )
        )

    def get_order_status(self, account_id: str, order_id: str) -> dict[str, Any]:
        return _ensure_dict(
            self._request(
                "GET",
                f"/iserver/account/{parse.quote(account_id)}/order/status/{parse.quote(order_id)}",
            )
        )

    def list_orders(self, account_id: str, *, filters: str | None = None) -> list[dict[str, Any]]:
        query = {"filters": filters, "force": "true"}
        response = self._request("GET", "/iserver/account/orders", query=query)
        if isinstance(response, dict) and isinstance(response.get("orders"), list):
            response = response["orders"]
        orders = _ensure_list(response, "orders")
        return [order for order in orders if str(order.get("acct") or account_id) == account_id]

    def close(self) -> None:
        close = getattr(self.transport, "close", None)
        if callable(close):
            close()

    def _request(
        self,
        method: str,
        path: str,
        *,
        query: dict[str, Any] | None = None,
        payload: Any | None = None,
    ) -> Any:
        url = f"{self.base_url}{path}"
        filtered_query = {
            key: value
            for key, value in (query or {}).items()
            if value is not None and value != ""
        }
        if filtered_query:
            url = f"{url}?{parse.urlencode(filtered_query)}"
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        headers = {"Accept": "application/json"}
        if self.credentials.access_token:
            headers["Authorization"] = f"Bearer {self.credentials.access_token}"
        if body is not None:
            headers["Content-Type"] = "application/json"

        status, _response_headers, response_body = self.transport.request(
            method,
            url,
            headers=headers,
            body=body,
            timeout=self.timeout,
        )
        parsed = _parse_json_response(response_body)
        if not 200 <= status < 300:
            raise IBKRAPIError(_error_message(parsed, status), status_code=status, payload=parsed)
        return parsed


def create_ibkr_web_api_client(
    broker_config: BrokerConfig,
    *,
    env_values: dict[str, str] | None = None,
    transport: IBKRTransport | None = None,
) -> IBKRWebAPIClient:
    """Create a real REST client from normalized broker config."""
    credentials = IBKRCredentials.from_env(
        dict(broker_config.credential_env_keys),
        env_values=env_values,
    )
    return IBKRWebAPIClient(
        base_url=broker_config.base_url or "https://api.ibkr.com/v1/api",
        credentials=credentials,
        transport=transport,
    )


def _parse_json_response(response_body: str) -> Any:
    if not response_body:
        return {}
    try:
        return json.loads(response_body)
    except json.JSONDecodeError:
        return {"raw_body": response_body}


def _ensure_dict(response: Any) -> dict[str, Any]:
    if not isinstance(response, dict):
        raise IBKRAPIError("expected IBKR response to be an object", payload=response)
    return dict(response)


def _ensure_list(response: Any, name: str) -> list[dict[str, Any]]:
    if not isinstance(response, list):
        raise IBKRAPIError(f"expected IBKR {name} response to be a list", payload=response)
    return [dict(item) for item in response]


def _error_message(payload: Any, status_code: int) -> str:
    if isinstance(payload, dict):
        for key in ("error", "message", "detail"):
            if payload.get(key):
                return f"IBKR API error {status_code}: {payload[key]}"
    return f"IBKR API error {status_code}"


__all__ = [
    "IBKRAPIError",
    "IBKRClient",
    "IBKRCredentials",
    "IBKRTransport",
    "IBKRWebAPIClient",
    "UrllibIBKRTransport",
    "create_ibkr_web_api_client",
]
