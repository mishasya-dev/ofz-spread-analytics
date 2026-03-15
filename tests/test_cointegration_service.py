"""
Тесты для core/cointegration_service.py

Проверяет:
- CointegrationService
- Кэширование результатов
- Интеграцию с cointegration.py
"""
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestCointegrationServiceInit:
    """Тесты инициализации"""

    def test_initializes_with_default_ttl(self):
        """Инициализация с TTL по умолчанию"""
        with patch('core.cointegration_service.get_db_facade'):
            from core.cointegration_service import CointegrationService
            service = CointegrationService()
            assert service.ttl_hours == 24  # default

    def test_initializes_with_custom_ttl(self):
        """Инициализация с кастомным TTL"""
        with patch('core.cointegration_service.get_db_facade'):
            from core.cointegration_service import CointegrationService
            service = CointegrationService(ttl_hours=48)
            assert service.ttl_hours == 48


class TestGetOrCalculate:
    """Тесты get_or_calculate"""

    @patch('core.cointegration_service.get_db_facade')
    @patch('core.cointegration_service.CointegrationAnalyzer')
    def test_returns_cached_result(self, mock_analyzer_class, mock_get_facade):
        """Возвращает закэшированный результат"""
        # Мокаем фасад БД
        mock_db = MagicMock()
        mock_db.get_cointegration_cache.return_value = {
            'is_cointegrated': True,
            'p_value': 0.01
        }
        mock_get_facade.return_value = mock_db

        from core.cointegration_service import CointegrationService

        service = CointegrationService()
        ytm1 = pd.Series([10.0] * 100)
        ytm2 = pd.Series([9.5] * 100)

        result = service.get_or_calculate(
            'SU26224RMFS4', 'SU26225RMFS4', 100, ytm1, ytm2
        )

        assert result['from_cache'] == True
        assert result['is_cointegrated'] == True

    @patch('core.cointegration_service.get_db_facade')
    @patch('core.cointegration_service.CointegrationAnalyzer')
    def test_calculates_if_not_cached(self, mock_analyzer_class, mock_get_facade):
        """Вычисляет если нет в кэше"""
        # Мокаем фасад БД
        mock_db = MagicMock()
        mock_db.get_cointegration_cache.return_value = None
        mock_db.save_cointegration_cache.return_value = 1
        mock_get_facade.return_value = mock_db

        # Мокаем анализатор
        mock_analyzer = MagicMock()
        mock_analyzer.analyze_pair.return_value = {
            'is_cointegrated': True,
            'p_value': 0.01,
            'half_life': 5.0,
            'hedge_ratio': 0.95,
            'n_observations': 100
        }
        mock_analyzer_class.return_value = mock_analyzer

        from core.cointegration_service import CointegrationService

        service = CointegrationService()
        ytm1 = pd.Series([10.0 + np.random.randn() * 0.1 for _ in range(100)])
        ytm2 = pd.Series([9.5 + np.random.randn() * 0.1 for _ in range(100)])

        result = service.get_or_calculate(
            'SU26224RMFS4', 'SU26225RMFS4', 100, ytm1, ytm2
        )

        assert result['from_cache'] == False
        mock_analyzer.analyze_pair.assert_called_once()
        mock_db.save_cointegration_cache.assert_called_once()

    @patch('core.cointegration_service.get_db_facade')
    def test_force_refresh_ignores_cache(self, mock_get_facade):
        """force_refresh игнорирует кэш"""
        mock_db = MagicMock()
        mock_db.get_cointegration_cache.return_value = {
            'is_cointegrated': True,
        }
        mock_db.save_cointegration_cache.return_value = 1
        mock_get_facade.return_value = mock_db

        from core.cointegration_service import CointegrationService

        with patch.object(CointegrationService, '_calculate') as mock_calc:
            mock_calc.return_value = {'is_cointegrated': False, 'n_observations': 100}
            service = CointegrationService()
            ytm1 = pd.Series([10.0] * 100)
            ytm2 = pd.Series([9.5] * 100)

            result = service.get_or_calculate(
                'SU26224RMFS4', 'SU26225RMFS4', 100, ytm1, ytm2, force_refresh=True
            )

            # Кэш не должен проверяться
            mock_db.get_cointegration_cache.assert_not_called()


class TestCalculate:
    """Тесты _calculate"""

    @patch('core.cointegration_service.get_db_facade')
    def test_handles_none_input(self, mock_get_facade):
        """Обрабатывает None входные данные"""
        mock_get_facade.return_value = MagicMock()

        from core.cointegration_service import CointegrationService

        service = CointegrationService()
        result = service._calculate(None, pd.Series([10.0] * 100))

        assert 'error' in result

    @patch('core.cointegration_service.get_db_facade')
    def test_handles_insufficient_data(self, mock_get_facade):
        """Обрабатывает недостаточные данные"""
        mock_get_facade.return_value = MagicMock()

        from core.cointegration_service import CointegrationService

        service = CointegrationService()
        ytm1 = pd.Series([10.0, 10.1, 10.2])
        ytm2 = pd.Series([9.5, 9.6, 9.7])

        result = service._calculate(ytm1, ytm2)

        assert 'error' in result
        assert result['error'] == 'Insufficient data'


class TestClearCache:
    """Тесты clear_cache"""

    @patch('core.cointegration_service.get_db_facade')
    def test_clears_all_cache(self, mock_get_facade):
        """Очищает весь кэш"""
        mock_db = MagicMock()
        mock_db.clear_cointegration_cache.return_value = 10
        mock_get_facade.return_value = mock_db

        from core.cointegration_service import CointegrationService

        service = CointegrationService()
        count = service.clear_cache()

        assert count == 10
        mock_db.clear_cointegration_cache.assert_called_once_with(None, None, None)

    @patch('core.cointegration_service.get_db_facade')
    def test_clears_specific_bond_pair(self, mock_get_facade):
        """Очищает кэш для конкретной пары"""
        mock_db = MagicMock()
        mock_db.clear_cointegration_cache.return_value = 1
        mock_get_facade.return_value = mock_db

        from core.cointegration_service import CointegrationService

        service = CointegrationService()
        count = service.clear_cache('SU26224RMFS4', 'SU26225RMFS4', 100)

        mock_db.clear_cointegration_cache.assert_called_once_with(
            'SU26224RMFS4', 'SU26225RMFS4', 100
        )


class TestGetCointegrationService:
    """Тесты singleton"""

    @patch('core.cointegration_service.get_db_facade')
    def test_returns_singleton(self, mock_get_facade):
        """Возвращает singleton"""
        from core.cointegration_service import get_cointegration_service, _service

        # Сбрасываем singleton
        import core.cointegration_service as cs
        cs._service = None

        service1 = get_cointegration_service()
        service2 = get_cointegration_service()

        assert service1 is service2
