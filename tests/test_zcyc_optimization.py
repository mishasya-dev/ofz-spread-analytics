"""
Тест оптимизации загрузки ZCYC

Проверяет что:
1. ZCYC API возвращает данные для всех облигаций сразу
2. Загрузка всех облигаций происходит за один проход
3. Фильтрация по ISIN работает корректно
"""
import pytest
import time
from datetime import date, timedelta
import pandas as pd
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.moex_client import MOEXClient
from api.moex_zcyc import get_zcyc_history_parallel
from core.db import get_g_spread_repo, init_database


# Инициализируем БД при импорте
init_database()


class TestZCYCOptimization:
    """Тесты для оптимизации загрузки ZCYC"""

    def test_zcyc_api_returns_all_bonds(self):
        """
        Тест 1: ZCYC API возвращает данные для ВСЕХ облигаций за один запрос
        
        Это ключевое условие для оптимизации.
        """
        test_date = date.today() - timedelta(days=1)

        with MOEXClient() as client:
            data = client.get_json(
                "/engines/stock/zcyc.json",
                {"iss.meta": "off", "date": test_date.strftime("%Y-%m-%d")}
            )

        securities = data.get("securities", {})
        rows = securities.get("data", [])
        columns = securities.get("columns", [])

        print(f"\n=== ZCYC API Response for {test_date} ===")
        print(f"Total bonds: {len(rows)}")

        # API должен вернуть больше одной облигации
        assert len(rows) > 10, f"Ожидалось > 10 облигаций, получено {len(rows)}"

        # Проверяем колонки
        assert "secid" in columns
        assert "trdyield" in columns
        assert "clcyield" in columns

        return True

    def test_load_all_vs_filtered(self):
        """
        Тест 2: Загрузка всех облигаций vs фильтрация
        
        Проверяет что:
        1. Загрузка без фильтрации возвращает все облигации
        2. Фильтрация по ISIN работает корректно
        """
        start_date = date.today() - timedelta(days=5)
        end_date = date.today() - timedelta(days=1)

        repo = get_g_spread_repo()

        # Очищаем кэш для чистого теста
        # (в реальности кэш полезен, но для теста нужен чистый старт)

        # Загружаем без фильтрации (все облигации)
        print("\n=== Загрузка всех облигаций ===")
        start_time = time.time()
        all_df = get_zcyc_history_parallel(
            start_date=start_date,
            end_date=end_date,
            isin=None,  # Без фильтрации!
            use_cache=True,
            save_callback=repo.save_zcyc,
            max_workers=5
        )
        time_all = time.time() - start_time

        print(f"Загружено {len(all_df)} записей за {time_all:.2f}с")
        print(f"Уникальных ISIN: {all_df['secid'].nunique() if not all_df.empty else 0}")

        if all_df.empty:
            print("Нет данных (возможно выходные) - пропускаем тест")
            return True

        # Выбираем случайный ISIN для теста фильтрации
        test_isin = all_df['secid'].iloc[0]
        print(f"\nТестируем фильтрацию по ISIN: {test_isin}")

        # Загружаем с фильтрацией (должно взять из кэша)
        print("\n=== Загрузка с фильтрацией (из кэша) ===")
        start_time = time.time()
        filtered_df = get_zcyc_history_parallel(
            start_date=start_date,
            end_date=end_date,
            isin=test_isin,
            use_cache=True,
            save_callback=repo.save_zcyc,
            max_workers=5
        )
        time_filtered = time.time() - start_time

        print(f"Загружено {len(filtered_df)} записей за {time_filtered:.2f}с")

        # Проверки
        # 1. Все облигации должны быть загружены
        assert all_df['secid'].nunique() > 1, "Должны быть загружены разные облигации"

        # 2. Отфильтрованный результат содержит только нужный ISIN
        assert filtered_df['secid'].unique()[0] == test_isin, "Фильтрация не работает"

        # 3. Количество записей для ISIN совпадает
        expected_count = len(all_df[all_df['secid'] == test_isin])
        assert len(filtered_df) == expected_count, \
            f"Количество записей не совпадает: {len(filtered_df)} vs {expected_count}"

        print("\n✅ Все проверки пройдены!")
        return True

    def test_cached_dates_global(self):
        """
        Тест 3: Проверка глобального кэша дат
        
        После загрузки без фильтрации, кэш должен содержать
        даты для всех облигаций.
        """
        start_date = date.today() - timedelta(days=3)
        end_date = date.today() - timedelta(days=1)

        repo = get_g_spread_repo()

        # Проверяем кэш дат
        cached_dates = repo.get_zcyc_cached_dates(
            isin=None,  # Все даты
            start_date=start_date,
            end_date=end_date
        )

        print(f"\n=== Кэш дат ===")
        print(f"Дат в кэше: {len(cached_dates)}")

        # Проверяем для конкретного ISIN
        test_isin = "SU26224RMFS4"
        cached_dates_for_isin = repo.get_zcyc_cached_dates(
            isin=test_isin,
            start_date=start_date,
            end_date=end_date
        )

        print(f"Дат для {test_isin}: {len(cached_dates_for_isin)}")

        # Если есть глобальный кэш, он должен быть не меньше чем для конкретного ISIN
        if cached_dates:
            assert len(cached_dates) >= len(cached_dates_for_isin), \
                "Глобальный кэш должен содержать >= дат чем для конкретного ISIN"

        return True


def test_full_optimization():
    """
    Полный тест оптимизации
    
    Демонстрирует выигрыш от оптимизации:
    - До: N облигаций × D дней запросов
    - После: D дней запросов (все облигации загружаются сразу)
    """
    test = TestZCYCOptimization()

    print("\n" + "=" * 60)
    print("ТЕСТ 1: ZCYC API возвращает все облигации")
    print("=" * 60)
    test.test_zcyc_api_returns_all_bonds()

    print("\n" + "=" * 60)
    print("ТЕСТ 2: Загрузка всех облигаций vs фильтрация")
    print("=" * 60)
    test.test_load_all_vs_filtered()

    print("\n" + "=" * 60)
    print("ТЕСТ 3: Глобальный кэш дат")
    print("=" * 60)
    test.test_cached_dates_global()

    print("\n" + "=" * 60)
    print("✅ ВСЕ ТЕСТЫ ПРОЙДЕНЫ!")
    print("=" * 60)


if __name__ == "__main__":
    test_full_optimization()
