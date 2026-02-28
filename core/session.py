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
    from core.database import get_db
    from config import AppConfig
    import logging
    
    logger = logging.getLogger(__name__)
    
    # Инициализируем defaults
    SessionManager.init_defaults()
    
    # Инициализируем конфиг если нужно
    if st.session_state.config is None:
        st.session_state.config = AppConfig()
    
    # Миграция при первом запуске
    if not st.session_state.bonds_loaded:
        db = get_db()
        config = st.session_state.config
        migrated = db.migrate_config_bonds(config.bonds)
        if migrated > 0:
            logger.info(f"Мигрировано {migrated} облигаций из config.py в БД")
        st.session_state.bonds_loaded = True
    
    # Загрузка/обновление облигаций из БД
    db = get_db()
    favorites = db.get_favorite_bonds_as_config()
    
    if favorites:
        current_keys = set(st.session_state.get('bonds', {}).keys())
        new_keys = set(favorites.keys())
        if current_keys != new_keys:
            st.session_state.bonds = favorites
            logger.info(f"Обновлён список облигаций: {len(favorites)} избранное")
    else:
        if 'bonds' not in st.session_state or not st.session_state.bonds:
            config = st.session_state.config
            st.session_state.bonds = {
                isin: {
                    'isin': isin,
                    'name': bond.name,
                    'maturity_date': bond.maturity_date,
                    'coupon_rate': bond.coupon_rate,
                    'face_value': bond.face_value,
                    'coupon_frequency': bond.coupon_frequency,
                    'issue_date': bond.issue_date,
                    'day_count_convention': getattr(bond, 'day_count_convention', 'ACT/ACT'),
                }
                for isin, bond in config.bonds.items()
            }
