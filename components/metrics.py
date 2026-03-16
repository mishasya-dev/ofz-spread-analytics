"""
Компонент для отображения метрик и статистики

Содержит функции для рендеринга метрик.
Расчёт статистики импортируется из services/spread_calculator.py
"""
import streamlit as st
from typing import Dict

# Импортируем расчёт из правильного места
from services.spread_calculator import calculate_spread_stats


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


__all__ = ['calculate_spread_stats', 'render_spread_stats']
