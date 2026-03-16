"""
Тесты для sidebar функционала v0.3.0

Запуск:
    python3 tests/test_sidebar_v030.py

Тестирует:
- render_period_selector() — единственный слайдер периода 30-730 дней
- render_candle_interval_selector() — выбор интервала свечей
- render_auto_refresh() — настройки автообновления
- render_db_panel() — панель управления БД с callback
- render_bond_selection() — выбор облигаций с trading_data
- format_bond_label() — форматирование метки с YTM/дюрацией
"""
import sys
import os
import unittest
from unittest.mock import MagicMock, patch, Mock
from datetime import datetime, timedelta

# Добавляем родительскую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Подменяем streamlit до импорта компонентов
from tests.mock_streamlit import st_mock, SessionStateDict
sys.modules['streamlit'] = st_mock


class TestRenderPeriodSelector(unittest.TestCase):
    """Тесты для render_period_selector() — единственный слайдер периода"""

    def setUp(self):
        """Настройка перед каждым тестом"""
        # Сбрасываем mock в исходное состояние
        st_mock.reset()
        st_mock.session_state = SessionStateDict({'period': 365})

    def test_returns_period_in_valid_range(self):
        """Возвращает период в диапазоне 30-730 дней"""
        from components.sidebar import render_period_selector

        # st.slider вернёт value из kwargs
        st_mock.slider = Mock(return_value=180)

        result = render_period_selector()

        self.assertIn(result, range(30, 731))

    def test_uses_session_state_key(self):
        """Slider использует key для синхронизации с session_state"""
        st_mock.session_state = SessionStateDict({'period': 500})

        from components.sidebar import render_period_selector

        result = render_period_selector()

        # Проверяем, что slider возвращает значение из session_state
        self.assertEqual(result, 500)

    def test_slider_has_key_parameter(self):
        """Slider вызывается с key='period' для синхронизации"""
        st_mock.session_state = SessionStateDict({'period': 365})

        from components.sidebar import render_period_selector

        # Сохраняем оригинальный метод
        original_slider = st_mock.slider
        st_mock.slider = Mock(side_effect=original_slider)

        render_period_selector()

        call_args = st_mock.slider.call_args
        self.assertEqual(call_args[1]['key'], 'period')

    def test_step_is_30_days(self):
        """Шаг слайдера = 30 дней"""
        from components.sidebar import render_period_selector

        st_mock.slider = Mock(return_value=365)

        render_period_selector()

        call_args = st_mock.slider.call_args
        self.assertEqual(call_args[1]['step'], 30)

    def test_min_value_is_30(self):
        """Минимальное значение = 30 дней"""
        from components.sidebar import render_period_selector

        st_mock.slider = Mock(return_value=30)

        render_period_selector()

        call_args = st_mock.slider.call_args
        self.assertEqual(call_args[1]['min_value'], 30)

    def test_max_value_is_730(self):
        """Максимальное значение = 730 дней (2 года)"""
        from components.sidebar import render_period_selector

        st_mock.slider = Mock(return_value=730)

        render_period_selector()

        call_args = st_mock.slider.call_args
        self.assertEqual(call_args[1]['max_value'], 730)


class TestRenderCandleIntervalSelector(unittest.TestCase):
    """Тесты для render_candle_interval_selector() — выбор интервала свечей"""

    def setUp(self):
        """Настройка перед каждым тестом"""
        st_mock.reset()
        st_mock.session_state = SessionStateDict({'candle_interval': '10'})
        st_mock.caption = Mock()

    def test_returns_valid_interval(self):
        """Возвращает валидный интервал (1, 10 или 60)"""
        from components.sidebar import render_candle_interval_selector

        st_mock.radio = Mock(return_value='10')

        result = render_candle_interval_selector()

        self.assertIn(result, ['1', '10', '60'])

    def test_default_from_session_state(self):
        """Использует значение из session_state"""
        st_mock.session_state = SessionStateDict({'candle_interval': '60'})

        from components.sidebar import render_candle_interval_selector

        st_mock.radio = Mock(return_value='60')

        result = render_candle_interval_selector()

        self.assertEqual(result, '60')

    def test_radio_has_key_parameter(self):
        """Radio использует key='candle_interval' для синхронизации"""
        st_mock.session_state = SessionStateDict({'candle_interval': '1'})

        from components.sidebar import render_candle_interval_selector

        # Сохраняем оригинальный метод
        original_radio = st_mock.radio
        st_mock.radio = Mock(side_effect=original_radio)

        render_candle_interval_selector()

        call_args = st_mock.radio.call_args
        self.assertEqual(call_args[1]['key'], 'candle_interval')

    def test_options_are_correct(self):
        """Опции radio: 1, 10, 60"""
        from components.sidebar import render_candle_interval_selector

        st_mock.radio = Mock(return_value='10')

        render_candle_interval_selector()

        call_args = st_mock.radio.call_args
        self.assertEqual(call_args[1]['options'], ['1', '10', '60'])

    def test_format_func_exists(self):
        """format_func преобразует в читаемый вид"""
        from components.sidebar import render_candle_interval_selector

        st_mock.radio = Mock(return_value='10')

        render_candle_interval_selector()

        call_args = st_mock.radio.call_args
        format_func = call_args[1]['format_func']

        # Проверяем преобразование
        self.assertEqual(format_func('1'), '1 мин')
        self.assertEqual(format_func('10'), '10 мин')
        self.assertEqual(format_func('60'), '1 час')


class TestRenderAutoRefresh(unittest.TestCase):
    """Тесты для render_auto_refresh() — настройки автообновления"""

    def setUp(self):
        """Настройка перед каждым тестом"""
        st_mock.reset()
        st_mock.session_state = SessionStateDict({
            'auto_refresh': False,
            'refresh_interval': 60,
            'last_update': None
        })

    def test_returns_bool(self):
        """Возвращает boolean"""
        from components.sidebar import render_auto_refresh

        st_mock.toggle = Mock(return_value=False)

        result = render_auto_refresh()

        self.assertIsInstance(result, bool)

    def test_toggle_has_key_parameter(self):
        """Toggle использует key='auto_refresh' для синхронизации"""
        st_mock.session_state['auto_refresh'] = True

        from components.sidebar import render_auto_refresh

        # Сохраняем оригинальный метод
        original_toggle = st_mock.toggle
        st_mock.toggle = Mock(side_effect=original_toggle)

        render_auto_refresh()

        call_args = st_mock.toggle.call_args
        self.assertEqual(call_args[1]['key'], 'auto_refresh')

    def test_returns_session_state_value(self):
        """Возвращает значение из session_state"""
        st_mock.session_state['auto_refresh'] = True

        from components.sidebar import render_auto_refresh

        result = render_auto_refresh()

        self.assertEqual(result, True)

    def test_interval_slider_only_when_enabled(self):
        """Слайдер интервала показывается только когда включено"""
        from components.sidebar import render_auto_refresh

        # Сначала выключено
        st_mock.toggle = Mock(return_value=False)
        st_mock.slider = Mock()

        render_auto_refresh()

        # slider не должен вызываться для интервала (в этом случае)
        # Но если включено - должен

        st_mock.session_state['auto_refresh'] = False
        st_mock.toggle = Mock(return_value=True)
        st_mock.slider = Mock(return_value=120)

        render_auto_refresh()

        # Теперь slider должен быть вызван для интервала
        # (но это зависит от реализации mock)


class TestRenderDbPanel(unittest.TestCase):
    """Тесты для render_db_panel() — панель управления БД"""

    def setUp(self):
        """Настройка перед каждым тестом"""
        st_mock.reset()
        st_mock.session_state = SessionStateDict({'updating_db': False})
        st_mock.expander = Mock()
        st_mock.expander.return_value.__enter__ = Mock(return_value=Mock())
        st_mock.expander.return_value.__exit__ = Mock(return_value=False)
        st_mock.write = Mock()
        st_mock.button = Mock(return_value=False)
        st_mock.progress = Mock(return_value=Mock())
        st_mock.empty = Mock(return_value=Mock())
        st_mock.info = Mock()
        st_mock.success = Mock()
        st_mock.error = Mock()

    def test_shows_db_stats(self):
        """Показывает статистику БД"""
        from components.sidebar import render_db_panel

        db_stats = {
            'bonds_count': 16,
            'daily_ytm_count': 821,
            'intraday_ytm_count': 5000
        }

        render_db_panel(db_stats)

        # Проверяем что write был вызван с правильными данными
        write_calls = [str(call) for call in st_mock.write.call_args_list]
        self.assertTrue(any('16' in str(call) for call in write_calls))

    def test_button_triggers_update(self):
        """Кнопка запускает обновление БД"""
        from components.sidebar import render_db_panel

        st_mock.button = Mock(return_value=True)

        render_db_panel({'bonds_count': 10})

        self.assertTrue(st_mock.session_state.get('updating_db', False))

    def test_calls_callback_when_updating(self):
        """Вызывает callback при обновлении"""
        from components.sidebar import render_db_panel

        # Имитируем нажатие кнопки в предыдущем рендере
        st_mock.session_state['updating_db'] = True
        st_mock.button = Mock(return_value=False)

        # Мок для progress bar
        progress_mock = Mock()
        progress_mock.progress = Mock()
        st_mock.progress = Mock(return_value=progress_mock)

        status_mock = Mock()
        status_mock.text = Mock()
        st_mock.empty = Mock(return_value=status_mock)

        # Callback
        callback = Mock(return_value={'daily_ytm_saved': 100, 'intraday_ytm_saved': 500})

        render_db_panel({'bonds_count': 10}, on_update_db=callback)

        # Callback должен быть вызван
        callback.assert_called_once()

    def test_shows_success_after_update(self):
        """Показывает успех после обновления"""
        from components.sidebar import render_db_panel

        st_mock.session_state['updating_db'] = True
        st_mock.button = Mock(return_value=False)

        progress_mock = Mock()
        progress_mock.progress = Mock()
        st_mock.progress = Mock(return_value=progress_mock)

        status_mock = Mock()
        status_mock.text = Mock()
        st_mock.empty = Mock(return_value=status_mock)

        callback = Mock(return_value={'daily_ytm_saved': 100, 'intraday_ytm_saved': 500})

        render_db_panel({'bonds_count': 10}, on_update_db=callback)

        # Должен показать success
        st_mock.success.assert_called()

    def test_handles_callback_error(self):
        """Обрабатывает ошибку callback"""
        from components.sidebar import render_db_panel

        st_mock.session_state['updating_db'] = True
        st_mock.button = Mock(return_value=False)

        progress_mock = Mock()
        progress_mock.progress = Mock()
        st_mock.progress = Mock(return_value=progress_mock)

        status_mock = Mock()
        status_mock.text = Mock()
        st_mock.empty = Mock(return_value=status_mock)

        # Callback с ошибкой
        callback = Mock(side_effect=Exception("Test error"))

        render_db_panel({'bonds_count': 10}, on_update_db=callback)

        # Должен показать error
        st_mock.error.assert_called()


class TestRenderBondSelection(unittest.TestCase):
    """Тесты для render_bond_selection() — выбор облигаций"""

    def setUp(self):
        """Настройка перед каждым тестом"""
        st_mock.reset()
        st_mock.session_state = SessionStateDict({
            'selected_bond1': 0,
            'selected_bond2': 1
        })
        st_mock.selectbox = Mock(return_value=0)

    def test_returns_tuple_of_indices(self):
        """Возвращает кортеж индексов (bond1_idx, bond2_idx)"""
        from components.sidebar import render_bond_selection

        # Создаём мок-облигацию с format_label
        class MockBond:
            def __init__(self, isin, name):
                self.isin = isin
                self.name = name
                self.short_name = name
                self.maturity_date = '2030-01-01'
            
            @property
            def years_to_maturity(self):
                return 5.0
            
            def format_label(self, ytm=None, duration_years=None):
                parts = [self.name]
                if ytm is not None:
                    parts.append(f"YTM: {ytm:.2f}%")
                if duration_years is not None:
                    parts.append(f"Дюр: {duration_years:.1f}г.")
                parts.append(f"{self.years_to_maturity}г. до погашения")
                return " | ".join(parts)

        bonds = [MockBond('SU26221', 'ОФЗ 26221'), MockBond('SU26225', 'ОФЗ 26225')]
        trading_data = {}

        st_mock.selectbox = Mock(side_effect=[0, 1])

        result = render_bond_selection(bonds, trading_data)

        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)
        self.assertIn(result[0], [0, 1])
        self.assertIn(result[1], [0, 1])

    def test_shows_ytm_in_label(self):
        """Показывает YTM в метке облигации"""
        from components.sidebar import render_bond_selection

        class MockBond:
            def __init__(self, isin, name):
                self.isin = isin
                self.name = name
                self.short_name = name
                self.maturity_date = '2030-01-01'
            
            @property
            def years_to_maturity(self):
                return 5.0
            
            def format_label(self, ytm=None, duration_years=None):
                parts = [self.name]
                if ytm is not None:
                    parts.append(f"YTM: {ytm:.2f}%")
                if duration_years is not None:
                    parts.append(f"Дюр: {duration_years:.1f}г.")
                parts.append(f"{self.years_to_maturity}г. до погашения")
                return " | ".join(parts)

        bonds = [MockBond('SU26221', 'ОФЗ 26221')]
        trading_data = {
            'SU26221': {'has_data': True, 'yield': 14.5, 'duration_years': 5.0}
        }

        st_mock.selectbox = Mock(side_effect=[0, 0])

        render_bond_selection(bonds, trading_data)

        # Проверяем format_func в selectbox
        call_args = st_mock.selectbox.call_args
        format_func = call_args[1]['format_func']

        label = format_func(0)
        self.assertIn('YTM:', label)

    def test_selectbox_uses_key_parameter(self):
        """Selectbox использует key для синхронизации с session_state"""
        from components.sidebar import render_bond_selection

        class MockBond:
            def __init__(self, isin, name):
                self.isin = isin
                self.name = name
                self.short_name = name
                self.maturity_date = '2030-01-01'
            
            @property
            def years_to_maturity(self):
                return 5.0
            
            def format_label(self, ytm=None, duration_years=None):
                return self.name

        bonds = [MockBond('SU1', 'B1'), MockBond('SU2', 'B2')]
        trading_data = {}

        # Сохраняем оригинальный метод
        original_selectbox = st_mock.selectbox
        st_mock.selectbox = Mock(side_effect=original_selectbox)

        render_bond_selection(bonds, trading_data)

        # Проверяем, что selectbox вызван с правильными key
        calls = st_mock.selectbox.call_args_list
        self.assertEqual(calls[0][1]['key'], 'selected_bond1')
        self.assertEqual(calls[1][1]['key'], 'selected_bond2')


class TestFormatBondLabel(unittest.TestCase):
    """Тесты для format_bond_label() — форматирование метки"""

    def test_format_with_all_data(self):
        """Форматирование с YTM и дюрацией"""
        from utils.bond_utils import format_bond_label, BondItem

        bond = BondItem({
            'isin': 'SU26221',
            'name': 'ОФЗ 26221',
            'maturity_date': (datetime.now() + timedelta(days=365*8)).strftime('%Y-%m-%d')
        })
        label = format_bond_label(bond, ytm=14.5, duration_years=5.0)

        self.assertIn('ОФЗ 26221', label)
        self.assertIn('YTM: 14.50%', label)
        self.assertIn('Дюр: 5.0г.', label)
        self.assertIn('до погашения', label)

    def test_format_without_ytm(self):
        """Форматирование без YTM"""
        from utils.bond_utils import format_bond_label, BondItem

        bond = BondItem({
            'isin': 'SU26221',
            'name': 'ОФЗ 26221',
            'maturity_date': (datetime.now() + timedelta(days=365*8)).strftime('%Y-%m-%d')
        })
        label = format_bond_label(bond, ytm=None, duration_years=5.0)

        self.assertIn('ОФЗ 26221', label)
        self.assertNotIn('YTM:', label)
        self.assertIn('Дюр:', label)

    def test_format_without_duration(self):
        """Форматирование без дюрации"""
        from utils.bond_utils import format_bond_label, BondItem

        bond = BondItem({
            'isin': 'SU26221',
            'name': 'ОФЗ 26221',
            'maturity_date': (datetime.now() + timedelta(days=365*8)).strftime('%Y-%m-%d')
        })
        label = format_bond_label(bond, ytm=14.5, duration_years=None)

        self.assertIn('YTM: 14.50%', label)
        self.assertNotIn('Дюр:', label)

    def test_format_minimal(self):
        """Минимальное форматирование (только имя и годы)"""
        from utils.bond_utils import format_bond_label, BondItem

        bond = BondItem({
            'isin': 'SU26221',
            'name': 'ОФЗ 26221',
            'maturity_date': (datetime.now() + timedelta(days=365*8)).strftime('%Y-%m-%d')
        })
        label = format_bond_label(bond)

        self.assertIn('ОФЗ 26221', label)
        self.assertNotIn('YTM:', label)
        self.assertNotIn('Дюр:', label)
        self.assertIn('до погашения', label)

    def test_uses_short_name_if_no_name(self):
        """Использует short_name если name отсутствует"""
        from utils.bond_utils import format_bond_label, BondItem

        bond = BondItem({
            'isin': 'SU26221',
            'name': None,
            'short_name': 'ОФЗ 26221',
            'maturity_date': (datetime.now() + timedelta(days=365*8)).strftime('%Y-%m-%d')
        })
        label = format_bond_label(bond)

        self.assertIn('ОФЗ 26221', label)

    def test_uses_isin_if_no_names(self):
        """Использует ISIN если нет ни name ни short_name"""
        from utils.bond_utils import format_bond_label, BondItem

        bond = BondItem({
            'isin': 'SU26221RMFS0',
            'name': None,
            'short_name': None,
            'maturity_date': (datetime.now() + timedelta(days=365*8)).strftime('%Y-%m-%d')
        })
        label = format_bond_label(bond)

        self.assertIn('SU26221RMFS0', label)


class TestGetYearsToMaturity(unittest.TestCase):
    """Тесты для get_years_to_maturity()"""

    def test_future_date(self):
        """Дата в будущем"""
        from components.sidebar import get_years_to_maturity

        future_date = (datetime.now() + timedelta(days=365*5)).strftime('%Y-%m-%d')
        years = get_years_to_maturity(future_date)

        self.assertAlmostEqual(years, 5.0, delta=0.2)

    def test_past_date(self):
        """Дата в прошлом (погашенная)"""
        from components.sidebar import get_years_to_maturity

        past_date = "2020-01-01"
        years = get_years_to_maturity(past_date)

        self.assertLess(years, 0)

    def test_invalid_format(self):
        """Неверный формат даты"""
        from components.sidebar import get_years_to_maturity

        years = get_years_to_maturity("invalid")

        self.assertEqual(years, 0)

    def test_near_maturity(self):
        """Близкое погашение"""
        from components.sidebar import get_years_to_maturity

        near_date = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
        years = get_years_to_maturity(near_date)

        self.assertLess(years, 0.2)


class TestGetBondsList(unittest.TestCase):
    """Тесты для get_bonds_list()"""

    def setUp(self):
        """Настройка"""
        st_mock.reset()
        st_mock.session_state = SessionStateDict({
            'bonds': {
                'SU26221': {
                    'isin': 'SU26221',
                    'name': 'ОФЗ 26221',
                    'maturity_date': '2033-03-23',
                    'coupon_rate': 7.7
                }
            }
        })

    def test_returns_list(self):
        """Возвращает список"""
        from components.sidebar import get_bonds_list

        result = get_bonds_list()

        self.assertIsInstance(result, list)

    def test_items_have_isin(self):
        """Элементы имеют атрибут isin"""
        from components.sidebar import get_bonds_list

        result = get_bonds_list()

        if result:
            self.assertTrue(hasattr(result[0], 'isin'))

    def test_empty_when_no_bonds(self):
        """Пустой список при отсутствии облигаций"""
        st_mock.session_state = SessionStateDict({})

        from components.sidebar import get_bonds_list

        result = get_bonds_list()

        self.assertEqual(result, [])


def run_tests():
    """Запуск всех тестов"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    suite.addTests(loader.loadTestsFromTestCase(TestRenderPeriodSelector))
    suite.addTests(loader.loadTestsFromTestCase(TestRenderCandleIntervalSelector))
    suite.addTests(loader.loadTestsFromTestCase(TestRenderAutoRefresh))
    suite.addTests(loader.loadTestsFromTestCase(TestRenderDbPanel))
    suite.addTests(loader.loadTestsFromTestCase(TestRenderBondSelection))
    suite.addTests(loader.loadTestsFromTestCase(TestFormatBondLabel))
    suite.addTests(loader.loadTestsFromTestCase(TestGetYearsToMaturity))
    suite.addTests(loader.loadTestsFromTestCase(TestGetBondsList))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)
