"""
Тесты для components/metrics.py и components/signals.py
"""
import pytest
import pandas as pd
import numpy as np
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from components.metrics import calculate_spread_stats as metrics_calculate_spread_stats
from components.signals import calculate_spread_stats as signals_calculate_spread_stats
from components.signals import generate_signal


class TestMetricsCalculateSpreadStats:
    """Тесты для components/metrics.py::calculate_spread_stats"""

    def test_basic_calculation(self):
        """Базовый расчёт статистики"""
        series = pd.Series([10, 20, 30, 40, 50])
        stats = metrics_calculate_spread_stats(series)

        assert stats['mean'] == 30.0
        assert stats['median'] == 30.0
        assert stats['min'] == 10.0
        assert stats['max'] == 50.0

    def test_percentiles(self):
        """Расчёт перцентилей"""
        series = pd.Series(range(1, 101))
        stats = metrics_calculate_spread_stats(series)

        assert 10 < stats['p10'] < 11
        assert 25 < stats['p25'] < 26
        assert 75 < stats['p75'] < 76
        assert 90 < stats['p90'] < 91

    def test_current_is_last_value(self):
        """Current = последнее значение"""
        series = pd.Series([100, 200, 300])
        stats = metrics_calculate_spread_stats(series)
        assert stats['current'] == 300

    def test_std_calculation(self):
        """Расчёт стандартного отклонения"""
        series = pd.Series([10, 20, 30, 40, 50])
        stats = metrics_calculate_spread_stats(series)
        # std of [10,20,30,40,50] = sqrt(250) ≈ 15.81
        assert 15 < stats['std'] < 16


class TestSignalsCalculateSpreadStats:
    """Тесты для components/signals.py::calculate_spread_stats"""

    def test_basic_calculation(self):
        """Базовый расчёт статистики"""
        series = pd.Series([10, 20, 30, 40, 50])
        stats = signals_calculate_spread_stats(series)

        assert stats['mean'] == 30.0
        assert stats['median'] == 30.0
        assert stats['min'] == 10.0
        assert stats['max'] == 50.0

    def test_matches_metrics_version(self):
        """Обе версии должны давать одинаковый результат"""
        series = pd.Series([10, 20, 30, 40, 50, 60, 70])
        stats_metrics = metrics_calculate_spread_stats(series)
        stats_signals = signals_calculate_spread_stats(series)

        assert stats_metrics['mean'] == stats_signals['mean']
        assert stats_metrics['median'] == stats_signals['median']
        assert stats_metrics['std'] == stats_signals['std']
        assert stats_metrics['p25'] == stats_signals['p25']
        assert stats_metrics['p75'] == stats_signals['p75']


class TestGenerateSignal:
    """Тесты для components/signals.py::generate_signal"""

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
        assert '5.0' in signal['reason']


class TestSignalInterpretation:
    """Тесты для проверки интерпретации сигналов"""

    def test_low_spread_means_bond1_expensive(self):
        """Низкий спред = Облигация 1 дорогая относительно Облигации 2"""
        signal = generate_signal(
            current_spread=5.0,  # низкий спред
            p10=0.0,
            p25=10.0,
            p75=30.0,
            p90=40.0
        )

        # SELL_BUY = продать 1, купить 2
        assert signal['signal'] == 'SELL_BUY'
        assert 'переоценена' in signal['reason']

    def test_high_spread_means_bond1_cheap(self):
        """Высокий спред = Облигация 1 дешёвая относительно Облигации 2"""
        signal = generate_signal(
            current_spread=35.0,  # высокий спред
            p10=0.0,
            p25=10.0,
            p75=30.0,
            p90=40.0
        )

        # BUY_SELL = купить 1, продать 2
        assert signal['signal'] == 'BUY_SELL'
        assert 'недооценена' in signal['reason']
