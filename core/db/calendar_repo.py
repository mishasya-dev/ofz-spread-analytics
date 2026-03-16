"""
Репозиторий для работы с торговым календарём MOEX.

Таблицы:
- trading_calendar: даты с флагом is_trading
- calendar_meta: метаданные (cached_month, cached_years, last_update)
"""

import logging
from datetime import date, timedelta
from typing import Optional, Set, List

from .connection import get_db_connection, get_db_cursor

logger = logging.getLogger(__name__)


class CalendarRepository:
    """Репозиторий для работы с торговым календарём"""
    
    def save_trading_days(self, dates: List[date], source: str = 'moex') -> int:
        """
        Сохранить торговые дни в БД.
        
        Args:
            dates: Список торговых дней
            source: Источник данных (moex/computed)
            
        Returns:
            Количество сохранённых записей
        """
        if not dates:
            return 0
        
        saved = 0
        with get_db_connection() as conn:
            cursor = conn.cursor()
            for d in dates:
                try:
                    cursor.execute('''
                        INSERT OR REPLACE INTO trading_calendar (date, is_trading, source)
                        VALUES (?, 1, ?)
                    ''', (d.isoformat(), source))
                    saved += 1
                except Exception as e:
                    logger.warning(f"Ошибка сохранения {d}: {e}")
        
        logger.info(f"Сохранено {saved} торговых дней")
        return saved
    
    def load_trading_days_in_range(self, start_date: date, end_date: date) -> Set[date]:
        """
        Загрузить торговые дни в диапазоне.
        
        Args:
            start_date: Начальная дата
            end_date: Конечная дата
            
        Returns:
            Множество торговых дней
        """
        with get_db_cursor() as cursor:
            cursor.execute('''
                SELECT date FROM trading_calendar
                WHERE date >= ? AND date <= ? AND is_trading = 1
                ORDER BY date
            ''', (start_date.isoformat(), end_date.isoformat()))
            rows = cursor.fetchall()
        
        return {date.fromisoformat(row[0]) for row in rows}
    
    def is_trading_day(self, d: date) -> Optional[bool]:
        """
        Проверить, торговый ли день.
        
        Args:
            d: Дата для проверки
            
        Returns:
            True/False если есть в БД, None если нет записи
        """
        with get_db_cursor() as cursor:
            cursor.execute('''
                SELECT is_trading FROM trading_calendar WHERE date = ?
            ''', (d.isoformat(),))
            row = cursor.fetchone()
        
        if row is None:
            return None
        return bool(row[0])
    
    def count_trading_days(self) -> int:
        """Количество торговых дней в БД"""
        with get_db_cursor() as cursor:
            cursor.execute('SELECT COUNT(*) FROM trading_calendar WHERE is_trading = 1')
            row = cursor.fetchone()
        return row[0] if row else 0
    
    def date_range(self) -> Optional[tuple]:
        """Диапазон дат в календаре"""
        with get_db_cursor() as cursor:
            cursor.execute('SELECT MIN(date), MAX(date) FROM trading_calendar')
            row = cursor.fetchone()
        
        if row and row[0]:
            return (date.fromisoformat(row[0]), date.fromisoformat(row[1]))
        return None
    
    def save_non_trading_days(self, dates: List[date], source: str = 'moex') -> int:
        """
        Сохранить неторговые дни в БД.
        
        Args:
            dates: Список неторговых дней
            source: Источник данных
            
        Returns:
            Количество сохранённых записей
        """
        if not dates:
            return 0
        
        saved = 0
        with get_db_connection() as conn:
            cursor = conn.cursor()
            for d in dates:
                try:
                    cursor.execute('''
                        INSERT OR REPLACE INTO trading_calendar (date, is_trading, source)
                        VALUES (?, 0, ?)
                    ''', (d.isoformat(), source))
                    saved += 1
                except Exception as e:
                    logger.warning(f"Ошибка сохранения {d}: {e}")
        
        logger.info(f"Сохранено {saved} неторговых дней")
        return saved
    
    def load_trading_days_in_range(self, start_date: date, end_date: date) -> Set[date]:
        """
        Загрузить торговые дни в диапазоне.
        
        Args:
            start_date: Начальная дата
            end_date: Конечная дата
            
        Returns:
            Множество торговых дней
        """
        with get_db_cursor() as cursor:
            cursor.execute('''
                SELECT date FROM trading_calendar
                WHERE date >= ? AND date <= ? AND is_trading = 1
                ORDER BY date
            ''', (start_date.isoformat(), end_date.isoformat()))
            rows = cursor.fetchall()
        
        return {date.fromisoformat(row[0]) for row in rows}
    
    def is_trading_day(self, d: date) -> Optional[bool]:
        """
        Проверить, торговый ли день.
        
        Args:
            d: Дата для проверки
            
        Returns:
            True/False если есть в БД, None если нет записи
        """
        with get_db_cursor() as cursor:
            cursor.execute('''
                SELECT is_trading FROM trading_calendar WHERE date = ?
            ''', (d.isoformat(),))
            row = cursor.fetchone()
        
        if row is None:
            return None
        return bool(row[0])
    
    def count_trading_days(self) -> int:
        """Количество торговых дней в БД"""
        with get_db_cursor() as cursor:
            cursor.execute('SELECT COUNT(*) FROM trading_calendar WHERE is_trading = 1')
            row = cursor.fetchone()
        return row[0] if row else 0
    
    def date_range(self) -> Optional[tuple]:
        """Диапазон дат в календаре"""
        with get_db_cursor() as cursor:
            cursor.execute('SELECT MIN(date), MAX(date) FROM trading_calendar')
            row = cursor.fetchone()
        
        if row and row[0]:
            return (date.fromisoformat(row[0]), date.fromisoformat(row[1]))
        return None
    
    # ==========================================
    # МЕТАДАННЫЕ
    # ==========================================
    
    def get_meta(self, key: str) -> Optional[str]:
        """Получить значение метаданных"""
        with get_db_cursor() as cursor:
            cursor.execute('SELECT value FROM calendar_meta WHERE key = ?', (key,))
            row = cursor.fetchone()
        return row[0] if row else None
    
    def set_meta(self, key: str, value: str) -> None:
        """Установить значение метаданных"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO calendar_meta (key, value)
                VALUES (?, ?)
            ''', (key, value))
    
    def cached_years(self) -> Set[int]:
        """Получить список закэшированных годов"""
        years_str = self.get_meta('cached_years')
        if not years_str:
            return set()
        try:
            return {int(y) for y in years_str.split(',') if y.strip()}
        except (ValueError, AttributeError):
            return set()
    
    def get_last_update(self) -> Optional[date]:
        """Дата последнего обновления календаря"""
        last_update = self.get_meta('last_update')
        if last_update:
            try:
                return date.fromisoformat(last_update)
            except ValueError:
                pass
        return None
    
    def get_cached_month(self) -> Optional[int]:
        """Получить закэшированный месяц (YYYYMM)"""
        month_str = self.get_meta('cached_month')
        if month_str:
            try:
                return int(month_str)
            except ValueError:
                pass
        return None
