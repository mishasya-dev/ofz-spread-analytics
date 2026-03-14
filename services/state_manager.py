"""
Управление состоянием приложения через браузерное хранилище.

localStorage:
  - last_pair: последняя пара облигаций (переживает закрытие браузера)

sessionStorage:
  - settings: настройки текущей вкладки (уникально для каждой вкладки)
"""
import streamlit as st
from streamlit_browser_storage import LocalStorage, SessionStorage

# Инициализация хранилищ
LOCAL = LocalStorage(key="ofz_local")
SESSION = SessionStorage(key="ofz_session")

# Ключи для сохранения в sessionStorage
SESSION_KEYS = [
    'period',
    'spread_window',
    'z_threshold',
    'g_spread_period',
    'g_spread_window',
    'g_spread_z_threshold',
    'candle_interval',
    'candle_days',
    'auto_refresh',
    'refresh_interval',
]


def save_last_pair(bond1_isin: str, bond2_isin: str) -> None:
    """
    Сохранить последнюю пару облигаций в localStorage.

    Args:
        bond1_isin: ISIN первой облигации
        bond2_isin: ISIN второй облигации
    """
    LOCAL.set("last_pair", {"b1": bond1_isin, "b2": bond2_isin})


def load_last_pair() -> dict:
    """
    Загрузить последнюю пару облигаций из localStorage.

    Returns:
        dict с ключами 'b1' и 'b2' (ISIN), или пустой dict если нет данных
    """
    return LOCAL.get("last_pair") or {}


def save_session() -> None:
    """
    Сохранить текущие настройки вкладки в sessionStorage.
    Вызывать при изменении любого виджета (on_change).
    """
    settings = {}
    for key in SESSION_KEYS:
        value = st.session_state.get(key)
        if value is not None:
            settings[key] = value

    SESSION.set("settings", settings)


def load_session() -> None:
    """
    Загрузить настройки вкладки из sessionStorage в session_state.
    Вызывать при инициализации приложения.
    """
    settings = SESSION.get("settings")
    if settings:
        for key in SESSION_KEYS:
            if key in settings and settings[key] is not None:
                st.session_state[key] = settings[key]
