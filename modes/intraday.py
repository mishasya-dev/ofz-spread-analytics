"""
Режим работы с внутридневными данными
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

from api.moex_trading import TradingChecker, TradingStatus
from api.moex_candles import CandleFetcher, CandleInterval
from api.moex_history import HistoryFetcher
from core.spread import SpreadCalculator, SpreadStats
from core.signals import SignalGenerator, TradingSignal
from config import AppConfig

logger = logging.getLogger(__name__)


@dataclass
class IntradayPoint:
    """Точка внутридневных данных"""
    time: datetime
    ytm_long: float
    ytm_short: float
    spread_bp: float
    price_long: Optional[float] = None
    price_short: Optional[float] = None


@dataclass
class IntradayModeResult:
    """Результат работы внутридневного режима"""
    # Статус
    is_trading: bool
    exchange_status: TradingStatus
    current_time: datetime
    
    # Данные по парам
    pairs_data: Dict[str, List[IntradayPoint]] = field(default_factory=dict)
    
    # Текущие значения
    current_spreads: Dict[str, float] = field(default_factory=dict)
    
    # Сигналы
    signals: List[TradingSignal] = field(default_factory=list)
    
    # Статистика за день
    daily_stats: Dict[str, Dict[str, float]] = field(default_factory=dict)
    
    # Метаданные
    last_update: datetime = field(default_factory=datetime.now)
    data_available: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        """Конвертировать в словарь"""
        return {
            "is_trading": self.is_trading,
            "exchange_status": self.exchange_status.value,
            "current_time": self.current_time.isoformat(),
            "current_spreads": self.current_spreads,
            "signals": [s.to_dict() for s in self.signals],
            "daily_stats": self.daily_stats,
            "last_update": self.last_update.isoformat(),
            "data_available": self.data_available
        }


class IntradayMode:
    """
    Внутридневной режим работы
    
    - Часовые свечи в реальном времени
    - Отслеживание спредов внутри дня
    - Генерация сигналов на коротких интервалах
    """
    
    def __init__(self, config: Optional[AppConfig] = None):
        """
        Инициализация
        
        Args:
            config: Конфигурация приложения
        """
        self.config = config or AppConfig()
        self.trading_checker = TradingChecker()
        self.candle_fetcher = CandleFetcher()
        self.history_fetcher = HistoryFetcher()
        self.spread_calculator = SpreadCalculator()
        self.signal_generator = SignalGenerator()
        
        # Кэш
        self._candles_cache: Dict[str, pd.DataFrame] = {}
        self._history_cache: Dict[str, pd.DataFrame] = {}
    
    def run(self) -> IntradayModeResult:
        """
        Запустить анализ
        
        Returns:
            IntradayModeResult
        """
        result = IntradayModeResult(
            is_trading=False,
            exchange_status=TradingStatus.CLOSED,
            current_time=datetime.now()
        )
        
        # 1. Проверяем статус биржи
        exchange_info = self.trading_checker.check_comprehensive()
        result.exchange_status = exchange_info.status
        result.is_trading = exchange_info.is_trading
        
        if not exchange_info.is_trading:
            result.data_available = False
            return result
        
        # 2. Загружаем часовые свечи
        isins = self._get_all_isins()
        
        try:
            self._candles_cache = self.candle_fetcher.fetch_multi_bonds_candles(
                isins,
                interval=CandleInterval.MIN_60,
                start_date=date.today(),
                end_date=date.today()
            )
        except Exception as e:
            logger.error(f"Error fetching candles: {e}")
            result.data_available = False
            return result
        
        # 3. Загружаем историю для перцентилей
        start_date = date.today() - timedelta(days=self.config.lookback_days)
        self._history_cache = self.history_fetcher.fetch_multi_bonds_history(
            isins,
            start_date=start_date
        )
        
        # 4. Обрабатываем каждую пару
        for bond_long, bond_short in self.config.spread_pairs:
            pair_key = f"{bond_long}_{bond_short}"
            
            pair_data = self._process_pair(bond_long, bond_short)
            
            if pair_data:
                result.pairs_data[pair_key] = pair_data
                
                # Текущий спред
                if pair_data:
                    result.current_spreads[pair_key] = pair_data[-1].spread_bp
                
                # Дневная статистика
                result.daily_stats[pair_key] = self._calculate_daily_stats(pair_data)
        
        # 5. Генерируем сигналы
        result.signals = self._generate_intraday_signals()
        
        result.last_update = datetime.now()
        
        return result
    
    def get_intraday_chart_data(self, pair_key: str) -> pd.DataFrame:
        """
        Получить данные для внутридневного графика
        
        Args:
            pair_key: Ключ пары
            
        Returns:
            DataFrame с данными
        """
        if pair_key not in self._candles_cache:
            return pd.DataFrame()
        
        bond_long, bond_short = pair_key.split("_", 1)
        bond_short = pair_key.split("_")[-1]
        
        # Находим правильные ISIN
        parts = pair_key.split("_")
        bond_long = "_".join(parts[:3]) if len(parts) > 2 else parts[0]
        bond_short = "_".join(parts[3:]) if len(parts) > 4 else parts[-1]
        
        df_long = self._candles_cache.get(bond_long)
        df_short = self._candles_cache.get(bond_short)
        
        if df_long is None or df_short is None:
            return pd.DataFrame()
        
        # Объединяем по времени
        combined = pd.DataFrame({
            "close_long": df_long["close"] if "close" in df_long.columns else None,
            "close_short": df_short["close"] if "close" in df_short.columns else None,
        })
        
        # Рассчитываем спред (упрощённо, по цене)
        if "close" in df_long.columns and "close" in df_short.columns:
            # Нормализуем к YTM (упрощённо)
            combined["spread_bp"] = (df_long["close"] - df_short["close"]) * 10
        
        return combined.dropna()
    
    def get_current_status(self) -> Dict[str, Any]:
        """
        Получить текущий статус
        
        Returns:
            Словарь с информацией о статусе
        """
        exchange_info = self.trading_checker.check_comprehensive()
        
        return {
            "is_trading": exchange_info.is_trading,
            "status": exchange_info.status.value,
            "message": exchange_info.message,
            "session_end": exchange_info.session_end.isoformat() if exchange_info.session_end else None,
            "current_time": datetime.now().isoformat()
        }
    
    def refresh(self) -> IntradayModeResult:
        """
        Обновить данные
        
        Returns:
            IntradayModeResult
        """
        self._candles_cache.clear()
        return self.run()
    
    def _get_all_isins(self) -> List[str]:
        """Получить все уникальные ISIN из пар"""
        isins = set()
        for bond_long, bond_short in self.config.spread_pairs:
            isins.add(bond_long)
            isins.add(bond_short)
        return list(isins)
    
    def _process_pair(
        self,
        bond_long: str,
        bond_short: str
    ) -> List[IntradayPoint]:
        """
        Обработать пару облигаций
        
        Args:
            bond_long: ISIN длинной облигации
            bond_short: ISIN короткой облигации
            
        Returns:
            Список точек данных
        """
        df_long = self._candles_cache.get(bond_long)
        df_short = self._candles_cache.get(bond_short)
        
        if df_long is None or df_short is None:
            return []
        
        # Получаем исторические YTM для оценки
        hist_long = self._history_cache.get(bond_long)
        hist_short = self._history_cache.get(bond_short)
        
        points = []
        
        # Выравниваем по времени
        common_index = df_long.index.intersection(df_short.index)
        
        for idx in common_index:
            row_long = df_long.loc[idx]
            row_short = df_short.loc[idx]
            
            # Оценка YTM из цены
            ytm_long = self._estimate_ytm(row_long.get("close"), hist_long)
            ytm_short = self._estimate_ytm(row_short.get("close"), hist_short)
            
            if ytm_long is None or ytm_short is None:
                continue
            
            spread_bp = (ytm_long - ytm_short) * 100
            
            point = IntradayPoint(
                time=idx,
                ytm_long=ytm_long,
                ytm_short=ytm_short,
                spread_bp=round(spread_bp, 2),
                price_long=row_long.get("close"),
                price_short=row_short.get("close")
            )
            
            points.append(point)
        
        return points
    
    def _estimate_ytm(
        self,
        price: Optional[float],
        history_df: Optional[pd.DataFrame]
    ) -> Optional[float]:
        """
        Оценить YTM из цены
        
        Args:
            price: Цена облигации
            history_df: Исторические данные
            
        Returns:
            Оценка YTM или None
        """
        if price is None or pd.isna(price):
            return None
        
        if history_df is None or history_df.empty:
            return None
        
        # Ищем ближайшую цену в истории и берём соответствующий YTM
        if "close_price" in history_df.columns and "ytm" in history_df.columns:
            # Удаляем NaN
            valid = history_df[["close_price", "ytm"]].dropna()
            
            if valid.empty:
                return None
            
            # Находим ближайшую цену
            idx = (valid["close_price"] - price).abs().idxmin()
            return valid.loc[idx, "ytm"]
        
        return None
    
    def _calculate_daily_stats(self, points: List[IntradayPoint]) -> Dict[str, float]:
        """
        Рассчитать статистику за день
        
        Args:
            points: Список точек данных
            
        Returns:
            Словарь со статистикой
        """
        if not points:
            return {}
        
        spreads = [p.spread_bp for p in points]
        
        return {
            "open": spreads[0],
            "current": spreads[-1],
            "high": max(spreads),
            "low": min(spreads),
            "mean": round(np.mean(spreads), 2),
            "std": round(np.std(spreads), 2),
            "change": round(spreads[-1] - spreads[0], 2),
            "change_pct": round((spreads[-1] - spreads[0]) / spreads[0] * 100, 2) if spreads[0] != 0 else 0,
            "data_points": len(points)
        }
    
    def _generate_intraday_signals(self) -> List[TradingSignal]:
        """
        Генерировать внутридневные сигналы
        
        Returns:
            Список сигналов
        """
        signals = []
        
        for bond_long, bond_short in self.config.spread_pairs:
            pair_key = f"{bond_long}_{bond_short}"
            
            # Получаем исторический спред
            hist_long = self._history_cache.get(bond_long)
            hist_short = self._history_cache.get(bond_short)
            
            if hist_long is None or hist_short is None:
                continue
            
            if "ytm" not in hist_long.columns or "ytm" not in hist_short.columns:
                continue
            
            # Строим исторический спред
            spread_series = self.spread_calculator.calculate_spread_series(
                hist_long["ytm"],
                hist_short["ytm"]
            )
            
            if spread_series.empty:
                continue
            
            # Генерируем сигнал
            signal = self.signal_generator.generate_signal(
                spread_series,
                bond_long,
                bond_short,
                pair_key
            )
            
            signals.append(signal)
        
        return signals
    
    def close(self):
        """Закрыть соединения"""
        self.trading_checker.close()
        self.candle_fetcher.close()
        self.history_fetcher.close()


def run_intraday_analysis() -> IntradayModeResult:
    """
    Быстрый запуск внутридневного анализа
    
    Returns:
        IntradayModeResult
    """
    mode = IntradayMode()
    return mode.run()
