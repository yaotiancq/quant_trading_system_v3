"""Low-level Alpaca Trading API client.

This module intentionally stays below the normalized brokerage layer. It knows
about Alpaca REST endpoints and headers, but it does not expose vendor objects
to strategy, risk, execution, or portfolio code.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Protocol
from urllib import error, parse, request

from qts.core import BrokerError, ConfigurationError
from qts.domain import BrokerConfig


class AlpacaClient(Protocol):
    """Small client surface consumed by `AlpacaBrokerage`."""

    def get_account(self) -> dict[str, Any]:
        """Return Alpaca account payload."""

    def list_positions(self) -> list[dict[str, Any]]:
        """Return Alpaca open position payloads."""

    def submit_order(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Submit an Alpaca order payload."""

    def cancel_order(self, order_id: str) -> dict[str, Any]:
        """Cancel an Alpaca order."""

    def get_order(self, order_id: str) -> dict[str, Any]:
        """Return one Alpaca order payload."""

    def list_orders(
        self,
        *,
        status: str = "open",
        symbols: str | None = None,
        after: str | None = None,
        until: str | None = None,
        limit: int = 100,
        direction: str = "desc",
    ) -> list[dict[str, Any]]:
        """Return Alpaca order payloads."""

    def get_clock(self) -> dict[str, Any]:
        """Return Alpaca market clock payload."""

    def close(self) -> None:
        """Release client resources."""


@dataclass(frozen=True)
class AlpacaCredentials:
    """Alpaca API credentials loaded at the adapter boundary."""

    api_key_id: str
    secret_key: str

    @classmethod
    def from_env(
        cls,
        credential_env_keys: dict[str, str],
        *,
        env_values: dict[str, str] | None = None,
    ) -> "AlpacaCredentials":
        env = os.environ if env_values is None else env_values
        api_key_name = credential_env_keys.get("api_key_id", "ALPACA_API_KEY_ID")
        secret_key_name = credential_env_keys.get("secret_key", "ALPACA_SECRET_KEY")
        api_key_id = env.get(api_key_name)
        secret_key = env.get(secret_key_name)
        missing = [
            name
            for name, value in ((api_key_name, api_key_id), (secret_key_name, secret_key))
            if not value
        ]
        if missing:
            raise ConfigurationError(
                "missing Alpaca credential environment variables: " + ", ".join(missing)
            )
        return cls(api_key_id=str(api_key_id), secret_key=str(secret_key))


class AlpacaAPIError(BrokerError):
    """Raised when Alpaca returns an error response or cannot be reached."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        payload: Any = None,
        request_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload
        self.request_id = request_id


class AlpacaTransport(Protocol):
    """HTTP transport used by `AlpacaTradingClient`."""

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


class UrllibAlpacaTransport:
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
            raise AlpacaAPIError(f"could not reach Alpaca API: {exc.reason}") from exc


class AlpacaTradingClient:
    """Minimal REST client for Alpaca Trading API v2."""

    def __init__(
        self,
        *,
        base_url: str,
        credentials: AlpacaCredentials,
        transport: AlpacaTransport | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.credentials = credentials
        self.transport = transport or UrllibAlpacaTransport()
        self.timeout = timeout

    def get_account(self) -> dict[str, Any]:
        return self._request("GET", "/v2/account")

    def list_positions(self) -> list[dict[str, Any]]:
        response = self._request("GET", "/v2/positions")
        return _ensure_list(response, "positions")

    def submit_order(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/v2/orders", payload=payload)

    def cancel_order(self, order_id: str) -> dict[str, Any]:
        return self._request("DELETE", f"/v2/orders/{parse.quote(order_id)}")

    def get_order(self, order_id: str) -> dict[str, Any]:
        return self._request("GET", f"/v2/orders/{parse.quote(order_id)}")

    def list_orders(
        self,
        *,
        status: str = "open",
        symbols: str | None = None,
        after: str | None = None,
        until: str | None = None,
        limit: int = 100,
        direction: str = "desc",
    ) -> list[dict[str, Any]]:
        query = {
            "status": status,
            "symbols": symbols,
            "after": after,
            "until": until,
            "limit": limit,
            "direction": direction,
        }
        response = self._request("GET", "/v2/orders", query=query)
        return _ensure_list(response, "orders")

    def get_clock(self) -> dict[str, Any]:
        return self._request("GET", "/v2/clock")

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
        payload: dict[str, Any] | None = None,
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
        headers = {
            "APCA-API-KEY-ID": self.credentials.api_key_id,
            "APCA-API-SECRET-KEY": self.credentials.secret_key,
            "Accept": "application/json",
        }
        if body is not None:
            headers["Content-Type"] = "application/json"

        status, response_headers, response_body = self.transport.request(
            method,
            url,
            headers=headers,
            body=body,
            timeout=self.timeout,
        )
        parsed = _parse_json_response(response_body)
        if not 200 <= status < 300:
            request_id = _case_insensitive_get(response_headers, "X-Request-ID")
            raise AlpacaAPIError(
                _error_message(parsed, status),
                status_code=status,
                payload=parsed,
                request_id=request_id,
            )
        return parsed


def create_alpaca_trading_client(
    broker_config: BrokerConfig,
    *,
    env_values: dict[str, str] | None = None,
    transport: AlpacaTransport | None = None,
) -> AlpacaTradingClient:
    """Create a real REST client from normalized broker config."""
    default_base_url = (
        "https://paper-api.alpaca.markets"
        if broker_config.paper is not False
        else "https://api.alpaca.markets"
    )
    credentials = AlpacaCredentials.from_env(
        dict(broker_config.credential_env_keys),
        env_values=env_values,
    )
    return AlpacaTradingClient(
        base_url=broker_config.base_url or default_base_url,
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


def _ensure_list(response: Any, name: str) -> list[dict[str, Any]]:
    if not isinstance(response, list):
        raise AlpacaAPIError(f"expected Alpaca {name} response to be a list")
    return [dict(item) for item in response]


def _error_message(payload: Any, status_code: int) -> str:
    if isinstance(payload, dict):
        for key in ("message", "error", "detail"):
            if payload.get(key):
                return f"Alpaca API error {status_code}: {payload[key]}"
    return f"Alpaca API error {status_code}"


def _case_insensitive_get(headers: dict[str, str], key: str) -> str | None:
    lowered = key.lower()
    for header_key, value in headers.items():
        if header_key.lower() == lowered:
            return value
    return None


__all__ = [
    "AlpacaAPIError",
    "AlpacaClient",
    "AlpacaCredentials",
    "AlpacaTradingClient",
    "AlpacaTransport",
    "UrllibAlpacaTransport",
    "create_alpaca_trading_client",
]
