"""
Расчёт G-spread через модель Nelson-Siegel

G-spread = YTM_облигации - YTM_КБД(duration)

Модель Nelson-Siegel:
Y(t) = b1 + b2 * f1(t) + b3 * f2(t)

где:
- t = duration (срок до погашения в годах)
- b1 = долгосрочный уровень ставки (base level)
- b2 = краткосрочный наклон (short-term slope)  
- b3 = кривизна (curvature)
- tau (t1) = масштаб времени
- f1(t) = (1 - exp(-t/tau)) / (t/tau)
- f2(t) = f1(t) - exp(-t/tau)
"""
import numpy as np
import pandas as pd
from datetime import date, datetime
from typing import Optional, Dict, Tuple
import logging

logger = logging.getLogger(__name__)


def nelson_siegel(
    t: float,
    b1: float,
    b2: float,
    b3: float,
    tau: float
) -> float:
    """
    Рассчитать YTM по КБД (Nelson-Siegel model)
    
    Y(t) = b1 + b2 * f1(t) + b3 * f2(t)
    
    Args:
        t: Срок до погашения (duration в годах)
        b1: Долгосрочный уровень ставки (в %)
        b2: Краткосрочный наклон (в %)
        b3: Кривизна (в %)
        tau: Масштаб времени
        
    Returns:
        YTM по КБД (в %)
        
    Examples:
        >>> nelson_siegel(5.0, 16.0, -2.0, 3.0, 2.0)
        15.12
    """
    if t <= 0 or tau <= 0:
        # Для нулевой дюрации возвращаем b1 + b2 (краткосрочная ставка)
        return b1 + b2
    
    # f1(t) = (1 - exp(-t/tau)) / (t/tau)
    x = t / tau
    if x > 100:  # Защита от переполнения
        f1 = 1.0
        f2 = 1.0
    else:
        exp_x = np.exp(-x)
        f1 = (1 - exp_x) / x
        f2 = f1 - exp_x
    
    ytm = b1 + b2 * f1 + b3 * f2
    
    return ytm


def nelson_siegel_vectorized(
    durations: np.ndarray,
    b1: float,
    b2: float,
    b3: float,
    tau: float
) -> np.ndarray:
    """
    Векторизованный расчёт YTM по КБД для массива дюраций
    
    Args:
        durations: Массив дюраций (годы)
        b1, b2, b3, tau: Параметры Nelson-Siegel
        
    Returns:
        Массив YTM по КБД
    """
    durations = np.asarray(durations, dtype=float)
    
    # Защита от деления на ноль
    durations = np.where(durations <= 0, 1e-10, durations)
    
    if tau <= 0:
        tau = 1e-10
    
    x = durations / tau
    x = np.clip(x, 0, 100)  # Защита от переполнения
    
    exp_x = np.exp(-x)
    f1 = (1 - exp_x) / x
    f2 = f1 - exp_x
    
    ytm = b1 + b2 * f1 + b3 * f2
    
    return ytm


def calculate_g_spread(
    ytm_bond: float,
    duration_years: float,
    b1: float,
    b2: float,
    b3: float,
    tau: float
) -> Tuple[float, float]:
    """
    Рассчитать G-spread для одной точки
    
    G-spread = YTM_bond - YTM_KBD(duration)
    
    Args:
        ytm_bond: Реальный YTM облигации (в %)
        duration_years: Дюрация в годах
        b1, b2, b3, tau: Параметры Nelson-Siegel
        
    Returns:
        (ytm_kbd, g_spread_bp):
            ytm_kbd: YTM по КБД (в %)
            g_spread_bp: G-spread (в базисных пунктах)
    """
    ytm_kbd = nelson_siegel(duration_years, b1, b2, b3, tau)
    g_spread_bp = (ytm_bond - ytm_kbd) * 100  # в базисных пунктах
    
    return ytm_kbd, g_spread_bp


def calculate_g_spread_history(
    bond_ytm_df: pd.DataFrame,
    ns_params_df: pd.DataFrame
) -> pd.DataFrame:
    """
    Рассчитать историю G-spread для облигации
    
    Args:
        bond_ytm_df: DataFrame с колонками ['ytm', 'duration_days']
                     индекс = date
        ns_params_df: DataFrame с колонками ['b1', 'b2', 'b3', 't1']
                      индекс = date
                      
    Returns:
        DataFrame с колонками:
            - ytm_bond: YTM облигации (%)
            - duration_years: Дюрация (годы)
            - ytm_kbd: YTM по КБД (%)
            - g_spread_bp: G-spread (б.п.)
    """
    if bond_ytm_df.empty or ns_params_df.empty:
        return pd.DataFrame()
    
    # Объединяем по дате
    merged = bond_ytm_df.join(ns_params_df, how='inner')
    
    if merged.empty:
        logger.warning("Нет пересекающихся дат между YTM и параметрами NS")
        return pd.DataFrame()
    
    # Проверяем наличие нужных колонок
    required_cols = ['ytm', 'duration_days', 'b1', 'b2', 'b3', 't1']
    missing = [c for c in required_cols if c not in merged.columns]
    if missing:
        logger.error(f"Отсутствуют колонки: {missing}")
        return pd.DataFrame()
    
    # Удаляем строки с None/NaN
    merged = merged.dropna(subset=required_cols)
    
    if merged.empty:
        logger.warning("Все строки содержат None значения")
        return pd.DataFrame()
    
    # Рассчитываем duration в годах
    merged['duration_years'] = merged['duration_days'] / 365.25
    
    # Рассчитываем YTM по КБД
    merged['ytm_kbd'] = nelson_siegel_vectorized(
        merged['duration_years'].values,
        merged['b1'].values,
        merged['b2'].values,
        merged['b3'].values,
        merged['t1'].values
    )
    
    # Рассчитываем G-spread
    merged['ytm_bond'] = merged['ytm']
    merged['g_spread_bp'] = (merged['ytm_bond'] - merged['ytm_kbd']) * 100
    
    # Возвращаем только нужные колонки
    result = merged[['ytm_bond', 'duration_years', 'ytm_kbd', 'g_spread_bp']].copy()
    
    logger.info(f"Рассчитано {len(result)} значений G-spread")
    
    return result


def calculate_g_spread_stats(g_spread_series: pd.Series) -> Dict:
    """
    Рассчитать статистику G-spread
    
    Args:
        g_spread_series: Series со значениями G-spread (б.п.)
        
    Returns:
        Словарь со статистикой
    """
    if g_spread_series.empty:
        return {}
    
    clean = g_spread_series.dropna()
    
    if clean.empty:
        return {}
    
    return {
        'mean': clean.mean(),
        'median': clean.median(),
        'std': clean.std(),
        'min': clean.min(),
        'max': clean.max(),
        'p10': clean.quantile(0.10),
        'p25': clean.quantile(0.25),
        'p75': clean.quantile(0.75),
        'p90': clean.quantile(0.90),
        'current': clean.iloc[-1] if len(clean) > 0 else 0,
        'count': len(clean)
    }


def generate_g_spread_signal(
    current_spread: float,
    p10: float,
    p25: float,
    p75: float,
    p90: float
) -> Dict:
    """
    Генерировать торговый сигнал на основе G-spread
    
    Интерпретация G-spread:
    - G-spread < 0: Облигация дешевле КБД (покупка)
    - G-spread > 0: Облигация дороже КБД (продажа)
    
    Mean-Reversion стратегия:
    - G-spread < P25: Облигация недооценена → ПОКУПКА
    - G-spread > P75: Облигация переоценена → ПРОДАЖА
    
    Args:
        current_spread: Текущий G-spread (б.п.)
        p10, p25, p75, p90: Перцентили
        
    Returns:
        Словарь с сигналом
    """
    if current_spread < p25:
        # Облигация недооценена относительно КБД
        return {
            'signal': 'BUY',
            'action': 'ПОКУПКА — облигация недооценена относительно КБД',
            'reason': f'G-spread {current_spread:.1f} б.п. ниже P25 ({p25:.1f} б.п.)',
            'color': '#28a745',  # зелёный
            'strength': 'Сильный' if current_spread < p10 else 'Средний'
        }
    elif current_spread > p75:
        # Облигация переоценена относительно КБД
        return {
            'signal': 'SELL',
            'action': 'ПРОДАЖА — облигация переоценена относительно КБД',
            'reason': f'G-spread {current_spread:.1f} б.п. выше P75 ({p75:.1f} б.п.)',
            'color': '#dc3545',  # красный
            'strength': 'Сильный' if current_spread > p90 else 'Средний'
        }
    else:
        return {
            'signal': 'HOLD',
            'action': 'УДЕРЖИВАТЬ — справедливая оценка',
            'reason': f'G-spread {current_spread:.1f} б.п. в нормальном диапазоне [{p25:.1f}, {p75:.1f}]',
            'color': '#ffc107',  # жёлтый
            'strength': 'Нет сигнала'
        }


class GSpreadCalculator:
    """
    Калькулятор G-spread для облигаций
    
    Использование:
        calculator = GSpreadCalculator()
        
        # Загрузить данные
        calculator.load_ns_params(ns_df)
        
        # Рассчитать G-spread для облигации
        g_spread_df = calculator.calculate(isin, ytm_df)
    """
    
    def __init__(self):
        self._ns_params: Optional[pd.DataFrame] = None
    
    def load_ns_params(self, ns_params_df: pd.DataFrame):
        """Загрузить параметры Nelson-Siegel"""
        self._ns_params = ns_params_df.copy()
        logger.info(f"Загружено {len(self._ns_params)} параметров NS")
    
    def calculate(
        self,
        bond_ytm_df: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Рассчитать G-spread для облигации
        
        Args:
            bond_ytm_df: DataFrame с YTM и duration облигации
            
        Returns:
            DataFrame с G-spread
        """
        if self._ns_params is None:
            logger.error("Параметры NS не загружены")
            return pd.DataFrame()
        
        return calculate_g_spread_history(bond_ytm_df, self._ns_params)
    
    def calculate_current(
        self,
        ytm: float,
        duration_years: float,
        ns_params: Dict
    ) -> Tuple[float, float]:
        """
        Рассчитать текущий G-spread
        
        Args:
            ytm: Текущий YTM облигации
            duration_years: Дюрация в годах
            ns_params: Параметры NS {'b1', 'b2', 'b3', 't1'}
            
        Returns:
            (ytm_kbd, g_spread_bp)
        """
        return calculate_g_spread(
            ytm,
            duration_years,
            ns_params['b1'],
            ns_params['b2'],
            ns_params['b3'],
            ns_params['t1']
        )
