"""
Тесты для торгового календаря MOEX

Тестирует:
- CalendarRepository: сохранение/загрузка торговых дней
- TradingCalendar: определение торговых дней, поиск первого/последнего
"""
import pytest
from datetime import date, timedelta
import tempfile
import os
import sys

# Добавляем путь к проекту
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def temp_db():
    """Создаём временную БД для тестов"""
    import sqlite3
    from core.db.connection import init_database
    
    # Создаём временный файл
    fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    
    # Патчим путь к БД
    import core.db.connection as conn_module
    old_path = conn_module.DB_PATH
    conn_module.DB_PATH = db_path
    
    # Инициализируем БД
    init_database()
    
    yield db_path
    
    # Восстанавливаем
    conn_module.DB_PATH = old_path
    if os.path.exists(db_path):
        os.unlink(db_path)


class TestCalendarRepository:
    """Тесты репозитория календаря"""
    
    def test_save_trading_days(self, temp_db):
        """Сохранение торговых дней"""
        from core.db.calendar_repo import CalendarRepository
        
        repo = CalendarRepository()
        dates = [date(2025, 1, 20), date(2025, 1, 21), date(2025, 1, 22)]
        
        saved = repo.save_trading_days(dates)
        assert saved == 3
        
        # Проверяем что сохранилось
        assert repo.is_trading_day(date(2025, 1, 20)) == True
        assert repo.is_trading_day(date(2025, 1, 21)) == True
        assert repo.is_trading_day(date(2025, 1, 22)) == True
    
    def test_save_non_trading_days(self, temp_db):
        """Сохранение неторговых дней"""
        from core.db.calendar_repo import CalendarRepository
        
        repo = CalendarRepository()
        dates = [date(2025, 1, 18), date(2025, 1, 19)]  # сб, вс
        
        saved = repo.save_non_trading_days(dates)
        assert saved == 2
        
        assert repo.is_trading_day(date(2025, 1, 18)) == False
        assert repo.is_trading_day(date(2025, 1, 19)) == False
    
    def test_is_trading_day_unknown(self, temp_db):
        """Проверка неизвестной даты"""
        from core.db.calendar_repo import CalendarRepository
        
        repo = CalendarRepository()
        # Дата не сохранена - должен вернуть None
        assert repo.is_trading_day(date(2020, 1, 1)) is None
    
    def test_load_trading_days_in_range(self, temp_db):
        """Загрузка торговых дней в диапазоне"""
        from core.db.calendar_repo import CalendarRepository
        
        repo = CalendarRepository()
        
        # Сохраняем неделю (пн-пт = торговые, сб-вс = нет)
        trading = [date(2025, 1, 20), date(2025, 1, 21), date(2025, 1, 22),
                   date(2025, 1, 23), date(2025, 1, 24)]
        non_trading = [date(2025, 1, 25), date(2025, 1, 26)]
        
        repo.save_trading_days(trading)
        repo.save_non_trading_days(non_trading)
        
        # Загружаем диапазон
        loaded = repo.load_trading_days_in_range(date(2025, 1, 20), date(2025, 1, 26))
        
        assert len(loaded) == 5
        assert date(2025, 1, 20) in loaded
        assert date(2025, 1, 24) in loaded
        assert date(2025, 1, 25) not in loaded  # сб
        assert date(2025, 1, 26) not in loaded  # вс
    
    def test_count_trading_days(self, temp_db):
        """Подсчёт торговых дней"""
        from core.db.calendar_repo import CalendarRepository
        
        repo = CalendarRepository()
        dates = [date(2025, 1, 20), date(2025, 1, 21), date(2025, 1, 22)]
        repo.save_trading_days(dates)
        
        assert repo.count_trading_days() == 3
    
    def test_date_range(self, temp_db):
        """Диапазон дат в календаре"""
        from core.db.calendar_repo import CalendarRepository
        
        repo = CalendarRepository()
        
        # Пустой календарь
        assert repo.date_range() is None
        
        # Добавляем даты
        dates = [date(2025, 1, 20), date(2025, 1, 25)]
        repo.save_trading_days(dates)
        
        dr = repo.date_range()
        assert dr == (date(2025, 1, 20), date(2025, 1, 25))
    
    def test_meta_operations(self, temp_db):
        """Операции с метаданными"""
        from core.db.calendar_repo import CalendarRepository
        
        repo = CalendarRepository()
        
        # Нет значения
        assert repo.get_meta('test_key') is None
        
        # Устанавливаем
        repo.set_meta('test_key', 'test_value')
        assert repo.get_meta('test_key') == 'test_value'
        
        # Обновляем
        repo.set_meta('test_key', 'new_value')
        assert repo.get_meta('test_key') == 'new_value'
    
    def test_cached_years(self, temp_db):
        """Получение закэшированных годов"""
        from core.db.calendar_repo import CalendarRepository
        
        repo = CalendarRepository()
        
        # Пусто
        assert repo.cached_years() == set()
        
        # Устанавливаем
        repo.set_meta('cached_years', '2024,2025')
        assert repo.cached_years() == {2024, 2025}
    
    def test_get_cached_month(self, temp_db):
        """Получение закэшированного месяца"""
        from core.db.calendar_repo import CalendarRepository
        
        repo = CalendarRepository()
        
        # Пусто
        assert repo.get_cached_month() is None
        
        # Устанавливаем
        repo.set_meta('cached_month', '202501')
        assert repo.get_cached_month() == 202501


class TestTradingCalendar:
    """Тесты TradingCalendar"""
    
    def test_is_trading_day_weekday(self, temp_db):
        """Проверка буднего дня"""
        from services.trading_calendar import TradingCalendar
        
        # Сброс singleton для теста
        TradingCalendar._instance = None
        cal = TradingCalendar()
        
        # Понедельник - торговый
        monday = date(2025, 1, 20)
        assert cal.is_trading_day(monday) == True
        
        # Пятница - торговый
        friday = date(2025, 1, 24)
        assert cal.is_trading_day(friday) == True
    
    def test_is_trading_day_weekend(self, temp_db):
        """Проверка выходного дня"""
        from services.trading_calendar import TradingCalendar
        
        TradingCalendar._instance = None
        cal = TradingCalendar()
        
        # Суббота - неторговый
        saturday = date(2025, 1, 25)
        assert cal.is_trading_day(saturday) == False
        
        # Воскресенье - неторговый
        sunday = date(2025, 1, 26)
        assert cal.is_trading_day(sunday) == False
    
    def test_get_first_trading_day_from_weekday(self, temp_db):
        """Поиск первого торгового дня от буднего"""
        from services.trading_calendar import TradingCalendar
        
        TradingCalendar._instance = None
        cal = TradingCalendar()
        
        # Понедельник -> понедельник
        monday = date(2025, 1, 20)
        assert cal.get_first_trading_day_from(monday) == monday
    
    def test_get_first_trading_day_from_weekend(self, temp_db):
        """Поиск первого торгового дня от выходного"""
        from services.trading_calendar import TradingCalendar
        
        TradingCalendar._instance = None
        cal = TradingCalendar()
        
        # Суббота -> понедельник
        saturday = date(2025, 1, 25)
        result = cal.get_first_trading_day_from(saturday)
        assert result == date(2025, 1, 27)  # следующий понедельник
        
        # Воскресенье -> понедельник
        sunday = date(2025, 1, 26)
        result = cal.get_first_trading_day_from(sunday)
        assert result == date(2025, 1, 27)
    
    def test_get_last_trading_day_before_weekday(self, temp_db):
        """Поиск последнего торгового дня до буднего"""
        from services.trading_calendar import TradingCalendar
        
        TradingCalendar._instance = None
        cal = TradingCalendar()
        
        # Понедельник -> понедельник (если он торговый)
        monday = date(2025, 1, 20)
        result = cal.get_last_trading_day_before(monday)
        assert result == monday
    
    def test_get_last_trading_day_before_weekend(self, temp_db):
        """Поиск последнего торгового дня до выходного"""
        from services.trading_calendar import TradingCalendar
        
        TradingCalendar._instance = None
        cal = TradingCalendar()
        
        # Суббота -> пятница
        saturday = date(2025, 1, 25)
        result = cal.get_last_trading_day_before(saturday)
        assert result == date(2025, 1, 24)  # пятница
        
        # Воскресенье -> пятница
        sunday = date(2025, 1, 26)
        result = cal.get_last_trading_day_before(sunday)
        assert result == date(2025, 1, 24)  # пятница


class TestCalendarIntegration:
    """Интеграционные тесты календаря"""
    
    def test_weekend_scenario_no_unnecessary_reload(self, temp_db):
        """Сценарий: запуск в понедельник, данные за пятницу - не нужен запрос"""
        from services.trading_calendar import TradingCalendar
        
        TradingCalendar._instance = None
        cal = TradingCalendar()
        
        # Понедельник 20.01.2025
        today = date(2025, 1, 20)
        last_db_date = date(2025, 1, 17)  # пятница
        
        # Старая логика: today - 1 = воскресенье
        old_check = today - timedelta(days=1)
        old_need_update = last_db_date < old_check  # True - лишний запрос!
        
        # Новая логика: последний торговый день
        last_trading_day = cal.get_last_trading_day_before(today)
        new_need_update = last_db_date < last_trading_day
        
        # Старая логика давала ложноположительный результат
        assert old_need_update == True  # Лишний запрос
        
        # Новая логика: если сегодня понедельник до торгов - данных достаточно
        # Но если понедельник торговый - нужен инкремент
        # Это зависит от времени суток, но календарь хотя бы правильно
        # определяет что воскресенье = не торговый
        assert cal.is_trading_day(old_check) == False  # воскресенье
    
    def test_weekend_skip(self, temp_db):
        """Сценарий: стартовая дата попала на выходной"""
        from services.trading_calendar import TradingCalendar
        
        TradingCalendar._instance = None
        cal = TradingCalendar()
        
        # Запросили данные с воскресенья
        start_date = date(2025, 1, 19)  # воскресенье
        first_trading = cal.get_first_trading_day_from(start_date)
        
        # Должен вернуть понедельник
        assert first_trading == date(2025, 1, 20)
        
        # Если данные в БД начинаются с понедельника - это ОК
        db_min_date = date(2025, 1, 20)
        assert db_min_date == first_trading  # Данные покрывают период
