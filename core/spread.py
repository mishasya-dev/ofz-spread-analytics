"""
Расчёт спредов доходности между облигациями
"""
import pandas as pd
import numpy as np
from datetime import date, datetime
from typing import Optional, Dict, List, Tuple, Any
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class SpreadData:
    """Данные спреда"""
    bond_long: str       # ISIN длинной облигации
    bond_short: str      # ISIN короткой облигации
    spread_bp: float     # Спред в базисных пунктах
    ytm_long: float      # YTM длинной облигации
    ytm_short: float     # YTM короткой облигации
    duration_long: float # Дюрация длинной
    duration_short: float # Дюрация короткой
    date: date
    time: Optional[datetime] = None  # Для внутридневных данных


@dataclass
class SpreadStats:
    """Статистика спреда"""
    current: float
    mean: float
    std: float
    min: float
    max: float
    percentile_10: float
    percentile_25: float
    percentile_50: float
    percentile_75: float
    percentile_90: float
    zscore: float
    lookback_days: int


class SpreadCalculator:
    """Калькулятор спредов доходности"""
    
    def __init__(self, lookback_days: int = 252):
        """
        Инициализация
        
        Args:
            lookback_days: Окно для расчёта статистики (торговых дней)
        """
        self.lookback_days = lookback_days
    
    def calculate_spread(
        self,
        ytm_long: float,
        ytm_short: float
    ) -> float:
        """
        Рассчитать спред между двумя YTM
        
        Спред = (YTM_long - YTM_short) × 100 базисных пунктов
        
        Args:
            ytm_long: YTM длинной облигации (%)
            ytm_short: YTM короткой облигации (%)
            
        Returns:
            Спред в базисных пунктах
        """
        spread = (ytm_long - ytm_short) * 100
        return round(spread, 2)
    
    def calculate_spread_series(
        self,
        ytm_long_series: pd.Series,
        ytm_short_series: pd.Series
    ) -> pd.Series:
        """
        Рассчитать серию спредов
        
        Args:
            ytm_long_series: Series с YTM длинной облигации
            ytm_short_series: Series с YTM короткой облигации
            
        Returns:
            Series со спредами в б.п.
        """
        # Выравниваем по датам
        aligned = pd.DataFrame({
            "ytm_long": ytm_long_series,
            "ytm_short": ytm_short_series
        }).dropna()
        
        spread = (aligned["ytm_long"] - aligned["ytm_short"]) * 100
        
        return spread.round(2)
    
    def calculate_spread_stats(
        self,
        spread_series: pd.Series,
        lookback: Optional[int] = None
    ) -> SpreadStats:
        """
        Рассчитать статистику спреда
        
        Args:
            spread_series: Series со спредами
            lookback: Окно для расчёта (переопределяет default)
            
        Returns:
            SpreadStats с рассчитанными метриками
        """
        if lookback is None:
            lookback = self.lookback_days
        
        # Берём последние lookback значений
        spread_window = spread_series.dropna().tail(lookback)
        
        if spread_window.empty:
            raise ValueError("Пустой ряд спредов")
        
        current = spread_window.iloc[-1]
        mean = spread_window.mean()
        std = spread_window.std()
        
        zscore = (current - mean) / std if std > 0 else 0
        
        return SpreadStats(
            current=round(current, 2),
            mean=round(mean, 2),
            std=round(std, 2),
            min=round(spread_window.min(), 2),
            max=round(spread_window.max(), 2),
            percentile_10=round(np.percentile(spread_window, 10), 2),
            percentile_25=round(np.percentile(spread_window, 25), 2),
            percentile_50=round(np.percentile(spread_window, 50), 2),
            percentile_75=round(np.percentile(spread_window, 75), 2),
            percentile_90=round(np.percentile(spread_window, 90), 2),
            zscore=round(zscore, 2),
            lookback_days=len(spread_window)
        )
    
    def calculate_duration_weighted_spread(
        self,
        ytm_long: float,
        ytm_short: float,
        duration_long: float,
        duration_short: float
    ) -> float:
        """
        Рассчитать дюрационно-взвешенный спред
        
        Нормализует спред с учётом разницы дюраций.
        
        Args:
            ytm_long: YTM длинной облигации
            ytm_short: YTM короткой облигации
            duration_long: Дюрация длинной
            duration_short: Дюрация короткой
            
        Returns:
            Взвешенный спред в б.п.
        """
        spread = (ytm_long - ytm_short) * 100
        
        # Взвешиваем по средней дюрации
        avg_duration = (duration_long + duration_short) / 2
        weighted_spread = spread / avg_duration * 10  # Нормализуем к 10 годам
        
        return round(weighted_spread, 2)
    
    def calculate_all_pairs_spreads(
        self,
        ytm_data: Dict[str, pd.DataFrame],
        pairs: List[Tuple[str, str]]
    ) -> Dict[str, SpreadData]:
        """
        Рассчитать спреды для всех пар
        
        Args:
            ytm_data: Словарь {ISIN: DataFrame с YTM}
            pairs: Список пар (ISIN_long, ISIN_short)
            
        Returns:
            Словарь {(ISIN_long, ISIN_short): SpreadData}
        """
        results = {}
        
        for bond_long, bond_short in pairs:
            pair_key = f"{bond_long}_{bond_short}"
            
            if bond_long not in ytm_data or bond_short not in ytm_data:
                logger.warning(f"Нет данных для пары {pair_key}")
                continue
            
            df_long = ytm_data[bond_long]
            df_short = ytm_data[bond_short]
            
            # Получаем последние значения
            if "ytm" not in df_long.columns or "ytm" not in df_short.columns:
                logger.warning(f"Нет YTM для пары {pair_key}")
                continue
            
            ytm_long = df_long["ytm"].iloc[-1]
            ytm_short = df_short["ytm"].iloc[-1]
            
            if pd.isna(ytm_long) or pd.isna(ytm_short):
                logger.warning(f"Пропущенные значения для пары {pair_key}")
                continue
            
            # Получаем дюрации если есть
            duration_long = df_long.get("duration_years", pd.Series([0])).iloc[-1]
            duration_short = df_short.get("duration_years", pd.Series([0])).iloc[-1]
            
            # Дата
            trade_date = df_long.index[-1].date() if hasattr(df_long.index[-1], 'date') else date.today()
            
            spread_bp = self.calculate_spread(ytm_long, ytm_short)
            
            results[pair_key] = SpreadData(
                bond_long=bond_long,
                bond_short=bond_short,
                spread_bp=spread_bp,
                ytm_long=ytm_long,
                ytm_short=ytm_short,
                duration_long=duration_long if not pd.isna(duration_long) else 0,
                duration_short=duration_short if not pd.isna(duration_short) else 0,
                date=trade_date
            )
        
        return results
    
    def build_spread_history(
        self,
        ytm_data: Dict[str, pd.DataFrame],
        pairs: List[Tuple[str, str]]
    ) -> Dict[str, pd.DataFrame]:
        """
        Построить историю спредов для всех пар
        
        Args:
            ytm_data: Словарь {ISIN: DataFrame с YTM}
            pairs: Список пар (ISIN_long, ISIN_short)
            
        Returns:
            Словарь {pair_key: DataFrame со спредами}
        """
        results = {}
        
        for bond_long, bond_short in pairs:
            pair_key = f"{bond_long}_{bond_short}"
            
            if bond_long not in ytm_data or bond_short not in ytm_data:
                continue
            
            df_long = ytm_data[bond_long]
            df_short = ytm_data[bond_short]
            
            if "ytm" not in df_long.columns or "ytm" not in df_short.columns:
                continue
            
            # Рассчитываем серию спредов
            spread_series = self.calculate_spread_series(
                df_long["ytm"],
                df_short["ytm"]
            )
            
            # Создаём DataFrame с историей
            spread_df = pd.DataFrame({
                "spread_bp": spread_series,
                "ytm_long": df_long.loc[spread_series.index, "ytm"],
                "ytm_short": df_short.loc[spread_series.index, "ytm"]
            })
            
            # Добавляем скользящие статистики
            spread_df["spread_mean_20"] = spread_df["spread_bp"].rolling(20).mean()
            spread_df["spread_std_20"] = spread_df["spread_bp"].rolling(20).std()
            spread_df["spread_mean_60"] = spread_df["spread_bp"].rolling(60).mean()
            spread_df["spread_std_60"] = spread_df["spread_bp"].rolling(60).std()
            
            results[pair_key] = spread_df
        
        return results
    
    def detect_anomalies(
        self,
        spread_series: pd.Series,
        threshold_std: float = 2.0
    ) -> pd.Series:
        """
        Обнаружить аномалии в спредах
        
        Args:
            spread_series: Series со спредами
            threshold_std: Порог в стандартных отклонениях
            
        Returns:
            Series с булевыми значениями (True = аномалия)
        """
        rolling_mean = spread_series.rolling(20).mean()
        rolling_std = spread_series.rolling(20).std()
        
        upper_bound = rolling_mean + threshold_std * rolling_std
        lower_bound = rolling_mean - threshold_std * rolling_std
        
        anomalies = (spread_series > upper_bound) | (spread_series < lower_bound)
        
        return anomalies
    
    def calculate_spread_change(
        self,
        spread_series: pd.Series,
        periods: int = 1
    ) -> pd.Series:
        """
        Рассчитать изменение спреда
        
        Args:
            spread_series: Series со спредами
            periods: Количество периодов для расчёта изменения
            
        Returns:
            Series с изменениями в б.п.
        """
        return spread_series.diff(periods)
    
    def get_spread_percentile_rank(
        self,
        current_spread: float,
        spread_series: pd.Series,
        lookback: Optional[int] = None
    ) -> float:
        """
        Получить перцентиль-ранг текущего спреда
        
        Args:
            current_spread: Текущий спред
            spread_series: История спредов
            lookback: Окно для расчёта
            
        Returns:
            Перцентиль-ранг (0-100)
        """
        if lookback:
            spread_window = spread_series.dropna().tail(lookback)
        else:
            spread_window = spread_series.dropna()
        
        if spread_window.empty:
            return 50.0
        
        rank = (spread_window < current_spread).sum() / len(spread_window) * 100
        
        return round(rank, 1)


# Удобные функции
def get_spread(ytm1: float, ytm2: float) -> float:
    """Быстрый расчёт спреда в базисных пунктах"""
    return round((ytm1 - ytm2) * 100, 2)


def get_spread_stats(spread_series: pd.Series, lookback: int = 252) -> Dict[str, float]:
    """Быстрый расчёт статистики спреда"""
    calc = SpreadCalculator(lookback)
    stats = calc.calculate_spread_stats(spread_series, lookback)
    return {
        "current": stats.current,
        "mean": stats.mean,
        "std": stats.std,
        "p10": stats.percentile_10,
        "p25": stats.percentile_25,
        "p75": stats.percentile_75,
        "p90": stats.percentile_90,
        "zscore": stats.zscore
    }