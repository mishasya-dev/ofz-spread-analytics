"""
Тесты для новых графиков v0.3.0

Проверяет:
- calculate_future_range() — расчёт оси X с запасом
- create_daily_ytm_chart() — график YTM по дневным данным
- create_daily_spread_chart() — график спреда
- create_combined_ytm_chart() — склеенный график
- create_intraday_spread_chart() — intraday спред с референсом

Запуск:
    python3 tests/test_charts_v030.py
"""
import sys
import os
import unittest
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

# Добавляем родительскую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Подменяем streamlit до импорта компонентов
from tests.mock_streamlit import st_mock
sys.modules['streamlit'] = st_mock


class TestCalculateFutureRange(unittest.TestCase):
    """Тесты для расчёта диапазона оси X с запасом для будущего"""

    def setUp(self):
        """Импортируем функцию"""
        from components.charts import calculate_future_range
        self.calculate_future_range = calculate_future_range

    def test_empty_index(self):
        """Пустой индекс возвращает (None, None)"""
        result = self.calculate_future_range(pd.DatetimeIndex([]))
        self.assertEqual(result, (None, None))

    def test_single_point(self):
        """Одна точка — добавляет future_percent от 0"""
        dt = datetime(2024, 6, 15)
        idx = pd.DatetimeIndex([dt])
        
        start, end = self.calculate_future_range(idx, future_percent=0.15)
        
        self.assertEqual(start, dt)
        # future = 0 * 0.15 = 0, но добавляем 15% от "нуля" как запас
        # Фактически end = start + небольшой запас
        self.assertGreaterEqual(end, start)

    def test_normal_range(self):
        """Нормальный диапазон с 15% запасом"""
        start_dt = datetime(2024, 1, 1)
        end_dt = datetime(2024, 4, 10)  # ~100 дней
        idx = pd.DatetimeIndex([start_dt, end_dt])
        
        start, end = self.calculate_future_range(idx, future_percent=0.15)
        
        self.assertEqual(start, start_dt)
        # 100 дней * 0.15 = 15 дней запас
        expected_end = end_dt + timedelta(days=15)
        self.assertEqual(end.date(), expected_end.date())

    def test_custom_percent(self):
        """Кастомный процент будущего"""
        start_dt = datetime(2024, 1, 1)
        end_dt = datetime(2024, 7, 1)  # ~182 дня
        idx = pd.DatetimeIndex([start_dt, end_dt])
        
        start, end = self.calculate_future_range(idx, future_percent=0.20)
        
        # 182 дня * 0.20 = ~36 дней запас
        expected_end = end_dt + timedelta(days=36)
        self.assertEqual(end.date(), expected_end.date())

    def test_one_year_range(self):
        """Годовой диапазон"""
        start_dt = datetime(2023, 1, 1)
        end_dt = datetime(2024, 1, 1)
        idx = pd.DatetimeIndex([start_dt, end_dt])
        
        start, end = self.calculate_future_range(idx, future_percent=0.15)
        
        # 365 дней * 0.15 = ~55 дней
        days_diff = (end - end_dt).days
        self.assertAlmostEqual(days_diff, 55, delta=2)


class TestDailyYtmChart(unittest.TestCase):
    """Тесты для графика YTM по дневным данным"""

    def setUp(self):
        """Импортируем функцию"""
        from components.charts import create_daily_ytm_chart
        self.create_chart = create_daily_ytm_chart

    def test_empty_dataframes(self):
        """Пустые DataFrame возвращают Figure"""
        df1 = pd.DataFrame()
        df2 = pd.DataFrame()
        
        fig = self.create_chart(df1, df2, "Bond1", "Bond2")
        
        self.assertIsNotNone(fig)
        # Plotly Figure всегда возвращается, даже пустой

    def test_single_bond(self):
        """График с одной облигацией"""
        dates = pd.date_range('2024-01-01', periods=30, freq='D')
        df1 = pd.DataFrame({
            'ytm': np.random.uniform(14, 16, 30)
        }, index=dates)
        df2 = pd.DataFrame()
        
        fig = self.create_chart(df1, df2, "ОФЗ 26221", "ОФЗ 26225")
        
        self.assertIsNotNone(fig)
        # Должна быть 1 линия (облигация 1)
        self.assertEqual(len(fig.data), 1)

    def test_two_bonds(self):
        """График с двумя облигациями"""
        dates = pd.date_range('2024-01-01', periods=30, freq='D')
        df1 = pd.DataFrame({'ytm': np.random.uniform(14, 15, 30)}, index=dates)
        df2 = pd.DataFrame({'ytm': np.random.uniform(13, 14, 30)}, index=dates)
        
        fig = self.create_chart(df1, df2, "ОФЗ 26221", "ОФЗ 26225")
        
        self.assertEqual(len(fig.data), 2)

    def test_bond1_color_dark_blue(self):
        """Облигация 1 — тёмно-синий цвет"""
        dates = pd.date_range('2024-01-01', periods=10, freq='D')
        df1 = pd.DataFrame({'ytm': [14.0] * 10}, index=dates)
        df2 = pd.DataFrame()
        
        fig = self.create_chart(df1, df2, "Bond1", "Bond2")
        
        # Цвет линии облигации 1
        color = fig.data[0].line.color
        self.assertEqual(color, '#1a5276')  # BOND1_COLORS["history"]

    def test_bond2_color_dark_red(self):
        """Облигация 2 — тёмно-красный цвет"""
        dates = pd.date_range('2024-01-01', periods=10, freq='D')
        df1 = pd.DataFrame({'ytm': [14.0] * 10}, index=dates)
        df2 = pd.DataFrame({'ytm': [13.0] * 10}, index=dates)
        
        fig = self.create_chart(df1, df2, "Bond1", "Bond2")
        
        # Цвет линии облигации 2
        color = fig.data[1].line.color
        self.assertEqual(color, '#922B21')  # BOND2_COLORS["history"]

    def test_has_legend(self):
        """График имеет легенду"""
        dates = pd.date_range('2024-01-01', periods=10, freq='D')
        df1 = pd.DataFrame({'ytm': [14.0] * 10}, index=dates)
        df2 = pd.DataFrame({'ytm': [13.0] * 10}, index=dates)
        
        fig = self.create_chart(df1, df2, "ОФЗ 26221", "ОФЗ 26225")
        
        # Проверяем наличие легенды
        self.assertIn('legend', fig.layout)
        # Имена в легенде
        self.assertEqual(fig.data[0].name, "ОФЗ 26221")
        self.assertEqual(fig.data[1].name, "ОФЗ 26225")

    def test_hovermode_unified(self):
        """Hovermode = 'x unified'"""
        fig = self.create_chart(pd.DataFrame(), pd.DataFrame(), "B1", "B2")
        
        self.assertEqual(fig.layout.hovermode, 'x unified')

    def test_title_present(self):
        """График имеет заголовок"""
        fig = self.create_chart(pd.DataFrame(), pd.DataFrame(), "B1", "B2")
        
        self.assertIn('title', fig.layout)
        self.assertIn('YTM', fig.layout.title.text)


class TestDailySpreadChart(unittest.TestCase):
    """Тесты для графика спреда по дневным данным"""

    def setUp(self):
        """Импортируем функцию"""
        from components.charts import create_daily_spread_chart
        self.create_chart = create_daily_spread_chart

    def test_empty_dataframe(self):
        """Пустой DataFrame возвращает Figure"""
        df = pd.DataFrame()
        
        fig = self.create_chart(df)
        
        self.assertIsNotNone(fig)

    def test_with_stats(self):
        """График с перцентилями P25, P75, среднее"""
        dates = pd.date_range('2024-01-01', periods=30, freq='D')
        df = pd.DataFrame({
            'date': dates,
            'spread': np.random.uniform(50, 150, 30)
        })
        stats = {
            'mean': 100,
            'p25': 75,
            'p75': 125
        }
        
        fig = self.create_chart(df, stats=stats)
        
        # Должны быть линии перцентилей (shapes в Plotly)
        self.assertGreater(len(fig.layout.shapes), 0)

    def test_without_stats(self):
        """График без статистики (только линия спреда)"""
        dates = pd.date_range('2024-01-01', periods=30, freq='D')
        df = pd.DataFrame({
            'date': dates,
            'spread': np.random.uniform(50, 150, 30)
        })
        
        fig = self.create_chart(df, stats=None)
        
        # Только линия спреда, без перцентилей
        self.assertEqual(len(fig.data), 1)

    def test_spread_fill(self):
        """Заполнение области под графиком"""
        dates = pd.date_range('2024-01-01', periods=10, freq='D')
        df = pd.DataFrame({
            'date': dates,
            'spread': [100] * 10
        })
        
        fig = self.create_chart(df)
        
        # fill='tozeroy'
        self.assertEqual(fig.data[0].fill, 'tozeroy')

    def test_spread_color_purple(self):
        """Цвет спреда — фиолетовый"""
        dates = pd.date_range('2024-01-01', periods=10, freq='D')
        df = pd.DataFrame({
            'date': dates,
            'spread': [100] * 10
        })
        
        fig = self.create_chart(df)
        
        self.assertEqual(fig.data[0].line.color, '#9B59B6')


class TestCombinedYtmChart(unittest.TestCase):
    """Тесты для склеенного графика YTM"""

    def setUp(self):
        """Импортируем функцию"""
        from components.charts import create_combined_ytm_chart
        self.create_chart = create_combined_ytm_chart

    def test_history_only(self):
        """Только исторические данные"""
        dates = pd.date_range('2024-01-01', periods=30, freq='D')
        daily_df = pd.DataFrame({'ytm': [14.0] * 30}, index=dates)
        
        fig = self.create_chart(
            daily_df, pd.DataFrame(),
            pd.DataFrame(), pd.DataFrame(),
            "Bond1", "Bond2"
        )
        
        # Только 1 линия (история bond1)
        self.assertEqual(len(fig.data), 1)

    def test_intraday_only(self):
        """Только intraday данные"""
        dates = pd.date_range('2024-01-01', periods=100, freq='h')
        intraday_df = pd.DataFrame({
            'ytm_close': [14.0 + i*0.01 for i in range(100)]
        }, index=dates)
        
        fig = self.create_chart(
            pd.DataFrame(), pd.DataFrame(),
            intraday_df, pd.DataFrame(),
            "Bond1", "Bond2"
        )
        
        # 1 линия (intraday bond1)
        self.assertEqual(len(fig.data), 1)

    def test_history_and_intraday(self):
        """История + свечи (склеенный график)"""
        # История
        daily_dates = pd.date_range('2024-01-01', periods=30, freq='D')
        daily_df = pd.DataFrame({'ytm': [14.0] * 30}, index=daily_dates)
        
        # Intraday
        intraday_dates = pd.date_range('2024-01-31', periods=24, freq='h')
        intraday_df = pd.DataFrame({
            'ytm_close': [14.5] * 24
        }, index=intraday_dates)
        
        fig = self.create_chart(
            daily_df, pd.DataFrame(),
            intraday_df, pd.DataFrame(),
            "Bond1", "Bond2"
        )
        
        # 2 линии (история + intraday для bond1)
        self.assertEqual(len(fig.data), 2)

    def test_intraday_color_brighter(self):
        """Intraday цвета ярче исторических"""
        dates = pd.date_range('2024-01-01', periods=10, freq='D')
        daily_df = pd.DataFrame({'ytm': [14.0] * 10}, index=dates)
        
        intraday_dates = pd.date_range('2024-01-10', periods=10, freq='h')
        intraday_df = pd.DataFrame({'ytm_close': [14.0] * 10}, index=intraday_dates)
        
        fig = self.create_chart(
            daily_df, pd.DataFrame(),
            intraday_df, pd.DataFrame(),
            "Bond1", "Bond2"
        )
        
        # История bond1: #1a5276 (тёмно-синий)
        # Intraday bond1: #3498DB (ярко-синий)
        history_color = fig.data[0].line.color
        intraday_color = fig.data[1].line.color
        
        self.assertEqual(history_color, '#1a5276')
        self.assertEqual(intraday_color, '#3498DB')

    def test_four_lines_with_two_bonds(self):
        """4 линии при полной загрузке (2 облигации × 2 типа данных)"""
        dates = pd.date_range('2024-01-01', periods=30, freq='D')
        daily_df = pd.DataFrame({'ytm': [14.0] * 30}, index=dates)
        
        intraday_dates = pd.date_range('2024-01-30', periods=10, freq='h')
        intraday_df = pd.DataFrame({'ytm_close': [14.0] * 10}, index=intraday_dates)
        
        fig = self.create_chart(
            daily_df, daily_df.copy(),
            intraday_df, intraday_df.copy(),
            "Bond1", "Bond2"
        )
        
        # 4 линии: bond1 история, bond1 intraday, bond2 история, bond2 intraday
        self.assertEqual(len(fig.data), 4)


class TestIntradaySpreadChart(unittest.TestCase):
    """Тесты для графика intraday спреда"""

    def setUp(self):
        """Импортируем функцию"""
        from components.charts import create_intraday_spread_chart
        self.create_chart = create_intraday_spread_chart

    def test_with_daily_stats_reference(self):
        """Перцентили от дневных данных (референс)"""
        dates = pd.date_range('2024-01-31', periods=24, freq='h')
        df = pd.DataFrame({
            'datetime': dates,
            'spread': [100 + i for i in range(24)]
        })
        
        # Статистика от ДНЕВНЫХ данных
        daily_stats = {
            'p10': 50,
            'p25': 75,
            'mean': 100,
            'p75': 125,
            'p90': 150
        }
        
        fig = self.create_chart(df, daily_stats=daily_stats)
        
        # Должны быть линии перцентилей
        self.assertGreater(len(fig.layout.shapes), 0)

    def test_empty_dataframe(self):
        """Пустой DataFrame"""
        fig = self.create_chart(pd.DataFrame())
        
        self.assertIsNotNone(fig)

    def test_percentile_lines_colors(self):
        """Цвета линий перцентилей"""
        dates = pd.date_range('2024-01-31', periods=10, freq='h')
        df = pd.DataFrame({
            'datetime': dates,
            'spread': [100] * 10
        })
        stats = {'p10': 80, 'p25': 90, 'mean': 100, 'p75': 110, 'p90': 120}
        
        fig = self.create_chart(df, daily_stats=stats)
        
        # Проверяем наличие shapes (линий)
        shapes = fig.layout.shapes
        self.assertEqual(len(shapes), 5)  # p10, p25, mean, p75, p90


class TestApplyZoomRange(unittest.TestCase):
    """Тесты для применения zoom к графику"""

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
        
        # Проверяем что диапазон применён
        self.assertIsNotNone(result.layout.xaxis.range)

    def test_apply_none_range(self):
        """Применение None диапазона (без изменений)"""
        import plotly.graph_objects as go
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=[1, 2, 3], y=[1, 2, 3]))
        
        result = self.apply_zoom(fig, None)
        
        # Должен вернуть тот же figure
        self.assertEqual(result, fig)


def run_tests():
    """Запуск всех тестов"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    suite.addTests(loader.loadTestsFromTestCase(TestCalculateFutureRange))
    suite.addTests(loader.loadTestsFromTestCase(TestDailyYtmChart))
    suite.addTests(loader.loadTestsFromTestCase(TestDailySpreadChart))
    suite.addTests(loader.loadTestsFromTestCase(TestCombinedYtmChart))
    suite.addTests(loader.loadTestsFromTestCase(TestIntradaySpreadChart))
    suite.addTests(loader.loadTestsFromTestCase(TestApplyZoomRange))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)
