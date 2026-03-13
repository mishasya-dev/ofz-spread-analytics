"""
API модули для работы с Мосбиржей

Новая архитектура (v2.0):
- MOEXClient: единый клиент с context manager
- Функции вместо классов: fetch_*, get_*, check_*
"""
from .moex_client import (
    MOEXClient,
    get_client,
    close_client,
    MOEX_BASE_URL,
)

from .moex_trading import (
    TradingStatus,
    ExchangeInfo,
    check_by_api,
    check_by_schedule,
    check_comprehensive,
    is_trading_now,
    is_market_open,
    get_trading_schedule,
)

from .moex_bonds import (
    fetch_all_bonds,
    fetch_ofz_only,
    fetch_bond_details,
    fetch_market_data,
    fetch_all_market_data,
    fetch_ofz_with_market_data,
    fetch_all_ofz,
    filter_ofz_for_trading,
    fetch_and_filter_ofz,
)

from .moex_zcyc import (
    NSParams,
    fetch_ns_params_by_date,
    fetch_ns_params_history,
    fetch_ns_params_incremental,
    fetch_current_zcyc,
    fetch_current_clcyield,
    fetch_all_clcyields,
    get_ns_params_history,
    get_zcyc_data_for_date,
    get_zcyc_history,
    get_zcyc_history_parallel,
)

from .moex_candles import (
    CandleInterval,
    Candle,
    fetch_candles,
    fetch_candles_with_ytm,
    get_raw_candles,
)

from .moex_history import (
    BondData,
    is_valid_ytm_row,
    fetch_ytm_history,
    fetch_multi_bonds_history,
    fetch_multi_bonds_history_parallel,
    fetch_bond_info,
    get_latest_ytm,
    get_trading_data,
    get_ytm_history,
)


__all__ = [
    # Client
    "MOEXClient",
    "get_client",
    "close_client",
    "MOEX_BASE_URL",
    # Trading
    "TradingStatus",
    "ExchangeInfo",
    "check_by_api",
    "check_by_schedule",
    "check_comprehensive",
    "is_trading_now",
    "is_market_open",
    "get_trading_schedule",
    # Bonds
    "fetch_all_bonds",
    "fetch_ofz_only",
    "fetch_bond_details",
    "fetch_market_data",
    "fetch_all_market_data",
    "fetch_ofz_with_market_data",
    "fetch_all_ofz",
    "filter_ofz_for_trading",
    "fetch_and_filter_ofz",
    # ZCYC
    "NSParams",
    "fetch_ns_params_by_date",
    "fetch_ns_params_history",
    "fetch_ns_params_incremental",
    "fetch_current_zcyc",
    "fetch_current_clcyield",
    "fetch_all_clcyields",
    "get_ns_params_history",
    "get_zcyc_data_for_date",
    "get_zcyc_history",
    "get_zcyc_history_parallel",
    # Candles
    "CandleInterval",
    "Candle",
    "fetch_candles",
    "fetch_candles_with_ytm",
    "get_raw_candles",
    # History
    "BondData",
    "is_valid_ytm_row",
    "fetch_ytm_history",
    "fetch_multi_bonds_history",
    "fetch_multi_bonds_history_parallel",
    "fetch_bond_info",
    "get_latest_ytm",
    "get_trading_data",
    "get_ytm_history",
]
