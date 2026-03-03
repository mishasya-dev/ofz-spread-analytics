"""
Расчёт спредов и статистики для OFZ Spread Analytics

Содержит функции для расчёта спредов, статистики и генерации сигналов.
"""
import pandas as pd
import numpy as np
from typing import Dict, Optional


def calculate_spread_stats(spread_series: pd.Series) -> Dict:
    """
    Вычисляет статистику спреда.

    Args:
        spread_series: Series со значениями спреда в базисных пунктах

    Returns:
        Dict с ключами: mean, median, std, min, max, p10, p25, p75, p90, current
        Пустой dict если series пустой или все NaN
    """
    if spread_series.empty:
        return {}

    # Удаляем NaN для статистики
    clean_series = spread_series.dropna()

    if clean_series.empty:
        return {}

    return {
        'mean': clean_series.mean(),
        'median': clean_series.median(),
        'std': clean_series.std(),
        'min': clean_series.min(),
        'max': clean_series.max(),
        'p10': clean_series.quantile(0.10),
        'p25': clean_series.quantile(0.25),
        'p75': clean_series.quantile(0.75),
        'p90': clean_series.quantile(0.90),
        'current': clean_series.iloc[-1] if len(clean_series) > 0 else 0
    }


def generate_signal(
    current_spread: float,
    p10: float,
    p25: float,
    p75: float,
    p90: float
) -> Dict:
    """
    Генерирует торговый сигнал на основе перцентилей.

    Логика:
    - spread < p25: SELL_BUY (продать длинную, купить короткую)
      - spread < p10: Сильный сигнал
      - иначе: Средний сигнал
    - spread > p75: BUY_SELL (купить длинную, продать короткую)
      - spread > p90: Сильный сигнал
      - иначе: Средний сигнал
    - иначе: NEUTRAL (удерживать)

    Args:
        current_spread: Текущее значение спреда в б.п.
        p10: 10-й перцентиль
        p25: 25-й перцентиль
        p75: 75-й перцентиль
        p90: 90-й перцентиль

    Returns:
        Dict с ключами: signal, action, reason, color, strength
    """
    if current_spread < p25:
        return {
            'signal': 'SELL_BUY',
            'action': 'ПРОДАТЬ Облигацию 1, КУПИТЬ Облигацию 2',
            'reason': f'Спред {current_spread:.2f} б.п. ниже P25 ({p25:.2f} б.п.)',
            'color': '#FF6B6B',
            'strength': 'Сильный' if current_spread < p10 else 'Средний'
        }
    elif current_spread > p75:
        return {
            'signal': 'BUY_SELL',
            'action': 'КУПИТЬ Облигацию 1, ПРОДАТЬ Облигацию 2',
            'reason': f'Спред {current_spread:.2f} б.п. выше P75 ({p75:.2f} б.п.)',
            'color': '#4ECDC4',
            'strength': 'Сильный' if current_spread > p90 else 'Средний'
        }
    else:
        return {
            'signal': 'NEUTRAL',
            'action': 'Удерживать позиции',
            'reason': f'Спред {current_spread:.2f} б.п. в диапазоне [P25={p25:.2f}, P75={p75:.2f}]',
            'color': '#95A5A6',
            'strength': 'Нет сигнала'
        }


def prepare_spread_dataframe(
    df1: pd.DataFrame,
    df2: pd.DataFrame,
    is_intraday: bool = False
) -> pd.DataFrame:
    """
    Подготовить DataFrame со спредом.

    Объединяет YTM двух облигаций и рассчитывает спред.

    Args:
        df1: DataFrame с YTM первой облигации
        df2: DataFrame с YTM второй облигации
        is_intraday: True для intraday данных (колонка ytm_close),
                    False для daily данных (колонка ytm)

    Returns:
        DataFrame с колонками: ytm1, ytm2, spread, (date или datetime)
        Пустой DataFrame если входные данные пустые
    """
    if df1.empty or df2.empty:
        return pd.DataFrame()

    ytm_col = 'ytm_close' if is_intraday else 'ytm'

    if ytm_col not in df1.columns or ytm_col not in df2.columns:
        return pd.DataFrame()

    # Удаляем дубликаты в индексах перед объединением
    df1_clean = df1[~df1.index.duplicated(keep='last')][[ytm_col]].copy()
    df2_clean = df2[~df2.index.duplicated(keep='last')][[ytm_col]].copy()

    # Объединяем по индексу с помощью join
    merged = df1_clean.join(df2_clean, lsuffix='_1', rsuffix='_2', how='inner')

    # Переименовываем колонки
    merged.columns = ['ytm1', 'ytm2']

    # Удаляем NaN
    merged = merged.dropna()

    if merged.empty:
        return pd.DataFrame()

    # Спред в базисных пунктах
    merged['spread'] = (merged['ytm1'] - merged['ytm2']) * 100

    # Добавляем колонки для графиков
    if is_intraday:
        merged['datetime'] = merged.index
    else:
        merged['date'] = merged.index

    return merged


def calculate_rolling_stats(
    spread_series: pd.Series,
    window: int = 30
) -> pd.DataFrame:
    """
    Рассчитать скользящую статистику спреда.

    Args:
        spread_series: Series со значениями спреда
        window: Размер окна для расчёта

    Returns:
        DataFrame с колонками: spread, rolling_mean, rolling_std, upper_bound, lower_bound
    """
    if spread_series.empty:
        return pd.DataFrame()

    df = pd.DataFrame({'spread': spread_series})

    df['rolling_mean'] = df['spread'].rolling(window=window, min_periods=1).mean()
    df['rolling_std'] = df['spread'].rolling(window=window, min_periods=1).std()

    return df


def calculate_zscore(
    spread: float,
    mean: float,
    std: float
) -> Optional[float]:
    """
    Рассчитать Z-Score.

    Args:
        spread: Значение спреда
        mean: Среднее значение
        std: Стандартное отклонение

    Returns:
        Z-Score или None если std == 0
    """
    if std == 0 or pd.isna(std):
        return None
    return (spread - mean) / std
