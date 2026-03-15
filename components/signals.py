"""
Компонент для отображения торговых сигналов

Содержит логику генерации и рендеринга сигналов.

NOTE: calculate_spread_stats() moved to components/metrics.py
"""
import streamlit as st
from typing import Dict


def generate_signal(current_spread: float, p10: float, p25: float, p75: float, p90: float) -> Dict:
    """Генерирует торговый сигнал"""
    if current_spread < p25:
        return {
            'signal': 'SELL_BUY',
            'action': 'ПРОДАТЬ Облигацию 1, КУПИТЬ Облигацию 2',
            'reason': f'Спред {current_spread:.2f} б.п. ниже P25 ({p25:.2f} б.п.) — Облигация 1 переоценена относительно Облигации 2',
            'color': '#FF6B6B',
            'strength': 'Сильный' if current_spread < p10 else 'Средний'
        }
    elif current_spread > p75:
        return {
            'signal': 'BUY_SELL',
            'action': 'КУПИТЬ Облигацию 1, ПРОДАТЬ Облигацию 2',
            'reason': f'Спред {current_spread:.2f} б.п. выше P75 ({p75:.2f} б.п.) — Облигация 1 недооценена относительно Облигации 2',
            'color': '#4ECDC4',
            'strength': 'Сильный' if current_spread > p90 else 'Средний'
        }
    else:
        return {
            'signal': 'NEUTRAL',
            'action': 'Удерживать позиции',
            'reason': f'Спред {current_spread:.2f} б.п. в нормальном диапазоне [P25={p25:.2f}, P75={p75:.2f}]',
            'color': '#95A5A6',
            'strength': 'Нет сигнала'
        }


def render_signal_card(signal: Dict, bond1_name: str, bond2_name: str):
    """Рендерит карточку сигнала"""
    signal_type = signal['signal']
    
    # Определяем CSS класс
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
