"""
OFZ Analytics - Аналитика спредов ОФЗ

Версия 2.2.0 - Новая архитектура MOEX API
"""

__version__ = "2.2.0"
__author__ = "OFZ Analytics Team"

# Ленивый импорт - только при реальном использовании
__all__ = [
    # API (v2.0)
    "MOEXClient",
    "TradingStatus",
    "ExchangeInfo",
    "is_market_open",
    "fetch_ofz_only",
    "fetch_ytm_history",
    "fetch_candles",
    # Config
    "AppConfig",
    "BondConfig",
    "TradingHours",
    "BacktestConfig",
    "SignalConfig",
    "ExportConfig",
    # Core
    "YTMCalculator",
    "SpreadCalculator",
    "SignalGenerator",
    "TradingSignal",
    "Backtester",
    # Export
    "SignalSender",
    "JSONFormatter",
    "TelegramFormatter",
    "WebhookFormatter",
    # Modes
    "DailyMode",
    "IntradayMode",
]


def __getattr__(name):
    """Ленивый импорт при обращении к атрибутам"""
    if name == "MOEXClient":
        from api.moex_client import MOEXClient
        return MOEXClient
    elif name == "TradingStatus":
        from api.moex_trading import TradingStatus
        return TradingStatus
    elif name == "ExchangeInfo":
        from api.moex_trading import ExchangeInfo
        return ExchangeInfo
    elif name == "is_market_open":
        from api.moex_trading import is_market_open
        return is_market_open
    elif name == "fetch_ofz_only":
        from api.moex_bonds import fetch_ofz_only
        return fetch_ofz_only
    elif name == "fetch_ytm_history":
        from api.moex_history import fetch_ytm_history
        return fetch_ytm_history
    elif name == "fetch_candles":
        from api.moex_candles import fetch_candles
        return fetch_candles
    elif name in ("AppConfig", "BondConfig", "TradingHours", "BacktestConfig", "SignalConfig", "ExportConfig"):
        from config import AppConfig, BondConfig, TradingHours, BacktestConfig, SignalConfig, ExportConfig
        return locals()[name]
    elif name in ("YTMCalculator", "SpreadCalculator", "SignalGenerator", "TradingSignal", "Backtester"):
        from core import YTMCalculator, SpreadCalculator, SignalGenerator, TradingSignal, Backtester
        return locals()[name]
    elif name in ("SignalSender", "JSONFormatter", "TelegramFormatter", "WebhookFormatter"):
        from export import SignalSender, JSONFormatter, TelegramFormatter, WebhookFormatter
        return locals()[name]
    elif name in ("DailyMode", "IntradayMode"):
        from modes import DailyMode, IntradayMode
        return locals()[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
