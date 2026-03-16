"""
Расчёт G-spread через кривую КБД (G-Curve)

================================================================================
ВАЖНО: ИЗМЕНЕНИЕ МЕТОДОЛОГИИ (2026-03)
================================================================================

G-spread теперь берётся НАПРЯМУЮ из MOEX ZCYC API:
- get_zcyc_data_for_date() - точные данные за дату
- get_zcyc_history() - исторические данные

Формула: G-spread = trdyield - clcyield (уже рассчитан MOEX!)

DEPRECATED ФУНКЦИИ (не использовать):
- interpolate_kbd() - не нужна, MOEX даёт готовые значения
- nelson_siegel() - даёт ошибку ~90-100 bp
- nelson_siegel_vectorized() - то же
- calculate_g_spread() - старый метод
- calculate_g_spread_history() - старый метод
- enrich_bond_data() - старый метод
- enrich_bond_data_with_yearyields() - старый метод

АКТИВНЫЕ ФУНКЦИИ:
- calculate_g_spread_stats() - статистика по G-spread
- generate_g_spread_signal() - генерация торговых сигналов

================================================================================

G-spread = YTM_облигации - YTM_КБД(maturity)

MOEX использует MATURITY (срок до погашения), а не DURATION.
"""
import numpy as np
import pandas as pd
from datetime import date, datetime
from typing import Optional, Dict, Tuple, List
import logging

logger = logging.getLogger(__name__)


# ============================================================================
# DEPRECATED: Мёртвый код - заменено на get_zcyc_data_for_date / get_zcyc_history
# ============================================================================

# def interpolate_kbd(
#     maturity_years: float,
#     periods: List[float],
#     values: List[float]
# ) -> float:
#     """
#     DEPRECATED: Используйте get_zcyc_data_for_date() из api/moex_zcyc.py
#     
#     Интерполяция КБД по точкам yearyields
#     
#     Args:
#         maturity_years: Срок до погашения (годы)
#         periods: Список периодов КБД [0.25, 0.5, 0.75, 1, 2, 3, 5, 7, 10, 15, 20]
#         values: Список YTM КБД для каждого периода (%)
#         
#     Returns:
#         Интерполированное значение YTM КБД (%)
#     """
#     if not periods or not values:
#         return 0.0
#     
#     periods = np.array(periods)
#     values = np.array(values)
#     
#     # Граничные случаи
#     if maturity_years <= periods[0]:
#         return float(values[0])
#     if maturity_years >= periods[-1]:
#         return float(values[-1])
#     
#     # Линейная интерполяция
#     for i in range(len(periods) - 1):
#         if periods[i] <= maturity_years <= periods[i+1]:
#             frac = (maturity_years - periods[i]) / (periods[i+1] - periods[i])
#             return float(values[i] + frac * (values[i+1] - values[i]))
#     
#     return float(values[-1])


# def nelson_siegel(...) - DEPRECATED: даёт ошибку ~90-100 bp, используйте get_zcyc_data_for_date()
# def nelson_siegel_vectorized(...) - DEPRECATED
# def calculate_g_spread(...) - DEPRECATED
# def calculate_g_spread_history(...) - DEPRECATED


# ============================================================================
# АКТИВНЫЕ ФУНКЦИИ
# ============================================================================


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
    
    # Используем .item() для гарантии возврата скаляров
    return {
        'mean': float(clean.mean()),
        'median': float(clean.median()),
        'std': float(clean.std()),
        'min': float(clean.min()),
        'max': float(clean.max()),
        'p10': float(clean.quantile(0.10)),
        'p25': float(clean.quantile(0.25)),
        'p75': float(clean.quantile(0.75)),
        'p90': float(clean.quantile(0.90)),
        'current': float(clean.iloc[-1]) if len(clean) > 0 else 0.0,
        'count': int(len(clean))
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


# ============================================================================
# DEPRECATED: Мёртвый код (продолжение)
# ============================================================================
# enrich_bond_data(...) - DEPRECATED: используйте get_zcyc_history()
# enrich_bond_data_with_yearyields(...) - DEPRECATED: используйте get_zcyc_history()
# class GSpreadCalculator - DEPRECATED


# ============================================================================
# КОНЕЦ DEPRECATED КОДА
# ============================================================================


# ============================================================================
# G-SPREAD ИЗ ZCYC (MOEX API)
# ============================================================================


def calculate_g_spread_from_zcyc(
    zcyc_df: pd.DataFrame,
    window: int = 30
) -> Tuple[pd.DataFrame, float]:
    """
    Рассчитать G-spread с Z-Score и ADF тестом из ZCYC данных MOEX
    
    Принимает уже загруженные ZCYC данные и делает расчёты:
    - Rolling Z-Score
    - ADF тест на стационарность
    
    Args:
        zcyc_df: DataFrame с ZCYC данными (columns: date, g_spread_bp, trdyield, clcyield, duration_days)
        window: Окно для rolling Z-Score
        
    Returns:
        (DataFrame с результатами, p_value ADF теста)
    """
    if zcyc_df.empty:
        return pd.DataFrame(), 1.0
    
    from statsmodels.tsa.stattools import adfuller
    
    df = zcyc_df.copy()
    
    # Сортируем по дате
    if 'date' in df.columns:
        df = df.sort_values('date').reset_index(drop=True)
    elif df.index.name == 'date':
        df = df.reset_index().sort_values('date').reset_index(drop=True)
    
    # Rolling Z-Score (сохраняем также mean и std для графиков)
    roll = df['g_spread_bp'].rolling(window=window)
    df['rolling_mean'] = roll.mean()
    df['rolling_std'] = roll.std()
    df['z_score'] = (df['g_spread_bp'] - df['rolling_mean']) / df['rolling_std']
    
    # ADF тест
    p_value = 1.0
    try:
        g_spread_clean = df['g_spread_bp'].dropna()
        if len(g_spread_clean) >= 20:
            adf_result = adfuller(g_spread_clean)
            p_value = adf_result[1]
    except Exception as e:
        logger.warning(f"ADF тест не удался: {e}")
    
    # Формируем результат
    result_df = df.copy()
    
    # Устанавливаем индекс
    if 'date' in result_df.columns:
        result_df = result_df.set_index('date')
    
    # Добавляем колонки для совместимости с UI
    column_mapping = {
        'trdyield': 'ytm_bond',
        'clcyield': 'ytm_kbd',
        'duration_days': 'duration_days'
    }
    result_df = result_df.rename(columns=column_mapping)
    
    # Добавляем duration_years если есть duration_days
    if 'duration_days' in result_df.columns:
        result_df['duration_years'] = result_df['duration_days'] / 365.25
    
    return result_df, p_value
