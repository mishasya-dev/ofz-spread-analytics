"""
Сервисы для OFZ Spread Analytics

Сервисы инкапсулируют бизнес-логику и работу с внешними API.
"""
from .candle_service import CandleService, get_candle_service
from .data_loader import (
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
from .candle_processor_ytm_for_bonds import (
    BondYTMProcessor,
    calculate_ytm_for_bond_price,
    get_t1_settlement_date,
)
from .g_spread_calculator import (
    # DEPRECATED: nelson_siegel, nelson_siegel_vectorized, calculate_g_spread,
    # DEPRECATED: calculate_g_spread_history, enrich_bond_data, GSpreadCalculator
    calculate_g_spread_stats,
    generate_g_spread_signal,
)

__all__ = [
    # CandleService
    'CandleService',
    'get_candle_service',
    # DataLoader
    'fetch_historical_data',
    'fetch_candle_data',
    'update_database_full',
    # SpreadCalculator
    'calculate_spread_stats',
    'generate_signal',
    'prepare_spread_dataframe',
    'calculate_rolling_stats',
    'calculate_zscore',
    # BondYTMProcessor
    'BondYTMProcessor',
    'calculate_ytm_for_bond_price',
    'get_t1_settlement_date',
    # GSpreadCalculator (активные функции)
    'calculate_g_spread_stats',
    'generate_g_spread_signal',
]
