"""
Тесты с фиксированными наборами данных с известными результатами.

Наборы данных:
- cointegrated_pair.csv: коинтегрированная пара (p < 0.05)
- not_cointegrated_pair.csv: некоинтегрированная пара (p > 0.05)
- stationary_pair.csv: стационарные ряды (коинтеграция не применима)
"""
import sys
import os
import pytest
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.cointegration import CointegrationAnalyzer, format_cointegration_report


class TestCointegratedPair:
    """Тесты на коинтегрированной паре (известный результат: is_cointegrated = True)"""
    
    @pytest.fixture
    def data(self):
        df = pd.read_csv('tests/test_data/cointegrated_pair.csv')
        return df['ytm1'], df['ytm2']
    
    def test_both_nonstationary(self, data):
        """Оба ряда должны быть нестационарны"""
        ytm1, ytm2 = data
        analyzer = CointegrationAnalyzer()
        
        adf1 = analyzer.adf_test(ytm1)
        adf2 = analyzer.adf_test(ytm2)
        
        assert adf1['is_nonstationary'] == True, f"ytm1 должен быть нестационарен, p={adf1['pvalue']}"
        assert adf2['is_nonstationary'] == True, f"ytm2 должен быть нестационарен, p={adf2['pvalue']}"
    
    def test_is_cointegrated(self, data):
        """Пара должна быть коинтегрирована"""
        ytm1, ytm2 = data
        analyzer = CointegrationAnalyzer()
        
        result = analyzer.analyze_pair(ytm1, ytm2)
        
        assert result['is_cointegrated'] == True, f"p-value = {result['engle_granger']['pvalue']}"
        assert result['both_nonstationary'] == True
    
    def test_pvalue_below_threshold(self, data):
        """p-value должен быть значительно ниже 0.05"""
        ytm1, ytm2 = data
        analyzer = CointegrationAnalyzer()
        
        result = analyzer.analyze_pair(ytm1, ytm2)
        
        assert result['engle_granger']['pvalue'] < 0.01, \
            f"Ожидается p < 0.01, получено p = {result['engle_granger']['pvalue']}"
    
    def test_half_life_exists(self, data):
        """Half-life должен быть рассчитан"""
        ytm1, ytm2 = data
        analyzer = CointegrationAnalyzer()
        
        result = analyzer.analyze_pair(ytm1, ytm2)
        
        assert result['half_life'] is not None
        assert result['half_life'] != float('inf')
        assert result['half_life'] > 0
    
    def test_recommendation_is_pair_trading(self, data):
        """Рекомендация должна быть Pair Trading"""
        ytm1, ytm2 = data
        analyzer = CointegrationAnalyzer()
        
        result = analyzer.analyze_pair(ytm1, ytm2)
        
        assert 'Pair Trading' in result['recommendation']['strategy']
        assert result['recommendation']['risk'] in ['low', 'medium']


class TestNotCointegratedPair:
    """Тесты на некоинтегрированной паре (известный результат: is_cointegrated = False)"""
    
    @pytest.fixture
    def data(self):
        df = pd.read_csv('tests/test_data/not_cointegrated_pair.csv')
        return df['ytm1'], df['ytm2']
    
    def test_both_nonstationary(self, data):
        """Оба ряда должны быть нестационарны"""
        ytm1, ytm2 = data
        analyzer = CointegrationAnalyzer()
        
        adf1 = analyzer.adf_test(ytm1)
        adf2 = analyzer.adf_test(ytm2)
        
        assert adf1['is_nonstationary'] == True
        assert adf2['is_nonstationary'] == True
    
    def test_not_cointegrated(self, data):
        """Пара НЕ должна быть коинтегрирована"""
        ytm1, ytm2 = data
        analyzer = CointegrationAnalyzer()
        
        result = analyzer.analyze_pair(ytm1, ytm2)
        
        assert result['is_cointegrated'] == False, \
            f"Ожидается is_cointegrated=False, p-value = {result['engle_granger']['pvalue']}"
        assert result['both_nonstationary'] == True
    
    def test_pvalue_above_threshold(self, data):
        """p-value должен быть выше 0.05"""
        ytm1, ytm2 = data
        analyzer = CointegrationAnalyzer()
        
        result = analyzer.analyze_pair(ytm1, ytm2)
        
        assert result['engle_granger']['pvalue'] > 0.05, \
            f"Ожидается p > 0.05, получено p = {result['engle_granger']['pvalue']}"
    
    def test_recommendation_not_recommended(self, data):
        """Рекомендация должна быть 'Не рекомендуется'"""
        ytm1, ytm2 = data
        analyzer = CointegrationAnalyzer()
        
        result = analyzer.analyze_pair(ytm1, ytm2)
        
        assert result['recommendation']['risk'] == 'high'
    
    def test_report_no_halflife_shown(self, data):
        """Half-life и Hedge Ratio НЕ должны показываться в отчёте"""
        ytm1, ytm2 = data
        analyzer = CointegrationAnalyzer()
        
        result = analyzer.analyze_pair(ytm1, ytm2)
        report = format_cointegration_report(result, "BOND1", "BOND2")
        
        assert 'Half-life' not in report
        assert 'Hedge Ratio' not in report


class TestStationaryPair:
    """Тесты на стационарных рядах (коинтеграция не применима)"""
    
    @pytest.fixture
    def data(self):
        df = pd.read_csv('tests/test_data/stationary_pair.csv')
        return df['ytm1'], df['ytm2']
    
    def test_both_stationary(self, data):
        """Оба ряда должны быть стационарны"""
        ytm1, ytm2 = data
        analyzer = CointegrationAnalyzer()
        
        adf1 = analyzer.adf_test(ytm1)
        adf2 = analyzer.adf_test(ytm2)
        
        assert adf1['is_stationary'] == True, f"ytm1 должен быть стационарен, p={adf1['pvalue']}"
        assert adf2['is_stationary'] == True, f"ytm2 должен быть стационарен, p={adf2['pvalue']}"
    
    def test_not_both_nonstationary(self, data):
        """both_nonstationary должен быть False"""
        ytm1, ytm2 = data
        analyzer = CointegrationAnalyzer()
        
        result = analyzer.analyze_pair(ytm1, ytm2)
        
        assert result['both_nonstationary'] == False
    
    def test_recommendation_not_applicable(self, data):
        """Рекомендация должна быть 'Не применимо'"""
        ytm1, ytm2 = data
        analyzer = CointegrationAnalyzer()
        
        result = analyzer.analyze_pair(ytm1, ytm2)
        
        assert 'Не применимо' in result['recommendation']['strategy'] or \
               result['recommendation']['risk'] == 'high'


class TestBidirectionalCointegration:
    """Тесты для проверки bidirectional режима"""
    
    def test_bidirectional_finds_best_direction(self):
        """Bidirectional режим должен находить лучшее направление"""
        df = pd.read_csv('tests/test_data/cointegrated_pair.csv')
        ytm1, ytm2 = df['ytm1'], df['ytm2']
        
        analyzer = CointegrationAnalyzer()
        
        # Bidirectional (по умолчанию)
        result_bi = analyzer.engle_granger_test(ytm1, ytm2, bidirectional=True)
        
        # Однонаправленный
        result_single = analyzer.engle_granger_test(ytm1, ytm2, bidirectional=False)
        
        # Bidirectional должен давать p-value <= чем однонаправленный
        assert result_bi['pvalue'] <= result_single['pvalue'] + 0.0001, \
            f"Bidirectional p={result_bi['pvalue']} должен быть <= single p={result_single['pvalue']}"
    
    def test_direction_field_present(self):
        """Результат должен содержать поле direction"""
        df = pd.read_csv('tests/test_data/cointegrated_pair.csv')
        ytm1, ytm2 = df['ytm1'], df['ytm2']
        
        analyzer = CointegrationAnalyzer()
        result = analyzer.engle_granger_test(ytm1, ytm2)
        
        assert 'direction' in result
        assert result['direction'] in ['ytm1_ytm2', 'ytm2_ytm1']


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
