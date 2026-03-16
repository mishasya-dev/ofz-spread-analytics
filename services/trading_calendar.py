"""
Торговый календарь MOEX.

Загружается один раз за 2 года назад и на 1 год вперёд.
Проверка: если месяц не менялся - догрузки не требуется.
"""

import logging
from datetime import date, timedelta
from typing import Optional, Set, Dict

from api.moex_client import MOEXClient
from core.db.calendar_repo import CalendarRepository

logger = logging.getLogger(__name__)


def get_calendar():
    """Фабрика для получения singleton календаря"""
    return TradingCalendar()


class TradingCalendar:
    """
    Singleton для работы с торговым календарём MOEX.
    
    Автоматически загружает календарь при первом обращении.
    Кэширует в памяти торговые дни.
    """
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._repo = CalendarRepository()
            cls._instance._trading_days_cache: Set[date] = set()
            cls._instance._last_check_month: Optional[int] = None
            cls._instance._initialized = False
        return cls._instance
    
    def _ensure_loaded(self, years_back: int = 2, years_forward: int = 1) -> None:
        """
        Убедиться, что календарь загружен за нужный период.
        
        Args:
            years_back: Лет назад (по умолчанию 2)
            years_forward: Лет вперёд (по умолчанию 1)
        """
        if self._initialized:
            return
        
        today = date.today()
        
        # Определяем нужный период
        start_date = today - timedelta(days=years_back * 365)
        end_date = today + timedelta(days=years_forward * 365)
        
        # Проверяем текущий месяц
        current_month = today.year * 100 + today.month
        cached_month = self._repo.get_cached_month()
        
        need_load = False
        
        if cached_month is None:
            need_load = True
            logger.info("[CALENDAR] Первый запуск, загружаем календарь с MOEX")
        elif cached_month != current_month:
            # Месяц изменился - проверяем есть ли данные за новый месяц
            need_load = True
            logger.info(f"[CALENDAR] Новый месяц ({current_month}), проверяем данные")
        else:
            # Проверяем покрытие дат в БД
            date_range = self._repo.date_range()
            if date_range is None:
                need_load = True
                logger.info("[CALENDAR] Календарь пуст, загружаем")
            else:
                min_date, max_date = date_range
                if min_date > start_date or max_date < end_date:
                    need_load = True
                    logger.info(f"[CALENDAR] Расширяем период: сейчас {min_date}..{max_date}, нужно {start_date}..{end_date}")
        
        if need_load:
            self._load_from_moex(start_date, end_date)
        
        # Загружаем кэш в память
        self._trading_days_cache = self._repo.load_trading_days_in_range(start_date, end_date)
        self._last_check_month = current_month
        self._initialized = True
        
        logger.info(f"[CALENDAR] Загружено {len(self._trading_days_cache)} торговых дней в кэш")

    def _load_from_moex(self, start_date: date, end_date: date) -> None:
        """
        Загрузить календарь с MOEX и вычислить торговые дни.
        
        MOEX API возвращает только исключения (праздники и переносы).
        Торговые дни вычисляются: пн-пт минус праздники плюс переносы.
        """
        try:
            with MOEXClient() as client:
                data = client.get_json("/engines/stock.json", {"iss.meta": "off"})
            
            dailytable = data.get("dailytable", {})
            exceptions: Dict[date, bool] = {}
            
            if dailytable and "data" in dailytable:
                for row in dailytable["data"]:
                    d = date.fromisoformat(row[0])
                    is_trading = row[1] == 1
                    exceptions[d] = is_trading
            
            logger.info(f"[CALENDAR] Получено {len(exceptions)} исключений от MOEX")
            
            # Вычисляем торговые дни
            trading_days = []
            non_trading_days = []
            
            current = start_date
            while current <= end_date:
                # Базовое правило: пн-пт = торговые
                is_trading = current.weekday() < 5
                
                # Проверяем исключения от MOEX
                if current in exceptions:
                    is_trading = exceptions[current]
                
                if is_trading:
                    trading_days.append(current)
                else:
                    non_trading_days.append(current)
                
                current += timedelta(days=1)
            
            # Сохраняем в БД
            saved_trading = self._repo.save_trading_days(trading_days)
            saved_non_trading = self._repo.save_non_trading_days(non_trading_days)
            
            # Обновляем метаданные
            today = date.today()
            self._repo.set_meta('last_update', today.isoformat())
            self._repo.set_meta('cached_month', str(today.year * 100 + today.month))
            
            # Сохраняем годы
            years = set()
            for y in range(start_date.year, end_date.year + 1):
                years.add(y)
            self._repo.set_meta('cached_years', ','.join(str(y) for y in sorted(years)))
            
            logger.info(f"[CALENDAR] Сохранено: {saved_trading} торговых, {saved_non_trading} неторговых дней")
            
        except Exception as e:
            logger.error(f"[CALENDAR] Ошибка загрузки с MOEX: {e}")
            raise

    def is_trading_day(self, d: date) -> bool:
        """
        Проверить, торговый ли день.
        
        Args:
            d: Дата для проверки
            
        Returns:
            True если день торговый, False если неторговый
        """
        self._ensure_loaded()
        
        # Сначала проверяем кэш
        if d in self._trading_days_cache:
            return True
        
        # Проверяем БД
        result = self._repo.is_trading_day(d)
        if result is not None:
            if result:
                self._trading_days_cache.add(d)
            return result
        
        # Нет в БД - вычисляем по базовой логике
        # сб=5, вс=6
        is_trading = d.weekday() < 5
        logger.debug(f"[CALENDAR] {d} ({['пн','вт','ср','чт','пт','сб','вс'][d.weekday()]}) - нет в кэше, вычисляем: {is_trading}")
        return is_trading
    
    def get_first_trading_day_from(self, d: date) -> date:
        """
        Найти первый торговый день от указанной даты (включая дату).
        
        Если d - торговый, возвращает d.
        Иначе ищет следующий торговый день.
        
        Args:
            d: Начальная дата
            
        Returns:
            Первый торговый день от d
        """
        self._ensure_loaded()
        
        current = d
        max_days = 10  # максимум 10 дней вперёд
        for _ in range(max_days):
            if self.is_trading_day(current):
                return current
            current += timedelta(days=1)
        
        # Если не нашли - возвращаем следующий понедельник
        days_to_monday = (7 - d.weekday()) % 7
        if days_to_monday == 0:
            days_to_monday = 7
        return d + timedelta(days=days_to_monday)
    
    def get_last_trading_day_before(self, d: date) -> date:
        """
        Найти последний торговый день до указанной даты (включая дату).
        
        Если d - торговый, возвращает d.
        Иначе ищет предыдущий торговый день.
        
        Args:
            d: Конечная дата
            
        Returns:
            Последний торговый день до d
        """
        self._ensure_loaded()
        
        current = d
        max_days = 10  # максимум 10 дней назад
        for _ in range(max_days):
            if self.is_trading_day(current):
                return current
            current -= timedelta(days=1)
        
        # Если не нашли - возвращаем предыдущую пятницу
        days_to_friday = (d.weekday() - 4) % 7
        if days_to_friday <= 0:
            days_to_friday += 7
        return d - timedelta(days=days_to_friday)
    
    def get_trading_days_in_range(self, start_date: date, end_date: date) -> Set[date]:
        """Получить торговые дни в диапазоне"""
        self._ensure_loaded()
        return self._repo.load_trading_days_in_range(start_date, end_date)
    
    def get_last_completed_trading_day(self, hour_threshold: int = 19) -> date:
        """
        Получить последний торговый день, для которого исторические данные уже доступны.
        
        MOEX обновляет исторические данные после закрытия рынка (~19:00 МСК).
        До этого времени данные за текущий торговый день могут отсутствовать.
        
        Args:
            hour_threshold: Час (МСК), после которого считаем данные за сегодня доступными
            
        Returns:
            Последний торговый день с доступными историческими данными
        """
        from datetime import datetime, timezone
        from zoneinfo import ZoneInfo
        
        self._ensure_loaded()
        
        # Текущее время МСК
        msk_tz = ZoneInfo('Europe/Moscow')
        now_msk = datetime.now(msk_tz)
        today = now_msk.date()
        current_hour = now_msk.hour
        
        # Если сегодня торговый день и ещё не поздно — данные за сегодня недоступны
        if self.is_trading_day(today) and current_hour < hour_threshold:
            # Возвращаем предыдущий торговый день
            return self.get_last_trading_day_before(today - timedelta(days=1))
        
        # Иначе возвращаем последний торговый день (включая сегодня)
        return self.get_last_trading_day_before(today)
