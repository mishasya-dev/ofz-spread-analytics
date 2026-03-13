"""
OFZ Analytics - Аналитика спредов ОФЗ

Новая архитектура API (v2.0):
- MOEXClient: единый клиент с context manager
- Функции вместо классов: fetch_*, get_*, check_*
"""
# Безопасный импорт - работает и как пакет и как модуль
try:
    from .config import AppConfig, BondConfig, TradingHours, BacktestConfig, SignalConfig, ExportConfig
    # Новый API - функции вместо классов
    from .api import (
        MOEXClient,
        TradingStatus,
        fetch_ytm_history,
        fetch_candles,
        check_comprehensive,
    )
    from .core import YTMCalculator, SpreadCalculator, SignalGenerator, TradingSignal, Backtester
    from .export import SignalSender, JSONFormatter, TelegramFormatter, WebhookFormatter
    from .modes import DailyMode, IntradayMode
except ImportError:
    # Fallback для запуска без пакета
    from config import AppConfig, BondConfig, TradingHours, BacktestConfig, SignalConfig, ExportConfig
    from api import (
        MOEXClient,
        TradingStatus,
        fetch_ytm_history,
        fetch_candles,
        check_comprehensive,
    )
    from core import YTMCalculator, SpreadCalculator, SignalGenerator, TradingSignal, Backtester
    from export import SignalSender, JSONFormatter, TelegramFormatter, WebhookFormatter
    from modes import DailyMode, IntradayMode

__version__ = "2.1.0"
__author__ = "OFZ Analytics Team"

__all__ = [
    # Config
    "AppConfig",
    "BondConfig",
    "TradingHours",
    "BacktestConfig",
    "SignalConfig",
    "ExportConfig",
    # API (новая архитектура)
    "MOEXClient",
    "TradingStatus",
    "fetch_ytm_history",
    "fetch_candles",
    "check_comprehensive",
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
