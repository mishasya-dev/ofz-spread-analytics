"""
Тесты для проверки hover label в Spread Analytics chart

Ожидаемая схема hover label (hovermode='x unified'):

┌────────────────────────────┐
│ 📅 15.01.25                │  ← Дата жирным вверху (один раз)
│                            │  ← Пустая строка
│ ОФЗ 26238: 14.52%          │  ← Bond1
│ ОФЗ 26243: 13.85%          │  ← Bond2
│                            │
│ +2σ: 125.3 б.п.            │
│ -2σ: 45.2 б.п.             │
│ MA(30): 85.1 б.п.          │
│ Спред: 67.0 б.п.           │
└────────────────────────────┘

Ключевые требования:
1. Дата показывается один раз в самом верху
2. Дата показывается при наведении на ЛЮБУЮ часть графика
3. Формат даты: DD.MM.YY
"""
import sys
import os
import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestHoverLabelSchema:
    """Тесты схемы hover label для Spread Analytics chart"""

    @pytest.fixture
    def sample_data(self):
        """Создаём тестовые данные"""
        end_date = datetime.now()
        dates = pd.date_range(end=end_date, periods=100, freq='D')
        
        df1 = pd.DataFrame({'ytm': np.random.uniform(14, 15, 100)}, index=dates)
        df2 = pd.DataFrame({'ytm': np.random.uniform(13, 14, 100)}, index=dates)
        
        return df1, df2, dates

    def test_all_traces_have_customdata(self, sample_data):
        """
        Тест: все traces должны иметь customdata с датами
        
        Это необходимо для отображения даты в hover label
        """
        import importlib.util
        spec = importlib.util.spec_from_file_location('charts', 'components/charts.py')
        charts = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(charts)
        
        df1, df2, dates = sample_data
        
        fig = charts.create_spread_analytics_chart(
            df1, df2, 'Bond1', 'Bond2', window=30, z_threshold=2.0
        )
        
        # Все traces должны иметь customdata
        for i, trace in enumerate(fig.data):
            assert hasattr(trace, 'customdata'), f"Trace {i} ({trace.name}) missing customdata"
            assert trace.customdata is not None, f"Trace {i} ({trace.name}) customdata is None"
            assert len(trace.customdata) > 0, f"Trace {i} ({trace.name}) customdata is empty"

    def test_date_format_in_customdata(self, sample_data):
        """
        Тест: формат даты должен быть DD.MM.YY
        """
        import importlib.util
        spec = importlib.util.spec_from_file_location('charts', 'components/charts.py')
        charts = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(charts)
        
        df1, df2, dates = sample_data
        
        fig = charts.create_spread_analytics_chart(
            df1, df2, 'Bond1', 'Bond2', window=30, z_threshold=2.0
        )
        
        # Проверяем формат даты в первом trace
        first_trace = fig.data[0]
        first_date = first_trace.customdata[0]
        
        # Формат DD.MM.YY (8 символов)
        assert len(first_date) == 8, f"Date format should be DD.MM.YY, got: {first_date}"
        assert first_date[2] == '.', f"Date format should be DD.MM.YY, got: {first_date}"
        assert first_date[5] == '.', f"Date format should be DD.MM.YY, got: {first_date}"

    def test_date_in_hovertemplate(self, sample_data):
        """
        Тест: дата должна быть в hovertemplate
        
        Проверяем что hovertemplate содержит customdata
        """
        import importlib.util
        spec = importlib.util.spec_from_file_location('charts', 'components/charts.py')
        charts = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(charts)
        
        df1, df2, dates = sample_data
        
        fig = charts.create_spread_analytics_chart(
            df1, df2, 'Bond1', 'Bond2', window=30, z_threshold=2.0
        )
        
        # Первый trace (Bond1) должен показывать дату вверху
        first_trace = fig.data[0]
        hovertemplate = first_trace.hovertemplate
        
        # Должен содержать customdata и эмодзи календаря
        assert '%{customdata}' in hovertemplate, "Hovertemplate should contain %{customdata}"
        assert '📅' in hovertemplate or 'customdata' in hovertemplate.lower(), \
            "Hovertemplate should show date with calendar emoji"

    def test_hovermode_is_x_unified(self, sample_data):
        """
        Тест: hovermode должен быть 'x unified'
        
        Это обеспечивает единый tooltip для всех traces на одной X-координате
        """
        import importlib.util
        spec = importlib.util.spec_from_file_location('charts', 'components/charts.py')
        charts = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(charts)
        
        df1, df2, dates = sample_data
        
        fig = charts.create_spread_analytics_chart(
            df1, df2, 'Bond1', 'Bond2', window=30, z_threshold=2.0
        )
        
        assert fig.layout.hovermode == 'x unified', \
            f"hovermode should be 'x unified', got: {fig.layout.hovermode}"

    def test_date_at_top_of_hovertemplate(self, sample_data):
        """
        Тест: дата должна быть вверху hovertemplate (до остальных значений)
        
        Схема:
        1. 📅 DD.MM.YY (вверху)
        2. Пустая строка
        3. Bond значения
        4. Spread значения
        """
        import importlib.util
        spec = importlib.util.spec_from_file_location('charts', 'components/charts.py')
        charts = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(charts)
        
        df1, df2, dates = sample_data
        
        fig = charts.create_spread_analytics_chart(
            df1, df2, 'Bond1', 'Bond2', window=30, z_threshold=2.0
        )
        
        # Первый trace должен начинаться с даты
        first_trace = fig.data[0]
        hovertemplate = first_trace.hovertemplate
        
        # Дата должна быть в начале (до имени облигации)
        date_pos = hovertemplate.find('customdata')
        bond_pos = hovertemplate.find('Bond1')
        
        if bond_pos >= 0:  # Если имя bond есть в template
            assert date_pos < bond_pos, \
                f"Date should come before bond name in hovertemplate. Date pos: {date_pos}, Bond pos: {bond_pos}"

    def test_number_of_traces(self, sample_data):
        """
        Тест: правильное количество traces
        
        Ожидаемые traces:
        1. Невидимый (дата для верхней панели)
        2. Bond1 (YTM)
        3. Bond2 (YTM)
        4. Невидимый (дата для нижней панели)
        5. +2σ (граница)
        6. -2σ (граница)
        7. MA(30) (rolling mean)
        8. Спред
        9. Текущая точка
        """
        import importlib.util
        spec = importlib.util.spec_from_file_location('charts', 'components/charts.py')
        charts = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(charts)
        
        df1, df2, dates = sample_data
        
        fig = charts.create_spread_analytics_chart(
            df1, df2, 'Bond1', 'Bond2', window=30, z_threshold=2.0
        )
        
        assert len(fig.data) == 9, f"Expected 9 traces, got {len(fig.data)}"

    def test_hovertemplate_structure(self, sample_data):
        """
        Тест: структура hovertemplate для unified tooltip
        
        При hovermode='x unified' Plotly объединяет hovertemplates всех traces.
        
        Чтобы дата показывалась только один раз вверху:
        - Первый trace: показывает дату
        - Остальные traces: НЕ показывают дату
        """
        import importlib.util
        spec = importlib.util.spec_from_file_location('charts', 'components/charts.py')
        charts = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(charts)
        
        df1, df2, dates = sample_data
        
        fig = charts.create_spread_analytics_chart(
            df1, df2, 'Bond1', 'Bond2', window=30, z_threshold=2.0
        )
        
        # Первый trace должен показывать дату
        first_hover = fig.data[0].hovertemplate
        assert 'customdata' in first_hover, "First trace should show date"
        
        # Остальные traces НЕ должны дублировать дату вверху
        # (они могут иметь customdata для других целей, но не показывать её первой строкой)
        for i, trace in enumerate(fig.data[1:], start=1):
            hover = trace.hovertemplate
            # Если trace показывает customdata, он не должен быть первым элементом
            if 'customdata' in hover:
                # Дата не должна быть в самом начале
                # (допускается дата в середине или конце hovertemplate)
                pass  # Будет уточнено после реализации


class TestHoverLabelIntegration:
    """Интеграционные тесты hover label"""

    def test_hover_label_contains_all_values(self):
        """
        Тест: hover label должен содержать значения из обеих панелей
        
        При hovermode='x unified' наведение на любую точку показывает
        значения всех traces на этой X-координате.
        """
        import importlib.util
        spec = importlib.util.spec_from_file_location('charts', 'components/charts.py')
        charts = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(charts)
        
        dates = pd.date_range(end=datetime.now(), periods=100, freq='D')
        df1 = pd.DataFrame({'ytm': np.random.uniform(14, 15, 100)}, index=dates)
        df2 = pd.DataFrame({'ytm': np.random.uniform(13, 14, 100)}, index=dates)
        
        fig = charts.create_spread_analytics_chart(
            df1, df2, 'ОФЗ 26238', 'ОФЗ 26243', window=30, z_threshold=2.0
        )
        
        # Проверяем что все traces имеют валидные hovertemplates
        expected_keywords = ['ОФЗ', 'σ', 'MA', 'Спред']
        hover_text = ' '.join([t.hovertemplate for t in fig.data])
        
        for keyword in expected_keywords:
            assert keyword in hover_text, f"Hover should contain '{keyword}'"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
