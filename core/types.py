"""
Типы данных для OFZ Spread Analytics

TypedDict и Protocol для статической типизации.
"""
from typing import TypedDict, Optional, Dict, List, Any, Protocol
from datetime import date, datetime


# ==========================================
# ТИПЫ ДАННЫХ ОБЛИГАЦИЙ
# ==========================================

class BondDataDict(TypedDict, total=False):
    """Словарь с данными облигации (из БД или API)"""
    isin: str
    name: str
    short_name: str
    coupon_rate: float
    maturity_date: str
    issue_date: str
    face_value: float
    coupon_frequency: int
    day_count: str
    day_count_convention: str
    is_favorite: int
    last_price: float
    last_ytm: float
    duration_years: float
    duration_days: float
    last_trade_date: str
    last_updated: str


class BondConfigDict(TypedDict, total=False):
    """Словарь конфигурации облигации (из config.py)"""
    isin: str
    name: str
    short_name: str
    maturity_date: str
    coupon_rate: float
    face_value: float
    coupon_frequency: int
    issue_date: str
    day_count_convention: str


# ==========================================
# ТИПЫ ДАННЫХ YTM
# ==========================================

class YTMDataPoint(TypedDict):
    """Точка данных YTM"""
    date: date
    ytm: float
    price: Optional[float]
    duration_days: Optional[float]


class IntradayYTMPoint(TypedDict):
    """Точка внутридневного YTM"""
    datetime: datetime
    price_close: float
    ytm: float
    accrued_interest: Optional[float]


# ==========================================
# ТИПЫ ДАННЫХ СВЕЧЕЙ
# ==========================================

class CandleData(TypedDict, total=False):
    """Данные свечи"""
    datetime: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    ytm_open: Optional[float]
    ytm_high: Optional[float]
    ytm_low: Optional[float]
    ytm_close: Optional[float]


# ==========================================
# ТИПЫ ДАННЫХ СПРЕДОВ
# ==========================================

class SpreadDataPoint(TypedDict):
    """Точка данных спреда"""
    datetime: datetime
    isin_1: str
    isin_2: str
    ytm_1: float
    ytm_2: float
    spread_bp: float
    signal: Optional[str]
    p25: Optional[float]
    p75: Optional[float]


class SpreadStats(TypedDict):
    """Статистика спреда"""
    mean: float
    median: float
    std: float
    min: float
    max: float
    p10: float
    p25: float
    p75: float
    p90: float
    current: float


# ==========================================
# ТИПЫ СИГНАЛОВ
# ==========================================

class TradingSignalDict(TypedDict):
    """Торговый сигнал"""
    signal: str  # 'SELL_BUY', 'BUY_SELL', 'NEUTRAL'
    action: str
    reason: str
    color: str
    strength: str


# ==========================================
# ТИПЫ БАЗЫ ДАННЫХ
# ==========================================

class DatabaseStats(TypedDict):
    """Статистика базы данных"""
    bonds_count: int
    candles_count: int
    daily_ytm_count: int
    intraday_ytm_count: int
    spreads_count: int
    snapshots_count: int
    candles_by_interval: Dict[str, int]
    intraday_by_interval: Dict[str, int]
    last_daily_ytm: Optional[str]
    last_intraday_ytm: Optional[str]


# ==========================================
# ТИПЫ SESSION STATE
# ==========================================

class SessionStateDict(TypedDict, total=False):
    """Состояние сессии Streamlit"""
    config: Any
    bonds_loaded: bool
    bonds: Dict[str, BondConfigDict]
    selected_bond1: int
    selected_bond2: int
    period: int
    data_mode: str  # 'daily' | 'intraday'
    candle_interval: str  # '1' | '10' | '60'
    auto_refresh: bool
    refresh_interval: int
    intraday_refresh_interval: int
    last_update: Optional[datetime]
    intraday_period: int
    save_data: bool
    saved_count: int
    updating_db: bool
    bond_manager_open_id: Optional[str]
    bond_manager_last_shown_id: Optional[str]
    bond_manager_current_favorites: Optional[set]
    bond_manager_original_favorites: Optional[set]
    cached_favorites_count: int


# ==========================================
# PROTOCOLS
# ==========================================

class BondRepositoryProtocol(Protocol):
    """Протокол репозитория облигаций"""
    
    def save(self, bond_data: BondDataDict) -> bool: ...
    def load(self, isin: str) -> Optional[BondDataDict]: ...
    def get_all(self) -> List[BondDataDict]: ...
    def get_favorites(self) -> List[BondDataDict]: ...
    def set_favorite(self, isin: str, is_favorite: bool) -> bool: ...
    def delete(self, isin: str) -> bool: ...


class YTMRepositoryProtocol(Protocol):
    """Протокол репозитория YTM"""
    
    def save_daily_ytm(self, isin: str, df: Any) -> int: ...
    def load_daily_ytm(self, isin: str, start_date: Optional[date], end_date: Optional[date]) -> Any: ...
    def save_intraday_ytm(self, isin: str, interval: str, df: Any) -> int: ...
    def load_intraday_ytm(self, isin: str, interval: str, start_date: Optional[date], end_date: Optional[date]) -> Any: ...


class CandleServiceProtocol(Protocol):
    """Протокол сервиса свечей"""
    
    def get_candles_with_ytm(
        self,
        bond: Any,
        interval: str,
        days: int
    ) -> Any: ...
    def close(self) -> None: ...
