"""
Тесты для services/g_spread_calculator.py
"""
import pytest
import pandas as pd
import numpy as np
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.g_spread_calculator import calculate_g_spread_stats, generate_g_spread_signal


class TestCalculateGSpreadStats:
    """Тесты для calculate_g_spread_stats"""

    def test_basic_stats(self):
        """Базовый расчёт статистики"""
        series = pd.Series([10, 20, 30, 40, 50])
        stats = calculate_g_spread_stats(series)

        assert stats['mean'] == 30.0
        assert stats['median'] == 30.0
        assert stats['min'] == 10.0
        assert stats['max'] == 50.0
        assert stats['count'] == 5

    def test_percentiles(self):
        """Расчёт перцентилей"""
        # Равномерное распределение 0-100
        series = pd.Series(range(1, 101))
        stats = calculate_g_spread_stats(series)

        # P10 ≈ 10.9, P25 ≈ 25.75, P75 ≈ 75.25, P90 ≈ 90.1
        assert 10 < stats['p10'] < 11
        assert 25 < stats['p25'] < 26
        assert 75 < stats['p75'] < 76
        assert 90 < stats['p90'] < 91

    def test_current_is_last_value(self):
        """Current должен быть последним значением"""
        series = pd.Series([100, 200, 300, 400, 500])
        stats = calculate_g_spread_stats(series)
        assert stats['current'] == 500.0

    def test_empty_series_returns_empty_dict(self):
        """Пустая серия возвращает пустой словарь"""
        series = pd.Series([], dtype=float)
        stats = calculate_g_spread_stats(series)
        assert stats == {}

    def test_all_nan_returns_empty_dict(self):
        """Серия только из NaN возвращает пустой словарь"""
        series = pd.Series([np.nan, np.nan, np.nan])
        stats = calculate_g_spread_stats(series)
        assert stats == {}

    def test_drops_nan_values(self):
        """NaN значения игнорируются"""
        series = pd.Series([10, np.nan, 30, np.nan, 50])
        stats = calculate_g_spread_stats(series)

        assert stats['mean'] == 30.0  # (10+30+50)/3
        assert stats['count'] == 3

    def test_negative_values(self):
        """Работа с отрицательными значениями (G-spread может быть отрицательным)"""
        series = pd.Series([-50, -30, -10, 10, 30])
        stats = calculate_g_spread_stats(series)

        assert stats['min'] == -50.0
        assert stats['max'] == 30.0
        assert stats['mean'] == -10.0

    def test_single_value(self):
        """Серия из одного значения"""
        series = pd.Series([42.0])
        stats = calculate_g_spread_stats(series)

        assert stats['mean'] == 42.0
        assert stats['median'] == 42.0
        # std для одного значения = NaN (нормальное поведение pandas)
        assert pd.isna(stats['std']) or stats['std'] == 0.0
        assert stats['current'] == 42.0

    def test_returns_python_floats(self):
        """Возвращает Python float, не numpy типы"""
        series = pd.Series([1.0, 2.0, 3.0])
        stats = calculate_g_spread_stats(series)

        assert isinstance(stats['mean'], float)
        assert isinstance(stats['p10'], float)
        assert isinstance(stats['count'], int)


class TestGenerateGSpreadSignal:
    """Тесты для generate_g_spread_signal"""

    def test_buy_signal_below_p25(self):
        """Сигнал BUY когда G-spread ниже P25"""
        signal = generate_g_spread_signal(
            current_spread=5.0,
            p10=0.0,
            p25=10.0,
            p75=30.0,
            p90=40.0
        )

        assert signal['signal'] == 'BUY'
        assert 'ПОКУПКА' in signal['action']
        assert 'недооценена' in signal['action']
        assert signal['color'] == '#28a745'

    def test_strong_buy_signal_below_p10(self):
        """Сильный сигнал BUY когда G-spread ниже P10"""
        signal = generate_g_spread_signal(
            current_spread=-5.0,
            p10=0.0,
            p25=10.0,
            p75=30.0,
            p90=40.0
        )

        assert signal['signal'] == 'BUY'
        assert signal['strength'] == 'Сильный'

    def test_medium_buy_signal(self):
        """Средний сигнал BUY когда G-spread между P10 и P25"""
        signal = generate_g_spread_signal(
            current_spread=5.0,
            p10=0.0,
            p25=10.0,
            p75=30.0,
            p90=40.0
        )

        assert signal['signal'] == 'BUY'
        assert signal['strength'] == 'Средний'

    def test_sell_signal_above_p75(self):
        """Сигнал SELL когда G-spread выше P75"""
        signal = generate_g_spread_signal(
            current_spread=35.0,
            p10=0.0,
            p25=10.0,
            p75=30.0,
            p90=40.0
        )

        assert signal['signal'] == 'SELL'
        assert 'ПРОДАЖА' in signal['action']
        assert 'переоценена' in signal['action']
        assert signal['color'] == '#dc3545'

    def test_strong_sell_signal_above_p90(self):
        """Сильный сигнал SELL когда G-spread выше P90"""
        signal = generate_g_spread_signal(
            current_spread=45.0,
            p10=0.0,
            p25=10.0,
            p75=30.0,
            p90=40.0
        )

        assert signal['signal'] == 'SELL'
        assert signal['strength'] == 'Сильный'

    def test_medium_sell_signal(self):
        """Средний сигнал SELL когда G-spread между P75 и P90"""
        signal = generate_g_spread_signal(
            current_spread=35.0,
            p10=0.0,
            p25=10.0,
            p75=30.0,
            p90=40.0
        )

        assert signal['signal'] == 'SELL'
        assert signal['strength'] == 'Средний'

    def test_hold_signal_in_range(self):
        """Сигнал HOLD когда G-spread в нормальном диапазоне"""
        signal = generate_g_spread_signal(
            current_spread=20.0,
            p10=0.0,
            p25=10.0,
            p75=30.0,
            p90=40.0
        )

        assert signal['signal'] == 'HOLD'
        assert 'УДЕРЖИВАТЬ' in signal['action']
        assert signal['color'] == '#ffc107'
        assert signal['strength'] == 'Нет сигнала'

    def test_hold_at_p25_boundary(self):
        """HOLD когда G-sread равен P25 (граница)"""
        # current_spread = p25 означает HOLD (не BUY)
        signal = generate_g_spread_signal(
            current_spread=10.0,
            p10=0.0,
            p25=10.0,
            p75=30.0,
            p90=40.0
        )

        assert signal['signal'] == 'HOLD'

    def test_hold_at_p75_boundary(self):
        """HOLD когда G-sread равен P75 (граница)"""
        # current_spread = p75 означает HOLD (не SELL)
        signal = generate_g_spread_signal(
            current_spread=30.0,
            p10=0.0,
            p25=10.0,
            p75=30.0,
            p90=40.0
        )

        assert signal['signal'] == 'HOLD'

    def test_signal_contains_reason(self):
        """Сигнал содержит объяснение"""
        signal = generate_g_spread_signal(
            current_spread=5.0,
            p10=0.0,
            p25=10.0,
            p75=30.0,
            p90=40.0
        )

        assert 'reason' in signal
        assert '5.0' in signal['reason']

    def test_negative_spread_buy(self):
        """Отрицательный G-spread = недооценка = BUY"""
        signal = generate_g_spread_signal(
            current_spread=-20.0,
            p10=-15.0,
            p25=-5.0,
            p75=10.0,
            p90=20.0
        )

        assert signal['signal'] == 'BUY'
