"""
Управление состоянием сессии Streamlit

Централизованная инициализация session_state с значениями по умолчанию.
"""
import streamlit as st
from typing import Any, Dict


class SessionManager:
    """
    Менеджер состояния сессии Streamlit
    
    Централизует инициализацию session_state и предоставляет
    типобезопасный доступ к ключам.
    """
    
    # Ключи сессии и их значения по умолчанию
    DEFAULTS: Dict[str, Any] = {
        # Конфигурация
        'config': None,  # Инициализируется отдельно
        'bonds_loaded': False,
        'bonds': {},
        
        # Выбор облигаций
        'selected_bond1': 0,
        'selected_bond2': 1,
        
        # Режимы и периоды
        'period': 365,
        'data_mode': 'daily',  # 'daily' или 'intraday'
        'candle_interval': '60',  # '1', '10', '60'
        
        # Автообновление
        'auto_refresh': False,
        'refresh_interval': 60,
        'intraday_refresh_interval': 30,
        'last_update': None,
        
        # Intraday
        'intraday_period': 30,
        'save_data': False,
        'saved_count': 0,
        
        # БД
        'updating_db': False,
        
        # Bond Manager
        'bond_manager_open_id': None,
        'bond_manager_last_shown_id': None,
        'bond_manager_current_favorites': None,
        'bond_manager_original_favorites': None,
        'cached_favorites_count': 0,
    }
    
    @classmethod
    def init_defaults(cls):
        """
        Инициализировать все ключи session_state значениями по умолчанию.
        
        Вызывать в начале каждого rerun.
        """
        for key, value in cls.DEFAULTS.items():
            if key not in st.session_state:
                st.session_state[key] = value
    
    @classmethod
    def get(cls, key: str, default: Any = None) -> Any:
        """Получить значение из session_state"""
        return st.session_state.get(key, default)
    
    @classmethod
    def set(cls, key: str, value: Any):
        """Установить значение в session_state"""
        st.session_state[key] = value
    
    @classmethod
    def clear(cls, key: str):
        """Удалить ключ из session_state"""
        if key in st.session_state:
            del st.session_state[key]
    
    @classmethod
    def clear_all(cls):
        """Очистить все ключи, определённые в DEFAULTS"""
        for key in cls.DEFAULTS:
            if key in st.session_state:
                del st.session_state[key]


def init_session_state():
    """
    Инициализация состояния сессии с загрузкой облигаций из БД.
    
    Заменяет оригинальную функцию из app.py.
    """
    from core.db import get_db_facade
    from config import AppConfig
    import logging
    
    logger = logging.getLogger(__name__)
    
    # Инициализируем defaults
    SessionManager.init_defaults()
    
    # Инициализируем конфиг если нужно
    if st.session_state.config is None:
        st.session_state.config = AppConfig()
    
    # Загрузка облигаций из БД
    # При первом запуске OFZCache загрузит список с MOEX и пометит все как избранные
    db = get_db_facade()
    favorites = db.get_favorite_bonds_as_config()

    if not favorites:
        # Первый запуск - загружаем список ОФЗ с MOEX
        # OFZCache пометит все как избранные при первой загрузке
        from core.ofz_cache import OFZCache
        cache = OFZCache()
        cache.get_ofz_list()  # Загрузит и пометит все как избранные
        favorites = db.get_favorite_bonds_as_config()
        logger.info(f"Первый запуск: загружено {len(favorites)} облигаций как избранные")

    if favorites:
        current_keys = set(st.session_state.get('bonds', {}).keys())
        new_keys = set(favorites.keys())
        if current_keys != new_keys:
            st.session_state.bonds = favorites
            logger.info(f"Обновлён список облигаций: {len(favorites)} избранное")
