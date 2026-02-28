"""
Тесты для репозиториев БД

Модуль тестирует:
- BondsRepository
- YTMRepository
- SpreadsRepository
"""
import pytest
import pandas as pd
from datetime import date, datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
import sqlite3
import tempfile
import os

# Мок streamlit до импорта
import sys
sys.modules['streamlit'] = MagicMock()


# ============================================
# Fixtures
# ============================================

@pytest.fixture
def temp_db():
    """Временная БД для тестов"""
    fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    
    # Создаём таблицы
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Таблица bonds
    cursor.execute('''
        CREATE TABLE bonds (
            isin TEXT PRIMARY KEY,
            name TEXT,
            short_name TEXT,
            coupon_rate REAL,
            maturity_date TEXT,
            issue_date TEXT,
            face_value REAL DEFAULT 1000,
            coupon_frequency INTEGER DEFAULT 2,
            day_count TEXT DEFAULT 'ACT/ACT',
            is_favorite INTEGER DEFAULT 0,
            last_price REAL,
            last_ytm REAL,
            duration_years REAL,
            duration_days REAL,
            last_trade_date TEXT,
            last_updated TEXT
        )
    ''')
    
    # Таблица daily_ytm
    cursor.execute('''
        CREATE TABLE daily_ytm (
            isin TEXT,
            date TEXT,
            ytm REAL,
            price REAL,
            duration_days REAL,
            PRIMARY KEY (isin, date)
        )
    ''')
    
    # Таблица intraday_ytm
    cursor.execute('''
        CREATE TABLE intraday_ytm (
            isin TEXT,
            interval TEXT,
            datetime TEXT,
            price_close REAL,
            ytm REAL,
            accrued_interest REAL,
            PRIMARY KEY (isin, interval, datetime)
        )
    ''')
    
    # Таблица spreads
    cursor.execute('''
        CREATE TABLE spreads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            isin_1 TEXT,
            isin_2 TEXT,
            mode TEXT,
            interval TEXT,
            datetime TEXT,
            ytm_1 REAL,
            ytm_2 REAL,
            spread_bp REAL,
            signal TEXT,
            p25 REAL,
            p75 REAL,
            UNIQUE(isin_1, isin_2, mode, interval, datetime)
        )
    ''')
    
    conn.commit()
    conn.close()
    
    yield db_path
    
    # Cleanup
    if os.path.exists(db_path):
        os.unlink(db_path)


@pytest.fixture
def mock_connection(temp_db):
    """Мок соединения с БД"""
    def get_conn():
        conn = sqlite3.connect(temp_db)
        conn.row_factory = sqlite3.Row
        return conn
    return get_conn


@pytest.fixture
def sample_bond_data():
    """Тестовые данные облигации"""
    return {
        'isin': 'RU000A1038V6',
        'name': 'ОФЗ 26240',
        'short_name': 'ОФЗ 26240',
        'coupon_rate': 7.10,
        'maturity_date': '2046-05-15',
        'issue_date': '2016-05-18',
        'face_value': 1000,
        'coupon_frequency': 2,
        'day_count': 'ACT/ACT',
        'is_favorite': 1,
    }


@pytest.fixture
def sample_daily_ytm_df():
    """DataFrame с тестовыми дневными YTM"""
    dates = pd.date_range(
        start='2026-02-01',
        periods=10,
        freq='D'
    )
    return pd.DataFrame({
        'ytm': [14.5 + i * 0.1 for i in range(10)],
        'price': [95.0 + i * 0.1 for i in range(10)],
        'duration_days': [7000 - i * 10 for i in range(10)]
    }, index=dates)


@pytest.fixture
def sample_intraday_ytm_df():
    """DataFrame с тестовыми intraday YTM"""
    dates = pd.date_range(
        start='2026-02-20 10:00:00',
        periods=10,
        freq='h'
    )
    return pd.DataFrame({
        'close': [95.0 + i * 0.1 for i in range(10)],
        'ytm_close': [14.5 + i * 0.01 for i in range(10)],
        'accrued_interest': [25.0] * 10
    }, index=dates)


# ============================================
# TestBondsRepository
# ============================================

class TestBondsRepository:
    """Тесты BondsRepository"""
    
    @patch('core.db.bonds_repo.get_connection')
    def test_save_bond(self, mock_get_conn, mock_connection, sample_bond_data):
        """Сохранение облигации"""
        mock_get_conn.side_effect = mock_connection
        
        from core.db.bonds_repo import BondsRepository
        repo = BondsRepository()
        
        result = repo.save(sample_bond_data)
        
        assert result is True
    
    @patch('core.db.bonds_repo.get_connection')
    def test_load_bond(self, mock_get_conn, mock_connection, sample_bond_data):
        """Загрузка облигации"""
        mock_get_conn.side_effect = mock_connection
        
        from core.db.bonds_repo import BondsRepository
        repo = BondsRepository()
        
        # Сначала сохраняем
        repo.save(sample_bond_data)
        
        # Затем загружаем
        loaded = repo.load(sample_bond_data['isin'])
        
        assert loaded is not None
        assert loaded['isin'] == sample_bond_data['isin']
        assert loaded['name'] == sample_bond_data['name']
    
    @patch('core.db.bonds_repo.get_connection')
    def test_load_nonexistent_bond(self, mock_get_conn, mock_connection):
        """Загрузка несуществующей облигации"""
        mock_get_conn.side_effect = mock_connection
        
        from core.db.bonds_repo import BondsRepository
        repo = BondsRepository()
        
        loaded = repo.load('NOTEXIST')
        
        assert loaded is None
    
    @patch('core.db.bonds_repo.get_connection')
    def test_get_all(self, mock_get_conn, mock_connection, sample_bond_data):
        """Получение всех облигаций"""
        mock_get_conn.side_effect = mock_connection
        
        from core.db.bonds_repo import BondsRepository
        repo = BondsRepository()
        
        # Сохраняем 2 облигации
        repo.save(sample_bond_data)
        bond2 = sample_bond_data.copy()
        bond2['isin'] = 'RU000A1038V7'
        bond2['name'] = 'ОФЗ 26241'
        repo.save(bond2)
        
        all_bonds = repo.get_all()
        
        assert len(all_bonds) == 2
    
    @patch('core.db.bonds_repo.get_connection')
    def test_get_favorites(self, mock_get_conn, mock_connection, sample_bond_data):
        """Получение избранных облигаций"""
        mock_get_conn.side_effect = mock_connection
        
        from core.db.bonds_repo import BondsRepository
        repo = BondsRepository()
        
        # Сохраняем облигацию как избранную
        sample_bond_data['is_favorite'] = 1
        repo.save(sample_bond_data)
        
        # Сохраняем вторую как не избранную
        bond2 = sample_bond_data.copy()
        bond2['isin'] = 'RU000A1038V7'
        bond2['name'] = 'ОФЗ 26241'
        bond2['is_favorite'] = 0
        repo.save(bond2)
        
        favorites = repo.get_favorites()
        
        assert len(favorites) == 1
        assert favorites[0]['isin'] == sample_bond_data['isin']
    
    @patch('core.db.bonds_repo.get_connection')
    def test_set_favorite(self, mock_get_conn, mock_connection, sample_bond_data):
        """Установка флага избранного"""
        mock_get_conn.side_effect = mock_connection
        
        from core.db.bonds_repo import BondsRepository
        repo = BondsRepository()
        
        # Сохраняем без флага
        sample_bond_data['is_favorite'] = 0
        repo.save(sample_bond_data)
        
        # Устанавливаем флаг
        result = repo.set_favorite(sample_bond_data['isin'], True)
        
        assert result is True
        
        # Проверяем
        loaded = repo.load(sample_bond_data['isin'])
        assert loaded['is_favorite'] == 1
    
    @patch('core.db.bonds_repo.get_connection')
    def test_update_market_data(self, mock_get_conn, mock_connection, sample_bond_data):
        """Обновление рыночных данных"""
        mock_get_conn.side_effect = mock_connection
        
        from core.db.bonds_repo import BondsRepository
        repo = BondsRepository()
        
        repo.save(sample_bond_data)
        
        result = repo.update_market_data(
            isin=sample_bond_data['isin'],
            last_price=96.5,
            last_ytm=14.8,
            duration_years=15.5,
            duration_days=5600
        )
        
        assert result is True
        
        loaded = repo.load(sample_bond_data['isin'])
        assert loaded['last_price'] == 96.5
        assert loaded['last_ytm'] == 14.8
    
    @patch('core.db.bonds_repo.get_connection')
    def test_delete_bond(self, mock_get_conn, mock_connection, sample_bond_data):
        """Удаление облигации"""
        mock_get_conn.side_effect = mock_connection
        
        from core.db.bonds_repo import BondsRepository
        repo = BondsRepository()
        
        repo.save(sample_bond_data)
        
        result = repo.delete(sample_bond_data['isin'])
        
        assert result is True
        
        loaded = repo.load(sample_bond_data['isin'])
        assert loaded is None
    
    @patch('core.db.bonds_repo.get_connection')
    def test_count(self, mock_get_conn, mock_connection, sample_bond_data):
        """Подсчёт облигаций"""
        mock_get_conn.side_effect = mock_connection
        
        from core.db.bonds_repo import BondsRepository
        repo = BondsRepository()
        
        assert repo.count() == 0
        
        repo.save(sample_bond_data)
        assert repo.count() == 1


# ============================================
# TestYTMRepository
# ============================================

class TestYTMRepository:
    """Тесты YTMRepository"""
    
    @patch('core.db.ytm_repo.get_connection')
    def test_save_daily_ytm(self, mock_get_conn, mock_connection, sample_daily_ytm_df):
        """Сохранение дневных YTM"""
        mock_get_conn.side_effect = mock_connection
        
        from core.db.ytm_repo import YTMRepository
        repo = YTMRepository()
        
        isin = 'RU000A1038V6'
        count = repo.save_daily_ytm(isin, sample_daily_ytm_df)
        
        assert count == 10
    
    @patch('core.db.ytm_repo.get_connection')
    def test_load_daily_ytm(self, mock_get_conn, mock_connection, sample_daily_ytm_df):
        """Загрузка дневных YTM"""
        mock_get_conn.side_effect = mock_connection
        
        from core.db.ytm_repo import YTMRepository
        repo = YTMRepository()
        
        isin = 'RU000A1038V6'
        repo.save_daily_ytm(isin, sample_daily_ytm_df)
        
        loaded = repo.load_daily_ytm(isin)
        
        assert len(loaded) == 10
        assert 'ytm' in loaded.columns
    
    @patch('core.db.ytm_repo.get_connection')
    def test_load_daily_ytm_with_date_filter(self, mock_get_conn, mock_connection, sample_daily_ytm_df):
        """Загрузка дневных YTM с фильтром по датам"""
        mock_get_conn.side_effect = mock_connection
        
        from core.db.ytm_repo import YTMRepository
        repo = YTMRepository()
        
        isin = 'RU000A1038V6'
        repo.save_daily_ytm(isin, sample_daily_ytm_df)
        
        # Загружаем только последние 5 дней
        loaded = repo.load_daily_ytm(
            isin,
            start_date=date(2026, 2, 6),
            end_date=date(2026, 2, 10)
        )
        
        assert len(loaded) == 5
    
    @patch('core.db.ytm_repo.get_connection')
    def test_get_last_daily_ytm_date(self, mock_get_conn, mock_connection, sample_daily_ytm_df):
        """Получение последней даты дневных YTM"""
        mock_get_conn.side_effect = mock_connection
        
        from core.db.ytm_repo import YTMRepository
        repo = YTMRepository()
        
        isin = 'RU000A1038V6'
        repo.save_daily_ytm(isin, sample_daily_ytm_df)
        
        last_date = repo.get_last_daily_ytm_date(isin)
        
        assert last_date == date(2026, 2, 10)
    
    @patch('core.db.ytm_repo.get_connection')
    def test_save_intraday_ytm(self, mock_get_conn, mock_connection, sample_intraday_ytm_df):
        """Сохранение intraday YTM"""
        mock_get_conn.side_effect = mock_connection
        
        from core.db.ytm_repo import YTMRepository
        repo = YTMRepository()
        
        isin = 'RU000A1038V6'
        count = repo.save_intraday_ytm(isin, '60', sample_intraday_ytm_df)
        
        assert count == 10
    
    @patch('core.db.ytm_repo.get_connection')
    def test_load_intraday_ytm(self, mock_get_conn, mock_connection, sample_intraday_ytm_df):
        """Загрузка intraday YTM"""
        mock_get_conn.side_effect = mock_connection
        
        from core.db.ytm_repo import YTMRepository
        repo = YTMRepository()
        
        isin = 'RU000A1038V6'
        repo.save_intraday_ytm(isin, '60', sample_intraday_ytm_df)
        
        loaded = repo.load_intraday_ytm(isin, '60')
        
        assert len(loaded) == 10
        assert 'ytm_close' in loaded.columns
    
    @patch('core.db.ytm_repo.get_connection')
    def test_count_daily_ytm(self, mock_get_conn, mock_connection, sample_daily_ytm_df):
        """Подсчёт дневных YTM"""
        mock_get_conn.side_effect = mock_connection
        
        from core.db.ytm_repo import YTMRepository
        repo = YTMRepository()
        
        isin = 'RU000A1038V6'
        
        assert repo.count_daily_ytm() == 0
        
        repo.save_daily_ytm(isin, sample_daily_ytm_df)
        assert repo.count_daily_ytm() == 10
    
    @patch('core.db.ytm_repo.get_connection')
    def test_count_intraday_ytm(self, mock_get_conn, mock_connection, sample_intraday_ytm_df):
        """Подсчёт intraday YTM"""
        mock_get_conn.side_effect = mock_connection
        
        from core.db.ytm_repo import YTMRepository
        repo = YTMRepository()
        
        isin = 'RU000A1038V6'
        
        assert repo.count_intraday_ytm() == 0
        
        repo.save_intraday_ytm(isin, '60', sample_intraday_ytm_df)
        assert repo.count_intraday_ytm() == 10


# ============================================
# TestSpreadsRepository
# ============================================

class TestSpreadsRepository:
    """Тесты SpreadsRepository"""
    
    @patch('core.db.spreads_repo.get_connection')
    def test_save_spread(self, mock_get_conn, mock_connection):
        """Сохранение спреда"""
        mock_get_conn.side_effect = mock_connection
        
        from core.db.spreads_repo import SpreadsRepository
        repo = SpreadsRepository()
        
        spread_id = repo.save_spread(
            isin_1='RU000A1038V6',
            isin_2='RU000A1038V7',
            mode='daily',
            datetime_val='2026-02-20',
            ytm_1=14.5,
            ytm_2=15.0,
            spread_bp=50.0,
            signal='NEUTRAL'
        )
        
        assert spread_id > 0
    
    @patch('core.db.spreads_repo.get_connection')
    def test_save_spreads_batch(self, mock_get_conn, mock_connection):
        """Пакетное сохранение спредов"""
        mock_get_conn.side_effect = mock_connection
        
        from core.db.spreads_repo import SpreadsRepository
        repo = SpreadsRepository()
        
        dates = pd.date_range(start='2026-02-01', periods=10, freq='D')
        df = pd.DataFrame({
            'ytm_1': [14.5] * 10,
            'ytm_2': [15.0] * 10,
            'spread': [50.0] * 10,
            'signal': ['NEUTRAL'] * 10
        }, index=dates)
        
        count = repo.save_spreads_batch(
            isin_1='RU000A1038V6',
            isin_2='RU000A1038V7',
            mode='daily',
            df=df
        )
        
        assert count == 10
    
    @patch('core.db.spreads_repo.get_connection')
    def test_load_spreads(self, mock_get_conn, mock_connection):
        """Загрузка спредов"""
        mock_get_conn.side_effect = mock_connection
        
        from core.db.spreads_repo import SpreadsRepository
        repo = SpreadsRepository()
        
        # Сначала сохраняем
        dates = pd.date_range(start='2026-02-01', periods=10, freq='D')
        df = pd.DataFrame({
            'ytm_1': [14.5] * 10,
            'ytm_2': [15.0] * 10,
            'spread': [50.0 + i for i in range(10)],
            'signal': ['NEUTRAL'] * 10
        }, index=dates)
        
        repo.save_spreads_batch(
            isin_1='RU000A1038V6',
            isin_2='RU000A1038V7',
            mode='daily',
            df=df
        )
        
        # Загружаем
        loaded = repo.load_spreads(
            isin_1='RU000A1038V6',
            isin_2='RU000A1038V7',
            mode='daily'
        )
        
        assert len(loaded) == 10
        assert 'spread_bp' in loaded.columns
    
    @patch('core.db.spreads_repo.get_connection')
    def test_count_spreads(self, mock_get_conn, mock_connection):
        """Подсчёт спредов"""
        mock_get_conn.side_effect = mock_connection
        
        from core.db.spreads_repo import SpreadsRepository
        repo = SpreadsRepository()
        
        assert repo.count_spreads() == 0
        
        repo.save_spread(
            isin_1='RU000A1038V6',
            isin_2='RU000A1038V7',
            mode='daily',
            datetime_val='2026-02-20',
            ytm_1=14.5,
            ytm_2=15.0,
            spread_bp=50.0
        )
        
        assert repo.count_spreads() == 1
    
    @patch('core.db.spreads_repo.get_connection')
    def test_count_by_mode(self, mock_get_conn, mock_connection):
        """Подсчёт спредов по режимам"""
        mock_get_conn.side_effect = mock_connection
        
        from core.db.spreads_repo import SpreadsRepository
        repo = SpreadsRepository()
        
        # Сохраняем в разных режимах
        repo.save_spread(
            isin_1='RU000A1038V6',
            isin_2='RU000A1038V7',
            mode='daily',
            datetime_val='2026-02-20',
            ytm_1=14.5,
            ytm_2=15.0,
            spread_bp=50.0
        )
        
        repo.save_spread(
            isin_1='RU000A1038V6',
            isin_2='RU000A1038V7',
            mode='intraday',
            interval='60',
            datetime_val='2026-02-20 10:00:00',
            ytm_1=14.5,
            ytm_2=15.0,
            spread_bp=50.0
        )
        
        counts = repo.count_by_mode()
        
        assert counts.get('daily', 0) == 1
        assert counts.get('intraday', 0) == 1
