"""Dependency-free static SVG charts for backtest diagnostics."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from xml.sax.saxutils import escape

from qts.domain import BacktestResult, OrderSide

from .metrics import equity_curve


WIDTH = 960
HEIGHT = 360
PADDING_LEFT = 76
PADDING_RIGHT = 28
PADDING_TOP = 54
PADDING_BOTTOM = 58


def generate_backtest_charts(
    backtest_result: BacktestResult,
    output_path: str | Path,
) -> dict[str, Path]:
    """Write static SVG chart artifacts for a completed backtest."""
    output_dir = Path(output_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    run_id = backtest_result.run_id

    chart_paths = {
        "equity_curve_chart": output_dir / f"{run_id}_equity_curve.svg",
        "drawdown_chart": output_dir / f"{run_id}_drawdown.svg",
    }
    chart_paths["equity_curve_chart"].write_text(
        render_equity_curve_svg(backtest_result),
        encoding="utf-8",
    )
    chart_paths["drawdown_chart"].write_text(
        render_drawdown_svg(backtest_result),
        encoding="utf-8",
    )
    return chart_paths


def render_equity_curve_svg(backtest_result: BacktestResult) -> str:
    """Render an equity curve chart with buy/sell fill markers."""
    rows = equity_curve(backtest_result.portfolio_snapshots)
    markers = _trade_markers(backtest_result, rows)
    return _render_line_chart(
        title=f"Equity Curve - {backtest_result.run_id}",
        description="Portfolio equity through the backtest with executed fill markers.",
        rows=rows,
        value_key="equity",
        y_label="Equity",
        stroke="#2563eb",
        format_y=_format_money,
        markers=markers,
    )


def render_drawdown_svg(backtest_result: BacktestResult) -> str:
    """Render a drawdown chart from portfolio snapshots."""
    rows = equity_curve(backtest_result.portfolio_snapshots)
    return _render_line_chart(
        title=f"Drawdown - {backtest_result.run_id}",
        description="Peak-to-current portfolio equity drawdown through the backtest.",
        rows=rows,
        value_key="drawdown",
        y_label="Drawdown",
        stroke="#dc2626",
        format_y=_format_percent,
        include_zero=True,
        invert_y=False,
        fill_under_line=True,
    )


def _render_line_chart(
    *,
    title: str,
    description: str,
    rows: list[dict[str, float | str]],
    value_key: str,
    y_label: str,
    stroke: str,
    format_y: Callable[[float], str],
    include_zero: bool = False,
    invert_y: bool = True,
    fill_under_line: bool = False,
    markers: list[dict[str, float | str]] | None = None,
) -> str:
    chart_id = _svg_id(title)
    if not rows:
        return _empty_chart(title, description, chart_id, "No portfolio snapshots were recorded.")

    timestamps = [str(row["timestamp"]) for row in rows]
    values = [float(row[value_key]) for row in rows]
    y_min, y_max = _value_range(values, include_zero=include_zero)
    points = [
        (
            _scale_x(index, len(values)),
            _scale_y(value, y_min, y_max, invert=invert_y),
        )
        for index, value in enumerate(values)
    ]

    grid = _grid_lines(y_min, y_max, invert_y, format_y)
    point_text = " ".join(f"{x:.2f},{y:.2f}" for x, y in points)
    marker_text = _marker_elements(markers or [], y_min, y_max, len(values), invert_y)
    area_text = ""
    if fill_under_line and points:
        baseline = _scale_y(0.0 if include_zero else y_min, y_min, y_max, invert=invert_y)
        area_points = [(points[0][0], baseline), *points, (points[-1][0], baseline)]
        area_text = (
            f'<polygon points="{" ".join(f"{x:.2f},{y:.2f}" for x, y in area_points)}" '
            f'fill="{stroke}" opacity="0.10" />'
        )

    x_labels = _x_axis_labels(timestamps, len(values))
    legend = ""
    if markers:
        legend = (
            '<g font-family="Arial, sans-serif" font-size="12" fill="#334155">'
            '<circle cx="790" cy="30" r="4" fill="#059669" />'
            '<text x="800" y="34">Buy</text>'
            '<circle cx="842" cy="30" r="4" fill="#dc2626" />'
            '<text x="852" y="34">Sell</text>'
            "</g>"
        )

    return "\n".join(
        [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" '
            f'viewBox="0 0 {WIDTH} {HEIGHT}" role="img" '
            f'aria-labelledby="{chart_id}-title {chart_id}-desc">',
            f'<title id="{chart_id}-title">{escape(title)}</title>',
            f'<desc id="{chart_id}-desc">{escape(description)}</desc>',
            '<rect width="100%" height="100%" fill="#ffffff" />',
            f'<text x="{PADDING_LEFT}" y="28" font-family="Arial, sans-serif" '
            f'font-size="20" font-weight="700" fill="#0f172a">{escape(title)}</text>',
            legend,
            f'<line x1="{PADDING_LEFT}" y1="{HEIGHT - PADDING_BOTTOM}" '
            f'x2="{WIDTH - PADDING_RIGHT}" y2="{HEIGHT - PADDING_BOTTOM}" '
            'stroke="#94a3b8" stroke-width="1" />',
            f'<line x1="{PADDING_LEFT}" y1="{PADDING_TOP}" '
            f'x2="{PADDING_LEFT}" y2="{HEIGHT - PADDING_BOTTOM}" '
            'stroke="#94a3b8" stroke-width="1" />',
            grid,
            area_text,
            f'<polyline points="{point_text}" fill="none" stroke="{stroke}" '
            'stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round" />',
            marker_text,
            f'<text x="18" y="178" transform="rotate(-90 18 178)" '
            f'font-family="Arial, sans-serif" font-size="12" fill="#475569">{escape(y_label)}</text>',
            x_labels,
            "</svg>",
        ]
    )


def _trade_markers(
    backtest_result: BacktestResult,
    rows: list[dict[str, float | str]],
) -> list[dict[str, float | str]]:
    if not rows or not backtest_result.fills:
        return []
    snapshots = backtest_result.portfolio_snapshots
    markers: list[dict[str, float | str]] = []
    for fill in backtest_result.fills:
        nearest_index = min(
            range(len(snapshots)),
            key=lambda index: abs((snapshots[index].timestamp - fill.timestamp).total_seconds()),
        )
        side = fill.side.value if isinstance(fill.side, OrderSide) else str(fill.side)
        markers.append(
            {
                "index": float(nearest_index),
                "value": float(rows[nearest_index]["equity"]),
                "color": "#059669" if side.upper() == "BUY" else "#dc2626",
                "label": (
                    f"{side.upper()} {fill.quantity:g} {fill.symbol} "
                    f"at {fill.price:g} on {fill.timestamp.isoformat()}"
                ),
            }
        )
    return markers


def _marker_elements(
    markers: list[dict[str, float | str]],
    y_min: float,
    y_max: float,
    count: int,
    invert_y: bool,
) -> str:
    elements: list[str] = []
    for marker in markers:
        x = _scale_x(int(marker["index"]), count)
        y = _scale_y(float(marker["value"]), y_min, y_max, invert=invert_y)
        color = str(marker["color"])
        label = escape(str(marker["label"]))
        elements.append(
            f'<circle cx="{x:.2f}" cy="{y:.2f}" r="4.5" fill="{color}" '
            'stroke="#ffffff" stroke-width="1.5">'
            f"<title>{label}</title></circle>"
        )
    return "\n".join(elements)


def _grid_lines(
    y_min: float,
    y_max: float,
    invert_y: bool,
    format_y: Callable[[float], str],
) -> str:
    lines: list[str] = []
    for index in range(5):
        ratio = index / 4
        value = y_min + (y_max - y_min) * ratio
        y = _scale_y(value, y_min, y_max, invert=invert_y)
        lines.append(
            f'<line x1="{PADDING_LEFT}" y1="{y:.2f}" x2="{WIDTH - PADDING_RIGHT}" '
            f'y2="{y:.2f}" stroke="#e2e8f0" stroke-width="1" />'
        )
        lines.append(
            f'<text x="{PADDING_LEFT - 8}" y="{y + 4:.2f}" text-anchor="end" '
            f'font-family="Arial, sans-serif" font-size="11" fill="#64748b">'
            f"{escape(format_y(value))}</text>"
        )
    return "\n".join(lines)


def _x_axis_labels(timestamps: list[str], count: int) -> str:
    if not timestamps:
        return ""
    indexes = sorted({0, max(0, count // 2), count - 1})
    labels: list[str] = []
    for index in indexes:
        labels.append(
            f'<text x="{_scale_x(index, count):.2f}" y="326" text-anchor="middle" '
            f'font-family="Arial, sans-serif" font-size="11" fill="#64748b">'
            f"{escape(_short_timestamp(timestamps[index]))}</text>"
        )
    return "\n".join(labels)


def _scale_x(index: int, count: int) -> float:
    if count <= 1:
        return (PADDING_LEFT + WIDTH - PADDING_RIGHT) / 2
    plot_width = WIDTH - PADDING_LEFT - PADDING_RIGHT
    return PADDING_LEFT + plot_width * index / (count - 1)


def _scale_y(value: float, y_min: float, y_max: float, *, invert: bool) -> float:
    plot_height = HEIGHT - PADDING_TOP - PADDING_BOTTOM
    span = y_max - y_min or 1.0
    ratio = (value - y_min) / span
    if invert:
        ratio = 1.0 - ratio
    return PADDING_TOP + plot_height * ratio


def _value_range(values: list[float], *, include_zero: bool) -> tuple[float, float]:
    candidates = [*values, 0.0] if include_zero else values
    y_min = min(candidates)
    y_max = max(candidates)
    if y_min == y_max:
        padding = abs(y_min) * 0.01 or 1.0
        return y_min - padding, y_max + padding
    padding = (y_max - y_min) * 0.06
    if include_zero and y_min >= 0:
        y_min = 0.0
    else:
        y_min -= padding
    y_max += padding
    return y_min, y_max


def _empty_chart(title: str, description: str, chart_id: str, message: str) -> str:
    return "\n".join(
        [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" '
            f'viewBox="0 0 {WIDTH} {HEIGHT}" role="img" '
            f'aria-labelledby="{chart_id}-title {chart_id}-desc">',
            f'<title id="{chart_id}-title">{escape(title)}</title>',
            f'<desc id="{chart_id}-desc">{escape(description)}</desc>',
            '<rect width="100%" height="100%" fill="#ffffff" />',
            f'<text x="{PADDING_LEFT}" y="32" font-family="Arial, sans-serif" '
            f'font-size="20" font-weight="700" fill="#0f172a">{escape(title)}</text>',
            f'<text x="{WIDTH / 2:.0f}" y="{HEIGHT / 2:.0f}" text-anchor="middle" '
            f'font-family="Arial, sans-serif" font-size="14" fill="#64748b">'
            f"{escape(message)}</text>",
            "</svg>",
        ]
    )


def _short_timestamp(value: str) -> str:
    return value.replace("T", " ").replace("+00:00", "Z").replace(".000000", "")


def _format_money(value: float) -> str:
    abs_value = abs(value)
    if abs_value >= 1_000_000:
        return f"${value / 1_000_000:.2f}M"
    if abs_value >= 1_000:
        return f"${value / 1_000:.1f}K"
    return f"${value:.2f}"


def _format_percent(value: float) -> str:
    return f"{value * 100:.2f}%"


def _svg_id(value: str) -> str:
    cleaned = "".join(character.lower() if character.isalnum() else "-" for character in value)
    return "-".join(part for part in cleaned.split("-") if part) or "chart"


__all__ = [
    "generate_backtest_charts",
    "render_drawdown_svg",
    "render_equity_curve_svg",
]
