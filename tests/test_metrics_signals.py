"""
Тесты для services/spread_calculator.py

NOTE: Ранее тестировали components/metrics.py и components/signals.py,
но app.py использует функции из services/spread_calculator.py.
Теперь тестируем правильные функции.
"""
import pytest
import pandas as pd
import numpy as np
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.spread_calculator import calculate_spread_stats, generate_signal


class TestCalculateSpreadStats:
    """Тесты для services/spread_calculator.py::calculate_spread_stats"""

    def test_basic_calculation(self):
        """Базовый расчёт статистики"""
        series = pd.Series([10, 20, 30, 40, 50])
        stats = calculate_spread_stats(series)

        assert stats['mean'] == 30.0
        assert stats['median'] == 30.0
        assert stats['min'] == 10.0
        assert stats['max'] == 50.0

    def test_percentiles(self):
        """Расчёт перцентилей"""
        series = pd.Series(range(1, 101))
        stats = calculate_spread_stats(series)

        assert 9 < stats['p10'] < 11
        assert 24 < stats['p25'] < 26
        assert 74 < stats['p75'] < 76
        assert 89 < stats['p90'] < 91

    def test_current_is_last_value(self):
        """Current = последнее значение"""
        series = pd.Series([100, 200, 300])
        stats = calculate_spread_stats(series)
        assert stats['current'] == 300

    def test_std_calculation(self):
        """Расчёт стандартного отклонения"""
        series = pd.Series([10, 20, 30, 40, 50])
        stats = calculate_spread_stats(series)
        # std of [10,20,30,40,50] = sqrt(250) ≈ 15.81
        assert 15 < stats['std'] < 16

    def test_empty_series_returns_empty_dict(self):
        """Пустой series возвращает пустой dict"""
        series = pd.Series([])
        stats = calculate_spread_stats(series)
        assert stats == {}

    def test_all_nan_series_returns_empty_dict(self):
        """Series только с NaN возвращает пустой dict"""
        series = pd.Series([np.nan, np.nan, np.nan])
        stats = calculate_spread_stats(series)
        assert stats == {}

    def test_series_with_some_nan(self):
        """Series с некоторыми NaN - NaN игнорируются"""
        series = pd.Series([10, np.nan, 30, np.nan, 50])
        stats = calculate_spread_stats(series)

        assert stats['mean'] == 30.0  # (10+30+50)/3
        assert stats['min'] == 10.0
        assert stats['max'] == 50.0


class TestGenerateSignal:
    """Тесты для services/spread_calculator.py::generate_signal"""

    def test_sell_buy_signal(self):
        """Сигнал SELL_BUY когда спред ниже P25"""
        signal = generate_signal(
            current_spread=5.0,
            p10=0.0,
            p25=10.0,
            p75=30.0,
            p90=40.0
        )

        assert signal['signal'] == 'SELL_BUY'
        assert 'ПРОДАТЬ Облигацию 1' in signal['action']
        assert 'КУПИТЬ Облигацию 2' in signal['action']
        assert signal['color'] == '#FF6B6B'

    def test_buy_sell_signal(self):
        """Сигнал BUY_SELL когда спред выше P75"""
        signal = generate_signal(
            current_spread=35.0,
            p10=0.0,
            p25=10.0,
            p75=30.0,
            p90=40.0
        )

        assert signal['signal'] == 'BUY_SELL'
        assert 'КУПИТЬ Облигацию 1' in signal['action']
        assert 'ПРОДАТЬ Облигацию 2' in signal['action']
        assert signal['color'] == '#4ECDC4'

    def test_neutral_signal(self):
        """Сигнал NEUTRAL когда спред в нормальном диапазоне"""
        signal = generate_signal(
            current_spread=20.0,
            p10=0.0,
            p25=10.0,
            p75=30.0,
            p90=40.0
        )

        assert signal['signal'] == 'NEUTRAL'
        assert 'Удерживать' in signal['action']
        assert signal['color'] == '#95A5A6'

    def test_strong_signal_below_p10(self):
        """Сильный сигнал когда спред ниже P10"""
        signal = generate_signal(
            current_spread=-5.0,
            p10=0.0,
            p25=10.0,
            p75=30.0,
            p90=40.0
        )

        assert signal['signal'] == 'SELL_BUY'
        assert signal['strength'] == 'Сильный'

    def test_strong_signal_above_p90(self):
        """Сильный сигнал когда спред выше P90"""
        signal = generate_signal(
            current_spread=45.0,
            p10=0.0,
            p25=10.0,
            p75=30.0,
            p90=40.0
        )

        assert signal['signal'] == 'BUY_SELL'
        assert signal['strength'] == 'Сильный'

    def test_medium_signal(self):
        """Средний сигнал когда спред между P10-P25 или P75-P90"""
        signal = generate_signal(
            current_spread=5.0,
            p10=0.0,
            p25=10.0,
            p75=30.0,
            p90=40.0
        )

        assert signal['signal'] == 'SELL_BUY'
        assert signal['strength'] == 'Средний'

    def test_signal_contains_reason(self):
        """Сигнал содержит объяснение"""
        signal = generate_signal(
            current_spread=5.0,
            p10=0.0,
            p25=10.0,
            p75=30.0,
            p90=40.0
        )

        assert 'reason' in signal
        assert '5.00' in signal['reason']


class TestSignalLogic:
    """Тесты для проверки логики сигналов"""

    def test_low_spread_sell_buy(self):
        """Низкий спред = SELL_BUY (продать 1, купить 2)"""
        signal = generate_signal(
            current_spread=5.0,  # низкий спред
            p10=0.0,
            p25=10.0,
            p75=30.0,
            p90=40.0
        )

        assert signal['signal'] == 'SELL_BUY'

    def test_high_spread_buy_sell(self):
        """Высокий спред = BUY_SELL (купить 1, продать 2)"""
        signal = generate_signal(
            current_spread=35.0,  # высокий спред
            p10=0.0,
            p25=10.0,
            p75=30.0,
            p90=40.0
        )

        assert signal['signal'] == 'BUY_SELL'

    def test_boundary_p25(self):
        """На границе P25 - NEUTRAL (не строго меньше)"""
        signal = generate_signal(
            current_spread=10.0,  # равно P25
            p10=0.0,
            p25=10.0,
            p75=30.0,
            p90=40.0
        )

        assert signal['signal'] == 'NEUTRAL'

    def test_boundary_p75(self):
        """На границе P75 - NEUTRAL (не строго больше)"""
        signal = generate_signal(
            current_spread=30.0,  # равно P75
            p10=0.0,
            p25=10.0,
            p75=30.0,
            p90=40.0
        )

        assert signal['signal'] == 'NEUTRAL'
