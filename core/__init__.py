"""
Core модули для аналитики

NOTE: Removed DEAD CODE:
- SpreadCalculator → use services/spread_calculator.py
- SignalGenerator → use services/spread_calculator.py::generate_signal()
- TradingSignal → not needed
- Backtester → not used in app.py
"""
from .ytm_calculator import YTMCalculator

__all__ = [
    "YTMCalculator",
]
