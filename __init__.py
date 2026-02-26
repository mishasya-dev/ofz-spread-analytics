"""
OFZ Analytics - Аналитика спредов ОФЗ
"""
from .config import AppConfig, BondConfig, TradingHours, BacktestConfig, SignalConfig, ExportConfig
from .api import TradingChecker, TradingStatus, HistoryFetcher, CandleFetcher
from .core import YTMCalculator, SpreadCalculator, SignalGenerator, TradingSignal, Backtester
from .export import SignalSender, JSONFormatter, TelegramFormatter, WebhookFormatter
from .modes import DailyMode, IntradayMode
from .components import ChartBuilder

__version__ = "2.0.0"
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
    "TradingChecker",
    "TradingStatus",
    "HistoryFetcher",
    "CandleFetcher",
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
    # Components
    "ChartBuilder",
]