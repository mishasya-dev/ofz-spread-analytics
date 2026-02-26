"""
Конфигурация OFZ Analytics Application
"""
from dataclasses import dataclass, field
from typing import Dict, List
from datetime import time


@dataclass
class BondConfig:
    """Конфигурация облигации"""
    isin: str
    name: str
    maturity_date: str
    coupon_rate: float


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
    initial_capital: float = 1_000_000.0  # 1 млн рублей
    commission_rate: float = 0.0005  # 0.05% комиссия
    spread_cost: float = 0.5  # 0.5 б.п. затраты на спред
    holding_period_days: int = 5  # Период удержания позиции
    stop_loss_bp: float = 20.0  # Стоп-лосс в базисных пунктах
    take_profit_bp: float = 30.0  # Тейк-профит в базисных пунктах


@dataclass
class SignalConfig:
    """Конфигурация торговых сигналов"""
    percentile_window: int = 252  # Окно для расчёта перцентилей (торговых дней)
    entry_threshold_low: float = 10.0  # P10 - вход в длинную позицию
    entry_threshold_mid: float = 25.0  # P25
    exit_threshold_high: float = 75.0  # P75
    exit_threshold_extreme: float = 90.0  # P90 - выход


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
    
    # OFZ облигации для анализа (верифицированные ISIN из рабочей версии)
    bonds: Dict[str, BondConfig] = field(default_factory=lambda: {
        "SU26221RMFS0": BondConfig("SU26221RMFS0", "ОФЗ 26221", "2033-03-23", 7.7),
        "SU26225RMFS1": BondConfig("SU26225RMFS1", "ОФЗ 26225", "2034-05-10", 7.25),
        "SU26230RMFS1": BondConfig("SU26230RMFS1", "ОФЗ 26230", "2041-05-14", 7.1),
        "SU26238RMFS4": BondConfig("SU26238RMFS4", "ОФЗ 26238", "2041-11-26", 7.4),
        "SU26240RMFS0": BondConfig("SU26240RMFS0", "ОФЗ 26240", "2039-03-23", 6.9),
        "SU26241RMFS8": BondConfig("SU26241RMFS8", "ОФЗ 26241", "2042-02-18", 7.0),
        "SU26243RMFS4": BondConfig("SU26243RMFS4", "ОФЗ 26243", "2035-05-15", 7.6),
        "SU26244RMFS2": BondConfig("SU26244RMFS2", "ОФЗ 26244", "2036-03-11", 7.5),
        "SU26245RMFS9": BondConfig("SU26245RMFS9", "ОФЗ 26245", "2037-05-13", 7.35),
        "SU26246RMFS7": BondConfig("SU26246RMFS7", "ОФЗ 26246", "2038-02-16", 7.15),
        "SU26247RMFS5": BondConfig("SU26247RMFS5", "ОФЗ 26247", "2039-05-17", 6.9),
        "SU26248RMFS3": BondConfig("SU26248RMFS3", "ОФЗ 26248", "2039-11-15", 6.7),
        "SU26250RMFS9": BondConfig("SU26250RMFS9", "ОФЗ 26250", "2036-11-25", 7.7),
        "SU26252RMFS5": BondConfig("SU26252RMFS5", "ОФЗ 26252", "2037-11-17", 7.55),
        "SU26253RMFS3": BondConfig("SU26253RMFS3", "ОФЗ 26253", "2040-05-15", 7.2),
        "SU26254RMFS1": BondConfig("SU26254RMFS1", "ОФЗ 26254", "2040-11-13", 6.95),
    })
    
    # Торговые пары для спредов (будут выбираться пользователем)
    spread_pairs: List[tuple] = field(default_factory=lambda: [
        ("SU26221RMFS0", "SU26225RMFS1"),  # ОФЗ 26221 - ОФЗ 26225
        ("SU26230RMFS1", "SU26238RMFS4"),  # ОФЗ 26230 - ОФЗ 26238
        ("SU26240RMFS0", "SU26241RMFS8"),  # ОФЗ 26240 - ОФЗ 26241
        ("SU26243RMFS4", "SU26244RMFS2"),  # ОФЗ 26243 - ОФЗ 26244
    ])
    
    # API MOEX
    moex_base_url: str = "https://iss.moex.com/iss"
    cache_ttl_seconds: int = 300  # 5 минут
    
    # Подконфигурации
    trading_hours: TradingHours = field(default_factory=TradingHours)
    backtest: BacktestConfig = field(default_factory=BacktestConfig)
    signals: SignalConfig = field(default_factory=SignalConfig)
    export: ExportConfig = field(default_factory=ExportConfig)
    
    # Режим работы
    mode: str = "daily"  # "daily" или "intraday"
    auto_refresh_seconds: int = 60
    lookback_days: int = 365  # Дней истории для анализа


# Глобальный экземпляр конфигурации
config = AppConfig()
