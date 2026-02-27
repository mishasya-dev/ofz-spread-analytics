"""
Компонент заголовка приложения
"""
import streamlit as st


def render_header(data_mode: str):
    """
    Рендерит заголовок приложения
    
    Args:
        data_mode: 'daily' или 'intraday'
    """
    mode_badge = (
        '<span class="mode-badge mode-daily">📅 Дневной режим</span>' 
        if data_mode == "daily" 
        else '<span class="mode-badge mode-intraday">⏱️ Внутридневной режим</span>'
    )
    
    st.markdown(f"""
    <div style="display: flex; align-items: center; margin-bottom: 10px;">
        <h1 style="margin: 0;">📊 OFZ Spread Analytics</h1>
        {mode_badge}
    </div>
    <p style="margin: 0; color: #666;">Анализ спредов облигаций ОФЗ с данными Московской биржи</p>
    """, unsafe_allow_html=True)
