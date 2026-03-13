"""
Запуск всех тестов для OFZ Spread Analytics
Вывод: "ожидаем - получили"
"""
import sys
import os
import time
from datetime import date, datetime, timedelta
import pandas as pd
import numpy as np

# Добавляем путь к модулям
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Цвета для вывода
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'

def print_header(text):
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{text}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.END}\n")

def print_test(name, expected, actual, passed):
    status = f"{Colors.GREEN}✅ PASS{Colors.END}" if passed else f"{Colors.RED}❌ FAIL{Colors.END}"
    print(f"{status} {name}")
    print(f"   Ожидали:  {expected}")
    print(f"   Получили: {actual}")
    if not passed:
        print(f"   {Colors.YELLOW}Разница: нужно исправить{Colors.END}")
    print()

def print_section(name):
    print(f"\n{Colors.BOLD}--- {name} ---{Colors.END}\n")

# Результаты тестов
test_results = []

def run_test(name, expected, actual, condition=None):
    """Запуск одного теста"""
    if condition is None:
        passed = expected == actual
    else:
        passed = condition
    
    print_test(name, expected, actual, passed)
    test_results.append((name, passed))
    return passed


# ============================================
# ТЕСТЫ YTM CALCULATOR
# ============================================
def test_ytm_calculator():
    print_section("YTM Calculator")
    
    from core.ytm_calculator import YTMCalculator, BondParams, calculate_simple_ytm
    
    calc = YTMCalculator()
    
    # Тест 1: Создание параметров облигации
    bond = BondParams(
        isin="TEST123",
        name="Тестовая облигация",
        face_value=1000,
        coupon_rate=10.0,
        coupon_frequency=2,
        maturity_date=date(2030, 6, 15)
    )
    
    run_test(
        "Создание BondParams",
        "TEST123",
        bond.isin,
        bond.isin == "TEST123"
    )
    
    # Тест 2: Упрощённый расчёт YTM (цена = номинал)
    ytm_simple = calculate_simple_ytm(
        price_percent=100.0,
        coupon_rate=10.0,
        years_to_maturity=5.0
    )
    
    run_test(
        "Упрощённый YTM (цена=номинал) ≈ 10%",
        "~10%",
        f"{ytm_simple:.2f}%",
        abs(ytm_simple - 10.0) < 0.5
    )
    
    # Тест 3: Упрощённый расчёт YTM (цена < номинала)
    ytm_discount = calculate_simple_ytm(
        price_percent=90.0,
        coupon_rate=10.0,
        years_to_maturity=5.0
    )
    
    run_test(
        "YTM при дисконте (цена=90%) > купона",
        "> 10%",
        f"{ytm_discount:.2f}%",
        ytm_discount > 10.0
    )
    
    # Тест 4: Упрощённый расчёт YTM (цена > номинала)
    ytm_premium = calculate_simple_ytm(
        price_percent=110.0,
        coupon_rate=10.0,
        years_to_maturity=5.0
    )
    
    run_test(
        "YTM при премии (цена=110%) < купона",
        "< 10%",
        f"{ytm_premium:.2f}%",
        ytm_premium < 10.0
    )
    
    # Тест 5: Полный расчёт YTM методом Ньютона-Рафсона
    ytm_full = calc.calculate_ytm(
        price_percent=95.0,
        bond_params=bond,
        settlement_date=date(2025, 1, 1),
        accrued_interest=25.0
    )
    
    run_test(
        "Полный расчёт YTM (Ньютон-Рафсон)",
        "число > 0",
        f"{ytm_full}%" if ytm_full else "None",
        ytm_full is not None and ytm_full > 0
    )
    
    # Тест 6: Расчёт цены из YTM (учитываем НКД = dirty price)
    if ytm_full:
        price_back = calc.calculate_price_from_ytm(
            ytm=ytm_full,
            bond_params=bond,
            settlement_date=date(2025, 1, 1)
        )
        
        # dirty_price = clean_price + accrued_interest
        # clean_price = 95%, accrued = 25 руб = 2.5% от номинала
        # dirty_price ≈ 97.5%
        run_test(
            "Обратный расчёт цены из YTM (dirty price)",
            "~97.5% (±1%)",
            f"{price_back:.2f}%" if price_back else "None",
            price_back is not None and abs(price_back - 97.5) < 1.0
        )
    
    # Тест 7: Дюрация
    duration = calc.calculate_duration(
        ytm=10.0,
        bond_params=bond,
        settlement_date=date(2025, 1, 1)
    )
    
    run_test(
        "Расчёт дюрации",
        "число > 0",
        f"{duration:.2f} лет" if duration else "None",
        duration is not None and duration > 0
    )
    
    # Тест 8: Модифицированная дюрация
    mod_duration = calc.calculate_modified_duration(
        ytm=10.0,
        bond_params=bond,
        settlement_date=date(2025, 1, 1)
    )
    
    run_test(
        "Модифицированная дюрация < дюрации",
        f"< {duration:.2f}" if duration else "N/A",
        f"{mod_duration:.2f}" if mod_duration else "None",
        mod_duration is not None and (duration is None or mod_duration < duration)
    )


# ============================================
# ТЕСТЫ MOEX CANDLES
# ============================================
def test_moex_candles():
    print_section("MOEX Candles API")
    
    from api.moex_candles import CandleInterval, fetch_candles
    from api.moex_client import MOEXClient
    from config import AppConfig
    
    config = AppConfig()
    
    # Берём первую облигацию
    bond = list(config.bonds.values())[0]
    
    with MOEXClient() as client:
        # Тест 1: Получение 1-минутных свечей
        df_1min = fetch_candles(
            bond.isin,
            interval=CandleInterval.MIN_1,
            start_date=date.today() - timedelta(days=1),
            end_date=date.today(),
            client=client
        )
        
        run_test(
            "Получение 1-минутных свечей",
            "> 0 свечей",
            f"{len(df_1min)} свечей",
            len(df_1min) > 0
        )
        
        # Тест 2: Получение 10-минутных свечей
        df_10min = fetch_candles(
            bond.isin,
            interval=CandleInterval.MIN_10,
            start_date=date.today() - timedelta(days=3),
            end_date=date.today(),
            client=client
        )
        
        run_test(
            "Получение 10-минутных свечей",
            "> 0 свечей",
            f"{len(df_10min)} свечей",
            len(df_10min) > 0
        )
        
        # Тест 3: Получение часовых свечей
        df_60min = fetch_candles(
            bond.isin,
            interval=CandleInterval.MIN_60,
            start_date=date.today() - timedelta(days=7),
            end_date=date.today(),
            client=client
        )
        
        run_test(
            "Получение часовых свечей",
            "> 0 свечей",
            f"{len(df_60min)} свечей",
            len(df_60min) > 0
        )
    
    # Тест 4: Наличие колонок OHLCV
    has_ohlcv = all(col in df_60min.columns for col in ['open', 'high', 'low', 'close', 'volume']) if not df_60min.empty else False
    
    run_test(
        "Наличие колонок OHLCV",
        "True",
        str(has_ohlcv),
        has_ohlcv
    )
    
    # Тест 5: Валидные значения close
    if not df_60min.empty and 'close' in df_60min.columns:
        valid_close = df_60min['close'].notna().sum()
        total = len(df_60min)
        
        run_test(
            "Валидные close значения",
            f"> 50% от {total}",
            f"{valid_close}/{total} ({100*valid_close/total:.1f}%)",
            valid_close > total * 0.5
        )
    
    # Тест 6: Диапазон цен
    if not df_60min.empty and 'close' in df_60min.columns:
        close_min = df_60min['close'].min()
        close_max = df_60min['close'].max()
        
        run_test(
            "Цены в разумном диапазоне (50% - 150% от номинала)",
            "50 < price < 150",
            f"{close_min:.2f}% - {close_max:.2f}%",
            close_min > 50 and close_max < 150
        )


# ============================================
# ТЕСТЫ MOEX HISTORY
# ============================================
def test_moex_history():
    print_section("MOEX History API")
    
    from api.moex_history import fetch_ytm_history, get_trading_data
    from api.moex_client import MOEXClient
    from config import AppConfig
    
    config = AppConfig()
    
    bond = list(config.bonds.values())[0]
    
    with MOEXClient() as client:
        # Тест 1: Получение исторических данных
        df = fetch_ytm_history(
            bond.isin,
            start_date=date.today() - timedelta(days=30),
            client=client
        )
        
        run_test(
            "Получение исторических данных (30 дней)",
            "> 0 записей",
            f"{len(df)} записей",
            len(df) > 0
        )
        
        # Тест 2: Наличие колонки YTM
        has_ytm = 'ytm' in df.columns if not df.empty else False
        
        run_test(
            "Наличие колонки ytm",
            "True",
            str(has_ytm),
            has_ytm
        )
        
        # Тест 3: Торговые данные
        trading_data = get_trading_data(bond.isin, client=client)
        
        run_test(
            "Получение торговых данных",
            "has_data = True или yield есть",
            f"has_data = {trading_data.get('has_data', False)}",
            trading_data.get('has_data', False) or 'yield' in trading_data
        )
    
    # Тест 4: Дата последней сделки
    if not df.empty:
        last_date = df.index[-1]
        days_old = (date.today() - last_date.date()).days
        
        run_test(
            "Свежесть данных",
            "<= 7 дней",
            f"{days_old} дней",
            days_old <= 7
        )


# ============================================
# ТЕСТЫ SPREAD CALCULATOR
# ============================================
def test_spread_calculator():
    print_section("Spread Calculator")
    
    from core.spread import SpreadCalculator, get_spread, get_spread_stats
    
    calc = SpreadCalculator()
    
    # Тест 1: Расчёт спреда между двумя YTM
    spread = calc.calculate_spread(10.5, 10.0)
    
    run_test(
        "Расчёт спреда (10.5% - 10.0%) × 100",
        "50.0 б.п.",
        f"{spread} б.п.",
        spread == 50.0
    )
    
    # Тест 2: Расчёт серии спредов
    dates = pd.date_range(start='2025-01-01', periods=100, freq='D')
    ytm1 = pd.Series(10 + np.random.randn(100).cumsum() * 0.1, index=dates)
    ytm2 = pd.Series(9.5 + np.random.randn(100).cumsum() * 0.1, index=dates)
    
    spread_series = calc.calculate_spread_series(ytm1, ytm2)
    
    run_test(
        "Расчёт серии спредов",
        "100 значений",
        f"{len(spread_series)} значений",
        len(spread_series) == 100
    )
    
    # Тест 3: Статистика спреда
    stats = calc.calculate_spread_stats(spread_series)
    
    run_test(
        "Расчёт статистики спреда (mean)",
        "число",
        f"{stats.mean:.2f} б.п.",
        not np.isnan(stats.mean)
    )
    
    # Тест 4: Перцентили P25 < P75
    run_test(
        "P25 < P75",
        "True",
        f"P25={stats.percentile_25:.2f} < P75={stats.percentile_75:.2f}",
        stats.percentile_25 < stats.percentile_75
    )
    
    # Тест 5: Удобная функция get_spread
    spread_quick = get_spread(10.0, 9.5)
    
    run_test(
        "get_spread(10.0, 9.5)",
        "50.0 б.п.",
        f"{spread_quick} б.п.",
        spread_quick == 50.0
    )
    
    # Тест 6: Z-score
    run_test(
        "Z-score рассчитан",
        "число",
        f"{stats.zscore:.2f}",
        not np.isnan(stats.zscore)
    )


# ============================================
# ТЕСТЫ SIGNAL GENERATOR
# ============================================
def test_signal_generator():
    print_section("Signal Generator")
    
    from core.signals import SignalGenerator, SignalType, SignalDirection
    
    gen = SignalGenerator()
    
    # Создаём тестовые данные спредов
    np.random.seed(42)
    dates = pd.date_range(start='2025-01-01', periods=100, freq='D')
    spreads = pd.Series(np.random.normal(0, 5, 100), index=dates)  # средний спред 0, стд 5 б.п.
    
    # Тест 1: Генерация сигнала
    signal = gen.generate_signal(
        spread_series=spreads,
        bond_long="BOND1",
        bond_short="BOND2"
    )
    
    run_test(
        "Генерация сигнала",
        "TradingSignal",
        f"{type(signal).__name__}",
        type(signal).__name__ == 'TradingSignal'
    )
    
    # Тест 2: Тип сигнала в допустимых значениях
    valid_types = [SignalType.STRONG_BUY, SignalType.BUY, SignalType.NEUTRAL, 
                   SignalType.SELL, SignalType.STRONG_SELL, SignalType.NO_DATA]
    
    run_test(
        "Тип сигнала валиден",
        "один из SignalType",
        f"{signal.signal_type.name}",
        signal.signal_type in valid_types
    )
    
    # Тест 3: Направление валидно
    valid_dirs = [SignalDirection.LONG_SHORT, SignalDirection.SHORT_LONG, SignalDirection.FLAT]
    
    run_test(
        "Направление сигнала валидно",
        "один из SignalDirection",
        f"{signal.direction.name}",
        signal.direction in valid_dirs
    )
    
    # Тест 4: Confidence в диапазоне [0, 1]
    run_test(
        "Confidence в [0, 1]",
        "0 <= conf <= 1",
        f"{signal.confidence:.3f}",
        0 <= signal.confidence <= 1
    )
    
    # Тест 5: Сигнал при низком спреде (ниже P25)
    # Создаём данные где последний спред очень низкий
    spreads_low = spreads.copy()
    spreads_low.iloc[-1] = spreads_low.quantile(0.10) - 1  # ниже P10
    
    signal_low = gen.generate_signal(
        spread_series=spreads_low,
        bond_long="BOND1",
        bond_short="BOND2"
    )
    
    run_test(
        "При спреде < P10: STRONG_BUY или BUY",
        "BUY сигнал",
        f"{signal_low.signal_type.name}",
        signal_low.signal_type in [SignalType.STRONG_BUY, SignalType.BUY]
    )
    
    # Тест 6: Сигнал при высоком спреде (выше P75)
    spreads_high = spreads.copy()
    spreads_high.iloc[-1] = spreads_high.quantile(0.90) + 1  # выше P90
    
    signal_high = gen.generate_signal(
        spread_series=spreads_high,
        bond_long="BOND1",
        bond_short="BOND2"
    )
    
    run_test(
        "При спреде > P90: STRONG_SELL или SELL",
        "SELL сигнал",
        f"{signal_high.signal_type.name}",
        signal_high.signal_type in [SignalType.STRONG_SELL, SignalType.SELL]
    )


# ============================================
# ТЕСТЫ CONFIG
# ============================================
def test_config():
    print_section("Configuration")
    
    from config import AppConfig, BondConfig
    
    config = AppConfig()
    
    # Тест 1: Количество облигаций
    run_test(
        "Количество облигаций в конфигурации",
        ">= 10",
        f"{len(config.bonds)}",
        len(config.bonds) >= 10
    )
    
    # Тест 2: Валидность ISIN
    all_valid = all(
        isin.startswith('SU262') and len(isin) == 12
        for isin in config.bonds.keys()
    )
    
    run_test(
        "Валидность ISIN кодов (SU262...RMFS)",
        "True",
        str(all_valid),
        all_valid
    )
    
    # Тест 3: Положительная купонная ставка
    all_positive = all(
        bond.coupon_rate > 0
        for bond in config.bonds.values()
    )
    
    run_test(
        "Положительные купонные ставки",
        "True",
        str(all_positive),
        all_positive
    )
    
    # Тест 4: Даты погашения в будущем
    all_future = all(
        datetime.strptime(bond.maturity_date, '%Y-%m-%d').date() > date.today()
        for bond in config.bonds.values()
    )
    
    run_test(
        "Даты погашения в будущем",
        "True",
        str(all_future),
        all_future
    )


# ============================================
# ИНТЕГРАЦИОННЫЕ ТЕСТЫ
# ============================================
def test_integration():
    print_section("Integration Tests")
    
    from api.moex_candles import CandleInterval, fetch_candles
    from api.moex_history import get_trading_data
    from api.moex_client import MOEXClient
    from config import AppConfig
    
    config = AppConfig()
    
    bonds = list(config.bonds.values())
    bond1 = bonds[0]
    bond2 = bonds[1]
    
    with MOEXClient() as client:
        # Тест 1: Получение данных для двух облигаций
        df1 = fetch_candles(
            bond1.isin,
            interval=CandleInterval.MIN_60,
            start_date=date.today() - timedelta(days=3),
            end_date=date.today(),
            client=client
        )
        
        df2 = fetch_candles(
            bond2.isin,
            interval=CandleInterval.MIN_60,
            start_date=date.today() - timedelta(days=3),
            end_date=date.today(),
            client=client
        )
        
        run_test(
            "Данные для двух облигаций получены",
            "2 DataFrame",
            f"df1={len(df1)}, df2={len(df2)}",
            len(df1) > 0 and len(df2) > 0
        )
        
        # Тест 2: Расчёт спреда
        if not df1.empty and not df2.empty and 'close' in df1.columns:
            merged = pd.merge(
                df1[['close']],
                df2[['close']],
                left_index=True,
                right_index=True,
                how='inner'
            )
            
            if not merged.empty:
                spread = (merged['close_x'].iloc[-1] - merged['close_y'].iloc[-1])
                
                run_test(
                    "Расчёт спреда между облигациями",
                    "число",
                    f"{spread:.2f}",
                    not pd.isna(spread)
                )
            else:
                run_test(
                    "Расчёт спреда между облигациями",
                    "число",
                    "Нет общих точек",
                    False
                )
        
        # Тест 3: Сравнение цен с MOEX данными
        moex_data = get_trading_data(bond1.isin, client=client)
        
        if moex_data.get('price') and not df1.empty and 'close' in df1.columns:
            moex_price = moex_data['price']
            candle_price = df1['close'].iloc[-1]
            diff = abs(moex_price - candle_price)
            
            run_test(
                "Разница цен (MOEX vs свечи) < 2%",
                "< 2%",
                f"{diff:.2f}%",
                diff < 2
            )


# ============================================
# MAIN
# ============================================
def main():
    print_header("OFZ SPREAD ANALYTICS - TEST SUITE")
    print(f"Дата: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}")
    
    start_time = time.time()
    
    # Запуск всех тестов
    try:
        test_ytm_calculator()
    except Exception as e:
        print(f"{Colors.RED}Ошибка в test_ytm_calculator: {e}{Colors.END}\n")
        import traceback
        traceback.print_exc()
    
    try:
        test_moex_candles()
    except Exception as e:
        print(f"{Colors.RED}Ошибка в test_moex_candles: {e}{Colors.END}\n")
        import traceback
        traceback.print_exc()
    
    try:
        test_moex_history()
    except Exception as e:
        print(f"{Colors.RED}Ошибка в test_moex_history: {e}{Colors.END}\n")
        import traceback
        traceback.print_exc()
    
    try:
        test_spread_calculator()
    except Exception as e:
        print(f"{Colors.RED}Ошибка в test_spread_calculator: {e}{Colors.END}\n")
        import traceback
        traceback.print_exc()
    
    try:
        test_signal_generator()
    except Exception as e:
        print(f"{Colors.RED}Ошибка в test_signal_generator: {e}{Colors.END}\n")
        import traceback
        traceback.print_exc()
    
    try:
        test_config()
    except Exception as e:
        print(f"{Colors.RED}Ошибка в test_config: {e}{Colors.END}\n")
        import traceback
        traceback.print_exc()
    
    try:
        test_integration()
    except Exception as e:
        print(f"{Colors.RED}Ошибка в test_integration: {e}{Colors.END}\n")
        import traceback
        traceback.print_exc()
    
    # Итоги
    elapsed = time.time() - start_time
    
    print_header("ИТОГИ ТЕСТИРОВАНИЯ")
    
    passed = sum(1 for _, p in test_results if p)
    failed = sum(1 for _, p in test_results if not p)
    total = len(test_results)
    
    print(f"Всего тестов: {total}")
    print(f"{Colors.GREEN}Пройдено: {passed}{Colors.END}")
    print(f"{Colors.RED}Провалено: {failed}{Colors.END}")
    print(f"Время: {elapsed:.2f} сек.")
    
    if failed > 0:
        print(f"\n{Colors.YELLOW}Проваленные тесты:{Colors.END}")
        for name, p in test_results:
            if not p:
                print(f"  ❌ {name}")
    
    print(f"\n{Colors.BOLD}{'='*60}{Colors.END}")
    
    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
