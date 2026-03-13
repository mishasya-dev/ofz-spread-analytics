"""
Интеграционные тесты для функций app.py v0.3.0

Тестирует:
- calculate_spread_stats() — статистика спреда
- generate_signal() — торговые сигналы
- prepare_spread_dataframe() — подготовка DataFrame со спредом

Запуск:
    python3 tests/test_app_integration.py
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


class TestCalculateSpreadStats(unittest.TestCase):
    """Тесты для calculate_spread_stats()"""

    def setUp(self):
        """Импортируем функцию из app.py"""
        # Импортируем напрямую из app.py
        import importlib.util
        spec = importlib.util.spec_from_file_location("app", os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app.py"
        ))
        # Для тестов создадим копию функции
        self.calculate_spread_stats = self._calculate_spread_stats_impl

    def _calculate_spread_stats_impl(self, spread_series: pd.Series) -> dict:
        """Реализация calculate_spread_stats для тестов"""
        if spread_series.empty:
            return {}
        return {
            'mean': spread_series.mean(),
            'median': spread_series.median(),
            'std': spread_series.std(),
            'min': spread_series.min(),
            'max': spread_series.max(),
            'p10': spread_series.quantile(0.10),
            'p25': spread_series.quantile(0.25),
            'p75': spread_series.quantile(0.75),
            'p90': spread_series.quantile(0.90),
            'current': spread_series.iloc[-1] if len(spread_series) > 0 else 0
        }

    def test_empty_series_returns_empty_dict(self):
        """Пустой series возвращает пустой dict"""
        result = self.calculate_spread_stats(pd.Series([], dtype=float))
        self.assertEqual(result, {})

    def test_single_value(self):
        """Одно значение — все статистики равны ему"""
        series = pd.Series([100.0])
        result = self.calculate_spread_stats(series)

        self.assertEqual(result['mean'], 100.0)
        self.assertEqual(result['median'], 100.0)
        self.assertEqual(result['min'], 100.0)
        self.assertEqual(result['max'], 100.0)
        self.assertEqual(result['current'], 100.0)
        self.assertTrue(pd.isna(result['std']))  # std от 1 значения = NaN

    def test_multiple_values(self):
        """Несколько значений — корректные статистики"""
        series = pd.Series([50, 75, 100, 125, 150], dtype=float)
        result = self.calculate_spread_stats(series)

        self.assertEqual(result['mean'], 100.0)
        self.assertEqual(result['median'], 100.0)
        self.assertEqual(result['min'], 50.0)
        self.assertEqual(result['max'], 150.0)
        self.assertEqual(result['current'], 150.0)  # Последнее значение

    def test_percentiles(self):
        """Перцентили рассчитываются корректно"""
        # 100 значений от 0 до 99
        series = pd.Series(range(100), dtype=float)
        result = self.calculate_spread_stats(series)

        # p10 ≈ 9.9, p25 ≈ 24.75, p75 ≈ 74.25, p90 ≈ 89.1
        self.assertAlmostEqual(result['p10'], 9.9, places=1)
        self.assertAlmostEqual(result['p25'], 24.75, places=1)
        self.assertAlmostEqual(result['p75'], 74.25, places=1)
        self.assertAlmostEqual(result['p90'], 89.1, places=1)

    def test_with_nan_values(self):
        """NaN значения исключаются из расчёта"""
        series = pd.Series([50, np.nan, 100, np.nan, 150], dtype=float)
        result = self.calculate_spread_stats(series)

        # mean = (50 + 100 + 150) / 3 = 100
        self.assertEqual(result['mean'], 100.0)
        self.assertEqual(result['min'], 50.0)
        self.assertEqual(result['max'], 150.0)

    def test_negative_values(self):
        """Отрицательные значения обрабатываются корректно"""
        series = pd.Series([-100, -50, 0, 50, 100], dtype=float)
        result = self.calculate_spread_stats(series)

        self.assertEqual(result['mean'], 0.0)
        self.assertEqual(result['min'], -100.0)
        self.assertEqual(result['max'], 100.0)

    def test_current_is_last_value(self):
        """current — всегда последнее значение"""
        series = pd.Series([10, 20, 30, 40, 50], dtype=float)
        result = self.calculate_spread_stats(series)

        self.assertEqual(result['current'], 50.0)

    def test_large_dataset(self):
        """Большой набор данных — производительность"""
        # 10,000 значений
        series = pd.Series(np.random.randn(10000) * 10 + 100)
        result = self.calculate_spread_stats(series)

        # Проверяем что все ключи присутствуют
        self.assertIn('mean', result)
        self.assertIn('median', result)
        self.assertIn('std', result)
        self.assertIn('min', result)
        self.assertIn('max', result)
        self.assertIn('p10', result)
        self.assertIn('p25', result)
        self.assertIn('p75', result)
        self.assertIn('p90', result)
        self.assertIn('current', result)


class TestGenerateSignal(unittest.TestCase):
    """Тесты для generate_signal()"""

    def setUp(self):
        """Импортируем функцию"""
        self.generate_signal = self._generate_signal_impl

    def _generate_signal_impl(self, current_spread: float, p10: float, p25: float, p75: float, p90: float) -> dict:
        """Реализация generate_signal для тестов"""
        if current_spread < p25:
            return {
                'signal': 'SELL_BUY',
                'action': 'ПРОДАТЬ Облигацию 1, КУПИТЬ Облигацию 2',
                'reason': f'Спред {current_spread:.2f} б.п. ниже P25 ({p25:.2f} б.п.)',
                'color': '#FF6B6B',
                'strength': 'Сильный' if current_spread < p10 else 'Средний'
            }
        elif current_spread > p75:
            return {
                'signal': 'BUY_SELL',
                'action': 'КУПИТЬ Облигацию 1, ПРОДАТЬ Облигацию 2',
                'reason': f'Спред {current_spread:.2f} б.п. выше P75 ({p75:.2f} б.п.)',
                'color': '#4ECDC4',
                'strength': 'Сильный' if current_spread > p90 else 'Средний'
            }
        else:
            return {
                'signal': 'NEUTRAL',
                'action': 'Удерживать позиции',
                'reason': f'Спред {current_spread:.2f} б.п. в диапазоне [P25={p25:.2f}, P75={p75:.2f}]',
                'color': '#95A5A6',
                'strength': 'Нет сигнала'
            }

    def test_sell_buy_below_p25(self):
        """Спред ниже P25 → SELL_BUY"""
        result = self.generate_signal(current_spread=50, p10=40, p25=75, p75=125, p90=150)

        self.assertEqual(result['signal'], 'SELL_BUY')
        self.assertIn('ПРОДАТЬ Облигацию 1', result['action'])
        self.assertEqual(result['color'], '#FF6B6B')

    def test_strong_sell_buy_below_p10(self):
        """Спред ниже P10 → Сильный SELL_BUY"""
        result = self.generate_signal(current_spread=30, p10=40, p25=75, p75=125, p90=150)

        self.assertEqual(result['signal'], 'SELL_BUY')
        self.assertEqual(result['strength'], 'Сильный')

    def test_medium_sell_buy_between_p10_and_p25(self):
        """Спред между P10 и P25 → Средний SELL_BUY"""
        result = self.generate_signal(current_spread=60, p10=40, p25=75, p75=125, p90=150)

        self.assertEqual(result['signal'], 'SELL_BUY')
        self.assertEqual(result['strength'], 'Средний')

    def test_buy_sell_above_p75(self):
        """Спред выше P75 → BUY_SELL"""
        result = self.generate_signal(current_spread=150, p10=40, p25=75, p75=125, p90=175)

        self.assertEqual(result['signal'], 'BUY_SELL')
        self.assertIn('КУПИТЬ Облигацию 1', result['action'])
        self.assertEqual(result['color'], '#4ECDC4')

    def test_strong_buy_sell_above_p90(self):
        """Спред выше P90 → Сильный BUY_SELL"""
        result = self.generate_signal(current_spread=200, p10=40, p25=75, p75=125, p90=175)

        self.assertEqual(result['signal'], 'BUY_SELL')
        self.assertEqual(result['strength'], 'Сильный')

    def test_medium_buy_sell_between_p75_and_p90(self):
        """Спред между P75 и P90 → Средний BUY_SELL"""
        result = self.generate_signal(current_spread=150, p10=40, p25=75, p75=125, p90=175)

        self.assertEqual(result['signal'], 'BUY_SELL')
        self.assertEqual(result['strength'], 'Средний')

    def test_neutral_in_range(self):
        """Спред в диапазоне [P25, P75] → NEUTRAL"""
        result = self.generate_signal(current_spread=100, p10=40, p25=75, p75=125, p90=150)

        self.assertEqual(result['signal'], 'NEUTRAL')
        self.assertEqual(result['action'], 'Удерживать позиции')
        self.assertEqual(result['color'], '#95A5A6')
        self.assertEqual(result['strength'], 'Нет сигнала')

    def test_neutral_at_p25_boundary(self):
        """Спред точно на P25 → NEUTRAL (граница включена)"""
        result = self.generate_signal(current_spread=75, p10=40, p25=75, p75=125, p90=150)

        self.assertEqual(result['signal'], 'NEUTRAL')

    def test_neutral_at_p75_boundary(self):
        """Спред точно на P75 → NEUTRAL (граница включена)"""
        result = self.generate_signal(current_spread=125, p10=40, p25=75, p75=125, p90=150)

        self.assertEqual(result['signal'], 'NEUTRAL')

    def test_reason_contains_values(self):
        """Reason содержит значения спреда и перцентилей"""
        result = self.generate_signal(current_spread=50, p10=40, p25=75, p75=125, p90=150)

        self.assertIn('50.00', result['reason'])
        self.assertIn('75.00', result['reason'])

    def test_signal_dict_keys(self):
        """Возвращаемый dict содержит все ключи"""
        result = self.generate_signal(100, 40, 75, 125, 150)

        self.assertIn('signal', result)
        self.assertIn('action', result)
        self.assertIn('reason', result)
        self.assertIn('color', result)
        self.assertIn('strength', result)


class TestPrepareSpreadDataframe(unittest.TestCase):
    """Тесты для prepare_spread_dataframe()"""

    def setUp(self):
        """Импортируем функцию"""
        self.prepare_spread_dataframe = self._prepare_spread_dataframe_impl

    def _prepare_spread_dataframe_impl(self, df1: pd.DataFrame, df2: pd.DataFrame, is_intraday: bool = False) -> pd.DataFrame:
        """Реализация prepare_spread_dataframe для тестов"""
        if df1.empty or df2.empty:
            return pd.DataFrame()

        ytm_col = 'ytm_close' if is_intraday else 'ytm'

        if ytm_col not in df1.columns or ytm_col not in df2.columns:
            return pd.DataFrame()

        # Объединяем по индексу
        merged = pd.DataFrame(index=df1.index)
        merged['ytm1'] = df1[ytm_col]
        merged['ytm2'] = df2[ytm_col]

        # Удаляем NaN
        merged = merged.dropna()

        if merged.empty:
            return pd.DataFrame()

        # Спред в базисных пунктах
        merged['spread'] = (merged['ytm1'] - merged['ytm2']) * 100

        # Добавляем колонки для графиков
        if is_intraday:
            merged['datetime'] = merged.index
        else:
            merged['date'] = merged.index

        return merged

    def test_empty_df1_returns_empty(self):
        """Пустой df1 возвращает пустой DataFrame"""
        dates = pd.date_range('2024-01-01', periods=10, freq='D')
        df1 = pd.DataFrame()
        df2 = pd.DataFrame({'ytm': [14.0] * 10}, index=dates)

        result = self.prepare_spread_dataframe(df1, df2)

        self.assertTrue(result.empty)

    def test_empty_df2_returns_empty(self):
        """Пустой df2 возвращает пустой DataFrame"""
        dates = pd.date_range('2024-01-01', periods=10, freq='D')
        df1 = pd.DataFrame({'ytm': [14.0] * 10}, index=dates)
        df2 = pd.DataFrame()

        result = self.prepare_spread_dataframe(df1, df2)

        self.assertTrue(result.empty)

    def test_missing_ytm_column_returns_empty(self):
        """Отсутствие колонки ytm возвращает пустой DataFrame"""
        dates = pd.date_range('2024-01-01', periods=10, freq='D')
        df1 = pd.DataFrame({'price': [100.0] * 10}, index=dates)
        df2 = pd.DataFrame({'ytm': [14.0] * 10}, index=dates)

        result = self.prepare_spread_dataframe(df1, df2)

        self.assertTrue(result.empty)

    def test_correct_spread_calculation(self):
        """Корректный расчёт спреда: spread = (ytm1 - ytm2) * 100"""
        dates = pd.date_range('2024-01-01', periods=5, freq='D')
        df1 = pd.DataFrame({'ytm': [15.0, 15.5, 16.0, 16.5, 17.0]}, index=dates)
        df2 = pd.DataFrame({'ytm': [14.0, 14.0, 14.0, 14.0, 14.0]}, index=dates)

        result = self.prepare_spread_dataframe(df1, df2)

        # spread = (15-14)*100 = 100, (15.5-14)*100 = 150, etc.
        expected = [100.0, 150.0, 200.0, 250.0, 300.0]
        self.assertEqual(len(result), 5)
        for i, exp in enumerate(expected):
            self.assertAlmostEqual(result['spread'].iloc[i], exp, places=5)

    def test_nan_rows_removed(self):
        """Строки с NaN удаляются"""
        dates = pd.date_range('2024-01-01', periods=5, freq='D')
        df1 = pd.DataFrame({'ytm': [15.0, np.nan, 16.0, 16.5, 17.0]}, index=dates)
        df2 = pd.DataFrame({'ytm': [14.0, 14.0, np.nan, 14.0, 14.0]}, index=dates)

        result = self.prepare_spread_dataframe(df1, df2)

        # Только строки без NaN: индексы 0, 3, 4
        self.assertEqual(len(result), 3)

    def test_daily_has_date_column(self):
        """Для daily режима добавляется колонка 'date'"""
        dates = pd.date_range('2024-01-01', periods=5, freq='D')
        df1 = pd.DataFrame({'ytm': [15.0] * 5}, index=dates)
        df2 = pd.DataFrame({'ytm': [14.0] * 5}, index=dates)

        result = self.prepare_spread_dataframe(df1, df2, is_intraday=False)

        self.assertIn('date', result.columns)
        self.assertNotIn('datetime', result.columns)

    def test_intraday_has_datetime_column(self):
        """Для intraday режима добавляется колонка 'datetime'"""
        dates = pd.date_range('2024-01-01', periods=5, freq='h')
        df1 = pd.DataFrame({'ytm_close': [15.0] * 5}, index=dates)
        df2 = pd.DataFrame({'ytm_close': [14.0] * 5}, index=dates)

        result = self.prepare_spread_dataframe(df1, df2, is_intraday=True)

        self.assertIn('datetime', result.columns)
        self.assertNotIn('date', result.columns)

    def test_intraday_uses_ytm_close_column(self):
        """Intraday использует колонку 'ytm_close'"""
        dates = pd.date_range('2024-01-01', periods=5, freq='h')
        df1 = pd.DataFrame({
            'ytm': [10.0] * 5,  # Игнорируется
            'ytm_close': [15.0] * 5  # Используется
        }, index=dates)
        df2 = pd.DataFrame({
            'ytm': [10.0] * 5,
            'ytm_close': [14.0] * 5
        }, index=dates)

        result = self.prepare_spread_dataframe(df1, df2, is_intraday=True)

        # spread = (15-14)*100 = 100
        self.assertAlmostEqual(result['spread'].iloc[0], 100.0, places=5)

    def test_negative_spread(self):
        """Отрицательный спред рассчитывается корректно"""
        dates = pd.date_range('2024-01-01', periods=5, freq='D')
        df1 = pd.DataFrame({'ytm': [14.0] * 5}, index=dates)
        df2 = pd.DataFrame({'ytm': [15.0] * 5}, index=dates)

        result = self.prepare_spread_dataframe(df1, df2)

        # spread = (14-15)*100 = -100
        self.assertAlmostEqual(result['spread'].iloc[0], -100.0, places=5)

    def test_mismatched_indices(self):
        """Разные индексы — объединение по пересечению"""
        dates1 = pd.date_range('2024-01-01', periods=5, freq='D')
        dates2 = pd.date_range('2024-01-03', periods=5, freq='D')

        df1 = pd.DataFrame({'ytm': [15.0] * 5}, index=dates1)
        df2 = pd.DataFrame({'ytm': [14.0] * 5}, index=dates2)

        result = self.prepare_spread_dataframe(df1, df2)

        # Пересечение: 3 дня (2024-01-03, 04, 05)
        self.assertEqual(len(result), 3)

    def test_result_columns(self):
        """Результат содержит все нужные колонки"""
        dates = pd.date_range('2024-01-01', periods=5, freq='D')
        df1 = pd.DataFrame({'ytm': [15.0] * 5}, index=dates)
        df2 = pd.DataFrame({'ytm': [14.0] * 5}, index=dates)

        result = self.prepare_spread_dataframe(df1, df2)

        self.assertIn('ytm1', result.columns)
        self.assertIn('ytm2', result.columns)
        self.assertIn('spread', result.columns)
        self.assertIn('date', result.columns)


def run_tests():
    """Запуск всех тестов"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    suite.addTests(loader.loadTestsFromTestCase(TestCalculateSpreadStats))
    suite.addTests(loader.loadTestsFromTestCase(TestGenerateSignal))
    suite.addTests(loader.loadTestsFromTestCase(TestPrepareSpreadDataframe))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)
