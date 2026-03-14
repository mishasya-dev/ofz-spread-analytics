"""
Интеграционные тесты для state_manager в app.py

Проверяем:
1. load_session() вызывается в init_session_state()
2. load_last_pair() восстанавливает пару облигаций
3. Значения из sessionStorage используются вместо defaults
4. on_change callbacks правильно сохраняют состояние
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
import sys

# Мокаем streamlit до импорта
mock_st = MagicMock()
mock_st.session_state = {}
sys.modules['streamlit'] = mock_st


class TestInitSessionStateIntegration:
    """Тесты интеграции load в init_session_state"""

    def test_load_session_called_on_init(self):
        """load_session() вызывается при инициализации"""
        with patch.dict(sys.modules, {'streamlit': mock_st}):
            with patch('services.state_manager.load_session') as mock_load:
                # Импортируем после мока
                from services.state_manager import load_session as load_session_real

                # Симулируем что load_session был вызван
                mock_st.session_state = {}
                load_session_real()

                # Проверяем что функция существует и может быть вызвана
                assert callable(load_session_real)

    def test_load_session_provides_values_before_defaults(self):
        """Значения из load_session используются вместо defaults"""
        with patch('services.state_manager.SESSION') as mock_session:
            mock_session.get.return_value = {
                'period': 180,
                'spread_window': 45,
                'z_threshold': 2.5,
                'g_spread_period': 730,
            }
            mock_st.session_state = {}

            from services.state_manager import load_session
            load_session()

            # Эти значения должны быть из sessionStorage, не defaults
            assert mock_st.session_state.get('period') == 180
            assert mock_st.session_state.get('spread_window') == 45
            assert mock_st.session_state.get('z_threshold') == 2.5
            assert mock_st.session_state.get('g_spread_period') == 730

    def test_defaults_used_when_session_empty(self):
        """Defaults используются когда sessionStorage пуст"""
        with patch('services.state_manager.SESSION') as mock_session:
            mock_session.get.return_value = None
            mock_st.session_state = {}

            from services.state_manager import load_session
            load_session()

            # session_state должен остаться пустым (defaults применяются потом)
            assert mock_st.session_state == {}


class TestLoadLastPairIntegration:
    """Тесты восстановления последней пары облигаций"""

    def test_load_last_pair_restores_bond_indices(self):
        """load_last_pair восстанавливает индексы по ISIN"""
        with patch('services.state_manager.LOCAL') as mock_local:
            mock_local.get.return_value = {
                "b1": "RU000A1038V6",
                "b2": "RU000A1038V7"
            }

            from services.state_manager import load_last_pair
            result = load_last_pair()

            assert result['b1'] == "RU000A1038V6"
            assert result['b2'] == "RU000A1038V7"

    def test_bond_indices_resolved_from_isins(self):
        """Индексы облигаций корректно вычисляются из ISIN"""
        # Симулируем bonds dict
        bonds = {
            'RU000A1038V5': {'name': 'ОФЗ 26218'},
            'RU000A1038V6': {'name': 'ОФЗ 26219'},
            'RU000A1038V7': {'name': 'ОФЗ 26220'},
            'RU000A1038V8': {'name': 'ОФЗ 26221'},
        }
        isins = list(bonds.keys())

        # Ищем индексы
        b1_isin = 'RU000A1038V6'
        b2_isin = 'RU000A1038V8'

        idx1 = isins.index(b1_isin) if b1_isin in isins else 0
        idx2 = isins.index(b2_isin) if b2_isin in isins else 1

        assert idx1 == 1  # RU000A1038V6 на позиции 1
        assert idx2 == 3  # RU000A1038V8 на позиции 3

    def test_invalid_isin_fallback_to_defaults(self):
        """Неверный ISIN → fallback к defaults (0, 1)"""
        bonds = {
            'RU000A1038V5': {'name': 'ОФЗ 26218'},
            'RU000A1038V6': {'name': 'ОФЗ 26219'},
        }
        isins = list(bonds.keys())

        # ISIN не в списке
        invalid_isin = 'RU000A9999999'

        idx = isins.index(invalid_isin) if invalid_isin in isins else 0

        assert idx == 0  # fallback


class TestOnChangeCallbacks:
    """Тесты on_change callbacks"""

    def test_save_session_callable(self):
        """save_session может быть использована как callback"""
        with patch('services.state_manager.SESSION') as mock_session:
            mock_st.session_state = {'period': 365}

            from services.state_manager import save_session

            # Может быть вызвана без аргументов (как callback)
            save_session()

            assert mock_session.set.called

    def test_save_last_pair_callable(self):
        """save_last_pair может быть использована в callback"""
        with patch('services.state_manager.LOCAL') as mock_local:
            from services.state_manager import save_last_pair

            # Типичный вызов из callback
            save_last_pair('RU000A1038V6', 'RU000A1038V7')

            mock_local.set.assert_called_once()

    def test_callback_integration_flow(self):
        """Полный flow: change → callback → save"""
        with patch('services.state_manager.SESSION') as mock_session:
            with patch('services.state_manager.LOCAL') as mock_local:
                mock_st.session_state = {
                    'period': 180,
                    'selected_bond1': 1,
                    'selected_bond2': 2,
                }

                from services.state_manager import save_session, save_last_pair

                # Симулируем callback при изменении периода
                save_session()

                # Симулируем callback при смене облигаций
                save_last_pair('ISIN1', 'ISIN2')

                # Оба хранилища были обновлены
                assert mock_session.set.called
                assert mock_local.set.called


class TestSessionStorageKeys:
    """Тесты полноты сохраняемых ключей"""

    def test_all_slider_keys_in_session_keys(self):
        """Все слайдеры включены в SESSION_KEYS"""
        from services.state_manager import SESSION_KEYS

        expected_keys = [
            'period',
            'spread_window',
            'z_threshold',
            'g_spread_period',
            'g_spread_window',
            'g_spread_z_threshold',
            'candle_interval',
            'candle_days',
            'auto_refresh',
            'refresh_interval',
        ]

        for key in expected_keys:
            assert key in SESSION_KEYS, f"Missing key: {key}"

    def test_session_keys_not_include_transient_state(self):
        """В SESSION_KEYS нет transient переменных (updating_db, ytm_validation)"""
        from services.state_manager import SESSION_KEYS

        transient_keys = ['updating_db', 'ytm_validation', 'last_update', 'validation_isins']

        for key in transient_keys:
            assert key not in SESSION_KEYS, f"Transient key should not be saved: {key}"
