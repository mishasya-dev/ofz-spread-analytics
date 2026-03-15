"""
Тесты для services/data_loader.py

Проверяет:
- fetch_trading_data
- fetch_historical_data
- fetch_candle_data
- update_database_full
"""
import pytest
from unittest.mock import patch, MagicMock
import pandas as pd
from datetime import date, timedelta
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestFetchTradingData:
    """Тесты fetch_trading_data"""

    @patch('services.data_loader.get_trading_data')
    @patch('services.data_loader.MOEXClient')
    def test_returns_data(self, mock_client_class, mock_get_trading_data):
        """Возвращает данные от API"""
        mock_get_trading_data.return_value = {
            'secid': 'SU26224RMFS4',
            'price': 75.5,
            'yield': 16.5
        }
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_class.return_value = mock_client

        from services.data_loader import fetch_trading_data

        result = fetch_trading_data('SU26224RMFS4')

        assert result['secid'] == 'SU26224RMFS4'

    @patch('services.data_loader.get_trading_data')
    @patch('services.data_loader.MOEXClient')
    def test_handles_no_data(self, mock_client_class, mock_get_trading_data):
        """Обрабатывает отсутствие данных"""
        mock_get_trading_data.return_value = {'has_data': False}
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_class.return_value = mock_client

        from services.data_loader import fetch_trading_data

        result = fetch_trading_data('INVALID_ISIN')

        assert result.get('has_data') == False


class TestFetchHistoricalData:
    """Тесты fetch_historical_data"""

    @patch('core.db.get_db_facade')
    @patch('services.data_loader.fetch_ytm_history')
    @patch('services.data_loader.MOEXClient')
    def test_returns_from_db_when_fresh(self, mock_client_class, mock_fetch_history, mock_get_facade):
        """Возвращает из БД когда данные свежие"""
        # Мокаем БД
        mock_db = MagicMock()
        mock_df = pd.DataFrame({
            'ytm': [16.0, 16.1, 16.2]
        }, index=pd.date_range(date.today() - timedelta(days=3), periods=3))
        mock_db.load_daily_ytm.return_value = mock_df
        mock_db.get_last_daily_ytm_date.return_value = date.today()
        mock_get_facade.return_value = mock_db

        from services.data_loader import fetch_historical_data

        result = fetch_historical_data('SU26224RMFS4', days=10, use_cache=False)

        assert isinstance(result, pd.DataFrame)

    @patch('core.db.get_db_facade')
    @patch('services.data_loader.fetch_ytm_history')
    @patch('services.data_loader.MOEXClient')
    def test_fetches_from_api_when_db_empty(self, mock_client_class, mock_fetch_history, mock_get_facade):
        """Загружает с API когда БД пуста"""
        # Мокаем пустую БД
        mock_db = MagicMock()
        mock_db.load_daily_ytm.return_value = pd.DataFrame()
        mock_db.get_last_daily_ytm_date.return_value = None
        mock_db.save_daily_ytm.return_value = 10
        mock_get_facade.return_value = mock_db

        # Мокаем API
        mock_df = pd.DataFrame({
            'ytm': [16.0, 16.1, 16.2]
        }, index=pd.date_range(date.today() - timedelta(days=10), periods=10))
        mock_fetch_history.return_value = mock_df

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_class.return_value = mock_client

        from services.data_loader import fetch_historical_data

        result = fetch_historical_data('SU26224RMFS4', days=10, use_cache=False)

        assert len(result) == 10
        mock_fetch_history.assert_called_once()

    @patch('core.db.get_db_facade')
    @patch('services.data_loader.fetch_ytm_history')
    @patch('services.data_loader.MOEXClient')
    def test_returns_empty_on_api_error(self, mock_client_class, mock_fetch_history, mock_get_facade):
        """Возвращает пустой DataFrame при ошибке API"""
        mock_db = MagicMock()
        mock_db.load_daily_ytm.return_value = pd.DataFrame()
        mock_db.get_last_daily_ytm_date.return_value = None
        mock_get_facade.return_value = mock_db

        mock_fetch_history.return_value = pd.DataFrame()

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_class.return_value = mock_client

        from services.data_loader import fetch_historical_data

        result = fetch_historical_data('SU26224RMFS4', days=10, use_cache=False)

        assert result.empty


class TestFetchCandleData:
    """Тесты fetch_candle_data"""

    @patch('services.data_loader.BondYTMProcessor')
    @patch('core.db.get_db_facade')
    @patch('services.data_loader.fetch_candles')
    @patch('services.data_loader.MOEXClient')
    def test_returns_empty_when_no_candles(self, mock_client_class, mock_fetch_candles, mock_get_facade, mock_processor_class):
        """Возвращает пустой DataFrame когда нет свечей"""
        mock_fetch_candles.return_value = pd.DataFrame()
        mock_db = MagicMock()
        mock_db.load_intraday_ytm.return_value = pd.DataFrame()
        mock_get_facade.return_value = mock_db

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_class.return_value = mock_client

        from services.data_loader import fetch_candle_data

        result = fetch_candle_data(
            'SU26224RMFS4',
            {'isin': 'SU26224RMFS4', 'name': 'Test'},
            '60',
            1
        )

        assert result.empty


class TestUpdateDatabaseFull:
    """Тесты update_database_full"""

    @patch('services.data_loader.BondYTMProcessor')
    @patch('core.db.get_db_facade')
    @patch('services.data_loader.fetch_ytm_history')
    @patch('services.data_loader.fetch_candles')
    @patch('services.data_loader.MOEXClient')
    def test_returns_empty_when_no_bonds(self, mock_client_class, mock_fetch_candles, mock_fetch_history, mock_get_facade, mock_processor_class):
        """Возвращает ошибку когда нет облигаций"""
        from services.data_loader import update_database_full

        result = update_database_full(bonds_list=None)

        assert result['daily_ytm_saved'] == 0
        assert 'Нет облигаций' in result['errors']

    @patch('services.data_loader.BondYTMProcessor')
    @patch('core.db.get_db_facade')
    @patch('services.data_loader.fetch_ytm_history')
    @patch('services.data_loader.fetch_candles')
    @patch('services.data_loader.MOEXClient')
    def test_processes_bonds(self, mock_client_class, mock_fetch_candles, mock_fetch_history, mock_get_facade, mock_processor_class):
        """Обрабатывает список облигаций"""
        # Мокаем фасад БД
        mock_db = MagicMock()
        mock_db.save_daily_ytm.return_value = 10
        mock_db.save_intraday_ytm.return_value = 5
        mock_get_facade.return_value = mock_db

        # Мокаем API
        mock_df = pd.DataFrame({'ytm': [16.0]})
        mock_fetch_history.return_value = mock_df
        mock_fetch_candles.return_value = pd.DataFrame()

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_class.return_value = mock_client

        # Мокаем processor
        mock_processor = MagicMock()
        mock_processor.add_ytm_to_candles.return_value = pd.DataFrame()
        mock_processor_class.return_value = mock_processor

        from services.data_loader import update_database_full

        # Создаём mock bond
        bond = MagicMock()
        bond.isin = 'SU26224RMFS4'
        bond.name = 'Test Bond'

        result = update_database_full(bonds_list=[bond])

        assert result['daily_ytm_saved'] == 10
