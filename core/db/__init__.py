"""
Репозитории базы данных

Предоставляет удобный доступ к репозиториям для работы с данными.
"""
from .connection import (
    get_connection, 
    init_database, 
    DB_PATH,
    get_db_connection,  # Контекстный менеджер для соединения
    get_db_cursor,      # Контекстный менеджер для курсора
)
from .bonds_repo import BondsRepository
from .ytm_repo import YTMRepository
from .spreads_repo import SpreadsRepository
from .g_spread_repo import GSpreadRepository
from .calendar_repo import CalendarRepository
from .facade import DatabaseFacade, get_db_facade

__all__ = [
    # Соединения
    'get_connection',
    'get_db_connection',   # Контекстный менеджер для соединения
    'get_db_cursor',       # Контекстный менеджер для курсора
    'init_database',
    'DB_PATH',
    # Репозитории
    'BondsRepository',
    'YTMRepository',
    'SpreadsRepository',
    'GSpreadRepository',
    'CalendarRepository',
    # Фасад
    'DatabaseFacade',
    'get_db_facade',
    'get_db',  # Алиас для обратной совместимости
    # Фабрики
    'get_bonds_repo',
    'get_ytm_repo',
    'get_spreads_repo',
    'get_g_spread_repo',
    'get_calendar_repo',
]


# Фабрики для удобства
def get_bonds_repo() -> BondsRepository:
    """Получить репозиторий облигаций"""
    return BondsRepository()


def get_ytm_repo() -> YTMRepository:
    """Получить репозиторий YTM"""
    return YTMRepository()


def get_spreads_repo() -> SpreadsRepository:
    """Получить репозиторий спредов"""
    return SpreadsRepository()


def get_g_spread_repo() -> GSpreadRepository:
    """Получить репозиторий G-spread"""
    return GSpreadRepository()


def get_calendar_repo() -> CalendarRepository:
    """Получить репозиторий календаря"""
    return CalendarRepository()


def get_db() -> DatabaseFacade:
    """
    Получить фасад БД (алиас для get_db_facade).
    
    Для обратной совместимости с кодом, использовавшим core.database.get_db().
    """
    return get_db_facade()
