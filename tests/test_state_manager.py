"""
Тесты для services/state_manager.py

Тестируем работу с URL query_params.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
import sys

# Мокаем streamlit до импорта
mock_st = MagicMock()
mock_st.query_params = {}
mock_st.session_state = {}
sys.modules['streamlit'] = mock_st


class TestStateManagerFunctions:
    """Тесты функций state_manager"""

    def test_query_keys_defined(self):
        """Проверка списка ключей URL"""
        from services.state_manager import QUERY_KEYS

        assert 'period' in QUERY_KEYS
        assert 'spread_window' in QUERY_KEYS
        assert 'z_threshold' in QUERY_KEYS
        assert 'g_spread_period' in QUERY_KEYS
        assert 'candle_interval' in QUERY_KEYS

    def test_sync_from_url_reads_params(self):
        """sync_from_url читает параметры из URL"""
        mock_st.query_params = {'period': '180', 'spread_window': '45'}
        mock_st.session_state = {}
        
        from services.state_manager import sync_from_url
        sync_from_url()
        
        assert mock_st.session_state.get('period') == 180
        assert mock_st.session_state.get('spread_window') == 45

    def test_sync_from_url_handles_list_params(self):
        """sync_from_url обрабатывает list параметры"""
        mock_st.query_params = {'period': ['360']}  # Иногда возвращает list
        mock_st.session_state = {}
        
        from services.state_manager import sync_from_url
        sync_from_url()
        
        assert mock_st.session_state.get('period') == 360

    def test_sync_from_url_ignores_invalid(self):
        """sync_from_url игнорирует невалидные значения"""
        mock_st.query_params = {'period': 'invalid', 'spread_window': '30'}
        mock_st.session_state = {}
        
        from services.state_manager import sync_from_url
        sync_from_url()
        
        # period должен быть проигнорирован
        assert 'period' not in mock_st.session_state
        assert mock_st.session_state.get('spread_window') == 30

    def test_sync_to_url_writes_params(self):
        """sync_to_url записывает параметры в URL"""
        mock_st.session_state = {
            'period': 365,
            'spread_window': 30,
            'z_threshold': 2.0,
        }
        mock_st.query_params = {}
        
        from services.state_manager import sync_to_url
        sync_to_url()
        
        assert mock_st.query_params.get('period') == '365'
        assert mock_st.query_params.get('spread_window') == '30'
        assert mock_st.query_params.get('z_threshold') == '2.0'

    def test_sync_to_url_includes_bonds(self):
        """sync_to_url сохраняет ISIN облигаций"""
        mock_st.session_state = {
            'period': 365,
            'bonds': {'RU000A1038V6': {}, 'RU000A1038V7': {}},
            'selected_bond1': 0,
            'selected_bond2': 1,
        }
        mock_st.query_params = {}
        
        from services.state_manager import sync_to_url
        sync_to_url()
        
        assert mock_st.query_params.get('b1') == 'RU000A1038V6'
        assert mock_st.query_params.get('b2') == 'RU000A1038V7'

    def test_save_last_pair_updates_url(self):
        """save_last_pair обновляет URL"""
        mock_st.query_params = {}
        
        from services.state_manager import save_last_pair
        save_last_pair('ISIN1', 'ISIN2')
        
        assert mock_st.query_params.get('b1') == 'ISIN1'
        assert mock_st.query_params.get('b2') == 'ISIN2'

    def test_load_last_pair_from_url(self):
        """load_last_pair читает пару из URL"""
        mock_st.query_params = {'b1': 'ISIN1', 'b2': 'ISIN2'}
        
        from services.state_manager import load_last_pair
        result = load_last_pair()
        
        assert result['b1'] == 'ISIN1'
        assert result['b2'] == 'ISIN2'

    def test_load_last_pair_empty(self):
        """load_last_pair возвращает пустой dict если нет параметров"""
        mock_st.query_params = {}
        
        from services.state_manager import load_last_pair
        result = load_last_pair()
        
        assert result == {}

    def test_get_bond_indices_from_url(self):
        """get_bond_indices_from_url возвращает индексы по ISIN"""
        from services.state_manager import get_bond_indices_from_url
        
        # Создаём mock bonds
        bond1 = Mock(isin='ISIN_A')
        bond2 = Mock(isin='ISIN_B')
        bond3 = Mock(isin='ISIN_C')
        bonds = [bond1, bond2, bond3]
        
        mock_st.query_params = {'b1': 'ISIN_C', 'b2': 'ISIN_A'}
        
        idx1, idx2 = get_bond_indices_from_url(bonds)
        
        assert idx1 == 2  # ISIN_C на позиции 2
        assert idx2 == 0  # ISIN_A на позиции 0

    def test_get_bond_indices_defaults(self):
        """get_bond_indices_from_url возвращает defaults если нет параметров"""
        from services.state_manager import get_bond_indices_from_url
        
        bond1 = Mock(isin='ISIN_A')
        bond2 = Mock(isin='ISIN_B')
        bonds = [bond1, bond2]
        
        mock_st.query_params = {}
        
        idx1, idx2 = get_bond_indices_from_url(bonds)
        
        assert idx1 == 0
        assert idx2 == 1
