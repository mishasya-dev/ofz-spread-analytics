#!/usr/bin/env python3
"""
Тестовый скрипт для проверки расчёта G-spread

1. Загружает параметры Nelson-Siegel с MOEX
2. Загружает YTM облигации из БД
3. Рассчитывает G-spread
4. Сохраняет результаты в БД
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import date, timedelta
import pandas as pd

# Инициализация БД (создаёт новые таблицы)
from core.db.connection import init_database
init_database()

# Репозитории
from core.db import get_ytm_repo, get_g_spread_repo

# API для загрузки NS параметров
from api.moex_zcyc import ZCYCFetcher

# Калькулятор G-spread
from services.g_spread_calculator import (
    nelson_siegel,
    calculate_g_spread_history,
    calculate_g_spread_stats,
    GSpreadCalculator
)


def test_nelson_siegel_formula():
    """Тест формулы Nelson-Siegel"""
    print("\n" + "="*60)
    print("ТЕСТ: Формула Nelson-Siegel")
    print("="*60)
    
    # Примерные параметры для текущей КБД
    b1 = 16.0   # Долгосрочный уровень
    b2 = -2.0   # Наклон (отрицательный = инвертированная кривая)
    b3 = 3.0    # Кривизна
    tau = 2.0   # Масштаб времени
    
    durations = [0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 30.0]
    
    print(f"\nПараметры: b1={b1}, b2={b2}, b3={b3}, tau={tau}")
    print("\nDuration (лет) | YTM КБД (%)")
    print("-" * 30)
    
    for t in durations:
        ytm = nelson_siegel(t, b1, b2, b3, tau)
        print(f"      {t:5.1f}     |   {ytm:.2f}")
    
    print("\n✅ Формула работает")


def test_fetch_ns_params():
    """Тест загрузки параметров NS с MOEX"""
    print("\n" + "="*60)
    print("ТЕСТ: Загрузка параметров Nelson-Siegel с MOEX")
    print("="*60)
    
    fetcher = ZCYCFetcher()
    
    # Загружаем последние 7 дней (для ускорения теста)
    start_date = date.today() - timedelta(days=7)
    
    print(f"Загружаем данные за период: {start_date} - {date.today()}")
    
    try:
        ns_df = fetcher.fetch_ns_params_history(start_date=start_date)
    except Exception as e:
        print(f"❌ Ошибка при загрузке: {e}")
        return None
    
    if ns_df.empty:
        print("❌ Не удалось загрузить параметры NS")
        return None
    
    print(f"\n✅ Загружено {len(ns_df)} записей")
    print(f"Период: {ns_df.index.min()} - {ns_df.index.max()}")
    
    print("\nПоследние 5 записей:")
    print(ns_df.tail(5).to_string())
    
    # Сохраняем в БД
    g_spread_repo = get_g_spread_repo()
    saved = g_spread_repo.save_ns_params(ns_df)
    print(f"\nСохранено в БД: {saved} записей")
    
    return ns_df


def test_calculate_g_spread(isin: str = "SU26221RMFS0"):
    """Тест расчёта G-spread для облигации"""
    print("\n" + "="*60)
    print(f"ТЕСТ: Расчёт G-spread для {isin}")
    print("="*60)
    
    ytm_repo = get_ytm_repo()
    g_spread_repo = get_g_spread_repo()
    
    # 1. Загружаем YTM облигации из БД
    ytm_df = ytm_repo.load_daily_ytm(isin)
    
    if ytm_df.empty:
        print(f"❌ Нет данных YTM для {isin}")
        return None
    
    print(f"\nЗагружено YTM: {len(ytm_df)} записей")
    print(f"Период: {ytm_df.index.min()} - {ytm_df.index.max()}")
    
    # 2. Загружаем параметры NS из БД
    ns_df = g_spread_repo.load_ns_params()
    
    if ns_df.empty:
        print("❌ Нет параметров NS в БД. Запустите test_fetch_ns_params()")
        return None
    
    print(f"Параметров NS: {len(ns_df)} записей")
    
    # 3. Рассчитываем G-spread
    g_spread_df = calculate_g_spread_history(ytm_df, ns_df)
    
    if g_spread_df.empty:
        print("❌ Не удалось рассчитать G-spread")
        return None
    
    print(f"\nРассчитано G-spread: {len(g_spread_df)} значений")
    
    # 4. Статистика
    stats = calculate_g_spread_stats(g_spread_df['g_spread_bp'])
    
    print("\nСтатистика G-spread:")
    print(f"  Среднее:    {stats['mean']:.1f} б.п.")
    print(f"  Медиана:    {stats['median']:.1f} б.п.")
    print(f"  Std:        {stats['std']:.1f} б.п.")
    print(f"  Min:        {stats['min']:.1f} б.п.")
    print(f"  Max:        {stats['max']:.1f} б.п.")
    print(f"  P25:        {stats['p25']:.1f} б.п.")
    print(f"  P75:        {stats['p75']:.1f} б.п.")
    print(f"  Текущий:    {stats['current']:.1f} б.п.")
    
    # 5. Последние значения
    print("\nПоследние 5 значений:")
    print(g_spread_df.tail(5).to_string())
    
    # 6. Сохраняем в БД
    saved = g_spread_repo.save_g_spreads(isin, g_spread_df)
    print(f"\nСохранено в БД: {saved} записей")
    
    return g_spread_df


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
    print("# ТЕСТИРОВАНИЕ G-SPREAD")
    print("#"*60)
    
    # 1. Тест формулы NS
    test_nelson_siegel_formula()
    
    # 2. Загрузка параметров NS
    test_fetch_ns_params()
    
    # 3. Расчёт G-spread
    test_calculate_g_spread("SU26221RMFS0")
    test_calculate_g_spread("SU26225RMFS1")
    
    # 4. Статистика БД
    test_db_stats()
    
    print("\n" + "#"*60)
    print("# ТЕСТИРОВАНИЕ ЗАВЕРШЕНО")
    print("#"*60)


if __name__ == "__main__":
    main()
