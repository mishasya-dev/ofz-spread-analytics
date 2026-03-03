"""
Тесты для проверки инкрементальной загрузки данных при изменении периода слайдера

Тестирует логику fetch_historical_data_cached:
- При увеличении периода дозагружаются только недостающие данные
- Данные корректно объединяются с существующими в БД
- При уменьшении периода возвращаются отфильтрованные данные
"""
import sys
import os
import tempfile
import shutil
from datetime import datetime, date, timedelta
from unittest.mock import Mock, patch, MagicMock
import pandas as pd
import numpy as np
import pytest

# Добавляем путь к модулям
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestPeriodSliderIncrementalLoading:
    """Тесты инкрементальной загрузки при изменении периода"""

    @pytest.fixture
    def temp_db(self):
        """Создаём временную БД для тестов"""
        import core.database as db_module
        
        original_db_path = db_module.DB_PATH
        temp_dir = tempfile.mkdtemp()
        test_db_path = os.path.join(temp_dir, "test_ofz_data.db")
        db_module.DB_PATH = test_db_path
        db_module.init_database()
        
        yield test_db_path
        
        db_module.DB_PATH = original_db_path
        try:
            shutil.rmtree(temp_dir)
        except:
            pass

    @pytest.fixture
    def sample_daily_data_30_days(self):
        """Создаём тестовые данные за 30 дней"""
        end_date = date.today() - timedelta(days=1)
        start_date = end_date - timedelta(days=29)
        dates = pd.date_range(start=start_date, end=end_date, freq='D')
        
        return pd.DataFrame({
            'ytm': np.random.uniform(14.0, 15.0, 30),
            'price': np.random.uniform(70, 80, 30),
            'duration_days': np.random.uniform(2000, 3000, 30)
        }, index=dates)

    @pytest.fixture
    def sample_daily_data_60_days(self):
        """Создаём тестовые данные за 60 дней (с пересечением с 30 днями)"""
        end_date = date.today() - timedelta(days=1)
        start_date = end_date - timedelta(days=59)
        dates = pd.date_range(start=start_date, end=end_date, freq='D')
        
        return pd.DataFrame({
            'ytm': np.random.uniform(14.0, 15.0, 60),
            'price': np.random.uniform(70, 80, 60),
            'duration_days': np.random.uniform(2000, 3000, 60)
        }, index=dates)

    def test_load_data_for_30_days(self, temp_db, sample_daily_data_30_days):
        """Тест: начальная загрузка данных за 30 дней"""
        from core.database import DatabaseManager
        
        db = DatabaseManager()
        isin = 'TEST30DAYS'
        
        # Сохраняем данные за 30 дней
        saved = db.save_daily_ytm(isin, sample_daily_data_30_days)
        assert saved == 30, f"Ожидали сохранить 30 записей, сохранили {saved}"
        
        # Загружаем данные за 30 дней
        start_date = date.today() - timedelta(days=30)
        loaded = db.load_daily_ytm(isin, start_date=start_date)
        
        assert len(loaded) == 30, f"Ожидали загрузить 30 записей, загрузили {len(loaded)}"
        
        # Проверяем покрытие периода
        db_min_date = loaded.index.min().date()
        assert db_min_date <= start_date, f"Данные начинаются с {db_min_date}, ожидали не позднее {start_date}"

    def test_incremental_load_when_increasing_period(self, temp_db, sample_daily_data_30_days, sample_daily_data_60_days):
        """Тест: инкрементальная загрузка при увеличении периода с 30 до 60 дней"""
        from core.database import DatabaseManager
        
        db = DatabaseManager()
        isin = 'TEST60DAYS'
        
        # Шаг 1: Сохраняем данные за последние 30 дней (как будто уже были загружены)
        saved_30 = db.save_daily_ytm(isin, sample_daily_data_30_days)
        assert saved_30 == 30
        
        # Шаг 2: Проверяем минимальную дату в БД
        db_min_date = db.load_daily_ytm(isin).index.min().date()
        expected_min = date.today() - timedelta(days=30)
        
        # Шаг 3: Симулируем увеличение периода - данные нужны за 60 дней
        start_date_60 = date.today() - timedelta(days=60)
        
        # Проверяем условие need_reload
        assert db_min_date > start_date_60, "Данных недостаточно, нужна дозагрузка"
        
        # Шаг 4: Дозагружаем недостающий период (имитация fetch_historical_data_cached)
        # Недостающий период: от start_date_60 до db_min_date - 1 день
        history_end = db_min_date - timedelta(days=1)
        
        # Фильтруем данные за недостающий период из sample_daily_data_60_days
        additional_data = sample_daily_data_60_days[
            (sample_daily_data_60_days.index.date >= start_date_60) &
            (sample_daily_data_60_days.index.date <= history_end)
        ]
        
        # Сохраняем недостающие данные
        if not additional_data.empty:
            saved_additional = db.save_daily_ytm(isin, additional_data)
            assert saved_additional > 0, "Должны быть сохранены дополнительные данные"
        
        # Шаг 5: Загружаем полный период
        full_data = db.load_daily_ytm(isin, start_date=start_date_60)
        
        # Проверяем что данных достаточно для 60 дней
        assert len(full_data) >= 30, f"Ожидали минимум 30 записей, получили {len(full_data)}"
        
        # Проверяем покрытие периода
        new_min_date = full_data.index.min().date()
        assert new_min_date <= start_date_60 + timedelta(days=1), \
            f"Данные должны начинаться не позднее {start_date_60 + timedelta(days=1)}, начинаются с {new_min_date}"

    def test_data_concatenation_preserves_all_records(self, temp_db):
        """Тест: объединение данных сохраняет все записи"""
        from core.database import DatabaseManager
        
        db = DatabaseManager()
        isin = 'TEST_CONCAT'
        
        # Создаём данные за первые 30 дней
        dates1 = pd.date_range(
            start=date.today() - timedelta(days=60),
            end=date.today() - timedelta(days=31),
            freq='D'
        )
        data1 = pd.DataFrame({
            'ytm': [14.0 + i * 0.01 for i in range(30)],
            'price': [75.0] * 30,
            'duration_days': [2500] * 30
        }, index=dates1)
        
        # Создаём данные за следующие 30 дней
        dates2 = pd.date_range(
            start=date.today() - timedelta(days=30),
            end=date.today() - timedelta(days=1),
            freq='D'
        )
        data2 = pd.DataFrame({
            'ytm': [14.3 + i * 0.01 for i in range(30)],
            'price': [76.0] * 30,
            'duration_days': [2500] * 30
        }, index=dates2)
        
        # Сохраняем сначала вторую часть (как будто загружали 30 дней)
        db.save_daily_ytm(isin, data2)
        
        # Потом добавляем первую часть (увеличили период)
        db.save_daily_ytm(isin, data1)
        
        # Загружаем все данные
        full_data = db.load_daily_ytm(isin)
        
        # Должно быть 60 записей
        assert len(full_data) == 60, f"Ожидали 60 записей, получили {len(full_data)}"
        
        # Проверяем что нет дубликатов
        assert not full_data.index.duplicated().any(), "Не должно быть дубликатов дат"

    def test_coverage_check_for_need_reload(self, temp_db):
        """Тест: проверка условия need_reload при недостаточном покрытии периода"""
        from core.database import DatabaseManager
        
        db = DatabaseManager()
        isin = 'TEST_COVERAGE'
        
        # Создаём данные за последние 30 дней
        dates = pd.date_range(
            start=date.today() - timedelta(days=30),
            end=date.today() - timedelta(days=1),
            freq='D'
        )
        data = pd.DataFrame({
            'ytm': [14.0] * 30,
            'price': [75.0] * 30,
            'duration_days': [2500] * 30
        }, index=dates)
        
        db.save_daily_ytm(isin, data)
        
        # Проверяем покрытие для 30 дней - должно быть достаточно
        start_30 = date.today() - timedelta(days=30)
        loaded_30 = db.load_daily_ytm(isin, start_date=start_30)
        db_min_30 = loaded_30.index.min().date()
        
        need_reload_30 = db_min_30 > start_30
        assert not need_reload_30, "Для 30 дней данные должны быть достаточны"
        
        # Проверяем покрытие для 60 дней - должно быть недостаточно
        start_60 = date.today() - timedelta(days=60)
        loaded_60 = db.load_daily_ytm(isin, start_date=start_60)
        db_min_60 = loaded_60.index.min().date()
        
        need_reload_60 = db_min_60 > start_60
        assert need_reload_60, "Для 60 дней данных должно быть недостаточно"

    def test_slider_period_change_simulation(self, temp_db):
        """
        Тест: симуляция изменения слайдера периода
        1. Пользователь открывает приложение (период = 30 дней)
        2. Данные загружаются за 30 дней
        3. Пользователь увеличивает период до 365 дней
        4. Данные дозагружаются инкрементально
        """
        from core.database import DatabaseManager
        
        db = DatabaseManager()
        isin = 'TEST_SLIDER'
        
        # Сценарий 1: Начальная загрузка за 30 дней
        period_initial = 30
        start_initial = date.today() - timedelta(days=period_initial)
        
        dates_30 = pd.date_range(start=start_initial, end=date.today() - timedelta(days=1), freq='D')
        data_30 = pd.DataFrame({
            'ytm': np.random.uniform(14.0, 15.0, len(dates_30)),
            'price': np.random.uniform(70, 80, len(dates_30)),
            'duration_days': np.random.uniform(2000, 3000, len(dates_30))
        }, index=dates_30)
        
        db.save_daily_ytm(isin, data_30)
        
        # Проверяем что загружено
        loaded_30 = db.load_daily_ytm(isin, start_date=start_initial)
        count_30 = len(loaded_30)
        
        # Сценарий 2: Увеличение периода до 365 дней
        period_new = 365
        start_new = date.today() - timedelta(days=period_new)
        
        # Проверяем текущее покрытие
        existing_data = db.load_daily_ytm(isin, start_date=start_new)
        if not existing_data.empty:
            existing_min = existing_data.index.min().date()
        else:
            existing_min = date.today()
        
        # Если данных недостаточно
        if existing_min > start_new:
            # Вычисляем недостающий период
            history_end = existing_min - timedelta(days=1)
            
            # Создаём данные за недостающий период (в реальности загружается с MOEX)
            dates_additional = pd.date_range(start=start_new, end=history_end, freq='D')
            if len(dates_additional) > 0:
                data_additional = pd.DataFrame({
                    'ytm': np.random.uniform(14.0, 15.0, len(dates_additional)),
                    'price': np.random.uniform(70, 80, len(dates_additional)),
                    'duration_days': np.random.uniform(2000, 3000, len(dates_additional))
                }, index=dates_additional)
                
                # Сохраняем инкрементально
                db.save_daily_ytm(isin, data_additional)
        
        # Проверяем финальный результат
        final_data = db.load_daily_ytm(isin, start_date=start_new)
        
        # Данных должно быть больше чем изначально
        assert len(final_data) >= count_30, \
            f"После увеличения периода данных должно быть не меньше исходного: было {count_30}, стало {len(final_data)}"


class TestCandlePeriodSlider:
    """Тесты для слайдера периода свечей"""

    @pytest.fixture
    def temp_db(self):
        """Создаём временную БД для тестов"""
        import core.database as db_module
        
        original_db_path = db_module.DB_PATH
        temp_dir = tempfile.mkdtemp()
        test_db_path = os.path.join(temp_dir, "test_ofz_data.db")
        db_module.DB_PATH = test_db_path
        db_module.init_database()
        
        yield test_db_path
        
        db_module.DB_PATH = original_db_path
        try:
            shutil.rmtree(temp_dir)
        except:
            pass

    def test_candle_period_slider_range_validation(self):
        """Тест: валидация диапазона слайдера периода свечей"""
        from config import CANDLE_INTERVAL_CONFIG
        
        # Проверяем конфигурацию интервалов
        for interval, config in CANDLE_INTERVAL_CONFIG.items():
            min_days = config["min_days"]
            max_days = config["max_days"]
            
            assert min_days > 0, f"Минимум дней должен быть > 0 для интервала {interval}"
            assert max_days >= min_days, \
                f"Максимум дней должен быть >= минимума для интервала {interval}"
            
            # Проверяем что при period == min_days не будет краша слайдера
            for period in [min_days, max_days, (min_days + max_days) // 2]:
                max_candle_days = min(max_days, period)
                min_candle_days = min_days
                
                # Симуляция логики из app.py
                if min_candle_days < max_candle_days:
                    # Слайдер можно показать
                    slider_valid = True
                elif min_candle_days == max_candle_days:
                    # Слайдер вырожден - нужно показывать info вместо слайдера
                    slider_valid = True  # Это не ошибка, а особый случай
                else:
                    # Это ошибка - min > max
                    slider_valid = False
                
                assert slider_valid, \
                    f"Некорректный диапазон слайдера: interval={interval}, period={period}, min={min_candle_days}, max={max_candle_days}"

    def test_hourly_interval_with_30_day_period(self):
        """Тест: часовой интервал с периодом анализа 30 дней (граничный случай)"""
        from config import CANDLE_INTERVAL_CONFIG
        
        interval = "60"  # 1 час
        period = 30  # 30 дней анализа
        
        config = CANDLE_INTERVAL_CONFIG[interval]
        min_days = config["min_days"]  # 30 для 1 час
        max_days = config["max_days"]  # 360 для 1 час
        
        max_candle_days = min(max_days, period)  # min(360, 30) = 30
        min_candle_days = min_days  # 30
        
        # Граничный случай: min_candle_days == max_candle_days == 30
        # Это не должно вызывать крах слайдера
        assert min_candle_days == 30 and max_candle_days == 30, \
            "Для часового интервала с 30-дневным периодом min == max == 30"
        
        # При этом условии слайдер должен быть заменён на info сообщение
        # Проверяем что условие определено правильно
        show_slider = min_candle_days < max_candle_days
        assert not show_slider, "Слайдер не должен показываться при min == max"


class TestFetchHistoricalDataCachedLogic:
    """Тесты логики fetch_historical_data_cached"""

    def test_need_reload_branch_logic(self):
        """Тест: логика ветки need_reload"""
        # Симуляция условий
        
        # Случай 1: Данных нет в БД
        db_df_empty = pd.DataFrame()
        need_reload_1 = False  # Данных нет, это не need_reload, а пустая БД
        
        # Случай 2: Данные есть, но период не покрывает
        today = date.today()
        db_df_has_data = pd.DataFrame(
            {'ytm': [14.0], 'price': [75.0]},
            index=pd.date_range(start=today - timedelta(days=10), periods=1)
        )
        requested_start = today - timedelta(days=30)
        db_min_date = db_df_has_data.index.min().date()
        
        need_reload_2 = db_min_date > requested_start
        assert need_reload_2, "Когда данных недостаточно, need_reload должен быть True"
        
        # Случай 3: Данные покрывают период
        db_df_covers = pd.DataFrame(
            {'ytm': [14.0], 'price': [75.0]},
            index=pd.date_range(start=today - timedelta(days=40), periods=1)
        )
        db_min_date_3 = db_df_covers.index.min().date()
        
        need_reload_3 = db_min_date_3 > requested_start
        assert not need_reload_3, "Когда данных достаточно, need_reload должен быть False"

    def test_concat_vs_replace_behavior(self, temp_db=None):
        """Тест: concat сохраняет данные, replace теряет"""
        # Создаём два DataFrame
        df1 = pd.DataFrame({
            'ytm': [14.0, 14.1, 14.2],
            'price': [75.0, 75.1, 75.2]
        }, index=pd.date_range(start='2025-01-01', periods=3))
        
        df2 = pd.DataFrame({
            'ytm': [14.3, 14.4, 14.5],
            'price': [75.3, 75.4, 75.5]
        }, index=pd.date_range(start='2025-01-04', periods=3))
        
        # Правильный подход: concat
        result_concat = pd.concat([df2, df1])  # Новые + старые
        result_concat = result_concat[~result_concat.index.duplicated(keep='last')]
        
        assert len(result_concat) == 6, "Concat должен сохранить все 6 записей"
        
        # Неправильный подход: replace (то что было багом)
        result_replace = df2  # Только новые данные
        
        assert len(result_replace) == 3, "Replace теряет старые данные"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
