"""
Тесты модуля core/db (версия 0.3.0)

Запуск:
    python -m pytest tests/test_db_migration.py -v
"""
import pytest
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import date, datetime, timedelta
import pandas as pd
import numpy as np


# ============================================
# ФИКСТУРЫ
# ============================================

@pytest.fixture
def db():
    """DatabaseFacade"""
    from core.db import get_db, init_database
    init_database()
    return get_db()


@pytest.fixture
def sample_bond_data():
    """Тестовые данные облигации"""
    return {
        'isin': 'TEST_MIGRATION_001',
        'name': 'Тестовая облигация',
        'short_name': 'Тест',
        'coupon_rate': 7.5,
        'maturity_date': '2030-12-15',
        'issue_date': '2020-01-01',
        'face_value': 1000,
        'coupon_frequency': 2,
        'day_count': 'ACT/ACT',
        'is_favorite': 1,
    }


@pytest.fixture
def sample_daily_ytm():
    """Тестовые данные дневных YTM"""
    dates = pd.date_range(end=date.today(), periods=10, freq='D')
    return pd.DataFrame({
        'ytm': np.random.uniform(14, 16, 10),
        'price': np.random.uniform(95, 105, 10),
        'duration_days': np.random.uniform(1000, 2000, 10),
    }, index=dates)


@pytest.fixture
def sample_intraday_ytm():
    """Тестовые данные intraday YTM"""
    dates = pd.date_range(
        start=datetime.now() - timedelta(hours=10),
        periods=10,
        freq='h'
    )
    return pd.DataFrame({
        'close': np.random.uniform(95, 105, 10),
        'ytm_close': np.random.uniform(14, 16, 10),
        'accrued_interest': np.random.uniform(10, 30, 10),
        'volume': np.random.randint(100, 1000, 10),
    }, index=dates)


# ============================================
# ТЕСТЫ МЕТОДОВ
# ============================================

class TestBondsMethods:
    """Тесты методов облигаций"""

    def test_save_bond(self, db, sample_bond_data):
        """save_bond возвращает bool"""
        result = db.save_bond(sample_bond_data)
        assert isinstance(result, bool)
        assert result is True

    def test_load_bond(self, db, sample_bond_data):
        """load_bond возвращает Dict или None"""
        isin = sample_bond_data['isin']
        
        # Сначала сохраняем
        db.save_bond(sample_bond_data)
        
        bond = db.load_bond(isin)
        assert bond is not None
        assert bond['isin'] == isin

    def test_get_favorite_bonds(self, db, sample_bond_data):
        """get_favorite_bonds возвращает List[Dict]"""
        # Сохраняем избранную облигацию
        sample_bond_data['is_favorite'] = 1
        db.save_bond(sample_bond_data)
        
        favorites = db.get_favorite_bonds()
        assert isinstance(favorites, list)

    def test_get_favorite_bonds_as_config(self, db, sample_bond_data):
        """get_favorite_bonds_as_config возвращает Dict"""
        sample_bond_data['is_favorite'] = 1
        db.save_bond(sample_bond_data)
        
        config = db.get_favorite_bonds_as_config()
        assert isinstance(config, dict)


class TestYTMMethods:
    """Тесты методов YTM"""

    def test_save_daily_ytm(self, db, sample_daily_ytm):
        """save_daily_ytm возвращает int"""
        isin = 'TEST_DAILY_YTM_001'
        
        count = db.save_daily_ytm(isin, sample_daily_ytm)
        assert isinstance(count, int)
        assert count > 0

    def test_load_daily_ytm(self, db, sample_daily_ytm):
        """load_daily_ytm возвращает DataFrame"""
        isin = 'TEST_DAILY_YTM_002'
        
        db.save_daily_ytm(isin, sample_daily_ytm)
        
        df = db.load_daily_ytm(isin)
        assert isinstance(df, pd.DataFrame)
        assert len(df) > 0

    def test_get_last_daily_ytm_date(self, db, sample_daily_ytm):
        """get_last_daily_ytm_date возвращает date или None"""
        isin = 'TEST_DAILY_YTM_003'
        
        db.save_daily_ytm(isin, sample_daily_ytm)
        
        last_date = db.get_last_daily_ytm_date(isin)
        assert last_date is None or isinstance(last_date, date)

    def test_save_intraday_ytm(self, db, sample_intraday_ytm):
        """save_intraday_ytm возвращает int"""
        isin = 'TEST_INTRADAY_YTM_001'
        interval = '60'
        
        count = db.save_intraday_ytm(isin, interval, sample_intraday_ytm)
        assert isinstance(count, int)
        assert count > 0

    def test_load_intraday_ytm(self, db, sample_intraday_ytm):
        """load_intraday_ytm возвращает DataFrame"""
        isin = 'TEST_INTRADAY_YTM_002'
        interval = '60'
        
        db.save_intraday_ytm(isin, interval, sample_intraday_ytm)
        
        df = db.load_intraday_ytm(isin, interval)
        assert isinstance(df, pd.DataFrame)
        assert len(df) > 0

    def test_get_last_intraday_ytm_datetime(self, db, sample_intraday_ytm):
        """get_last_intraday_ytm_datetime возвращает datetime или None"""
        isin = 'TEST_INTRADAY_YTM_003'
        interval = '60'
        
        db.save_intraday_ytm(isin, interval, sample_intraday_ytm)
        
        last_dt = db.get_last_intraday_ytm_datetime(isin, interval)
        assert last_dt is None or isinstance(last_dt, datetime)


class TestStatsMethods:
    """Тесты методов статистики"""

    def test_get_stats(self, db):
        """get_stats возвращает Dict с ожидаемыми ключами"""
        stats = db.get_stats()
        assert isinstance(stats, dict)
        assert 'bonds_count' in stats
        assert 'daily_ytm_count' in stats
        assert 'intraday_ytm_count' in stats
        assert 'candles_count' in stats
        assert 'snapshots_count' in stats


class TestCointegrationMethods:
    """Тесты методов коинтеграции"""

    def test_save_and_load_cointegration(self, db):
        """Проверка сохранения и загрузки коинтеграции"""
        bond1 = 'TEST_COINT_001'
        bond2 = 'TEST_COINT_002'
        
        result = {
            'bond1_isin': bond1,
            'bond2_isin': bond2,
            'is_cointegrated': True,
            'pvalue': 0.03,
            'half_life': 10.5,
            'hedge_ratio': 0.95,
            'data_days': 365,
            'adf_bond1_pvalue': 0.5,
            'adf_bond2_pvalue': 0.6,
            'both_nonstationary': True,
        }
        
        db.save_cointegration_result(result)
        cached = db.load_cointegration_result(bond1, bond2)
        assert cached is not None
        assert cached['is_cointegrated'] == True

    def test_get_cointegration_cache(self, db):
        """Проверка старого API get_cointegration_cache"""
        bond1 = 'TEST_OLD_API_001'
        bond2 = 'TEST_OLD_API_002'
        period_days = 365
        
        result = {
            'is_cointegrated': True,
            'pvalue': 0.04,
            'half_life': 12.0,
        }
        
        db.save_cointegration_cache(bond1, bond2, period_days, result)
        cached = db.get_cointegration_cache(bond1, bond2, period_days)
        assert cached is not None
        assert cached['is_cointegrated'] == True

    def test_clear_cointegration_cache(self, db):
        """Проверка очистки кэша коинтеграции"""
        bond1 = 'TEST_CLEAR_001'
        bond2 = 'TEST_CLEAR_002'
        
        result = {
            'bond1_isin': bond1,
            'bond2_isin': bond2,
            'is_cointegrated': False, 
            'pvalue': 0.5
        }
        
        db.save_cointegration_result(result)
        deleted = db.clear_cointegration_cache(bond1, bond2)
        assert isinstance(deleted, int)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
