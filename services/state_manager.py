"""
Управление состоянием приложения через URL параметры.

Все настройки хранятся в URL query_params:
- period, spread_window, z_threshold, etc.
- b1, b2 - ISIN выбранных облигаций

Преимущества:
- Переживает F5
- Можно шарить ссылки
- Нет async/callback проблем
- Синхронное API
"""
import streamlit as st
from typing import Optional, Dict, Any, List

# Ключи для сохранения в URL (название -> тип конвертации)
QUERY_KEYS = {
    'period': int,
    'spread_window': int,
    'z_threshold': float,
    'g_spread_period': int,
    'g_spread_window': int,
    'g_spread_z_threshold': float,
    'candle_interval': str,
    'candle_days': int,
}


def sync_from_url() -> None:
    """
    Загрузить настройки из URL query_params в session_state.
    Вызывать при инициализации приложения (ДО установки defaults).
    """
    params = st.query_params
    
    for key, type_conv in QUERY_KEYS.items():
        if key in params:
            try:
                value = params[key]
                # query_params может вернуть list или str
                if isinstance(value, list):
                    value = value[0] if value else None
                if value is not None:
                    st.session_state[key] = type_conv(value)
            except (ValueError, TypeError):
                pass  # Игнорируем невалидные значения


def sync_to_url() -> None:
    """
    Сохранить текущие настройки в URL query_params.
    Вызывать ПОСЛЕ рендера виджетов.
    """
    for key in QUERY_KEYS:
        value = st.session_state.get(key)
        if value is not None:
            st.query_params[key] = str(value)
    
    # Сохраняем выбранные облигации по ISIN
    bonds = st.session_state.get('bonds', {})
    isins = list(bonds.keys())
    
    idx1 = st.session_state.get('selected_bond1', 0)
    idx2 = st.session_state.get('selected_bond2', 1 if len(isins) > 1 else 0)
    
    if isins:
        if 0 <= idx1 < len(isins):
            st.query_params['b1'] = isins[idx1]
        if 0 <= idx2 < len(isins):
            st.query_params['b2'] = isins[idx2]


def get_bond_indices_from_url(bonds: list) -> tuple:
    """
    Получить индексы облигаций из URL (b1, b2 параметры с ISIN).
    
    Args:
        bonds: список облигаций (BondItem)
        
    Returns:
        (idx1, idx2) или (0, 1) если не найдено
    """
    params = st.query_params
    isins = [b.isin for b in bonds] if bonds else []
    
    idx1, idx2 = 0, 1 if len(bonds) > 1 else 0
    
    if 'b1' in params:
        b1_isin = params['b1']
        if isinstance(b1_isin, list):
            b1_isin = b1_isin[0] if b1_isin else None
        if b1_isin and b1_isin in isins:
            idx1 = isins.index(b1_isin)
    
    if 'b2' in params:
        b2_isin = params['b2']
        if isinstance(b2_isin, list):
            b2_isin = b2_isin[0] if b2_isin else None
        if b2_isin and b2_isin in isins:
            idx2 = isins.index(b2_isin)
    
    return idx1, idx2


def update_url_with_bonds(bond1_isin: str, bond2_isin: str) -> None:
    """
    Обновить URL с текущей парой облигаций.
    
    Args:
        bond1_isin: ISIN первой облигации
        bond2_isin: ISIN второй облигации
    """
    st.query_params['b1'] = bond1_isin
    st.query_params['b2'] = bond2_isin


# Stub функции для совместимости с предыдущим API
def save_last_pair(bond1_isin: str, bond2_isin: str) -> None:
    """Сохранить пару облигаций в URL (alias для update_url_with_bonds)."""
    update_url_with_bonds(bond1_isin, bond2_isin)


def load_last_pair() -> dict:
    """Загрузить пару облигаций из URL."""
    params = st.query_params
    result = {}
    
    if 'b1' in params:
        b1 = params['b1']
        result['b1'] = b1[0] if isinstance(b1, list) else b1
    
    if 'b2' in params:
        b2 = params['b2']
        result['b2'] = b2[0] if isinstance(b2, list) else b2
    
    return result
