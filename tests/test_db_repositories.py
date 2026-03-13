"""
Тесты для репозиториев БД с контекстными менеджерами

Модуль тестирует:
- get_db_connection - контекстный менеджер для соединения
- get_db_cursor - контекстный менеджер для курсора  
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
from contextlib import contextmanager

# Мок streamlit до импорта
import sys
sys.modules['streamlit'] = MagicMock()


# ============================================
# Fixtures
# ============================================

@pytest.fixture
def temp_db_path():
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
            volume REAL,
            value REAL,
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
def mock_db(temp_db_path):
    """Мокирование БД через патч DB_PATH"""
    import core.db.connection as db_module
    original_path = db_module.DB_PATH
    db_module.DB_PATH = temp_db_path
    
    yield temp_db_path
    
    db_module.DB_PATH = original_path


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
        'accrued_interest': [25.0] * 10,
        'volume': [1000 + i * 100 for i in range(10)],
        'value': [950000 + i * 10000 for i in range(10)]
    }, index=dates)


# ============================================
# TestContextManagers - тесты контекстных менеджеров
# ============================================

class TestContextManagers:
    """Тесты контекстных менеджеров БД"""
    
    def test_get_db_connection_basic(self, mock_db):
        """Базовое использование get_db_connection"""
        from core.db.connection import get_db_connection
        
        with get_db_connection() as conn:
            assert conn is not None
            cursor = conn.cursor()
            cursor.execute('SELECT 1 as value')
            row = cursor.fetchone()
            assert row['value'] == 1
    
    def test_get_db_connection_auto_close(self, mock_db):
        """Автоматическое закрытие соединения"""
        from core.db.connection import get_db_connection
        
        conn_ref = None
        with get_db_connection() as conn:
            conn_ref = conn
            cursor = conn.cursor()
            cursor.execute('SELECT 1')
        
        # После выхода из контекста соединение закрыто
        with pytest.raises(sqlite3.ProgrammingError):
            conn_ref.execute('SELECT 1')
    
    def test_get_db_connection_commit_on_success(self, mock_db):
        """Автоматический commit при успешном выходе"""
        from core.db.connection import get_db_connection
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO bonds (isin, name) VALUES (?, ?)",
                ('TEST001', 'Test Bond')
            )
        
        # Проверяем, что данные сохранены
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM bonds WHERE isin = ?", ('TEST001',))
            row = cursor.fetchone()
            assert row is not None
            assert row['name'] == 'Test Bond'
    
    def test_get_db_connection_rollback_on_error(self, mock_db):
        """Rollback при исключении"""
        from core.db.connection import get_db_connection
        
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO bonds (isin, name) VALUES (?, ?)",
                    ('TEST002', 'Test Bond 2')
                )
                raise ValueError("Test exception")
        except ValueError:
            pass
        
        # Данные должны быть откачены
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM bonds WHERE isin = ?", ('TEST002',))
            row = cursor.fetchone()
            assert row is None
    
    def test_get_db_cursor_basic(self, mock_db):
        """Базовое использование get_db_cursor"""
        from core.db.connection import get_db_cursor
        
        with get_db_cursor() as cursor:
            cursor.execute('SELECT 1 as value')
            row = cursor.fetchone()
            assert row['value'] == 1


# ============================================
# TestBondsRepository
# ============================================

class TestBondsRepository:
    """Тесты BondsRepository"""
    
    def test_save_bond(self, mock_db, sample_bond_data):
        """Сохранение облигации"""
        from core.db.bonds_repo import BondsRepository
        repo = BondsRepository()
        
        result = repo.save(sample_bond_data)
        
        assert result is True
    
    def test_load_bond(self, mock_db, sample_bond_data):
        """Загрузка облигации"""
        from core.db.bonds_repo import BondsRepository
        repo = BondsRepository()
        
        # Сначала сохраняем
        repo.save(sample_bond_data)
        
        # Затем загружаем
        loaded = repo.load(sample_bond_data['isin'])
        
        assert loaded is not None
        assert loaded['isin'] == sample_bond_data['isin']
        assert loaded['name'] == sample_bond_data['name']
    
    def test_load_nonexistent_bond(self, mock_db):
        """Загрузка несуществующей облигации"""
        from core.db.bonds_repo import BondsRepository
        repo = BondsRepository()
        
        loaded = repo.load('NOTEXIST')
        
        assert loaded is None
    
    def test_get_all(self, mock_db, sample_bond_data):
        """Получение всех облигаций"""
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
    
    def test_get_favorites(self, mock_db, sample_bond_data):
        """Получение избранных облигаций"""
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
    
    def test_set_favorite(self, mock_db, sample_bond_data):
        """Установка флага избранного"""
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
    
    def test_count(self, mock_db, sample_bond_data):
        """Подсчёт облигаций"""
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
    
    def test_save_daily_ytm(self, mock_db, sample_daily_ytm_df):
        """Сохранение дневных YTM"""
        from core.db.ytm_repo import YTMRepository
        repo = YTMRepository()
        
        isin = 'RU000A1038V6'
        count = repo.save_daily_ytm(isin, sample_daily_ytm_df)
        
        assert count == 10
    
    def test_load_daily_ytm(self, mock_db, sample_daily_ytm_df):
        """Загрузка дневных YTM"""
        from core.db.ytm_repo import YTMRepository
        repo = YTMRepository()
        
        isin = 'RU000A1038V6'
        repo.save_daily_ytm(isin, sample_daily_ytm_df)
        
        loaded = repo.load_daily_ytm(isin)
        
        assert len(loaded) == 10
        assert 'ytm' in loaded.columns
    
    def test_get_last_daily_ytm_date(self, mock_db, sample_daily_ytm_df):
        """Получение последней даты дневных YTM"""
        from core.db.ytm_repo import YTMRepository
        repo = YTMRepository()
        
        isin = 'RU000A1038V6'
        repo.save_daily_ytm(isin, sample_daily_ytm_df)
        
        last_date = repo.get_last_daily_ytm_date(isin)
        
        assert last_date == date(2026, 2, 10)
    
    def test_save_intraday_ytm(self, mock_db, sample_intraday_ytm_df):
        """Сохранение intraday YTM"""
        from core.db.ytm_repo import YTMRepository
        repo = YTMRepository()
        
        isin = 'RU000A1038V6'
        count = repo.save_intraday_ytm(isin, '60', sample_intraday_ytm_df)
        
        assert count == 10
    
    def test_load_intraday_ytm(self, mock_db, sample_intraday_ytm_df):
        """Загрузка intraday YTM"""
        from core.db.ytm_repo import YTMRepository
        repo = YTMRepository()
        
        isin = 'RU000A1038V6'
        repo.save_intraday_ytm(isin, '60', sample_intraday_ytm_df)
        
        loaded = repo.load_intraday_ytm(isin, '60')
        
        assert len(loaded) == 10
        assert 'ytm_close' in loaded.columns
    
    def test_count_daily_ytm(self, mock_db, sample_daily_ytm_df):
        """Подсчёт дневных YTM"""
        from core.db.ytm_repo import YTMRepository
        repo = YTMRepository()
        
        isin = 'RU000A1038V6'
        
        assert repo.count_daily_ytm() == 0
        
        repo.save_daily_ytm(isin, sample_daily_ytm_df)
        assert repo.count_daily_ytm() == 10
    
    def test_count_intraday_ytm(self, mock_db, sample_intraday_ytm_df):
        """Подсчёт intraday YTM"""
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
    
    def test_save_spread(self, mock_db):
        """Сохранение спреда"""
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
    
    def test_save_spreads_batch(self, mock_db):
        """Пакетное сохранение спредов"""
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
    
    def test_load_spreads(self, mock_db):
        """Загрузка спредов"""
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
    
    def test_count_spreads(self, mock_db):
        """Подсчёт спредов"""
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
    
    def test_count_by_mode(self, mock_db):
        """Подсчёт спредов по режимам"""
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


# ============================================
# Run tests directly
# ============================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
