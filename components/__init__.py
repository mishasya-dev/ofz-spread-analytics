"""
Компоненты визуализации v0.3.0
"""
from .charts import (
    ChartBuilder,
    create_ytm_chart,
    create_spread_chart,
    create_signal_chart,
    create_backtest_chart,
    create_daily_ytm_chart,
    create_daily_spread_chart,
    create_combined_ytm_chart,
    create_intraday_spread_chart,
    apply_zoom_range,
)
from .sidebar import (
    get_bonds_list,
    get_years_to_maturity,
    format_bond_label,
    render_bond_selection,
    render_period_selector,
    render_candle_interval_selector,
    render_auto_refresh,
    render_db_panel,
    render_cache_clear,
    render_sidebar,
)
from .db_panel import (
    render_db_stats,
    render_db_panel as render_db_panel_component,
    update_database_full,
)
from .metrics import (
    calculate_spread_stats,
    render_spread_stats,
)
from .signals import (
    generate_signal,
    render_signal_card,
)
from .header import render_header
from .styles import apply_styles

__all__ = [
    # Charts
    "ChartBuilder",
    "create_ytm_chart",
    "create_spread_chart",
    "create_signal_chart",
    "create_backtest_chart",
    "create_daily_ytm_chart",
    "create_daily_spread_chart",
    "create_combined_ytm_chart",
    "create_intraday_spread_chart",
    "apply_zoom_range",
    # Sidebar
    "get_bonds_list",
    "get_years_to_maturity",
    "format_bond_label",
    "render_bond_selection",
    "render_period_selector",
    "render_candle_interval_selector",
    "render_auto_refresh",
    "render_db_panel",
    "render_cache_clear",
    "render_sidebar",
    # DB Panel
    "render_db_stats",
    "render_db_panel_component",
    "update_database_full",
    # Metrics
    "calculate_spread_stats",
    "render_spread_stats",
    # Signals
    "generate_signal",
    "render_signal_card",
    # Header
    "render_header",
    # Styles
    "apply_styles",
]
