"""
Тесты для linked zoom функциональности v0.3.0

Тестирует:
- Синхронизация zoom между графиками 1-2
- Синхронизация zoom между графиками 3-4
- Независимость zoom между парами графиков
- Сброс zoom

Запуск:
    python3 tests/test_linked_zoom.py
"""
import sys
import os
import unittest
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

# Добавляем родительскую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Подменяем streamlit до импорта
from tests.mock_streamlit import st_mock, SessionStateDict
sys.modules['streamlit'] = st_mock


class TestZoomRangeStorage(unittest.TestCase):
    """Тесты для хранения zoom range в session_state"""

    def setUp(self):
        """Настройка перед каждым тестом"""
        st_mock.session_state = SessionStateDict({
            'daily_zoom_range': None,
            'intraday_zoom_range': None
        })

    def test_daily_zoom_default_none(self):
        """По умолчанию daily_zoom_range = None"""
        self.assertIsNone(st_mock.session_state.get('daily_zoom_range'))

    def test_intraday_zoom_default_none(self):
        """По умолчанию intraday_zoom_range = None"""
        self.assertIsNone(st_mock.session_state.get('intraday_zoom_range'))

    def test_zoom_can_be_stored(self):
        """Zoom range может быть сохранён"""
        zoom_range = (datetime(2024, 1, 1), datetime(2024, 6, 1))
        st_mock.session_state['daily_zoom_range'] = zoom_range

        self.assertEqual(st_mock.session_state['daily_zoom_range'], zoom_range)

    def test_zoom_can_be_reset(self):
        """Zoom range может быть сброшен"""
        st_mock.session_state['daily_zoom_range'] = (datetime(2024, 1, 1), datetime(2024, 6, 1))
        st_mock.session_state['daily_zoom_range'] = None

        self.assertIsNone(st_mock.session_state['daily_zoom_range'])


class TestApplyZoomRange(unittest.TestCase):
    """Тесты для apply_zoom_range функции"""

    def setUp(self):
        """Импортируем функцию"""
        from components.charts import apply_zoom_range
        self.apply_zoom = apply_zoom_range

    def test_apply_valid_range(self):
        """Применение валидного диапазона"""
        import plotly.graph_objects as go

        fig = go.Figure()
        fig.add_trace(go.Scatter(x=[1, 2, 3], y=[1, 2, 3]))

        x_range = (datetime(2024, 1, 1), datetime(2024, 6, 1))
        result = self.apply_zoom(fig, x_range)

        # Диапазон применён
        self.assertIsNotNone(result.layout.xaxis.range)

    def test_apply_none_range(self):
        """Применение None диапазона — без изменений"""
        import plotly.graph_objects as go

        fig = go.Figure()
        fig.add_trace(go.Scatter(x=[1, 2, 3], y=[1, 2, 3]))

        result = self.apply_zoom(fig, None)

        # Возвращает тот же figure
        self.assertEqual(result, fig)

    def test_apply_partial_range(self):
        """Применение частичного диапазона (один None)"""
        import plotly.graph_objects as go

        fig = go.Figure()
        fig.add_trace(go.Scatter(x=[1, 2, 3], y=[1, 2, 3]))

        # Один конец None
        result = self.apply_zoom(fig, (None, datetime(2024, 6, 1)))

        # Не применяется
        self.assertEqual(result, fig)

    def test_apply_tuple_with_strings(self):
        """Применение диапазона со строками (от plotly)"""
        import plotly.graph_objects as go

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=pd.date_range('2024-01-01', periods=10, freq='D'),
            y=list(range(10))
        ))

        x_range = ('2024-01-01', '2024-01-10')
        result = self.apply_zoom(fig, x_range)

        # Применяется
        self.assertIsNotNone(result.layout.xaxis.range)


class TestDailyChartsSync(unittest.TestCase):
    """Тесты для синхронизации графиков 1-2 (дневные)"""

    def test_both_charts_use_same_range(self):
        """Оба графика используют один range"""
        from components.charts import create_daily_ytm_chart, create_daily_spread_chart

        dates = pd.date_range('2024-01-01', periods=100, freq='D')
        df1 = pd.DataFrame({'ytm': np.random.uniform(14, 16, 100)}, index=dates)
        df2 = pd.DataFrame({'ytm': np.random.uniform(13, 15, 100)}, index=dates)

        spread_df = pd.DataFrame({
            'date': dates,
            'spread': np.random.uniform(50, 150, 100)
        })

        x_range = (datetime(2024, 2, 1), datetime(2024, 4, 1))

        fig1 = create_daily_ytm_chart(df1, df2, "Bond1", "Bond2", x_range=x_range)
        fig2 = create_daily_spread_chart(spread_df, x_range=x_range)

        # Оба имеют одинаковый диапазон
        self.assertEqual(fig1.layout.xaxis.range, fig2.layout.xaxis.range)

    def test_zoom_applied_to_ytm_chart(self):
        """Zoom применяется к YTM графику"""
        from components.charts import create_daily_ytm_chart

        dates = pd.date_range('2024-01-01', periods=100, freq='D')
        df1 = pd.DataFrame({'ytm': [14.0] * 100}, index=dates)
        df2 = pd.DataFrame({'ytm': [13.0] * 100}, index=dates)

        x_range = (datetime(2024, 2, 1), datetime(2024, 3, 1))
        fig = create_daily_ytm_chart(df1, df2, "B1", "B2", x_range=x_range)

        # Диапазон применён
        self.assertIsNotNone(fig.layout.xaxis.range)

    def test_zoom_applied_to_spread_chart(self):
        """Zoom применяется к графику спреда"""
        from components.charts import create_daily_spread_chart

        dates = pd.date_range('2024-01-01', periods=100, freq='D')
        spread_df = pd.DataFrame({
            'date': dates,
            'spread': [100.0] * 100
        })

        x_range = (datetime(2024, 2, 1), datetime(2024, 3, 1))
        fig = create_daily_spread_chart(spread_df, x_range=x_range)

        self.assertIsNotNone(fig.layout.xaxis.range)


class TestIntradayChartsSync(unittest.TestCase):
    """Тесты для синхронизации графиков 3-4 (intraday)"""

    def test_combined_chart_accepts_range(self):
        """Склеенный график принимает range"""
        from components.charts import create_combined_ytm_chart

        daily_dates = pd.date_range('2024-01-01', periods=30, freq='D')
        intraday_dates = pd.date_range('2024-01-30', periods=24, freq='h')

        daily_df = pd.DataFrame({'ytm': [14.0] * 30}, index=daily_dates)
        intraday_df = pd.DataFrame({'ytm_close': [14.5] * 24}, index=intraday_dates)

        x_range = (datetime(2024, 1, 15), datetime(2024, 1, 31))
        fig = create_combined_ytm_chart(
            daily_df, pd.DataFrame(),
            intraday_df, pd.DataFrame(),
            "B1", "B2",
            x_range=x_range
        )

        self.assertIsNotNone(fig.layout.xaxis.range)

    def test_intraday_spread_accepts_range(self):
        """Intraday спред принимает range"""
        from components.charts import create_intraday_spread_chart

        dates = pd.date_range('2024-01-31', periods=24, freq='h')
        spread_df = pd.DataFrame({
            'datetime': dates,
            'spread': [100.0] * 24
        })

        x_range = (dates[0], dates[-1])
        fig = create_intraday_spread_chart(spread_df, x_range=x_range)

        self.assertIsNotNone(fig.layout.xaxis.range)


class TestZoomIndependence(unittest.TestCase):
    """Тесты для независимости zoom между парами графиков"""

    def test_daily_and_intraday_zoom_independent(self):
        """Daily и intraday zoom независимы"""
        st_mock.session_state = SessionStateDict({
            'daily_zoom_range': (datetime(2024, 1, 1), datetime(2024, 3, 1)),
            'intraday_zoom_range': None
        })

        # Разные значения
        self.assertIsNotNone(st_mock.session_state['daily_zoom_range'])
        self.assertIsNone(st_mock.session_state['intraday_zoom_range'])

    def test_can_set_intraday_without_affecting_daily(self):
        """Можно установить intraday zoom без влияния на daily"""
        st_mock.session_state = SessionStateDict({
            'daily_zoom_range': (datetime(2024, 1, 1), datetime(2024, 3, 1)),
            'intraday_zoom_range': None
        })

        # Устанавливаем intraday
        st_mock.session_state['intraday_zoom_range'] = (datetime(2024, 1, 30), datetime(2024, 1, 31))

        # Daily не изменился
        self.assertEqual(
            st_mock.session_state['daily_zoom_range'],
            (datetime(2024, 1, 1), datetime(2024, 3, 1))
        )

    def test_reset_daily_does_not_affect_intraday(self):
        """Сброс daily zoom не влияет на intraday"""
        st_mock.session_state = SessionStateDict({
            'daily_zoom_range': (datetime(2024, 1, 1), datetime(2024, 3, 1)),
            'intraday_zoom_range': (datetime(2024, 1, 30), datetime(2024, 1, 31))
        })

        # Сбрасываем daily
        st_mock.session_state['daily_zoom_range'] = None

        # Intraday остался
        self.assertIsNotNone(st_mock.session_state['intraday_zoom_range'])


class TestFutureRange(unittest.TestCase):
    """Тесты для future_range (15% запас для будущего)"""

    def setUp(self):
        """Импортируем функцию"""
        from components.charts import calculate_future_range
        self.calculate_future_range = calculate_future_range

    def test_default_15_percent(self):
        """По умолчанию 15% запас"""
        start_dt = datetime(2024, 1, 1)
        end_dt = datetime(2024, 4, 10)  # ~100 дней
        idx = pd.DatetimeIndex([start_dt, end_dt])

        start, end = self.calculate_future_range(idx)

        # 100 дней * 0.15 = 15 дней запас
        expected_end = end_dt + timedelta(days=15)
        self.assertEqual(end.date(), expected_end.date())

    def test_custom_percent(self):
        """Кастомный процент запаса"""
        start_dt = datetime(2024, 1, 1)
        end_dt = datetime(2024, 7, 1)  # ~182 дня
        idx = pd.DatetimeIndex([start_dt, end_dt])

        start, end = self.calculate_future_range(idx, future_percent=0.20)

        # 182 дня * 0.20 = ~36 дней запас
        expected_end = end_dt + timedelta(days=36)
        self.assertEqual(end.date(), expected_end.date())

    def test_year_range(self):
        """Годовой диапазон"""
        start_dt = datetime(2023, 1, 1)
        end_dt = datetime(2024, 1, 1)
        idx = pd.DatetimeIndex([start_dt, end_dt])

        start, end = self.calculate_future_range(idx, future_percent=0.15)

        # 365 дней * 0.15 = ~55 дней
        days_diff = (end - end_dt).days
        self.assertAlmostEqual(days_diff, 55, delta=2)


def run_tests():
    """Запуск всех тестов"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    suite.addTests(loader.loadTestsFromTestCase(TestZoomRangeStorage))
    suite.addTests(loader.loadTestsFromTestCase(TestApplyZoomRange))
    suite.addTests(loader.loadTestsFromTestCase(TestDailyChartsSync))
    suite.addTests(loader.loadTestsFromTestCase(TestIntradayChartsSync))
    suite.addTests(loader.loadTestsFromTestCase(TestZoomIndependence))
    suite.addTests(loader.loadTestsFromTestCase(TestFutureRange))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)
