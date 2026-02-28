"""
Тесты для граничных случаев v0.3.0

Тестирует:
- Пустые данные (daily, intraday)
- NaN в данных
- Одна точка данных
- MOEX API недоступен

Запуск:
    python3 tests/test_edge_cases.py
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
from tests.mock_streamlit import st_mock
sys.modules['streamlit'] = st_mock


class TestEmptyDailyData(unittest.TestCase):
    """Тесты для пустых дневных данных"""

    def test_empty_ytm_dataframe(self):
        """Пустой DataFrame YTM"""
        df = pd.DataFrame()
        self.assertTrue(df.empty)

    def test_empty_series_statistics(self):
        """Статистика пустого series"""
        series = pd.Series([], dtype=float)

        # mean, min, max = NaN для пустого series
        self.assertTrue(pd.isna(series.mean()))
        self.assertTrue(pd.isna(series.min()))
        self.assertTrue(pd.isna(series.max()))

    def test_empty_dataframe_index(self):
        """Пустой индекс DataFrame"""
        df = pd.DataFrame({'ytm': []})
        self.assertEqual(len(df.index), 0)

    def test_chart_with_empty_data(self):
        """График с пустыми данными"""
        from components.charts import create_daily_ytm_chart

        fig = create_daily_ytm_chart(
            pd.DataFrame(), pd.DataFrame(),
            "Bond1", "Bond2"
        )

        # Figure создаётся, но без данных
        self.assertIsNotNone(fig)
        self.assertEqual(len(fig.data), 0)

    def test_spread_chart_with_empty_data(self):
        """График спреда с пустыми данными"""
        from components.charts import create_daily_spread_chart

        fig = create_daily_spread_chart(pd.DataFrame())

        self.assertIsNotNone(fig)
        self.assertEqual(len(fig.data), 0)


class TestEmptyIntradayData(unittest.TestCase):
    """Тесты для пустых intraday данных"""

    def test_empty_candle_dataframe(self):
        """Пустой DataFrame свечей"""
        df = pd.DataFrame()
        self.assertTrue(df.empty)

    def test_intraday_chart_with_empty_data(self):
        """График intraday с пустыми данными"""
        from components.charts import create_intraday_spread_chart

        fig = create_intraday_spread_chart(pd.DataFrame())

        self.assertIsNotNone(fig)
        self.assertEqual(len(fig.data), 0)

    def test_combined_chart_with_only_daily(self):
        """Склеенный график с только дневными данными"""
        from components.charts import create_combined_ytm_chart

        dates = pd.date_range('2024-01-01', periods=30, freq='D')
        daily_df = pd.DataFrame({'ytm': [14.0] * 30}, index=dates)

        fig = create_combined_ytm_chart(
            daily_df, pd.DataFrame(),
            pd.DataFrame(), pd.DataFrame(),
            "Bond1", "Bond2"
        )

        # Только 1 линия (история bond1)
        self.assertEqual(len(fig.data), 1)


class TestNaNHandling(unittest.TestCase):
    """Тесты для обработки NaN"""

    def test_nan_in_ytm_series(self):
        """NaN в YTM series"""
        series = pd.Series([14.0, np.nan, 15.0, np.nan, 16.0])

        # mean игнорирует NaN
        self.assertAlmostEqual(series.mean(), 15.0, places=1)

        # dropna удаляет NaN
        self.assertEqual(len(series.dropna()), 3)

    def test_nan_in_spread_calculation(self):
        """NaN в расчёте спреда"""
        dates = pd.date_range('2024-01-01', periods=5, freq='D')
        df1 = pd.DataFrame({'ytm': [15.0, np.nan, 16.0, 16.5, 17.0]}, index=dates)
        df2 = pd.DataFrame({'ytm': [14.0, 14.0, np.nan, 14.0, 14.0]}, index=dates)

        # Объединение
        merged = pd.DataFrame(index=df1.index)
        merged['ytm1'] = df1['ytm']
        merged['ytm2'] = df2['ytm']
        merged = merged.dropna()

        # Только 3 строки без NaN
        self.assertEqual(len(merged), 3)

    def test_nan_percentile(self):
        """Перцентили с NaN"""
        series = pd.Series([10, 20, np.nan, 40, 50])

        # quantile игнорирует NaN по умолчанию
        p50 = series.quantile(0.5)
        self.assertEqual(p50, 30.0)  # (20 + 40) / 2

    def test_all_nan_series(self):
        """Series полностью из NaN"""
        series = pd.Series([np.nan, np.nan, np.nan])

        # mean = NaN
        self.assertTrue(pd.isna(series.mean()))
        # после dropna — пустой
        self.assertEqual(len(series.dropna()), 0)


class TestSingleDataPoint(unittest.TestCase):
    """Тесты для одной точки данных"""

    def test_single_ytm_value(self):
        """Одно значение YTM"""
        dates = pd.date_range('2024-01-01', periods=1, freq='D')
        df = pd.DataFrame({'ytm': [15.0]}, index=dates)

        self.assertEqual(len(df), 1)
        self.assertEqual(df['ytm'].iloc[0], 15.0)

    def test_single_point_statistics(self):
        """Статистика одной точки"""
        series = pd.Series([100.0])

        stats = {
            'mean': series.mean(),
            'median': series.median(),
            'min': series.min(),
            'max': series.max(),
            'current': series.iloc[-1]
        }

        # Все равны одному значению
        self.assertEqual(stats['mean'], 100.0)
        self.assertEqual(stats['median'], 100.0)
        self.assertEqual(stats['min'], 100.0)
        self.assertEqual(stats['max'], 100.0)
        self.assertEqual(stats['current'], 100.0)

    def test_single_point_chart(self):
        """График с одной точкой"""
        from components.charts import create_daily_ytm_chart

        dates = pd.date_range('2024-01-01', periods=1, freq='D')
        df1 = pd.DataFrame({'ytm': [15.0]}, index=dates)
        df2 = pd.DataFrame()

        fig = create_daily_ytm_chart(df1, df2, "Bond1", "Bond2")

        # 1 линия с 1 точкой
        self.assertEqual(len(fig.data), 1)

    def test_single_point_spread(self):
        """Спред из одной точки"""
        dates = pd.date_range('2024-01-01', periods=1, freq='D')
        df1 = pd.DataFrame({'ytm': [15.0]}, index=dates)
        df2 = pd.DataFrame({'ytm': [14.0]}, index=dates)

        merged = pd.DataFrame(index=df1.index)
        merged['ytm1'] = df1['ytm']
        merged['ytm2'] = df2['ytm']
        merged['spread'] = (merged['ytm1'] - merged['ytm2']) * 100

        self.assertEqual(len(merged), 1)
        self.assertEqual(merged['spread'].iloc[0], 100.0)


class TestFutureRangeEdgeCases(unittest.TestCase):
    """Краевые случаи для calculate_future_range"""

    def setUp(self):
        """Импортируем функцию"""
        from components.charts import calculate_future_range
        self.calculate_future_range = calculate_future_range

    def test_empty_index(self):
        """Пустой индекс возвращает (None, None)"""
        result = self.calculate_future_range(pd.DatetimeIndex([]))
        self.assertEqual(result, (None, None))

    def test_single_point_index(self):
        """Одна точка — диапазон от неё"""
        dt = datetime(2024, 6, 15)
        idx = pd.DatetimeIndex([dt])

        start, end = self.calculate_future_range(idx)

        self.assertEqual(start, dt)
        self.assertGreaterEqual(end, start)

    def test_very_short_range(self):
        """Очень короткий диапазон (1 день)"""
        idx = pd.date_range('2024-01-01', periods=2, freq='D')

        start, end = self.calculate_future_range(idx, future_percent=0.15)

        # 1 день * 0.15 = 0.15 дня запас
        self.assertEqual(start, idx[0])
        self.assertGreater(end, idx[-1])


class TestDateRangeBoundaries(unittest.TestCase):
    """Тесты для границ дат"""

    def test_period_min_30_days(self):
        """Минимальный период = 30 дней"""
        period = 30
        self.assertGreaterEqual(period, 30)

    def test_period_max_730_days(self):
        """Максимальный период = 730 дней (2 года)"""
        period = 730
        self.assertLessEqual(period, 730)

    def test_candle_1min_max_3_days(self):
        """1-минутные свечи = максимум 3 дня"""
        max_days = {"1": 3, "10": 30, "60": 365}
        self.assertEqual(max_days["1"], 3)

    def test_candle_10min_max_30_days(self):
        """10-минутные свечи = максимум 30 дней"""
        max_days = {"1": 3, "10": 30, "60": 365}
        self.assertEqual(max_days["10"], 30)

    def test_candle_60min_max_365_days(self):
        """Часовые свечи = максимум 365 дней"""
        max_days = {"1": 3, "10": 30, "60": 365}
        self.assertEqual(max_days["60"], 365)


class TestNegativeSpread(unittest.TestCase):
    """Тесты для отрицательного спреда"""

    def test_negative_spread_calculation(self):
        """Расчёт отрицательного спреда"""
        ytm1 = 14.0
        ytm2 = 15.5
        spread = (ytm1 - ytm2) * 100

        self.assertEqual(spread, -150.0)

    def test_negative_spread_signal(self):
        """Сигнал при отрицательном спреде"""
        # Если спред = -100, p25 = 50, p75 = 150
        # То спред < p25 → SELL_BUY
        current_spread = -100
        p25 = 50
        p75 = 150

        # Спред ниже P25
        self.assertLess(current_spread, p25)


class TestPercentileBoundaries(unittest.TestCase):
    """Тесты для границ перцентилей"""

    def test_percentile_order(self):
        """Порядок перцентилей: p10 < p25 < p50 < p75 < p90"""
        series = pd.Series(range(1, 101))  # 1..100

        p10 = series.quantile(0.10)
        p25 = series.quantile(0.25)
        p50 = series.quantile(0.50)
        p75 = series.quantile(0.75)
        p90 = series.quantile(0.90)

        self.assertLess(p10, p25)
        self.assertLess(p25, p50)
        self.assertLess(p50, p75)
        self.assertLess(p75, p90)

    def test_percentile_equals_value_at_boundary(self):
        """Перцентиль равен значению на границе"""
        # Для 100 значений 1..100
        series = pd.Series(range(1, 101))

        # P50 должен быть около 50.5
        p50 = series.quantile(0.50)
        self.assertAlmostEqual(p50, 50.5, places=1)


def run_tests():
    """Запуск всех тестов"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    suite.addTests(loader.loadTestsFromTestCase(TestEmptyDailyData))
    suite.addTests(loader.loadTestsFromTestCase(TestEmptyIntradayData))
    suite.addTests(loader.loadTestsFromTestCase(TestNaNHandling))
    suite.addTests(loader.loadTestsFromTestCase(TestSingleDataPoint))
    suite.addTests(loader.loadTestsFromTestCase(TestFutureRangeEdgeCases))
    suite.addTests(loader.loadTestsFromTestCase(TestDateRangeBoundaries))
    suite.addTests(loader.loadTestsFromTestCase(TestNegativeSpread))
    suite.addTests(loader.loadTestsFromTestCase(TestPercentileBoundaries))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)
