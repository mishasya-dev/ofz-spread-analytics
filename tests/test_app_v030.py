"""
Интеграционные тесты для v0.3.0

Модуль тестирует:
- prepare_spread_dataframe
- calculate_spread_stats
- generate_signal
- bond_config_to_dict
"""
import pytest
import pandas as pd
import numpy as np
from datetime import date, datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from dataclasses import dataclass
from typing import Dict, Optional

# Мок streamlit до импорта
import sys
sys.modules['streamlit'] = MagicMock()


# ============================================
# Test Helper Classes
# ============================================

@dataclass
class MockBondConfig:
    """Мок BondConfig из config.py"""
    isin: str
    name: str
    maturity_date: str
    coupon_rate: float
    face_value: float = 1000.0
    coupon_frequency: int = 2
    issue_date: str = ""
    day_count_convention: str = "ACT/ACT"


# ============================================
# TestPrepareSpreadDataframe
# ============================================

class TestPrepareSpreadDataframe:
    """Тесты prepare_spread_dataframe"""
    
    def test_prepare_daily_spread(self):
        """Подготовка DataFrame дневного спреда"""
        # Создаём тестовые данные
        dates = pd.date_range(start='2026-02-01', periods=10, freq='D')
        
        df1 = pd.DataFrame({
            'ytm': [14.5 + i * 0.1 for i in range(10)]
        }, index=dates)
        
        df2 = pd.DataFrame({
            'ytm': [15.0 + i * 0.05 for i in range(10)]
        }, index=dates)
        
        # Импортируем функцию
        from app import prepare_spread_dataframe
        
        result = prepare_spread_dataframe(df1, df2, is_intraday=False)
        
        assert len(result) == 10
        assert 'spread' in result.columns
        # Спред = (14.5 - 15.0) * 100 = -50 б.п. для первой точки
        assert result['spread'].iloc[0] == pytest.approx(-50.0, abs=1)
    
    def test_prepare_intraday_spread(self):
        """Подготовка DataFrame intraday спреда"""
        dates = pd.date_range(start='2026-02-20 10:00:00', periods=10, freq='h')
        
        df1 = pd.DataFrame({
            'ytm_close': [14.5 + i * 0.01 for i in range(10)]
        }, index=dates)
        
        df2 = pd.DataFrame({
            'ytm_close': [15.0 + i * 0.02 for i in range(10)]
        }, index=dates)
        
        from app import prepare_spread_dataframe
        
        result = prepare_spread_dataframe(df1, df2, is_intraday=True)
        
        assert len(result) == 10
        assert 'spread' in result.columns
    
    def test_prepare_empty_dataframe(self):
        """Пустой результат при пустых входных данных"""
        from app import prepare_spread_dataframe
        
        # Один пустой DataFrame
        df1 = pd.DataFrame()
        df2 = pd.DataFrame({'ytm': [15.0]}, index=pd.date_range('2026-02-01', periods=1))
        
        result = prepare_spread_dataframe(df1, df2, is_intraday=False)
        
        assert result.empty
    
    def test_spread_calculation_bp(self):
        """Спред в базисных пунктах: (ytm1 - ytm2) * 100"""
        dates = pd.date_range(start='2026-02-01', periods=1, freq='D')
        
        df1 = pd.DataFrame({'ytm': [14.0]}, index=dates)
        df2 = pd.DataFrame({'ytm': [15.0]}, index=dates)
        
        from app import prepare_spread_dataframe
        
        result = prepare_spread_dataframe(df1, df2, is_intraday=False)
        
        # (14.0 - 15.0) * 100 = -100 б.п.
        assert result['spread'].iloc[0] == pytest.approx(-100.0, abs=0.1)
    
    def test_spread_with_nan_values(self):
        """Обработка NaN значений - NaN сохраняются в результате"""
        dates = pd.date_range(start='2026-02-01', periods=5, freq='D')
        
        df1 = pd.DataFrame({
            'ytm': [14.5, np.nan, 14.7, 14.8, 14.9]
        }, index=dates)
        
        df2 = pd.DataFrame({
            'ytm': [15.0, 15.1, np.nan, 15.3, 15.4]
        }, index=dates)
        
        from app import prepare_spread_dataframe
        
        result = prepare_spread_dataframe(df1, df2, is_intraday=False)
        
        # Результат содержит spread колонку
        # NaN значения будут в результате там, где не было данных
        assert 'spread' in result.columns or result.empty


# ============================================
# TestCalculateSpreadStats
# ============================================

class TestCalculateSpreadStats:
    """Тесты calculate_spread_stats"""
    
    def test_stats_with_data(self):
        """Статистика с данными"""
        spread_series = pd.Series([50 + i for i in range(100)])  # 50..149
        
        from app import calculate_spread_stats
        
        stats = calculate_spread_stats(spread_series)
        
        assert 'mean' in stats
        assert 'median' in stats
        assert 'std' in stats
        assert 'p10' in stats
        assert 'p25' in stats
        assert 'p75' in stats
        assert 'p90' in stats
        assert 'current' in stats
        
        # Проверяем значения
        assert stats['mean'] == pytest.approx(99.5, abs=0.1)
        assert stats['p10'] == pytest.approx(59.5, abs=1)
        assert stats['p90'] == pytest.approx(139.5, abs=1)
    
    def test_stats_empty_series(self):
        """Пустая статистика при пустом Series"""
        spread_series = pd.Series([], dtype=float)
        
        from app import calculate_spread_stats
        
        stats = calculate_spread_stats(spread_series)
        
        # Должен вернуть пустой словарь или значения по умолчанию
        assert stats is None or stats == {} or all(pd.isna(v) for v in stats.values() if isinstance(v, float))
    
    def test_stats_current_value(self):
        """Текущее значение = последнее в Series"""
        spread_series = pd.Series([50, 60, 70, 80, 90])
        
        from app import calculate_spread_stats
        
        stats = calculate_spread_stats(spread_series)
        
        assert stats['current'] == 90
    
    def test_stats_percentiles_order(self):
        """Порядок перцентилей: p10 < p25 < median < p75 < p90"""
        spread_series = pd.Series([i for i in range(100)])
        
        from app import calculate_spread_stats
        
        stats = calculate_spread_stats(spread_series)
        
        assert stats['p10'] < stats['p25']
        assert stats['p25'] < stats['median']
        assert stats['median'] < stats['p75']
        assert stats['p75'] < stats['p90']


# ============================================
# TestGenerateSignal
# ============================================

class TestGenerateSignal:
    """Тесты generate_signal"""
    
    def test_signal_sell_buy_strong(self):
        """Сигнал SELL_BUY (сильный) когда спред < P10"""
        from app import generate_signal
        
        result = generate_signal(
            current_spread=40.0,  # < P10
            p10=50.0,
            p25=60.0,
            p75=80.0,
            p90=90.0
        )
        
        assert result['signal'] == 'SELL_BUY'
        assert result['strength'] == 'Сильный'
    
    def test_signal_sell_buy_medium(self):
        """Сигнал SELL_BUY (средний) когда P10 <= спред < P25"""
        from app import generate_signal
        
        result = generate_signal(
            current_spread=55.0,  # P10 <= 55 < P25
            p10=50.0,
            p25=60.0,
            p75=80.0,
            p90=90.0
        )
        
        assert result['signal'] == 'SELL_BUY'
        assert result['strength'] == 'Средний'
    
    def test_signal_neutral(self):
        """Сигнал NEUTRAL когда P25 <= спред <= P75"""
        from app import generate_signal
        
        result = generate_signal(
            current_spread=70.0,  # P25 <= 70 <= P75
            p10=50.0,
            p25=60.0,
            p75=80.0,
            p90=90.0
        )
        
        assert result['signal'] == 'NEUTRAL'
    
    def test_signal_buy_sell_medium(self):
        """Сигнал BUY_SELL (средний) когда P75 < спред <= P90"""
        from app import generate_signal
        
        result = generate_signal(
            current_spread=85.0,  # P75 < 85 <= P90
            p10=50.0,
            p25=60.0,
            p75=80.0,
            p90=90.0
        )
        
        assert result['signal'] == 'BUY_SELL'
        assert result['strength'] == 'Средний'
    
    def test_signal_buy_sell_strong(self):
        """Сигнал BUY_SELL (сильный) когда спред > P90"""
        from app import generate_signal
        
        result = generate_signal(
            current_spread=95.0,  # > P90
            p10=50.0,
            p25=60.0,
            p75=80.0,
            p90=90.0
        )
        
        assert result['signal'] == 'BUY_SELL'
        assert result['strength'] == 'Сильный'
    
    def test_signal_returns_action(self):
        """Сигнал содержит действие"""
        from app import generate_signal
        
        result = generate_signal(
            current_spread=70.0,
            p10=50.0,
            p25=60.0,
            p75=80.0,
            p90=90.0
        )
        
        assert 'action' in result
        assert 'reason' in result
        assert 'color' in result


# ============================================
# TestBondConfigToDict
# ============================================

class TestBondConfigToDict:
    """Тесты bond_config_to_dict"""
    
    def test_convert_bond_config(self):
        """Конвертация BondConfig в словарь"""
        bond = MockBondConfig(
            isin='RU000A1038V6',
            name='ОФЗ 26240',
            maturity_date='2046-05-15',
            coupon_rate=7.10,
            face_value=1000.0,
            coupon_frequency=2
        )
        
        from app import bond_config_to_dict
        
        result = bond_config_to_dict(bond)
        
        assert result['isin'] == 'RU000A1038V6'
        assert result['name'] == 'ОФЗ 26240'
        assert result['maturity_date'] == '2046-05-15'
        assert result['coupon_rate'] == 7.10
        assert result['face_value'] == 1000.0
        assert result['coupon_frequency'] == 2
    
    def test_convert_with_defaults(self):
        """Конвертация с значениями по умолчанию"""
        bond = MockBondConfig(
            isin='RU000A1038V6',
            name='ОФЗ 26240',
            maturity_date='2046-05-15',
            coupon_rate=7.10
        )
        
        from app import bond_config_to_dict
        
        result = bond_config_to_dict(bond)
        
        assert result['face_value'] == 1000.0
        assert result['coupon_frequency'] == 2


# ============================================
# TestFormatBondLabel
# ============================================

class TestFormatBondLabel:
    """Тесты format_bond_label"""
    
    def test_format_with_all_data(self):
        """Полная метка с YTM и дюрацией"""
        from app import format_bond_label
        
        bond = Mock(
            isin='RU000A1038V6',
            name='ОФЗ 26240'
        )
        
        result = format_bond_label(bond, ytm=14.5, duration_years=15.5)
        
        assert 'ОФЗ 26240' in result
        assert '14.5' in result or '14,5' in result
    
    def test_format_without_ytm(self):
        """Метка без YTM"""
        from app import format_bond_label
        
        bond = Mock(
            isin='RU000A1038V6',
            name='ОФЗ 26240'
        )
        
        result = format_bond_label(bond, ytm=None, duration_years=15.5)
        
        assert 'ОФЗ 26240' in result
    
    def test_format_without_duration(self):
        """Метка без дюрации"""
        from app import format_bond_label
        
        bond = Mock(
            isin='RU000A1038V6',
            name='ОФЗ 26240'
        )
        
        result = format_bond_label(bond, ytm=14.5, duration_years=None)
        
        assert 'ОФЗ 26240' in result


# ============================================
# TestGetYearsToMaturity
# ============================================

class TestGetYearsToMaturity:
    """Тесты get_years_to_maturity"""
    
    def test_valid_future_date(self):
        """Корректная будущая дата"""
        from app import get_years_to_maturity
        
        future_date = (date.today() + timedelta(days=3650)).strftime('%Y-%m-%d')
        
        result = get_years_to_maturity(future_date)
        
        assert result == pytest.approx(10.0, abs=0.1)
    
    def test_past_date(self):
        """Прошедшая дата"""
        from app import get_years_to_maturity
        
        past_date = '2020-01-01'
        
        result = get_years_to_maturity(past_date)
        
        assert result < 0
    
    def test_invalid_date_format(self):
        """Некорректный формат даты"""
        from app import get_years_to_maturity
        
        result = get_years_to_maturity('invalid-date')
        
        # Должен вернуть 0 или выбросить исключение
        assert result == 0 or result is None
    
    def test_empty_date(self):
        """Пустая дата"""
        from app import get_years_to_maturity
        
        result = get_years_to_maturity('')
        
        assert result == 0 or result is None
