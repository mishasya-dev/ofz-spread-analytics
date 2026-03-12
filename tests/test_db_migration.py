"""
Тесты миграции с core/database.py на core/db/facade.py

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
def old_db():
    """Старый DatabaseManager"""
    from core.database import DatabaseManager, init_database
    init_database()
    return DatabaseManager()


@pytest.fixture
def new_db():
    """Новый DatabaseFacade"""
    from core.db import get_db_facade, init_database
    init_database()
    return get_db_facade()


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
# ТЕСТЫ СОВМЕСТИМОСТИ
# ============================================

class TestBondsCompatibility:
    """Тесты совместимости методов облигаций"""

    def test_save_bond(self, old_db, new_db, sample_bond_data):
        """save_bond возвращает bool"""
        isin = sample_bond_data['isin']
        
        # Старый
        old_result = old_db.save_bond(sample_bond_data)
        assert isinstance(old_result, bool)
        assert old_result is True
        
        # Новый
        new_result = new_db.save_bond(sample_bond_data)
        assert isinstance(new_result, bool)
        assert new_result is True

    def test_load_bond(self, old_db, new_db, sample_bond_data):
        """load_bond возвращает Dict или None"""
        isin = sample_bond_data['isin']
        
        # Сначала сохраняем
        old_db.save_bond(sample_bond_data)
        
        # Старый
        old_bond = old_db.load_bond(isin)
        assert old_bond is not None
        assert old_bond['isin'] == isin
        
        # Новый
        new_bond = new_db.load_bond(isin)
        assert new_bond is not None
        assert new_bond['isin'] == isin

    def test_get_favorite_bonds(self, old_db, new_db, sample_bond_data):
        """get_favorite_bonds возвращает List[Dict]"""
        # Сохраняем избранную облигацию
        sample_bond_data['is_favorite'] = 1
        old_db.save_bond(sample_bond_data)
        
        # Старый
        old_favorites = old_db.get_favorite_bonds()
        assert isinstance(old_favorites, list)
        
        # Новый
        new_favorites = new_db.get_favorite_bonds()
        assert isinstance(new_favorites, list)

    def test_get_favorite_bonds_as_config(self, old_db, new_db, sample_bond_data):
        """get_favorite_bonds_as_config возвращает Dict"""
        sample_bond_data['is_favorite'] = 1
        old_db.save_bond(sample_bond_data)
        
        # Старый
        old_config = old_db.get_favorite_bonds_as_config()
        assert isinstance(old_config, dict)
        
        # Новый
        new_config = new_db.get_favorite_bonds_as_config()
        assert isinstance(new_config, dict)


class TestYTMCompatibility:
    """Тесты совместимости методов YTM"""

    def test_save_daily_ytm(self, old_db, new_db, sample_daily_ytm):
        """save_daily_ytm возвращает int"""
        isin = 'TEST_DAILY_YTM_001'
        
        # Старый
        old_count = old_db.save_daily_ytm(isin, sample_daily_ytm)
        assert isinstance(old_count, int)
        assert old_count > 0
        
        # Новый
        new_count = new_db.save_daily_ytm(isin, sample_daily_ytm)
        assert isinstance(new_count, int)
        assert new_count > 0

    def test_load_daily_ytm(self, old_db, new_db, sample_daily_ytm):
        """load_daily_ytm возвращает DataFrame"""
        isin = 'TEST_DAILY_YTM_002'
        
        old_db.save_daily_ytm(isin, sample_daily_ytm)
        
        # Старый
        old_df = old_db.load_daily_ytm(isin)
        assert isinstance(old_df, pd.DataFrame)
        assert len(old_df) > 0
        
        # Новый
        new_df = new_db.load_daily_ytm(isin)
        assert isinstance(new_df, pd.DataFrame)
        assert len(new_df) > 0

    def test_get_last_daily_ytm_date(self, old_db, new_db, sample_daily_ytm):
        """get_last_daily_ytm_date возвращает date или None"""
        isin = 'TEST_DAILY_YTM_003'
        
        old_db.save_daily_ytm(isin, sample_daily_ytm)
        
        # Старый
        old_date = old_db.get_last_daily_ytm_date(isin)
        assert old_date is None or isinstance(old_date, date)
        
        # Новый
        new_date = new_db.get_last_daily_ytm_date(isin)
        assert new_date is None or isinstance(new_date, date)

    def test_save_intraday_ytm(self, old_db, new_db, sample_intraday_ytm):
        """save_intraday_ytm возвращает int"""
        isin = 'TEST_INTRADAY_YTM_001'
        interval = '60'
        
        # Старый
        old_count = old_db.save_intraday_ytm(isin, interval, sample_intraday_ytm)
        assert isinstance(old_count, int)
        assert old_count > 0
        
        # Новый
        new_count = new_db.save_intraday_ytm(isin, interval, sample_intraday_ytm)
        assert isinstance(new_count, int)
        assert new_count > 0

    def test_load_intraday_ytm(self, old_db, new_db, sample_intraday_ytm):
        """load_intraday_ytm возвращает DataFrame"""
        isin = 'TEST_INTRADAY_YTM_002'
        interval = '60'
        
        old_db.save_intraday_ytm(isin, interval, sample_intraday_ytm)
        
        # Старый
        old_df = old_db.load_intraday_ytm(isin, interval)
        assert isinstance(old_df, pd.DataFrame)
        assert len(old_df) > 0
        
        # Новый
        new_df = new_db.load_intraday_ytm(isin, interval)
        assert isinstance(new_df, pd.DataFrame)
        assert len(new_df) > 0

    def test_get_last_intraday_ytm_datetime(self, old_db, new_db, sample_intraday_ytm):
        """get_last_intraday_ytm_datetime возвращает datetime или None"""
        isin = 'TEST_INTRADAY_YTM_003'
        interval = '60'
        
        old_db.save_intraday_ytm(isin, interval, sample_intraday_ytm)
        
        # Старый
        old_dt = old_db.get_last_intraday_ytm_datetime(isin, interval)
        assert old_dt is None or isinstance(old_dt, datetime)
        
        # Новый
        new_dt = new_db.get_last_intraday_ytm_datetime(isin, interval)
        assert new_dt is None or isinstance(new_dt, datetime)


class TestStatsCompatibility:
    """Тесты совместимости статистики"""

    def test_get_stats(self, old_db, new_db):
        """get_stats возвращает Dict с ожидаемыми ключами"""
        # Старый
        old_stats = old_db.get_stats()
        assert isinstance(old_stats, dict)
        assert 'bonds_count' in old_stats
        assert 'daily_ytm_count' in old_stats
        assert 'intraday_ytm_count' in old_stats
        
        # Новый
        new_stats = new_db.get_stats()
        assert isinstance(new_stats, dict)
        assert 'bonds_count' in new_stats
        assert 'daily_ytm_count' in new_stats
        assert 'intraday_ytm_count' in new_stats


class TestMigrationCompatibility:
    """Тесты миграции облигаций"""

    def test_migrate_config_bonds(self, old_db, new_db):
        """migrate_config_bonds возвращает int"""
        from config import BondConfig
        
        bonds_config = {
            'TEST_MIGRATION_001': BondConfig(
                isin='TEST_MIGRATION_001',
                name='Тест',
                maturity_date='2030-01-01',
                coupon_rate=7.5
            )
        }
        
        # Старый
        old_count = old_db.migrate_config_bonds(bonds_config)
        assert isinstance(old_count, int)
        assert old_count >= 0
        
        # Новый
        new_count = new_db.migrate_config_bonds(bonds_config)
        assert isinstance(new_count, int)
        assert new_count >= 0


class TestCointegrationCompatibility:
    """Тесты совместимости кэша коинтеграции"""

    def test_save_and_load_cointegration(self, old_db, new_db):
        """Проверка сохранения и загрузки коинтеграции"""
        bond1 = 'TEST_COINT_001'
        bond2 = 'TEST_COINT_002'
        period_days = 365
        
        result = {
            'is_cointegrated': True,
            'pvalue': 0.03,
            'half_life': 10.5,
            'hedge_ratio': 0.95,
            'data_days': 365,
            'adf_bond1_pvalue': 0.5,
            'adf_bond2_pvalue': 0.6,
            'both_nonstationary': True,
        }
        
        # Старый API
        old_db.save_cointegration_cache(bond1, bond2, period_days, result)
        old_cached = old_db.get_cointegration_cache(bond1, bond2, period_days)
        assert old_cached is not None
        assert old_cached['is_cointegrated'] == True
        
        # Новый API
        new_result = {
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
        new_db.save_cointegration_result(new_result)
        new_cached = new_db.load_cointegration_result(bond1, bond2)
        assert new_cached is not None
        assert new_cached['is_cointegrated'] == True

    def test_clear_cointegration_cache(self, old_db, new_db):
        """Проверка очистки кэша коинтеграции"""
        bond1 = 'TEST_CLEAR_001'
        bond2 = 'TEST_CLEAR_002'
        period_days = 365
        
        result = {'is_cointegrated': False, 'pvalue': 0.5}
        
        # Сохраняем
        old_db.save_cointegration_cache(bond1, bond2, period_days, result)
        
        # Старый API
        old_deleted = old_db.clear_cointegration_cache(bond1, bond2, period_days)
        assert isinstance(old_deleted, int)
        
        # Новый API (если метод есть)
        if hasattr(new_db, 'clear_cointegration_cache'):
            new_deleted = new_db.clear_cointegration_cache(bond1, bond2, period_days)
            assert isinstance(new_deleted, int)


# ============================================
# ТЕСТЫ РАВЕНСТВА РЕЗУЛЬТАТОВ
# ============================================

class TestResultsEquality:
    """Тесты что оба API возвращают одинаковые результаты"""

    def test_bond_data_equality(self, old_db, new_db, sample_bond_data):
        """Данные облигации одинаковы"""
        isin = sample_bond_data['isin']
        
        old_db.save_bond(sample_bond_data)
        
        old_bond = old_db.load_bond(isin)
        new_bond = new_db.load_bond(isin)
        
        # Ключевые поля должны совпадать
        assert old_bond['isin'] == new_bond['isin']
        assert old_bond['name'] == new_bond['name']
        assert old_bond['coupon_rate'] == new_bond['coupon_rate']

    def test_daily_ytm_equality(self, old_db, new_db, sample_daily_ytm):
        """Данные YTM одинаковы"""
        isin = 'TEST_EQUALITY_YTM_001'
        
        old_db.save_daily_ytm(isin, sample_daily_ytm)
        
        old_df = old_db.load_daily_ytm(isin)
        new_df = new_db.load_daily_ytm(isin)
        
        # Количество записей должно совпадать
        assert len(old_df) == len(new_df)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
