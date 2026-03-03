"""
Сервисы для OFZ Spread Analytics

Сервисы инкапсулируют бизнес-логику и работу с внешними API.
"""
from .candle_service import CandleService, get_candle_service
from .data_loader import (
    get_history_fetcher,
    get_candle_fetcher,
    fetch_trading_data,
    fetch_historical_data,
    fetch_candle_data,
    update_database_full,
)
from .spread_calculator import (
    calculate_spread_stats,
    generate_signal,
    prepare_spread_dataframe,
    calculate_rolling_stats,
    calculate_zscore,
)

__all__ = [
    # CandleService
    'CandleService',
    'get_candle_service',
    # DataLoader
    'get_history_fetcher',
    'get_candle_fetcher',
    'fetch_trading_data',
    'fetch_historical_data',
    'fetch_candle_data',
    'update_database_full',
    # SpreadCalculator
    'calculate_spread_stats',
    'generate_signal',
    'prepare_spread_dataframe',
    'calculate_rolling_stats',
    'calculate_zscore',
]
