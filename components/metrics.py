"""
Компонент для отображения метрик и статистики

Содержит функции для расчёта и отображения метрик.
"""
import streamlit as st
from typing import Dict
import pandas as pd


def calculate_spread_stats(spread_series: pd.Series) -> Dict[str, float]:
    """
    Вычисляет статистику спреда
    
    Args:
        spread_series: Series со значениями спреда
    
    Returns:
        Словарь со статистикой
    """
    return {
        'mean': spread_series.mean(),
        'median': spread_series.median(),
        'std': spread_series.std(),
        'min': spread_series.min(),
        'max': spread_series.max(),
        'p10': spread_series.quantile(0.10),
        'p25': spread_series.quantile(0.25),
        'p75': spread_series.quantile(0.75),
        'p90': spread_series.quantile(0.90),
        'current': spread_series.iloc[-1]
    }


def render_spread_stats(stats: Dict[str, float]):
    """
    Рендерит статистику спреда
    
    Args:
        stats: Словарь со статистикой
    """
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Среднее", f"{stats['mean']:.1f} б.п.")
    with col2:
        st.metric("Std", f"{stats['std']:.1f} б.п.")
    with col3:
        st.metric("Min", f"{stats['min']:.1f} б.п.")
    with col4:
        st.metric("Max", f"{stats['max']:.1f} б.п.")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("P25", f"{stats['p25']:.1f} б.п.")
    with col2:
        st.metric("P75", f"{stats['p75']:.1f} б.п.")
    with col3:
        st.metric("Текущий", f"{stats['current']:.1f} б.п.")
