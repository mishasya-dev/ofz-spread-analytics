"""
Компонент для отображения торговых сигналов

Содержит функции для рендеринга сигналов.
Логика генерации сигналов импортируется из services/spread_calculator.py
"""
import streamlit as st
from typing import Dict

# Импортируем логику из правильного места
from services.spread_calculator import generate_signal


def render_signal_card(signal: Dict, bond1_name: str, bond2_name: str):
    """
    Рендерит карточку сигнала

    Args:
        signal: Словарь с сигналом (signal, action, reason, color, strength)
        bond1_name: Имя облигации 1
        bond2_name: Имя облигации 2
    """
    signal_type = signal['signal']

    # Определяем CSS класс и иконку
    if signal_type == 'SELL_BUY':
        css_class = 'signal-sell'
        icon = '🔴'
    elif signal_type == 'BUY_SELL':
        css_class = 'signal-buy'
        icon = '🟢'
    else:
        css_class = 'signal-neutral'
        icon = '🟡'

    st.markdown(f"""
    <div class="metric-card {css_class}">
        <h3>{icon} Сигнал: {signal['signal']}</h3>
        <p><strong>{signal['action']}</strong></p>
        <p>{signal['reason']}</p>
        <p><em>Сила: {signal['strength']}</em></p>
    </div>
    """, unsafe_allow_html=True)


__all__ = ['generate_signal', 'render_signal_card']
