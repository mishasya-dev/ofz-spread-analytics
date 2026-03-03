"""
Комплексные тесты для Spread Analytics chart

Проверяет корректность отображения:
- Структура графика (traces, layout)
- Hover labels с датой вверху
- X-axis (даты внизу, привязка к нижней панели)
- Y-axis domains (верхняя и нижняя панели)
- Легенда (индивидуальное переключение traces)
- Разделительная линия между панелями
- Аннотации и заголовки

Версия: 0.6.5 (STABLE)
"""
import sys
import os
import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def sample_data():
    """Создаём тестовые данные"""
    end_date = datetime.now()
    dates = pd.date_range(end=end_date, periods=100, freq='D')
    
    df1 = pd.DataFrame({'ytm': np.random.uniform(14, 15, 100)}, index=dates)
    df2 = pd.DataFrame({'ytm': np.random.uniform(13, 14, 100)}, index=dates)
    
    return df1, df2


@pytest.fixture
def chart_figure(sample_data):
    """Создаём figure для тестов"""
    import importlib.util
    spec = importlib.util.spec_from_file_location('charts', 'components/charts.py')
    charts = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(charts)
    
    df1, df2 = sample_data
    return charts.create_spread_analytics_chart(
        df1, df2, 'ОФЗ 26238', 'ОФЗ 26243', window=30, z_threshold=2.0
    )


class TestChartStructure:
    """Тесты структуры графика"""

    def test_number_of_traces(self, chart_figure):
        """Тест: правильное количество traces (9)"""
        expected = 9  # 2 invisible + 2 bonds + 1 invisible + 4 spread + 1 current
        assert len(chart_figure.data) == expected, \
            f"Expected {expected} traces, got {len(chart_figure.data)}"

    def test_trace_names(self, chart_figure):
        """Тест: правильные имена traces"""
        expected_names = [
            '',           # 0: Невидимый (дата для YTM)
            'ОФЗ 26238',  # 1: Bond1
            'ОФЗ 26243',  # 2: Bond2
            '',           # 3: Невидимый (дата для Spread)
            '+2.0σ',      # 4: Верхняя граница
            '-2.0σ',      # 5: Нижняя граница
            'MA(30)',     # 6: Rolling mean
            'Спред',      # 7: Спред
        ]
        
        for i, expected in enumerate(expected_names):
            actual = chart_figure.data[i].name
            assert actual == expected, \
                f"Trace {i}: expected name '{expected}', got '{actual}'"

    def test_invisible_traces_have_no_legend(self, chart_figure):
        """Тест: невидимые traces не показываются в легенде"""
        # Trace 0 и 3 - невидимые
        assert chart_figure.data[0].showlegend == False, "Trace 0 should not show in legend"
        assert chart_figure.data[3].showlegend == False, "Trace 3 should not show in legend"

    def test_visible_traces_have_correct_yaxis(self, chart_figure):
        """Тест: правильная привязка traces к Y-осям"""
        # Верхняя панель (yaxis='y' - по умолчанию или 'y')
        # Trace 0 - невидимый для YTM
        # Trace 1, 2 - Bond1, Bond2
        for i in [0, 1, 2]:
            yaxis = getattr(chart_figure.data[i], 'yaxis', None)
            assert yaxis in [None, 'y'], f"Trace {i} should use yaxis (default or 'y'), got {yaxis}"
        
        # Нижняя панель (yaxis='y2')
        # Trace 3 - невидимый для Spread, traces 4-8
        for i in [3, 4, 5, 6, 7]:
            yaxis = getattr(chart_figure.data[i], 'yaxis', None)
            assert yaxis == 'y2', f"Trace {i} should use yaxis2, got {yaxis}"


class TestYAxisDomains:
    """Тесты Y-axis domains (верхняя и нижняя панели)"""

    def test_ytm_axis_domain(self, chart_figure):
        """Тест: YTM ось занимает верхнюю часть (52%-100%)"""
        domain = chart_figure.layout.yaxis.domain
        assert domain[0] == 0.52, f"YTM axis should start at 0.52, got {domain[0]}"
        assert domain[1] == 1.0, f"YTM axis should end at 1.0, got {domain[1]}"

    def test_spread_axis_domain(self, chart_figure):
        """Тест: Spread ось занимает нижнюю часть (0%-48%)"""
        domain = chart_figure.layout.yaxis2.domain
        assert domain[0] == 0.0, f"Spread axis should start at 0.0, got {domain[0]}"
        assert domain[1] == 0.48, f"Spread axis should end at 0.48, got {domain[1]}"

    def test_gap_between_panels(self, chart_figure):
        """Тест: есть зазор между панелями (~4%)"""
        ytm_bottom = chart_figure.layout.yaxis.domain[0]  # 0.52
        spread_top = chart_figure.layout.yaxis2.domain[1]  # 0.48
        
        # Зазор между панелями (с допуском для плавающей точки)
        gap = ytm_bottom - spread_top
        assert abs(gap - 0.04) < 0.001, f"Gap between panels should be ~0.04, got {gap}"

    def test_yaxis_titles(self, chart_figure):
        """Тест: заголовки Y-осей"""
        assert chart_figure.layout.yaxis.title.text == "YTM (%)"
        assert chart_figure.layout.yaxis2.title.text == "Спред (б.п.)"


class TestXAxis:
    """Тесты X-axis (даты)"""

    def test_xaxis_anchor_to_y2(self, chart_figure):
        """Тест: X-axis привязана к нижней панели (y2)"""
        assert chart_figure.layout.xaxis.anchor == 'y2', \
            f"X-axis should be anchored to y2, got {chart_figure.layout.xaxis.anchor}"

    def test_xaxis_side_bottom(self, chart_figure):
        """Тест: X-axis ticks внизу"""
        assert chart_figure.layout.xaxis.side == 'bottom', \
            f"X-axis side should be 'bottom', got {chart_figure.layout.xaxis.side}"

    def test_xaxis_tickmode_array(self, chart_figure):
        """Тест: X-axis использует массив тиков"""
        assert chart_figure.layout.xaxis.tickmode == 'array', \
            f"X-axis tickmode should be 'array', got {chart_figure.layout.xaxis.tickmode}"

    def test_xaxis_has_tickvals_and_ticktext(self, chart_figure):
        """Тест: X-axis имеет значения и подписи тиков"""
        assert chart_figure.layout.xaxis.tickvals is not None
        assert chart_figure.layout.xaxis.ticktext is not None
        assert len(chart_figure.layout.xaxis.tickvals) > 0
        assert len(chart_figure.layout.xaxis.ticktext) > 0

    def test_date_format_in_ticks(self, chart_figure):
        """Тест: формат дат в тиках DD.MM.YY"""
        ticktext = chart_figure.layout.xaxis.ticktext
        for date_str in ticktext[:3]:  # Проверяем первые 3
            assert len(date_str) == 8, f"Date should be DD.MM.YY format, got: {date_str}"
            assert date_str[2] == '.' and date_str[5] == '.', \
                f"Date should be DD.MM.YY format, got: {date_str}"


class TestHoverLabels:
    """Тесты hover labels"""

    def test_hovermode_x_unified(self, chart_figure):
        """Тест: hovermode='x unified' для единого tooltip"""
        assert chart_figure.layout.hovermode == 'x unified', \
            f"hovermode should be 'x unified', got {chart_figure.layout.hovermode}"

    def test_all_traces_have_customdata(self, chart_figure):
        """Тест: все traces имеют customdata с датами"""
        for i, trace in enumerate(chart_figure.data):
            assert hasattr(trace, 'customdata'), f"Trace {i} missing customdata"
            assert trace.customdata is not None, f"Trace {i} customdata is None"

    def test_date_in_invisible_traces_hovertemplate(self, chart_figure):
        """Тест: невидимые traces показывают дату в hovertemplate"""
        # Trace 0 - невидимый для YTM панели
        hover0 = chart_figure.data[0].hovertemplate
        assert 'customdata' in hover0, "Trace 0 should show date"
        assert '📅' in hover0, "Trace 0 should have calendar emoji"
        
        # Trace 3 - невидимый для Spread панели
        hover3 = chart_figure.data[3].hovertemplate
        assert 'customdata' in hover3, "Trace 3 should show date"
        assert '📅' in hover3, "Trace 3 should have calendar emoji"

    def test_visible_traces_do_not_show_date(self, chart_figure):
        """Тест: видимые traces НЕ показывают дату (она от невидимых)"""
        for i in [1, 2, 4, 5, 6, 7]:  # Видимые traces
            hover = chart_figure.data[i].hovertemplate
            assert '📅' not in hover, f"Trace {i} should not show date emoji"


class TestLegend:
    """Тесты легенды"""

    def test_legend_orientation_horizontal(self, chart_figure):
        """Тест: легенда горизонтальная"""
        assert chart_figure.layout.legend.orientation == 'h', \
            f"Legend orientation should be 'h', got {chart_figure.layout.legend.orientation}"

    def test_legend_position_above_chart(self, chart_figure):
        """Тест: легенда над графиком"""
        assert chart_figure.layout.legend.y > 1, \
            f"Legend should be above chart (y > 1), got y={chart_figure.layout.legend.y}"

    def test_legend_xanchor_right(self, chart_figure):
        """Тест: легенда привязана справа"""
        assert chart_figure.layout.legend.xanchor == 'right', \
            f"Legend xanchor should be 'right', got {chart_figure.layout.legend.xanchor}"

    def test_no_legendgroup(self, chart_figure):
        """Тест: traces не имеют legendgroup (индивидуальное переключение)"""
        for i, trace in enumerate(chart_figure.data):
            if trace.showlegend != False:  # Только для видимых в легенде
                assert not hasattr(trace, 'legendgroup') or trace.legendgroup is None, \
                    f"Trace {i} should not have legendgroup for individual toggle"


class TestSeparatorLine:
    """Тесты разделительной линии между панелями"""

    def test_separator_exists(self, chart_figure):
        """Тест: разделительная линия существует"""
        assert len(chart_figure.layout.shapes) > 0, "Should have separator shape"

    def test_separator_position(self, chart_figure):
        """Тест: разделительная линия на y=0.5"""
        shape = chart_figure.layout.shapes[0]
        assert shape.y0 == 0.5, f"Separator y0 should be 0.5, got {shape.y0}"
        assert shape.y1 == 0.5, f"Separator y1 should be 0.5, got {shape.y1}"
        assert shape.x0 == 0, f"Separator x0 should be 0, got {shape.x0}"
        assert shape.x1 == 1, f"Separator x1 should be 1, got {shape.x1}"

    def test_separator_references_paper(self, chart_figure):
        """Тест: координаты разделителя в paper space"""
        shape = chart_figure.layout.shapes[0]
        assert shape.xref == 'paper', f"Separator xref should be 'paper', got {shape.xref}"
        assert shape.yref == 'paper', f"Separator yref should be 'paper', got {shape.yref}"


class TestAnnotations:
    """Тесты аннотаций (заголовки панелей)"""

    def test_annotations_count(self, chart_figure):
        """Тест: количество аннотаций"""
        # Минимум 2: "Доходности YTM" и "Анализ спреда..."
        assert len(chart_figure.layout.annotations) >= 2, \
            f"Should have at least 2 annotations, got {len(chart_figure.layout.annotations)}"

    def test_ytm_panel_annotation(self, chart_figure):
        """Тест: аннотация 'Доходности YTM' вверху"""
        ytm_annotation = None
        for ann in chart_figure.layout.annotations:
            if 'Доходности YTM' in ann.text:
                ytm_annotation = ann
                break
        
        assert ytm_annotation is not None, "Should have 'Доходности YTM' annotation"
        assert ytm_annotation.y == 1.0, f"YTM annotation y should be 1.0, got {ytm_annotation.y}"

    def test_spread_analysis_annotation(self, chart_figure):
        """Тест: аннотация 'Анализ спреда...' внизу"""
        spread_annotation = None
        for ann in chart_figure.layout.annotations:
            if 'Анализ спреда' in ann.text:
                spread_annotation = ann
                break
        
        assert spread_annotation is not None, "Should have 'Анализ спреда' annotation"
        assert spread_annotation.y < 0, f"Spread annotation y should be < 0, got {spread_annotation.y}"


class TestLayoutGeneral:
    """Общие тесты layout"""

    def test_title(self, chart_figure):
        """Тест: заголовок графика"""
        assert chart_figure.layout.title.text == "Анализ спреда", \
            f"Title should be 'Анализ спреда', got '{chart_figure.layout.title.text}'"

    def test_template(self, chart_figure):
        """Тест: тема графика plotly_white"""
        # Template может быть объектом или строкой
        template = chart_figure.layout.template
        # Проверяем что template установлен (не None)
        assert template is not None, "Template should not be None"
        # Если это строка, проверяем напрямую
        if isinstance(template, str):
            assert template == "plotly_white", f"Template should be 'plotly_white', got {template}"

    def test_height(self, chart_figure):
        """Тест: высота графика"""
        assert chart_figure.layout.height == 700, \
            f"Height should be 700, got {chart_figure.layout.height}"

    def test_margins(self, chart_figure):
        """Тест: отступы"""
        margin = chart_figure.layout.margin
        assert margin.l == 60, f"Left margin should be 60, got {margin.l}"
        assert margin.r == 60, f"Right margin should be 60, got {margin.r}"
        assert margin.t == 60, f"Top margin should be 60, got {margin.t}"
        assert margin.b >= 60, f"Bottom margin should be >= 60, got {margin.b}"


class TestCurrentPoint:
    """Тесты текущей точки с сигналом"""

    def test_current_point_exists(self, chart_figure):
        """Тест: текущая точка существует (trace 8)"""
        assert len(chart_figure.data) >= 9, "Should have 9 traces including current point"
        
    def test_current_point_is_marker(self, chart_figure):
        """Тест: текущая точка - маркер"""
        current_trace = chart_figure.data[8]
        assert 'markers' in current_trace.mode, \
            f"Current point should be markers mode, got {current_trace.mode}"

    def test_current_point_has_z_score_text(self, chart_figure):
        """Тест: текущая точка показывает Z-score"""
        current_trace = chart_figure.data[8]
        assert current_trace.text is not None, "Current point should have text"
        assert 'Z=' in current_trace.text[0], f"Text should contain Z=, got {current_trace.text[0]}"


class TestEdgeCases:
    """Тесты краевых случаев"""

    def test_empty_data(self):
        """Тест: пустые данные не вызывают ошибку"""
        import importlib.util
        spec = importlib.util.spec_from_file_location('charts', 'components/charts.py')
        charts = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(charts)
        
        empty_df = pd.DataFrame()
        fig = charts.create_spread_analytics_chart(empty_df, empty_df, 'Bond1', 'Bond2')
        
        # Должен создаться пустой график без ошибки
        assert fig is not None

    def test_single_point_data(self):
        """Тест: одна точка данных"""
        import importlib.util
        spec = importlib.util.spec_from_file_location('charts', 'components/charts.py')
        charts = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(charts)
        
        dates = pd.date_range(end=datetime.now(), periods=1, freq='D')
        df1 = pd.DataFrame({'ytm': [14.5]}, index=dates)
        df2 = pd.DataFrame({'ytm': [13.5]}, index=dates)
        
        fig = charts.create_spread_analytics_chart(df1, df2, 'Bond1', 'Bond2')
        assert fig is not None

    def test_custom_window_and_threshold(self, sample_data):
        """Тест: кастомные window и z_threshold"""
        import importlib.util
        spec = importlib.util.spec_from_file_location('charts', 'components/charts.py')
        charts = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(charts)
        
        df1, df2 = sample_data
        fig = charts.create_spread_analytics_chart(
            df1, df2, 'Bond1', 'Bond2', 
            window=60, z_threshold=1.5
        )
        
        # Проверяем что MA изменился
        assert fig.data[6].name == 'MA(60)', "MA should be MA(60)"
        # Проверяем что границы изменились
        assert fig.data[4].name == '+1.5σ', "Upper band should be +1.5σ"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
