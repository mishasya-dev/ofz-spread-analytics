"""
Режим работы с дневными данными (базовый режим)
"""
import pandas as pd
import numpy as np
from datetime import date, datetime, timedelta
from typing import Optional, Dict, List, Tuple, Any
from dataclasses import dataclass, field
import logging

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.moex_trading import TradingChecker, TradingStatus, ExchangeInfo
from api.moex_history import HistoryFetcher
from core.spread import SpreadCalculator, SpreadStats, SpreadData
from core.signals import SignalGenerator, TradingSignal, SignalType
from core.backtest import Backtester, BacktestResult
from config import AppConfig

logger = logging.getLogger(__name__)


@dataclass
class BondInfo:
    """Информация об облигации"""
    isin: str
    name: str
    current_ytm: Optional[float]
    duration_years: Optional[float]
    years_to_maturity: Optional[float]
    last_price: Optional[float]
    coupon_rate: Optional[float]


@dataclass
class DailyModeResult:
    """Результат работы дневного режима"""
    # Статус биржи
    exchange_status: TradingStatus
    is_trading: bool
    exchange_message: str
    
    # Данные
    bonds: Dict[str, BondInfo] = field(default_factory=dict)
    ytm_history: Dict[str, pd.DataFrame] = field(default_factory=dict)
    spreads: Dict[str, SpreadData] = field(default_factory=dict)
    spread_stats: Dict[str, SpreadStats] = field(default_factory=dict)
    
    # Сигналы
    signals: List[TradingSignal] = field(default_factory=list)
    active_signals: List[TradingSignal] = field(default_factory=list)
    
    # Бэктест
    backtest_results: Dict[str, BacktestResult] = field(default_factory=dict)
    
    # Метаданные
    last_update: datetime = field(default_factory=datetime.now)
    data_source: str = "history"  # "trading" или "history"
    
    def to_dict(self) -> Dict[str, Any]:
        """Конвертировать в словарь"""
        return {
            "exchange_status": self.exchange_status.value,
            "is_trading": self.is_trading,
            "exchange_message": self.exchange_message,
            "bonds": {k: v.__dict__ for k, v in self.bonds.items()},
            "spreads": {k: {"spread_bp": v.spread_bp, "ytm_long": v.ytm_long, "ytm_short": v.ytm_short} 
                       for k, v in self.spreads.items()},
            "signals": [s.to_dict() for s in self.signals],
            "last_update": self.last_update.isoformat(),
            "data_source": self.data_source
        }


class DailyMode:
    """
    Дневной режим работы
    
    - Автоматическое определение режима торгов
    - Загрузка исторических или торговых данных
    - Расчёт спредов и генерация сигналов
    - Бэктестинг стратегий
    """
    
    def __init__(self, config: Optional[AppConfig] = None):
        """
        Инициализация
        
        Args:
            config: Конфигурация приложения
        """
        self.config = config or AppConfig()
        self.trading_checker = TradingChecker()
        self.history_fetcher = HistoryFetcher()
        self.spread_calculator = SpreadCalculator(self.config.signals.percentile_window)
        self.signal_generator = SignalGenerator()
        self.backtester = Backtester(self.config.backtest)
        
        # Кэш данных
        self._ytm_cache: Dict[str, pd.DataFrame] = {}
        self._last_fetch: Optional[datetime] = None
    
    def run(self, run_backtest: bool = False) -> DailyModeResult:
        """
        Запустить анализ
        
        Args:
            run_backtest: Запустить бэктест
            
        Returns:
            DailyModeResult с результатами
        """
        result = DailyModeResult(
            exchange_status=TradingStatus.CLOSED,
            is_trading=False,
            exchange_message=""
        )
        
        # 1. Проверяем статус биржи
        exchange_info = self.trading_checker.check_comprehensive()
        result.exchange_status = exchange_info.status
        result.is_trading = exchange_info.is_trading
        result.exchange_message = exchange_info.message
        
        logger.info(f"Exchange status: {exchange_info.status.value}, trading: {exchange_info.is_trading}")
        
        # 2. Загружаем данные
        if exchange_info.is_trading:
            # Пробуем торговые данные
            ytm_data = self._fetch_trading_data()
            result.data_source = "trading"
            
            # Если торговых данных нет, берём исторические
            if not ytm_data:
                ytm_data = self._fetch_history_data()
                result.data_source = "history"
        else:
            # Биржа закрыта - исторические данные
            ytm_data = self._fetch_history_data()
            result.data_source = "history"
        
        result.ytm_history = ytm_data
        self._ytm_cache = ytm_data
        
        # 3. Формируем информацию по облигациям
        result.bonds = self._build_bonds_info(ytm_data)
        
        # 4. Рассчитываем спреды
        result.spreads = self.spread_calculator.calculate_all_pairs_spreads(
            ytm_data,
            self.config.spread_pairs
        )
        
        # 5. Строим историю спредов и статистику
        spread_history = self.spread_calculator.build_spread_history(
            ytm_data,
            self.config.spread_pairs
        )
        
        for pair_key, spread_df in spread_history.items():
            if not spread_df.empty:
                stats = self.spread_calculator.calculate_spread_stats(spread_df["spread_bp"])
                result.spread_stats[pair_key] = stats
        
        # 6. Генерируем сигналы
        result.signals = self.signal_generator.generate_all_signals(
            spread_history,
            self.config.spread_pairs
        )
        
        # Фильтруем активные сигналы
        result.active_signals = self.signal_generator.filter_signals(result.signals)
        
        # 7. Бэктест (если запрошен)
        if run_backtest:
            result.backtest_results = self.backtester.run_multi_pair_backtest(
                spread_history,
                ytm_data,
                self.config.spread_pairs
            )
        
        result.last_update = datetime.now()
        
        return result
    
    def get_ytm_chart_data(self) -> pd.DataFrame:
        """
        Получить данные для графика YTM
        
        Returns:
            DataFrame с YTM всех облигаций
        """
        if not self._ytm_cache:
            return pd.DataFrame()
        
        # Объединяем YTM всех облигаций
        ytm_data = {}
        
        for isin, df in self._ytm_cache.items():
            if "ytm" in df.columns:
                bond_name = self.config.bonds.get(isin, None)
                name = bond_name.name if bond_name else isin
                ytm_data[name] = df["ytm"]
        
        return pd.DataFrame(ytm_data)
    
    def get_spread_chart_data(self) -> pd.DataFrame:
        """
        Получить данные для графика спредов
        
        Returns:
            DataFrame со спредами
        """
        spread_history = self.spread_calculator.build_spread_history(
            self._ytm_cache,
            self.config.spread_pairs
        )
        
        if not spread_history:
            return pd.DataFrame()
        
        # Объединяем спреды
        spread_data = {}
        for pair_key, df in spread_history.items():
            if "spread_bp" in df.columns:
                spread_data[pair_key] = df["spread_bp"]
        
        return pd.DataFrame(spread_data)
    
    def get_latest_ytm(self) -> Dict[str, float]:
        """
        Получить последние значения YTM
        
        Returns:
            Словарь {ISIN: YTM}
        """
        result = {}
        
        for isin, df in self._ytm_cache.items():
            if "ytm" in df.columns and not df.empty:
                last_ytm = df["ytm"].iloc[-1]
                if not pd.isna(last_ytm):
                    result[isin] = last_ytm
        
        return result
    
    def refresh(self) -> DailyModeResult:
        """
        Обновить данные
        
        Returns:
            DailyModeResult
        """
        self._ytm_cache.clear()
        self._last_fetch = None
        return self.run()
    
    def _fetch_trading_data(self) -> Dict[str, pd.DataFrame]:
        """
        Загрузить торговые данные
        
        Returns:
            Словарь {ISIN: DataFrame}
        """
        logger.info("Fetching trading data...")
        
        ytm_data = {}
        isins = list(self.config.bonds.keys())
        
        for isin in isins:
            try:
                trading_data = self.history_fetcher.get_trading_data(isin)
                
                if trading_data.get("has_data") and trading_data.get("yield"):
                    # Создаём DataFrame с одним значением
                    ytm = trading_data["yield"]
                    duration = trading_data.get("duration")
                    
                    df = pd.DataFrame({
                        "ytm": [ytm],
                        "duration_days": [duration] if duration else [None]
                    }, index=[pd.Timestamp.now()])
                    
                    ytm_data[isin] = df
                    logger.debug(f"Got trading YTM for {isin}: {ytm}")
                    
            except Exception as e:
                logger.warning(f"Error fetching trading data for {isin}: {e}")
        
        self._last_fetch = datetime.now()
        return ytm_data
    
    def _fetch_history_data(self) -> Dict[str, pd.DataFrame]:
        """
        Загрузить исторические данные
        
        Returns:
            Словарь {ISIN: DataFrame}
        """
        logger.info("Fetching historical data...")
        
        start_date = date.today() - timedelta(days=self.config.lookback_days)
        
        ytm_data = self.history_fetcher.fetch_multi_bonds_history(
            list(self.config.bonds.keys()),
            start_date=start_date
        )
        
        self._last_fetch = datetime.now()
        return ytm_data
    
    def _build_bonds_info(self, ytm_data: Dict[str, pd.DataFrame]) -> Dict[str, BondInfo]:
        """
        Построить информацию по облигациям
        
        Args:
            ytm_data: Данные YTM
            
        Returns:
            Словарь {ISIN: BondInfo}
        """
        bonds_info = {}
        
        for isin, bond_config in self.config.bonds.items():
            df = ytm_data.get(isin)
            
            current_ytm = None
            duration_years = None
            last_price = None
            
            if df is not None and not df.empty:
                if "ytm" in df.columns:
                    current_ytm = df["ytm"].iloc[-1]
                    if pd.isna(current_ytm):
                        current_ytm = None
                
                if "duration_years" in df.columns:
                    duration_years = df["duration_years"].iloc[-1]
                    if pd.isna(duration_years):
                        duration_years = None
                
                if "close_price" in df.columns:
                    last_price = df["close_price"].iloc[-1]
                    if pd.isna(last_price):
                        last_price = None
            
            # Рассчитываем годы до погашения
            years_to_maturity = None
            try:
                maturity = datetime.strptime(bond_config.maturity_date, "%Y-%m-%d").date()
                years_to_maturity = round((maturity - date.today()).days / 365.25, 1)
            except (ValueError, TypeError):
                pass
            
            bonds_info[isin] = BondInfo(
                isin=isin,
                name=bond_config.name,
                current_ytm=current_ytm,
                duration_years=duration_years,
                years_to_maturity=years_to_maturity,
                last_price=last_price,
                coupon_rate=bond_config.coupon_rate
            )
        
        return bonds_info
    
    def close(self):
        """Закрыть соединения"""
        self.trading_checker.close()
        self.history_fetcher.close()


def run_daily_analysis(lookback_days: int = 500) -> DailyModeResult:
    """
    Быстрый запуск анализа
    
    Args:
        lookback_days: Дней истории
        
    Returns:
        DailyModeResult
    """
    config = AppConfig(lookback_days=lookback_days)
    mode = DailyMode(config)
    return mode.run()