#!/usr/bin/env python3
"""
Тестовый скрипт для проверки расчёта G-spread

1. Загружает параметры Nelson-Siegel с MOEX
2. Загружает YTM облигации из БД
3. Рассчитывает G-spread
4. Сохраняет результаты в БД
5. Тестирует yearyields интерполяцию
6. Тестирует window параметр для Z-score
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import date, timedelta
import pandas as pd
import numpy as np

# Инициализация БД (создаёт новые таблицы)
from core.db.connection import init_database
init_database()

# Репозитории
from core.db import get_ytm_repo, get_g_spread_repo

# API для загрузки NS параметров и yearyields
from api.moex_zcyc import ZCYCFetcher, get_yearyields_for_date, get_yearyields_history

# Калькулятор G-spread
from services.g_spread_calculator import (
    nelson_siegel,
    calculate_g_spread_history,
    calculate_g_spread_stats,
    interpolate_kbd,
    enrich_bond_data_with_yearyields,
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


def test_interpolate_kbd():
    """Тест интерполяции КБД по yearyields"""
    print("\n" + "="*60)
    print("ТЕСТ: Интерполяция КБД по yearyields")
    print("="*60)
    
    # Пример yearyields (типичные значения)
    periods = [0.25, 0.5, 0.75, 1.0, 2.0, 3.0, 5.0, 7.0, 10.0, 15.0, 20.0]
    values = [15.5, 15.8, 16.0, 16.2, 16.5, 16.7, 17.0, 17.2, 17.5, 17.8, 18.0]
    
    print(f"\nИсходные точки yearyields:")
    for p, v in zip(periods, values):
        print(f"  {p:5.2f} лет -> {v:.2f}%")
    
    # Тест интерполяции
    test_maturities = [0.5, 1.5, 4.0, 8.0, 12.0, 18.0]
    
    print(f"\nИнтерполяция для разных сроков:")
    for mat in test_maturities:
        ytm_kbd = interpolate_kbd(mat, periods, values)
        print(f"  {mat:5.2f} лет -> {ytm_kbd:.2f}%")
    
    # Тест экстраполяции за границы
    print(f"\nЭкстраполяция за границы:")
    for mat in [0.1, 25.0, 30.0]:
        ytm_kbd = interpolate_kbd(mat, periods, values)
        print(f"  {mat:5.2f} лет -> {ytm_kbd:.2f}%")
    
    print("\n✅ Интерполяция работает")


def test_yearyields_api():
    """Тест загрузки yearyields с MOEX G-Curve API"""
    print("\n" + "="*60)
    print("ТЕСТ: Загрузка yearyields с MOEX G-Curve API")
    print("="*60)
    
    # Тест загрузки за текущую дату
    test_date = date.today() - timedelta(days=1)
    
    print(f"\nЗагружаем yearyields на {test_date}...")
    
    try:
        yy_df = get_yearyields_for_date(test_date)
        
        if yy_df.empty:
            print(f"❌ Нет данных на {test_date}")
        else:
            print(f"\n✅ Загружено {len(yy_df)} точек yearyields")
            print("\nТочки КБД:")
            print(yy_df.to_string())
            
            # Сохраняем в БД
            g_spread_repo = get_g_spread_repo()
            saved = g_spread_repo.save_yearyields(yy_df)
            print(f"\nСохранено в БД: {saved} записей")
            
    except Exception as e:
        print(f"❌ Ошибка: {e}")
    
    # Тест загрузки истории
    print(f"\nЗагружаем историю yearyields за последние 7 дней...")
    
    try:
        start_date = date.today() - timedelta(days=7)
        yy_history = get_yearyields_history(start_date, date.today())
        
        if yy_history.empty:
            print("❌ Не удалось загрузить историю")
        else:
            print(f"\n✅ Загружено {len(yy_history)} записей")
            unique_dates = yy_history['date'].nunique()
            print(f"Уникальных дат: {unique_dates}")
            print(f"Диапазон: {yy_history['date'].min()} - {yy_history['date'].max()}")
            
    except Exception as e:
        print(f"❌ Ошибка: {e}")


def test_window_parameter():
    """Тест влияния window на Z-score"""
    print("\n" + "="*60)
    print("ТЕСТ: Влияние параметра window на Z-score")
    print("="*60)
    
    # Создаём синтетические данные G-spread
    np.random.seed(42)
    n = 100
    dates = pd.date_range(end=date.today(), periods=n, freq='D')
    
    # G-spread с трендом и шумом
    trend = np.linspace(50, 80, n)  # Растущий тренд
    noise = np.random.normal(0, 10, n)  # Шум
    g_spread = trend + noise
    
    df = pd.DataFrame({
        'date': dates,
        'ytm': 16.0 + g_spread / 100,  # YTM в процентах
        'maturity_years': 5.0
    })
    
    # Создаём yearyields
    periods = [0.25, 0.5, 0.75, 1.0, 2.0, 3.0, 5.0, 7.0, 10.0, 15.0, 20.0]
    values = [15.0] * 11
    
    yy_rows = []
    for d in dates:
        for p, v in zip(periods, values):
            yy_rows.append({'date': d, 'period': p, 'value': v})
    
    yy_df = pd.DataFrame(yy_rows)
    
    # Тестируем разные window
    windows = [10, 20, 30, 60]
    
    print(f"\nСравнение Z-score для разных window:")
    print(f"{'Window':<10} {'Z-score last':<15} {'Mean':<15} {'Std':<15}")
    print("-" * 55)
    
    for window in windows:
        result_df, _ = enrich_bond_data_with_yearyields(df, yy_df, window=window)
        
        if not result_df.empty:
            last_z = result_df['z_score'].iloc[-1]
            mean_z = result_df['z_score'].mean()
            std_z = result_df['z_score'].std()
            print(f"{window:<10} {last_z:<15.2f} {mean_z:<15.2f} {std_z:<15.2f}")
    
    print("\n✅ Параметр window влияет на Z-score")


def test_g_spread_with_yearyields(isin: str = "SU26221RMFS0"):
    """Тест расчёта G-spread с yearyields интерполяцией"""
    print("\n" + "="*60)
    print(f"ТЕСТ: G-spread с yearyields для {isin}")
    print("="*60)
    
    ytm_repo = get_ytm_repo()
    g_spread_repo = get_g_spread_repo()
    
    # 1. Загружаем YTM облигации
    ytm_df = ytm_repo.load_daily_ytm(isin)
    
    if ytm_df.empty:
        print(f"❌ Нет данных YTM для {isin}")
        return
    
    print(f"\nYTM данных: {len(ytm_df)} записей")
    
    # 2. Загружаем yearyields
    yy_df = g_spread_repo.load_yearyields()
    
    if yy_df.empty:
        print("Yearyields нет в БД, загружаем с MOEX...")
        start_date = date.today() - timedelta(days=365)
        yy_df = get_yearyields_history(start_date, date.today())
        if not yy_df.empty:
            g_spread_repo.save_yearyields(yy_df)
    
    if yy_df.empty:
        print("❌ Не удалось загрузить yearyields")
        return
    
    print(f"Yearyields: {len(yy_df)} записей")
    
    # 3. Подготавливаем данные
    bond_data = ytm_df.reset_index()
    if 'index' in bond_data.columns:
        bond_data = bond_data.rename(columns={'index': 'date'})
    
    # Добавляем maturity_date (пример для OFZ 26221)
    if 'SU26221' in isin:
        maturity = date(2031, 5, 15)
    elif 'SU26225' in isin:
        maturity = date(2034, 5, 23)
    else:
        maturity = date.today() + timedelta(days=5*365)  # 5 лет по умолчанию
    
    bond_data['maturity_date'] = pd.to_datetime(maturity)
    
    # 4. Рассчитываем G-spread с разными window
    windows = [15, 30, 60]
    
    print(f"\nСравнение G-spread для разных window:")
    
    for window in windows:
        result_df, p_value = enrich_bond_data_with_yearyields(bond_data, yy_df, window=window)
        
        if not result_df.empty:
            stats = calculate_g_spread_stats(result_df['g_spread_bp'])
            last_z = result_df['z_score'].iloc[-1]
            
            print(f"\n--- Window = {window} дней ---")
            print(f"  G-spread текущий: {stats['current']:.1f} б.п.")
            print(f"  G-spread средний: {stats['mean']:.1f} б.п.")
            print(f"  Z-score последний: {last_z:.2f}")
            print(f"  ADF p-value: {p_value:.4f}")


def main():
    """Главная функция"""
    print("\n" + "#"*60)
    print("# ТЕСТИРОВАНИЕ G-SPREAD")
    print("#"*60)
    
    # 1. Тест формулы NS
    test_nelson_siegel_formula()
    
    # 2. Тест интерполяции КБД
    test_interpolate_kbd()
    
    # 3. Загрузка yearyields
    test_yearyields_api()
    
    # 4. Тест window параметра
    test_window_parameter()
    
    # 5. Загрузка параметров NS
    test_fetch_ns_params()
    
    # 6. Расчёт G-spread (старый метод)
    test_calculate_g_spread("SU26221RMFS0")
    
    # 7. Расчёт G-spread с yearyields (новый метод)
    test_g_spread_with_yearyields("SU26221RMFS0")
    
    # 8. Статистика БД
    test_db_stats()
    
    print("\n" + "#"*60)
    print("# ТЕСТИРОВАНИЕ ЗАВЕРШЕНО")
    print("#"*60)


if __name__ == "__main__":
    main()
