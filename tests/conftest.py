"""
Конфигурация pytest для тестов OFZ Analytics
"""
import sys
import os
import tempfile
import pytest

# Добавляем путь к родительской директории для импортов
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Проверяем, установлен ли streamlit
try:
    import streamlit
except ImportError:
    # Используем mock
    from tests.mock_streamlit import st_mock
    sys.modules['streamlit'] = st_mock


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def isolated_db():
    """
    Создаёт временную БД для каждого теста.
    
    Гарантирует изоляцию между тестами.
    Использование:
    
    def test_something(isolated_db):
        # isolated_db - путь к временной БД
        os.environ['DATABASE_PATH'] = isolated_db
        ...
    """
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    
    # Устанавливаем путь к БД
    old_path = os.environ.get('DATABASE_PATH')
    os.environ['DATABASE_PATH'] = db_path
    
    yield db_path
    
    # Очищаем
    if old_path:
        os.environ['DATABASE_PATH'] = old_path
    elif 'DATABASE_PATH' in os.environ:
        del os.environ['DATABASE_PATH']
    
    if os.path.exists(db_path):
        os.unlink(db_path)


@pytest.fixture
def mock_db_facade():
    """
    Мок фасада БД для тестов.
    
    Возвращает MagicMock с преднастроенными методами.
    """
    from unittest.mock import MagicMock
    import pandas as pd
    from datetime import date, timedelta
    
    mock = MagicMock()
    
    # Дневные YTM
    mock.load_daily_ytm.return_value = pd.DataFrame()
    mock.save_daily_ytm.return_value = 10
    mock.get_last_daily_ytm_date.return_value = None
    
    # Intraday YTM
    mock.load_intraday_ytm.return_value = pd.DataFrame()
    mock.save_intraday_ytm.return_value = 5
    
    # Облигации
    mock.get_favorite_bonds_as_config.return_value = {}
    mock.save_favorite_bond.return_value = True
    
    return mock
