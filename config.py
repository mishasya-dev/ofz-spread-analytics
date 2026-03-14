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

# Параметры интервалов свечей для слайдера периода свечей
CANDLE_INTERVAL_CONFIG = {
    "1": {
        "name": "1 минута",
        "min_days": 1,
        "max_days": 7,
        "default_days": 1,
        "step_days": 1,
        "api_max_days": 3,  # MOEX API ограничение
    },
    "10": {
        "name": "10 минут",
        "min_days": 10,
        "max_days": 90,
        "default_days": 10,
        "step_days": 1,
        "api_max_days": 90,
    },
    "60": {
        "name": "1 час",
        "min_days": 30,
        "max_days": 360,
        "default_days": 30,
        "step_days": 10,
        "api_max_days": 365,
    },
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
