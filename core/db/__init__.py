"""
Репозитории базы данных

Предоставляет удобный доступ к репозиториям для работы с данными.
"""
from .connection import get_connection, init_database, DB_PATH
from .bonds_repo import BondsRepository
from .ytm_repo import YTMRepository
from .spreads_repo import SpreadsRepository

__all__ = [
    'get_connection',
    'init_database',
    'DB_PATH',
    'BondsRepository',
    'YTMRepository',
    'SpreadsRepository',
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
