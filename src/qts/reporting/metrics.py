"""Backtest performance metrics."""

from __future__ import annotations

import math
from statistics import mean, stdev

from qts.domain import PortfolioSnapshot, TradeLedgerEntry


def calculate_metrics(
    portfolio_snapshots: list[PortfolioSnapshot],
    trade_ledger: list[TradeLedgerEntry],
    *,
    annualization_factor: float | None = None,
    risk_free_rate: float = 0.0,
) -> dict[str, float | int | None | dict[str, float]]:
    if not portfolio_snapshots:
        return {
            "total_return": 0.0,
            "annualized_return": None,
            "volatility": 0.0,
            "sharpe_ratio": None,
            "max_drawdown": 0.0,
            "win_rate": 0.0,
            "profit_factor": None,
            "average_trade_pnl": 0.0,
            "number_of_trades": len(trade_ledger),
            "number_of_closed_trades": 0,
            "exposure": {},
        }

    first = portfolio_snapshots[0]
    last = portfolio_snapshots[-1]
    total_return = (last.equity / first.equity - 1.0) if first.equity else 0.0
    returns = _equity_returns(portfolio_snapshots)
    volatility = stdev(returns) if len(returns) > 1 else 0.0
    period_risk_free_rate = (
        risk_free_rate / annualization_factor if annualization_factor and annualization_factor > 0 else 0.0
    )
    sharpe_scale = math.sqrt(annualization_factor) if annualization_factor else math.sqrt(len(returns))
    sharpe_ratio = (
        ((mean(returns) - period_risk_free_rate) / volatility * sharpe_scale)
        if volatility
        else None
    )
    realized_pnls = [
        entry.realized_pnl_delta or 0.0
        for entry in trade_ledger
        if abs(entry.realized_pnl_delta or 0.0) > 1e-12
    ]
    gross_profit = sum(value for value in realized_pnls if value > 0)
    gross_loss = abs(sum(value for value in realized_pnls if value < 0))
    win_rate = (
        sum(1 for value in realized_pnls if value > 0) / len(realized_pnls)
        if realized_pnls
        else 0.0
    )
    profit_factor = gross_profit / gross_loss if gross_loss else None
    elapsed_days = (last.timestamp - first.timestamp).total_seconds() / 86400.0
    annualized_return = _annualized_return(
        total_return,
        elapsed_days=elapsed_days,
        return_count=len(returns),
        annualization_factor=annualization_factor,
    )
    gross_exposures = [snapshot.gross_exposure for snapshot in portfolio_snapshots]
    net_exposures = [snapshot.net_exposure for snapshot in portfolio_snapshots]
    return {
        "total_return": total_return,
        "annualized_return": annualized_return,
        "volatility": volatility,
        "sharpe_ratio": sharpe_ratio,
        "max_drawdown": _max_drawdown(portfolio_snapshots),
        "win_rate": win_rate,
        "profit_factor": profit_factor,
        "average_trade_pnl": mean(realized_pnls) if realized_pnls else 0.0,
        "number_of_trades": len(trade_ledger),
        "number_of_closed_trades": len(realized_pnls),
        "exposure": {
            "max_gross_exposure": max(gross_exposures) if gross_exposures else 0.0,
            "average_gross_exposure": mean(gross_exposures) if gross_exposures else 0.0,
            "max_net_exposure": max(net_exposures) if net_exposures else 0.0,
            "min_net_exposure": min(net_exposures) if net_exposures else 0.0,
        },
    }


def equity_curve(portfolio_snapshots: list[PortfolioSnapshot]) -> list[dict[str, float | str]]:
    return [
        {
            "timestamp": snapshot.to_dict()["timestamp"],
            "cash": snapshot.cash,
            "equity": snapshot.equity,
            "positions_value": snapshot.positions_value,
            "gross_exposure": snapshot.gross_exposure,
            "net_exposure": snapshot.net_exposure,
            "drawdown": _drawdown_at(snapshot.equity, portfolio_snapshots[: index + 1]),
        }
        for index, snapshot in enumerate(portfolio_snapshots)
    ]


def _equity_returns(snapshots: list[PortfolioSnapshot]) -> list[float]:
    returns: list[float] = []
    for previous, current in zip(snapshots, snapshots[1:]):
        if previous.equity:
            returns.append(current.equity / previous.equity - 1.0)
    return returns


def _annualized_return(
    total_return: float,
    *,
    elapsed_days: float,
    return_count: int,
    annualization_factor: float | None,
) -> float | None:
    if total_return <= -1.0:
        return None
    if annualization_factor is not None:
        if annualization_factor <= 0 or return_count <= 0:
            return None
        return (1.0 + total_return) ** (annualization_factor / return_count) - 1.0
    if elapsed_days >= 1.0:
        return (1.0 + total_return) ** (365.0 / elapsed_days) - 1.0
    return None


def _max_drawdown(snapshots: list[PortfolioSnapshot]) -> float:
    peak = snapshots[0].equity if snapshots else 0.0
    max_drawdown = 0.0
    for snapshot in snapshots:
        peak = max(peak, snapshot.equity)
        if peak:
            max_drawdown = max(max_drawdown, (peak - snapshot.equity) / peak)
    return max_drawdown


def _drawdown_at(equity: float, snapshots: list[PortfolioSnapshot]) -> float:
    peak = max((snapshot.equity for snapshot in snapshots), default=equity)
    return (peak - equity) / peak if peak else 0.0


__all__ = ["calculate_metrics", "equity_curve"]
