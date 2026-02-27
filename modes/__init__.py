"""
Режимы работы приложения
"""
from .base import DailyMode, DailyModeResult
from .intraday import IntradayMode, IntradayModeResult

__all__ = [
    "DailyMode",
    "DailyModeResult",
    "IntradayMode",
    "IntradayModeResult",
]