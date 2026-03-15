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
    from .core import YTMCalculator
    # NOTE: Removed DEAD CODE - SpreadCalculator, SignalGenerator, TradingSignal, Backtester
    # Use services/spread_calculator.py instead
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
    from core import YTMCalculator

__version__ = "2.2.0"
__author__ = "OFZ Analytics Team"

__all__ = [
    # Config
    "AppConfig",
    "BondConfig",
    "TradingHours",
    "BacktestConfig",
    "SignalConfig",
    "ExportConfig",
    # API
    "MOEXClient",
    "TradingStatus",
    "fetch_ytm_history",
    "fetch_candles",
    "check_comprehensive",
    # Core
    "YTMCalculator",
]
