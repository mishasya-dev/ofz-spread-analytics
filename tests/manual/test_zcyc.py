#!/usr/bin/env python3
"""
Тесты для ZCYC (G-spread) функционала

Тестирует:
- get_zcyc_history_parallel() - исторические данные с кэшированием
- save_zcyc/load_zcyc - репозиторий БД
- save_empty_dates/load_empty_dates - кэш праздников
- calculate_g_spread_stats() - статистика
- generate_g_spread_signal() - торговые сигналы

DEPRECATED (удалено):
- get_zcyc_data_for_date() - заменён на get_zcyc_history_parallel()
- get_zcyc_history() - заменён на get_zcyc_history_parallel()
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import date, timedelta
import pandas as pd
import numpy as np

# Инициализация БД
from core.db.connection import init_database
init_database()

from core.db import get_g_spread_repo
from api.moex_zcyc import get_zcyc_history_parallel
from services.g_spread_calculator import calculate_g_spread_stats, generate_g_spread_signal


def test_zcyc_history_parallel():
    """Тест: параллельная загрузка истории с кэшированием"""
    print("\n=== Test: get_zcyc_history_parallel ===")
    
    isin = "SU26247RMFS5"
    start_date = date.today() - timedelta(days=30)
    end_date = date.today() - timedelta(days=1)
    
    repo = get_g_spread_repo()
    
    # Очищаем кэш для чистого теста
    # (в реальности не нужно, но для теста полезно)
    
    df = get_zcyc_history_parallel(
        start_date, end_date,
        isin=isin,
        save_callback=repo.save_zcyc,
        max_workers=5
    )
    
    if df.empty:
        print(f"  ⚠️ Нет данных для {isin}")
        return
    
    # Проверяем сортировку
    assert df['date'].is_monotonic_increasing, "Dates not sorted"
    
    # Проверяем фильтрацию по ISIN
    assert all(df['secid'] == isin), f"ISIN filter failed: {df['secid'].unique()}"
    
    print(f"  ✅ Загружено {len(df)} записей для {isin}")
    print(f"  ✅ Диапазон: {df['date'].min()} - {df['date'].max()}")


def test_zcyc_repository():
    """Тест: репозиторий ZCYC данных"""
    print("\n=== Test: ZCYC Repository ===")
    
    repo = get_g_spread_repo()
    
    # Статистика до
    count_before = repo.count_zcyc()
    print(f"  Записей в БД до: {count_before}")
    
    # Создаём тестовые данные
    test_data = pd.DataFrame({
        'date': [pd.Timestamp('2026-03-10'), pd.Timestamp('2026-03-11')],
        'secid': ['TEST_ISIN', 'TEST_ISIN'],
        'shortname': ['Test Bond', 'Test Bond'],
        'trdyield': [14.5, 14.6],
        'clcyield': [14.2, 14.3],
        'duration_days': [1825.0, 1826.0],
        'g_spread_bp': [30.0, 30.0]
    })
    
    # Сохраняем
    saved = repo.save_zcyc(test_data)
    print(f"  Сохранено: {saved} записей")
    assert saved == 2, f"Expected 2 saved, got {saved}"
    
    # Загружаем
    loaded = repo.load_zcyc(isin='TEST_ISIN')
    print(f"  Загружено: {len(loaded)} записей")
    assert len(loaded) == 2, f"Expected 2 loaded, got {len(loaded)}"
    
    # Проверяем даты
    cached_dates = repo.get_zcyc_cached_dates('TEST_ISIN')
    assert date(2026, 3, 10) in cached_dates
    assert date(2026, 3, 11) in cached_dates
    
    print(f"  ✅ Репозиторий работает корректно")


def test_empty_dates_cache():
    """Тест: кэш пустых дат (праздники)"""
    print("\n=== Test: Empty Dates Cache ===")
    
    repo = get_g_spread_repo()
    
    # Сохраняем тестовые пустые даты
    test_dates = [date(2026, 1, 1), date(2026, 1, 2), date(2026, 1, 7)]
    
    saved = repo.save_empty_dates(test_dates)
    print(f"  Сохранено пустых дат: {saved}")
    
    # Загружаем
    loaded = repo.load_empty_dates()
    print(f"  Загружено пустых дат: {len(loaded)}")
    
    for d in test_dates:
        assert d in loaded, f"Date {d} not found in empty dates"
    
    print(f"  ✅ Кэш пустых дат работает")


def test_g_spread_stats():
    """Тест: статистика G-spread"""
    print("\n=== Test: calculate_g_spread_stats ===")
    
    # Создаём тестовые данные
    np.random.seed(42)
    g_spreads = pd.Series(np.random.normal(50, 20, 100))
    
    stats = calculate_g_spread_stats(g_spreads)
    
    # Проверяем ключи
    expected_keys = {'mean', 'median', 'std', 'min', 'max', 'p10', 'p25', 'p75', 'p90', 'current', 'count'}
    assert expected_keys <= set(stats.keys()), f"Missing keys: {expected_keys - set(stats.keys())}"
    
    # Проверяем разумность значений
    assert stats['min'] <= stats['p10'] <= stats['p25'] <= stats['median']
    assert stats['median'] <= stats['p75'] <= stats['p90'] <= stats['max']
    assert stats['count'] == 100
    
    print(f"  ✅ Статистика: mean={stats['mean']:.1f}, std={stats['std']:.1f}")


def test_g_spread_signal():
    """Тест: генерация торговых сигналов"""
    print("\n=== Test: generate_g_spread_signal ===")
    
    # Тест BUY сигнала (спред ниже P25)
    signal = generate_g_spread_signal(
        current_spread=20,  # ниже P25
        p10=10, p25=30, p75=70, p90=90
    )
    assert signal['signal'] == 'BUY', f"Expected BUY, got {signal['signal']}"
    assert 'недооценена' in signal['action'].lower() or 'ПОКУПКА' in signal['action']
    print(f"  ✅ BUY сигнал: {signal['signal']}")
    
    # Тест SELL сигнала (спред выше P75)
    signal = generate_g_spread_signal(
        current_spread=80,  # выше P75
        p10=10, p25=30, p75=70, p90=90
    )
    assert signal['signal'] == 'SELL', f"Expected SELL, got {signal['signal']}"
    assert 'переоценена' in signal['action'].lower() or 'ПРОДАЖА' in signal['action']
    print(f"  ✅ SELL сигнал: {signal['signal']}")
    
    # Тест HOLD сигнала (спред в нормальном диапазоне)
    signal = generate_g_spread_signal(
        current_spread=50,  # между P25 и P75
        p10=10, p25=30, p75=70, p90=90
    )
    assert signal['signal'] == 'HOLD', f"Expected HOLD, got {signal['signal']}"
    print(f"  ✅ HOLD сигнал: {signal['signal']}")


def test_db_stats():
    """Вывод статистики БД"""
    print("\n=== DB Statistics ===")
    
    repo = get_g_spread_repo()
    stats = repo.get_stats()
    
    print(f"  NS params: {stats['ns_params_count']} записей")
    print(f"  G-spreads: {stats['g_spreads_count']} записей")
    print(f"  Empty dates: {repo.count_empty_dates()} записей")
    print(f"  ZCYC cache: {repo.count_zcyc()} записей")


def main():
    """Запуск всех тестов"""
    print("\n" + "="*60)
    print(" ZCYC (G-Spread) Tests")
    print("="*60)
    
    tests = [
        test_zcyc_history_parallel,
        test_zcyc_repository,
        test_empty_dates_cache,
        test_g_spread_stats,
        test_g_spread_signal,
        test_db_stats,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"  ❌ FAILED: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    
    print("\n" + "="*60)
    print(f" Results: {passed} passed, {failed} failed")
    print("="*60)
    
    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
