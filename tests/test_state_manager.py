"""
Тесты для services/state_manager.py

Внимание: streamlit-browser-storage требует Streamlit runtime.
Тестируем логику функций без реального браузера.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
import sys

# Мокаем streamlit до импорта
sys.modules['streamlit'] = MagicMock()


class TestStateManagerFunctions:
    """Тесты функций state_manager"""

    def test_session_keys_defined(self):
        """Проверка списка ключей сессии"""
        from services.state_manager import SESSION_KEYS

        assert 'period' in SESSION_KEYS
        assert 'spread_window' in SESSION_KEYS
        assert 'z_threshold' in SESSION_KEYS
        assert 'g_spread_period' in SESSION_KEYS
        assert 'candle_interval' in SESSION_KEYS

    def test_save_last_pair_calls_localstorage(self):
        """save_last_pair вызывает LocalStorage.set"""
        with patch('services.state_manager.LOCAL') as mock_local:
            from services.state_manager import save_last_pair

            save_last_pair('RU000A1038V6', 'RU000A1038V7')

            mock_local.set.assert_called_once_with(
                "last_pair",
                {"b1": "RU000A1038V6", "b2": "RU000A1038V7"}
            )

    def test_load_last_pair_returns_dict(self):
        """load_last_pair возвращает словарь"""
        with patch('services.state_manager.LOCAL') as mock_local:
            mock_local.get.return_value = {"b1": "RU000A1038V6", "b2": "RU000A1038V7"}

            from services.state_manager import load_last_pair
            result = load_last_pair()

            assert result == {"b1": "RU000A1038V6", "b2": "RU000A1038V7"}
            mock_local.get.assert_called_once_with("last_pair")

    def test_load_last_pair_empty(self):
        """load_last_pair возвращает пустой словарь если нет данных"""
        with patch('services.state_manager.LOCAL') as mock_local:
            mock_local.get.return_value = None

            from services.state_manager import load_last_pair
            result = load_last_pair()

            assert result == {}

    def test_save_session_collects_all_keys(self):
        """save_session собирает все ключи из session_state"""
        with patch('services.state_manager.SESSION') as mock_session:
            with patch('services.state_manager.st') as mock_st:
                mock_st.session_state = {
                    'period': 365,
                    'spread_window': 30,
                    'z_threshold': 2.0,
                    'g_spread_period': 365,
                    'g_spread_window': 30,
                    'g_spread_z_threshold': 2.0,
                    'candle_interval': '60',
                    'candle_days': 30,
                    'auto_refresh': False,
                    'refresh_interval': 60,
                }

                from services.state_manager import save_session
                save_session()

                # Проверяем что set был вызван
                assert mock_session.set.called
                call_args = mock_session.set.call_args
                assert call_args[0][0] == "settings"

                # Проверяем что все ключи собраны
                settings = call_args[0][1]
                assert settings['period'] == 365
                assert settings['spread_window'] == 30
                assert settings['candle_interval'] == '60'

    def test_load_session_updates_session_state(self):
        """load_session обновляет session_state из sessionStorage"""
        with patch('services.state_manager.SESSION') as mock_session:
            with patch('services.state_manager.st') as mock_st:
                mock_session.get.return_value = {
                    'period': 180,
                    'spread_window': 45,
                    'z_threshold': 2.5,
                    'g_spread_period': 730,
                    'g_spread_window': 60,
                    'g_spread_z_threshold': 1.5,
                    'candle_interval': '10',
                    'candle_days': 7,
                    'auto_refresh': True,
                    'refresh_interval': 120,
                }
                mock_st.session_state = {}

                from services.state_manager import load_session
                load_session()

                assert mock_st.session_state['period'] == 180
                assert mock_st.session_state['spread_window'] == 45
                assert mock_st.session_state['candle_interval'] == '10'
                assert mock_st.session_state['auto_refresh'] == True

    def test_load_session_empty_storage(self):
        """load_session не падает при пустом хранилище"""
        with patch('services.state_manager.SESSION') as mock_session:
            with patch('services.state_manager.st') as mock_st:
                mock_session.get.return_value = None
                mock_st.session_state = {}

                from services.state_manager import load_session
                # Не должно выбросить исключение
                load_session()

                # session_state остаётся пустым
                assert mock_st.session_state == {}
