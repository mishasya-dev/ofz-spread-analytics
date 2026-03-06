"""
Тесты для BondYTMProcessor

TDD: Сначала тесты, потом реализация
"""
import pytest
import pandas as pd
import numpy as np
from datetime import date, datetime, timedelta
from dataclasses import dataclass
from typing import Optional


# Мок BondConfig для тестов
@dataclass
class MockBondConfig:
    """Мок конфигурации облигации"""
    isin: str
    name: str
    maturity_date: str  # ISO формат
    coupon_rate: float
    face_value: float = 1000.0
    coupon_frequency: int = 2
    issue_date: Optional[str] = None
    day_count_convention: str = "ACT/ACT"


@pytest.fixture
def sample_bond():
    """Тестовая облигация (ОФЗ 26207)"""
    return MockBondConfig(
        isin="SU26207RMFS9",
        name="ОФЗ 26207",
        maturity_date="2027-02-03",
        coupon_rate=7.45,
        face_value=1000.0,
        coupon_frequency=2,
        issue_date="2017-01-25"
    )


@pytest.fixture
def sample_raw_candles():
    """Сырые свечи без YTM (как должен возвращать CandleFetcher)"""
    dates = pd.date_range(
        start="2025-03-03 07:00",
        end="2025-03-03 15:00",
        freq="1h"
    )
    
    return pd.DataFrame({
        "open": [98.5 + i * 0.1 for i in range(len(dates))],
        "high": [98.7 + i * 0.1 for i in range(len(dates))],
        "low": [98.3 + i * 0.1 for i in range(len(dates))],
        "close": [98.6 + i * 0.1 for i in range(len(dates))],
        "volume": [1000 + i * 100 for i in range(len(dates))],
        "value": [100000 + i * 10000 for i in range(len(dates))],
    }, index=dates)


class TestBondYTMProcessorInit:
    """Тесты инициализации"""
    
    def test_processor_can_be_instantiated(self):
        """Процессор можно создать"""
        from services.candle_processor_ytm_for_bonds import BondYTMProcessor
        
        processor = BondYTMProcessor()
        assert processor is not None
    
    def test_processor_has_ytm_calculator(self):
        """Процессор имеет YTMCalculator"""
        from services.candle_processor_ytm_for_bonds import BondYTMProcessor
        from core.ytm_calculator import YTMCalculator
        
        processor = BondYTMProcessor()
        assert hasattr(processor, '_ytm_calculator')
        assert isinstance(processor._ytm_calculator, YTMCalculator)


class TestAddYTMToCandles:
    """Тесты добавления YTM к свечам"""
    
    def test_adds_ytm_close_column(self, sample_bond, sample_raw_candles):
        """Процессор добавляет колонку ytm_close"""
        from services.candle_processor_ytm_for_bonds import BondYTMProcessor
        
        processor = BondYTMProcessor()
        result = processor.add_ytm_to_candles(sample_raw_candles, sample_bond)
        
        assert 'ytm_close' in result.columns
    
    def test_ytm_values_are_reasonable(self, sample_bond, sample_raw_candles):
        """YTM значения в разумном диапазоне (5-25%)"""
        from services.candle_processor_ytm_for_bonds import BondYTMProcessor
        
        processor = BondYTMProcessor()
        result = processor.add_ytm_to_candles(sample_raw_candles, sample_bond)
        
        ytm_values = result['ytm_close'].dropna()
        assert len(ytm_values) > 0
        assert all(5 < y < 25 for y in ytm_values), f"YTM values out of range: {ytm_values}"
    
    def test_preserves_original_columns(self, sample_bond, sample_raw_candles):
        """Оригинальные колонки сохраняются"""
        from services.candle_processor_ytm_for_bonds import BondYTMProcessor
        
        original_columns = set(sample_raw_candles.columns)
        
        processor = BondYTMProcessor()
        result = processor.add_ytm_to_candles(sample_raw_candles, sample_bond)
        
        assert original_columns.issubset(set(result.columns))
    
    def test_handles_empty_dataframe(self, sample_bond):
        """Обработка пустого DataFrame"""
        from services.candle_processor_ytm_for_bonds import BondYTMProcessor
        
        empty_df = pd.DataFrame()
        processor = BondYTMProcessor()
        result = processor.add_ytm_to_candles(empty_df, sample_bond)
        
        assert result.empty
    
    def test_handles_missing_close_column(self, sample_bond):
        """Обработка DataFrame без колонки close"""
        from services.candle_processor_ytm_for_bonds import BondYTMProcessor
        
        df_without_close = pd.DataFrame({
            "open": [98.5],
            "volume": [1000],
        }, index=pd.date_range("2025-03-03", periods=1, freq="h"))
        
        processor = BondYTMProcessor()
        result = processor.add_ytm_to_candles(df_without_close, sample_bond)
        
        # Должен вернуть как есть или с пустой колонкой ytm_close
        assert 'ytm_close' not in result.columns or result['ytm_close'].isna().all()


class TestCalculateYTMForPrice:
    """Тесты расчёта YTM для одной цены"""
    
    def test_calculates_ytm_for_single_price(self, sample_bond):
        """Расчёт YTM для одной цены"""
        from services.candle_processor_ytm_for_bonds import BondYTMProcessor
        
        processor = BondYTMProcessor()
        ytm = processor.calculate_ytm_for_price(
            price=98.5,
            bond_config=sample_bond,
            trade_date=date(2025, 3, 3)
        )
        
        assert ytm is not None
        assert 5 < ytm < 25
    
    def test_handles_invalid_price(self, sample_bond):
        """Обработка невалидной цены"""
        from services.candle_processor_ytm_for_bonds import BondYTMProcessor
        
        processor = BondYTMProcessor()
        
        # Отрицательная цена
        ytm = processor.calculate_ytm_for_price(
            price=-10,
            bond_config=sample_bond,
            trade_date=date(2025, 3, 3)
        )
        assert ytm is None
        
        # Нулевая цена
        ytm = processor.calculate_ytm_for_price(
            price=0,
            bond_config=sample_bond,
            trade_date=date(2025, 3, 3)
        )
        assert ytm is None


class TestT1Settlement:
    """Тесты учёта T+1 режима торгов"""
    
    def test_uses_settlement_date_for_ytm(self, sample_bond):
        """Для расчёта YTM используется settlement date (T+1)"""
        from services.candle_processor_ytm_for_bonds import BondYTMProcessor
        
        processor = BondYTMProcessor()
        
        # Пятница -> settlement в понедельник
        friday_trade = date(2025, 3, 7)  # Пятница
        ytm_friday = processor.calculate_ytm_for_price(
            price=98.5,
            bond_config=sample_bond,
            trade_date=friday_trade
        )
        
        # Понедельник -> settlement во вторник
        monday_trade = date(2025, 3, 10)  # Понедельник
        ytm_monday = processor.calculate_ytm_for_price(
            price=98.5,
            bond_config=sample_bond,
            trade_date=monday_trade
        )
        
        # YTM должен немного отличаться из-за разницы в settlement date
        assert ytm_friday is not None
        assert ytm_monday is not None


class TestBondParamsCache:
    """Тесты кэширования BondParams"""
    
    def test_caches_bond_params(self, sample_bond):
        """Параметры облигации кэшируются"""
        from services.candle_processor_ytm_for_bonds import BondYTMProcessor
        
        processor = BondYTMProcessor()
        
        # Первый вызов
        processor.calculate_ytm_for_price(98.5, sample_bond, date(2025, 3, 3))
        
        # Проверяем что в кэше
        assert sample_bond.isin in processor._bond_params_cache
    
    def test_uses_cached_params(self, sample_bond):
        """Используются кэшированные параметры"""
        from services.candle_processor_ytm_for_bonds import BondYTMProcessor
        
        processor = BondYTMProcessor()
        
        # Первый вызов
        ytm1 = processor.calculate_ytm_for_price(98.5, sample_bond, date(2025, 3, 3))
        
        # Второй вызов (должен использовать кэш)
        ytm2 = processor.calculate_ytm_for_price(98.6, sample_bond, date(2025, 3, 3))
        
        # Результаты должны быть близки (разные цены)
        assert abs(ytm1 - ytm2) < 0.5


class TestWithRealData:
    """Интеграционные тесты с реалистичными данными"""
    
    def test_ofz_26238_typical_prices(self):
        """Тест с типичными ценами ОФЗ 26238"""
        from services.candle_processor_ytm_for_bonds import BondYTMProcessor
        
        bond = MockBondConfig(
            isin="SU26238RMFS5",
            name="ОФЗ 26238",
            maturity_date="2041-05-15",
            coupon_rate=7.1,
            face_value=1000.0,
            coupon_frequency=2
        )
        
        # Типичная цена для длинной ОФЗ
        processor = BondYTMProcessor()
        ytm = processor.calculate_ytm_for_price(
            price=72.5,  # Длинная ОФЗ торгуется с дисконтом
            bond_config=bond,
            trade_date=date(2025, 3, 3)
        )
        
        assert ytm is not None
        # Длинная ОФЗ с дисконтом должна давать высокий YTM
        assert 10 < ytm < 20
    
    def test_ofz_26243_premium_price(self):
        """Тест с ценой выше номинала (премиум)"""
        from services.candle_processor_ytm_for_bonds import BondYTMProcessor
        
        bond = MockBondConfig(
            isin="SU26243RMFS2",
            name="ОФЗ 26243",
            maturity_date="2027-07-14",
            coupon_rate=7.7,
            face_value=1000.0,
            coupon_frequency=2
        )
        
        # Короткая ОФЗ может торговаться с премией
        processor = BondYTMProcessor()
        ytm = processor.calculate_ytm_for_price(
            price=105.0,  # Выше номинала
            bond_config=bond,
            trade_date=date(2025, 3, 3)
        )
        
        assert ytm is not None
        # При цене выше номинала YTM должен быть ниже купона
        assert ytm < bond.coupon_rate
