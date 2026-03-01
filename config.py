"""
Конфигурация OFZ Analytics Application

Централизованная конфигурация всех параметров приложения.
"""
from dataclasses import dataclass, field
from typing import Dict, List
from datetime import time, date


# ==========================================
# КОНСТАНТЫ MOEX API
# ==========================================

# Максимальное количество дней с последней торговли
MAX_TRADE_DAYS_AGO = 10

# Минимальный срок до погашения (дней)
MIN_MATURITY_DAYS = 180

# Базовый URL MOEX ISS API
MOEX_BASE_URL = "https://iss.moex.com/iss"


# ==========================================
# КОНСТАНТЫ ИНТЕРВАЛОВ
# ==========================================

# Параметры интервалов свечей
INTRADAY_INTERVALS = {
    "1": {"max_days": 3, "default": 1, "name": "1 минута"},
    "10": {"max_days": 60, "default": 7, "name": "10 минут"},
    "60": {"max_days": 365, "default": 30, "name": "1 час"},
}

# Интервалы для обновления БД
DB_UPDATE_INTERVALS = [
    ("60", 30),  # часовые за 30 дней
    ("10", 7),   # 10-минутные за 7 дней
    ("1", 3),    # минутные за 3 дня
]


# ==========================================
# КОНСТАНТЫ СИГНАЛОВ
# ==========================================

# Перцентили для сигналов
SIGNAL_PERCENTILES = {
    "entry_strong": 10,   # P10 - сильный сигнал на покупку
    "entry_mid": 25,       # P25 - средний сигнал на покупку
    "exit_mid": 75,        # P75 - средний сигнал на продажу
    "exit_strong": 90,     # P90 - сильный сигнал на продажу
}


# ==========================================
# КОНСТАНТЫ YTM
# ==========================================

# Параметры расчёта YTM
YTM_MAX_ITERATIONS = 100
YTM_TOLERANCE = 1e-8
YTM_FALLBACK_TOLERANCE = 1e-6


# ==========================================
# КОНФИГУРАЦИОННЫЕ КЛАССЫ
# ==========================================

@dataclass
class BondConfig:
    """Конфигурация облигации"""
    isin: str
    name: str
    maturity_date: str
    coupon_rate: float
    face_value: float = 1000.0
    coupon_frequency: int = 2  # Купоны в год (2 = полугодовые)
    issue_date: str = ""
    day_count_convention: str = "ACT/ACT"  # База расчёта дней


@dataclass
class TradingHours:
    """Часы торговли на Мосбирже"""
    premarket_start: time = time(6, 50)
    main_session_start: time = time(7, 0)
    main_session_end: time = time(15, 40)
    postmarket_start: time = time(15, 45)
    postmarket_end: time = time(16, 0)


@dataclass
class BacktestConfig:
    """Конфигурация бэктестинга"""
    initial_capital: float = 1_000_000.0
    commission_rate: float = 0.0005
    spread_cost: float = 0.5
    holding_period_days: int = 5
    stop_loss_bp: float = 20.0
    take_profit_bp: float = 30.0


@dataclass
class SignalConfig:
    """Конфигурация торговых сигналов"""
    percentile_window: int = 252
    entry_threshold_low: float = 10.0
    entry_threshold_mid: float = 25.0
    exit_threshold_high: float = 75.0
    exit_threshold_extreme: float = 90.0


@dataclass
class ExportConfig:
    """Конфигурация экспорта сигналов"""
    webhook_url: str = ""
    telegram_token: str = ""
    telegram_chat_id: str = ""
    api_endpoint: str = ""
    api_key: str = ""


@dataclass
class AppConfig:
    """Главная конфигурация приложения"""
    
    # OFZ облигации для анализа (полные параметры с MOEX)
    bonds: Dict[str, BondConfig] = field(default_factory=lambda: {
        "SU26221RMFS0": BondConfig(
            isin="SU26221RMFS0",
            name="ОФЗ 26221",
            maturity_date="2033-03-23",
            coupon_rate=7.7,
            face_value=1000,
            coupon_frequency=2,
            issue_date="2017-02-15",
        ),
        "SU26225RMFS1": BondConfig(
            isin="SU26225RMFS1",
            name="ОФЗ 26225",
            maturity_date="2034-05-10",
            coupon_rate=7.25,
            face_value=1000,
            coupon_frequency=2,
            issue_date="2018-02-21",
        ),
        "SU26230RMFS1": BondConfig(
            isin="SU26230RMFS1",
            name="ОФЗ 26230",
            maturity_date="2039-03-16",
            coupon_rate=7.7,
            face_value=1000,
            coupon_frequency=2,
            issue_date="2019-06-05",
        ),
        "SU26238RMFS4": BondConfig(
            isin="SU26238RMFS4",
            name="ОФЗ 26238",
            maturity_date="2041-05-15",
            coupon_rate=7.1,
            face_value=1000,
            coupon_frequency=2,
            issue_date="2021-06-16",
        ),
        "SU26240RMFS0": BondConfig(
            isin="SU26240RMFS0",
            name="ОФЗ 26240",
            maturity_date="2036-07-30",
            coupon_rate=7.0,
            face_value=1000,
            coupon_frequency=2,
            issue_date="2021-06-30",
        ),
        "SU26241RMFS8": BondConfig(
            isin="SU26241RMFS8",
            name="ОФЗ 26241",
            maturity_date="2032-11-17",
            coupon_rate=9.5,
            face_value=1000,
            coupon_frequency=2,
            issue_date="2022-11-16",
        ),
        "SU26243RMFS4": BondConfig(
            isin="SU26243RMFS4",
            name="ОФЗ 26243",
            maturity_date="2038-05-19",
            coupon_rate=9.8,
            face_value=1000,
            coupon_frequency=2,
            issue_date="2023-06-21",
        ),
        "SU26244RMFS2": BondConfig(
            isin="SU26244RMFS2",
            name="ОФЗ 26244",
            maturity_date="2034-03-15",
            coupon_rate=11.25,
            face_value=1000,
            coupon_frequency=2,
            issue_date="2023-10-25",
        ),
        "SU26245RMFS9": BondConfig(
            isin="SU26245RMFS9",
            name="ОФЗ 26245",
            maturity_date="2035-09-26",
            coupon_rate=12.0,
            face_value=1000,
            coupon_frequency=2,
            issue_date="2024-05-15",
        ),
        "SU26246RMFS7": BondConfig(
            isin="SU26246RMFS7",
            name="ОФЗ 26246",
            maturity_date="2036-03-12",
            coupon_rate=12.0,
            face_value=1000,
            coupon_frequency=2,
            issue_date="2024-05-15",
        ),
        "SU26247RMFS5": BondConfig(
            isin="SU26247RMFS5",
            name="ОФЗ 26247",
            maturity_date="2039-05-11",
            coupon_rate=12.25,
            face_value=1000,
            coupon_frequency=2,
            issue_date="2024-05-15",
        ),
        "SU26248RMFS3": BondConfig(
            isin="SU26248RMFS3",
            name="ОФЗ 26248",
            maturity_date="2040-05-16",
            coupon_rate=12.25,
            face_value=1000,
            coupon_frequency=2,
            issue_date="2024-05-15",
        ),
        "SU26250RMFS9": BondConfig(
            isin="SU26250RMFS9",
            name="ОФЗ 26250",
            maturity_date="2037-06-10",
            coupon_rate=12.0,
            face_value=1000,
            coupon_frequency=2,
            issue_date="2025-06-25",
        ),
        "SU26252RMFS5": BondConfig(
            isin="SU26252RMFS5",
            name="ОФЗ 26252",
            maturity_date="2033-10-12",
            coupon_rate=12.5,
            face_value=1000,
            coupon_frequency=2,
            issue_date="2025-10-22",
        ),
        "SU26253RMFS3": BondConfig(
            isin="SU26253RMFS3",
            name="ОФЗ 26253",
            maturity_date="2038-10-06",
            coupon_rate=13.0,
            face_value=1000,
            coupon_frequency=2,
            issue_date="2025-10-22",
        ),
        "SU26254RMFS1": BondConfig(
            isin="SU26254RMFS1",
            name="ОФЗ 26254",
            maturity_date="2040-10-03",
            coupon_rate=13.0,
            face_value=1000,
            coupon_frequency=2,
            issue_date="2025-10-22",
        ),
    })
    
    # Торговые пары для спредов
    spread_pairs: List[tuple] = field(default_factory=lambda: [
        ("SU26221RMFS0", "SU26225RMFS1"),
        ("SU26230RMFS1", "SU26238RMFS4"),
        ("SU26240RMFS0", "SU26241RMFS8"),
        ("SU26243RMFS4", "SU26244RMFS2"),
    ])
    
    # API MOEX
    moex_base_url: str = "https://iss.moex.com/iss"
    cache_ttl_seconds: int = 300
    
    # Подконфигурации
    trading_hours: TradingHours = field(default_factory=TradingHours)
    backtest: BacktestConfig = field(default_factory=BacktestConfig)
    signals: SignalConfig = field(default_factory=SignalConfig)
    export: ExportConfig = field(default_factory=ExportConfig)
    
    # Режим работы
    mode: str = "daily"
    auto_refresh_seconds: int = 60
    lookback_days: int = 365


# Глобальный экземпляр конфигурации
config = AppConfig()
