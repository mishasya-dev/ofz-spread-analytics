#!/usr/bin/env python3
"""
Тестовый скрипт для проверки расчёта G-spread

НОВАЯ ВЕРСИЯ: использует MOEX ZCYC API напрямую
- get_zcyc_data_for_date() - точные G-spread за дату
- get_zcyc_history() - исторические G-spread

DEPRECATED тесты закомментированы ниже.
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

# Репозитории
from core.db import get_ytm_repo, get_g_spread_repo

# API для загрузки ZCYC данных
from api.moex_zcyc import ZCYCFetcher, get_zcyc_data_for_date, get_zcyc_history

# Активные функции
from services.g_spread_calculator import (
    calculate_g_spread_stats,
    generate_g_spread_signal,
)


def test_zcyc_api():
    """Тест загрузки ZCYC данных (clcyield, trdyield, G-spread)"""
    print("\n" + "="*60)
    print("ТЕСТ: Загрузка ZCYC данных с MOEX")
    print("="*60)
    
    test_date = date.today() - timedelta(days=1)
    
    print(f"\nЗагружаем ZCYC на {test_date}...")
    
    try:
        df = get_zcyc_data_for_date(test_date)
        
        if df.empty:
            print(f"❌ Нет данных на {test_date}")
        else:
            print(f"\n✅ Загружено {len(df)} облигаций")
            print("\nКолонки:", list(df.columns))
            print("\nПервые 5 записей:")
            print(df.head().to_string())
            
            # Статистика G-spread
            stats = calculate_g_spread_stats(df['g_spread_bp'])
            print(f"\nСтатистика G-spread на {test_date}:")
            print(f"  Среднее:    {stats['mean']:.1f} б.п.")
            print(f"  Медиана:    {stats['median']:.1f} б.п.")
            print(f"  Min:        {stats['min']:.1f} б.п.")
            print(f"  Max:        {stats['max']:.1f} б.п.")
            
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()


def test_zcyc_history():
    """Тест загрузки истории ZCYC для конкретной облигации"""
    print("\n" + "="*60)
    print("ТЕСТ: Загрузка истории ZCYC")
    print("="*60)
    
    isin = "SU26247RMFS5"  # Пример облигации
    start_date = date.today() - timedelta(days=30)
    
    print(f"\nЗагружаем ZCYC для {isin} за {start_date} - {date.today()}...")
    
    try:
        df = get_zcyc_history(start_date, isin=isin)
        
        if df.empty:
            print(f"❌ Нет данных для {isin}")
        else:
            print(f"\n✅ Загружено {len(df)} записей")
            print(f"Диапазон: {df['date'].min()} - {df['date'].max()}")
            
            print("\nПоследние 5 записей:")
            print(df.tail().to_string())
            
            # Статистика
            stats = calculate_g_spread_stats(df['g_spread_bp'])
            current = stats['current']
            
            print(f"\nСтатистика G-spread:")
            print(f"  Текущий:    {current:.1f} б.п.")
            print(f"  Среднее:    {stats['mean']:.1f} б.п.")
            print(f"  Std:        {stats['std']:.1f} б.п.")
            
            # Торговый сигнал
            signal = generate_g_spread_signal(
                current,
                stats['p10'],
                stats['p25'],
                stats['p75'],
                stats['p90']
            )
            print(f"\nСигнал: {signal['signal']}")
            print(f"Действие: {signal['action']}")
            
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()


def test_db_stats():
    """Проверка статистики БД"""
    print("\n" + "="*60)
    print("СТАТИСТИКА БД")
    print("="*60)
    
    g_spread_repo = get_g_spread_repo()
    stats = g_spread_repo.get_stats()
    
    print(f"\nПараметры NS: {stats['ns_params_count']} записей")
    print(f"Диапазон дат: {stats['ns_params_date_range']}")
    print(f"\nG-spreads всего: {stats['g_spreads_count']} записей")
    
    if stats['g_spreads_by_isin']:
        print("По облигациям:")
        for isin, cnt in stats['g_spreads_by_isin'].items():
            print(f"  {isin}: {cnt}")


def main():
    """Главная функция"""
    print("\n" + "#"*60)
    print("# ТЕСТИРОВАНИЕ G-SPREAD (ZCYC API)")
    print("#"*60)
    
    # 1. Тест ZCYC API
    test_zcyc_api()
    
    # 2. Тест истории ZCYC
    test_zcyc_history()
    
    # 3. Статистика БД
    test_db_stats()
    
    print("\n" + "#"*60)
    print("# ТЕСТИРОВАНИЕ ЗАВЕРШЕНО")
    print("#"*60)


if __name__ == "__main__":
    main()


# ============================================================================
# DEPRECATED ТЕСТЫ (ниже закомментированы)
# ============================================================================
# 
# Эти тесты используют deprecated функции:
# - nelson_siegel() - даёт ~90-100 bp ошибку
# - interpolate_kbd() - заменено на clcyield от MOEX
# - enrich_bond_data_with_yearyields() - заменено на get_zcyc_history()
# 
# def test_nelson_siegel_formula():
#     """DEPRECATED: Формула Nelson-Siegel неточна"""
#     pass
# 
# def test_interpolate_kbd():
#     """DEPRECATED: Интерполяция неточна, используйте clcyield"""
#     pass
# 
# def test_yearyields_api():
#     """DEPRECATED: Используйте get_zcyc_data_for_date()"""
#     pass
# 
# def test_calculate_g_spread():
#     """DEPRECATED: Используйте get_zcyc_history()"""
#     pass
# 
# def test_g_spread_with_yearyields():
#     """DEPRECATED: Используйте get_zcyc_history()"""
#     pass
