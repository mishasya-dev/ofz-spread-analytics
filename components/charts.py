"""
Графики Plotly для визуализации данных
"""
import pandas as pd
import numpy as np
from datetime import datetime, date
from typing import Optional, Dict, List, Any, Tuple
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.express as px
import logging

logger = logging.getLogger(__name__)


# Цветовая палитра
COLORS = {
    "primary": "#1f77b4",
    "secondary": "#ff7f0e",
    "success": "#2ca02c",
    "danger": "#d62728",
    "warning": "#ffbb33",
    "info": "#17a2b8",
    "light": "#f8f9fa",
    "dark": "#343a40",
}

# Цвета для облигаций (история -> свечи)
BOND1_COLORS = {
    "history": "#1a5276",   # Тёмно-синий
    "intraday": "#3498DB",  # Ярко-синий
}
BOND2_COLORS = {
    "history": "#922B21",   # Тёмно-красный
    "intraday": "#E74C3C",  # Ярко-красный
}

# Цвета для спредов
SPREAD_COLOR = "#9B59B6"  # Фиолетовый

# Цвета для сигналов
SIGNAL_COLORS = {
    "STRONG_BUY": "#00ff00",
    "BUY": "#90EE90",
    "NEUTRAL": "#FFA500",
    "SELL": "#FF6B6B",
    "STRONG_SELL": "#FF0000",
    "NO_DATA": "#808080"
}


class ChartBuilder:
    """Построитель графиков"""
    
    def __init__(self, theme: str = "plotly_white"):
        """
        Инициализация
        
        Args:
            theme: Тема графиков
        """
        self.theme = theme
    
    def create_ytm_chart(
        self,
        ytm_data: pd.DataFrame,
        bonds_info: Optional[Dict[str, Any]] = None,
        title: str = "Доходность к погашению (YTM)"
    ) -> go.Figure:
        """
        Создать график YTM
        
        Args:
            ytm_data: DataFrame с YTM (columns = bond names)
            bonds_info: Информация по облигациям
            title: Заголовок
            
        Returns:
            Plotly Figure
        """
        fig = go.Figure()
        
        for i, col in enumerate(ytm_data.columns):
            color = BOND_COLORS[i % len(BOND_COLORS)]
            
            # Формируем имя для легенды
            name = col
            if bonds_info and col in bonds_info:
                info = bonds_info[col]
                # Формат: "ОФЗ 26238 (15.2г., YTM: 7.5%, D: 12.3)"
                parts = [col]
                if info.get("years_to_maturity"):
                    parts.append(f"{info['years_to_maturity']:.1f}г.")
                if info.get("current_ytm"):
                    parts.append(f"YTM: {info['current_ytm']:.2f}%")
                if info.get("duration_years"):
                    parts.append(f"D: {info['duration_years']:.1f}")
                name = " | ".join(parts)
            
            fig.add_trace(go.Scatter(
                x=ytm_data.index,
                y=ytm_data[col],
                mode='lines',
                name=name,
                line=dict(color=color, width=1.5),
                hovertemplate=f'%{{y:.2f}}%<extra></extra>'
            ))
        
        fig.update_layout(
            title=title,
            xaxis_title="Дата",
            yaxis_title="YTM (%)",
            hovermode='x unified',
            template=self.theme,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1,
                font=dict(size=10)
            ),
            height=500,
            margin=dict(l=60, r=30, t=80, b=60)
        )
        
        # Добавляем диапазон Y
        ytm_values = ytm_data.values.flatten()
        ytm_values = ytm_values[~np.isnan(ytm_values)]
        if len(ytm_values) > 0:
            y_min, y_max = ytm_values.min(), ytm_values.max()
            padding = (y_max - y_min) * 0.1
            fig.update_yaxes(range=[y_min - padding, y_max + padding])
        
        return fig
    
    def create_spread_chart(
        self,
        spread_data: pd.DataFrame,
        spread_stats: Optional[Dict[str, Any]] = None,
        show_percentiles: bool = True,
        title: str = "Спреды доходности"
    ) -> go.Figure:
        """
        Создать график спредов
        
        Args:
            spread_data: DataFrame со спредами (columns = pair names)
            spread_stats: Статистика спредов
            show_percentiles: Показывать перцентили
            title: Заголовок
            
        Returns:
            Plotly Figure
        """
        fig = go.Figure()
        
        # Цвета для разных пар
        colors = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728"]
        
        for i, col in enumerate(spread_data.columns):
            color = colors[i % len(colors)]
            
            fig.add_trace(go.Scatter(
                x=spread_data.index,
                y=spread_data[col],
                mode='lines',
                name=col,
                line=dict(color=color, width=1.5),
                hovertemplate=f'{col}: %{{y:.1f}} б.п.<extra></extra>'
            ))
        
        # Добавляем перцентили для первой пары если есть
        if show_percentiles and spread_stats:
            first_pair = list(spread_stats.keys())[0]
            stats = spread_stats[first_pair]
            
            # P10 (нижняя граница)
            fig.add_hline(
                y=stats.percentile_10,
                line_dash="dash",
                line_color="green",
                annotation_text=f"P10 ({stats.percentile_10:.0f})",
                annotation_position="right"
            )
            
            # P90 (верхняя граница)
            fig.add_hline(
                y=stats.percentile_90,
                line_dash="dash",
                line_color="red",
                annotation_text=f"P90 ({stats.percentile_90:.0f})",
                annotation_position="right"
            )
            
            # Среднее
            fig.add_hline(
                y=stats.mean,
                line_dash="dot",
                line_color="gray",
                annotation_text=f"Mean ({stats.mean:.0f})",
                annotation_position="left"
            )
        
        fig.update_layout(
            title=title,
            xaxis_title="Дата",
            yaxis_title="Спред (б.п.)",
            hovermode='x unified',
            template=self.theme,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            ),
            height=500,
            margin=dict(l=60, r=30, t=80, b=60)
        )
        
        return fig
    
    def create_signal_chart(
        self,
        spread_series: pd.Series,
        signals: List[Any],
        title: str = "Сигналы на спреде"
    ) -> go.Figure:
        """
        Создать график сигналов
        
        Args:
            spread_series: Series со спредом
            signals: Список сигналов
            title: Заголовок
            
        Returns:
            Plotly Figure
        """
        fig = go.Figure()
        
        # График спреда
        fig.add_trace(go.Scatter(
            x=spread_series.index,
            y=spread_series,
            mode='lines',
            name='Спред',
            line=dict(color="#1f77b4", width=1.5),
            hovertemplate='Спред: %{y:.1f} б.п.<extra></extra>'
        ))
        
        # Перцентили
        lookback = min(252, len(spread_series))
        spread_window = spread_series.tail(lookback)
        
        p10 = spread_window.quantile(0.1)
        p25 = spread_window.quantile(0.25)
        p75 = spread_window.quantile(0.75)
        p90 = spread_window.quantile(0.9)
        
        # Зоны
        # Зона покупки (ниже P25)
        fig.add_hrect(
            y0=spread_window.min() - 5,
            y1=p25,
            fillcolor="green",
            opacity=0.1,
            line_width=0,
            annotation_text="Покупка",
            annotation_position="inside left"
        )
        
        # Зона продажи (выше P75)
        fig.add_hrect(
            y0=p75,
            y1=spread_window.max() + 5,
            fillcolor="red",
            opacity=0.1,
            line_width=0,
            annotation_text="Продажа",
            annotation_position="inside left"
        )
        
        # Линии перцентилей
        for pct, val, color in [(p10, "P10", "darkgreen"), (p90, "P90", "darkred")]:
            fig.add_hline(
                y=val,
                line_dash="dash",
                line_color=color,
                opacity=0.7,
                annotation_text=f"{pct}={val:.0f}",
                annotation_position="right"
            )
        
        # Текущее значение
        current = spread_series.iloc[-1]
        fig.add_trace(go.Scatter(
            x=[spread_series.index[-1]],
            y=[current],
            mode='markers',
            marker=dict(size=12, color='red', symbol='diamond'),
            name=f'Текущий: {current:.1f}',
            showlegend=True
        ))
        
        fig.update_layout(
            title=title,
            xaxis_title="Дата",
            yaxis_title="Спред (б.п.)",
            hovermode='x unified',
            template=self.theme,
            height=500,
            margin=dict(l=60, r=30, t=60, b=60)
        )
        
        return fig
    
    def create_backtest_chart(
        self,
        backtest_result: Any,
        title: str = "Результаты бэктеста"
    ) -> go.Figure:
        """
        Создать график бэктеста
        
        Args:
            backtest_result: BacktestResult
            title: Заголовок
            
        Returns:
            Plotly Figure
        """
        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=(
                "Кривая капитала",
                "Распределение P&L",
                "P&L по сделкам",
                "Метрики"
            ),
            specs=[
                [{"type": "scatter"}, {"type": "histogram"}],
                [{"type": "bar"}, {"type": "table"}]
            ],
            vertical_spacing=0.15,
            horizontal_spacing=0.1
        )
        
        # 1. Кривая капитала
        if backtest_result.equity_curve:
            fig.add_trace(
                go.Scatter(
                    y=backtest_result.equity_curve,
                    mode='lines',
                    name='Капитал',
                    line=dict(color='#1f77b4', width=2)
                ),
                row=1, col=1
            )
        
        # 2. Распределение P&L
        pnl_values = [p.pnl_bp for p in backtest_result.positions]
        if pnl_values:
            colors = ['green' if x > 0 else 'red' for x in pnl_values]
            fig.add_trace(
                go.Histogram(
                    x=pnl_values,
                    nbinsx=20,
                    name='P&L',
                    marker_color='#1f77b4',
                    opacity=0.7
                ),
                row=1, col=2
            )
        
        # 3. P&L по сделкам
        if backtest_result.positions:
            trade_numbers = list(range(1, len(backtest_result.positions) + 1))
            pnl_by_trade = [p.pnl_bp for p in backtest_result.positions]
            colors = ['green' if x > 0 else 'red' for x in pnl_by_trade]
            
            fig.add_trace(
                go.Bar(
                    x=trade_numbers,
                    y=pnl_by_trade,
                    marker_color=colors,
                    name='P&L'
                ),
                row=2, col=1
            )
        
        # 4. Метрики
        metrics = [
            ["Метрика", "Значение"],
            ["Всего сделок", str(backtest_result.total_trades)],
            ["Win Rate", f"{backtest_result.win_rate:.1f}%"],
            ["P&L (б.п.)", f"{backtest_result.total_pnl_bp:.1f}"],
            ["P&L (%)", f"{backtest_result.total_pnl_percent:.2f}%"],
            ["Profit Factor", f"{backtest_result.profit_factor:.2f}"],
            ["Max DD (б.п.)", f"{backtest_result.max_drawdown_bp:.1f}"],
            ["Avg Hold (дней)", f"{backtest_result.avg_holding_days:.1f}"]
        ]
        
        fig.add_trace(
            go.Table(
                header=dict(
                    values=metrics[0],
                    fill_color='#f8f9fa',
                    align='left',
                    font=dict(size=12, weight='bold')
                ),
                cells=dict(
                    values=list(zip(*metrics[1:])),
                    fill_color='white',
                    align='left',
                    font=dict(size=11)
                )
            ),
            row=2, col=2
        )
        
        fig.update_layout(
            title=title,
            template=self.theme,
            height=700,
            showlegend=False
        )
        
        fig.update_xaxes(title_text="Номер сделки", row=2, col=1)
        fig.update_yaxes(title_text="P&L (б.п.)", row=2, col=1)
        fig.update_yaxes(title_text="Капитал", row=1, col=1)
        fig.update_xaxes(title_text="P&L (б.п.)", row=1, col=2)
        fig.update_yaxes(title_text="Частота", row=1, col=2)
        
        return fig
    
    def create_intraday_chart(
        self,
        intraday_data: List[Any],
        pair_name: str,
        title: Optional[str] = None
    ) -> go.Figure:
        """
        Создать внутридневной график
        
        Args:
            intraday_data: Список IntradayPoint
            pair_name: Название пары
            title: Заголовок
            
        Returns:
            Plotly Figure
        """
        if title is None:
            title = f"Внутридневной спред: {pair_name}"
        
        times = [p.time for p in intraday_data]
        spreads = [p.spread_bp for p in intraday_data]
        ytm_long = [p.ytm_long for p in intraday_data]
        ytm_short = [p.ytm_short for p in intraday_data]
        
        fig = make_subplots(
            rows=2, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.1,
            subplot_titles=("Спред", "YTM"),
            row_heights=[0.6, 0.4]
        )
        
        # Спред
        fig.add_trace(
            go.Scatter(
                x=times,
                y=spreads,
                mode='lines+markers',
                name='Спред',
                line=dict(color='#1f77b4', width=2),
                marker=dict(size=6)
            ),
            row=1, col=1
        )
        
        # YTM
        fig.add_trace(
            go.Scatter(
                x=times,
                y=ytm_long,
                mode='lines',
                name='YTM Long',
                line=dict(color='#2ca02c', width=1.5)
            ),
            row=2, col=1
        )
        
        fig.add_trace(
            go.Scatter(
                x=times,
                y=ytm_short,
                mode='lines',
                name='YTM Short',
                line=dict(color='#d62728', width=1.5)
            ),
            row=2, col=1
        )
        
        fig.update_layout(
            title=title,
            template=self.theme,
            height=600,
            hovermode='x unified',
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            )
        )
        
        fig.update_yaxes(title_text="Спред (б.п.)", row=1, col=1)
        fig.update_yaxes(title_text="YTM (%)", row=2, col=1)
        fig.update_xaxes(title_text="Время", row=2, col=1)
        
        return fig
    
    def create_exchange_status_card(
        self,
        status: str,
        is_trading: bool,
        message: str,
        last_update: datetime
    ) -> str:
        """
        Создать HTML-карточку статуса биржи
        
        Args:
            status: Статус
            is_trading: Открыта ли биржа
            message: Сообщение
            last_update: Время обновления
            
        Returns:
            HTML строка
        """
        color = "#28a745" if is_trading else "#dc3545"
        icon = "🟢" if is_trading else "🔴"
        
        return f"""
        <div style="
            background: linear-gradient(135deg, {color}20, {color}10);
            border-left: 4px solid {color};
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 20px;
        ">
            <div style="display: flex; align-items: center; gap: 10px;">
                <span style="font-size: 24px;">{icon}</span>
                <div>
                    <div style="font-weight: bold; font-size: 18px;">{message}</div>
                    <div style="color: #666; font-size: 14px;">
                        Статус: {status} | Обновлено: {last_update.strftime('%H:%M:%S')}
                    </div>
                </div>
            </div>
        </div>
        """


# Удобные функции
def create_ytm_chart(ytm_data: pd.DataFrame, **kwargs) -> go.Figure:
    """Создать график YTM"""
    builder = ChartBuilder()
    return builder.create_ytm_chart(ytm_data, **kwargs)


def create_spread_chart(spread_data: pd.DataFrame, **kwargs) -> go.Figure:
    """Создать график спредов"""
    builder = ChartBuilder()
    return builder.create_spread_chart(spread_data, **kwargs)


def create_signal_chart(spread_series: pd.Series, signals: List, **kwargs) -> go.Figure:
    """Создать график сигналов"""
    builder = ChartBuilder()
    return builder.create_signal_chart(spread_series, signals, **kwargs)


def create_backtest_chart(backtest_result: Any, **kwargs) -> go.Figure:
    """Создать график бэктеста"""
    builder = ChartBuilder()
    return builder.create_backtest_chart(backtest_result, **kwargs)


# ============================================
# НОВЫЕ ФУНКЦИИ ДЛЯ СВЯЗАННЫХ ГРАФИКОВ v0.3.0
# ============================================

def calculate_future_range(df_index, future_percent: float = 0.15):
    """
    Рассчитать диапазон оси X с запасом для "будущего"
    
    Args:
        df_index: Индекс DataFrame (datetime)
        future_percent: Процент от длины для будущего
        
    Returns:
        (x_min, x_max) tuple
    """
    if len(df_index) == 0:
        return None, None
    
    start = df_index[0]
    end = df_index[-1]
    
    # Добавляем future_percent от длины периода
    period_length = (end - start).total_seconds() if hasattr(end, 'total_seconds') else (end - start).days
    future_length = period_length * future_percent
    
    if hasattr(end, 'total_seconds'):
        future_end = end + pd.Timedelta(seconds=future_length)
    else:
        future_end = end + pd.Timedelta(days=future_length)
    
    return start, future_end


def create_daily_ytm_chart(
    df1: pd.DataFrame,
    df2: pd.DataFrame,
    bond1_name: str,
    bond2_name: str,
    x_range: Optional[Tuple] = None,
    future_percent: float = 0.15
) -> go.Figure:
    """
    Создать график YTM по дневным данным (YIELDCLOSE)
    
    Args:
        df1: DataFrame с YTM облигации 1
        df2: DataFrame с YTM облигации 2
        bond1_name: Название облигации 1
        bond2_name: Название облигации 2
        x_range: Диапазон оси X (для синхронизации)
        future_percent: Процент места для будущего
        
    Returns:
        Plotly Figure
    """
    fig = go.Figure()
    
    ytm_col = 'ytm'  # Дневные данные
    
    # Облигация 1 - тёмно-синий
    if not df1.empty and ytm_col in df1.columns:
        fig.add_trace(go.Scatter(
            x=df1.index,
            y=df1[ytm_col],
            name=bond1_name,
            line=dict(color=BOND1_COLORS["history"], width=2),
            hovertemplate=f'{bond1_name}: %{{y:.2f}}%<extra></extra>'
        ))
    
    # Облигация 2 - тёмно-красный
    if not df2.empty and ytm_col in df2.columns:
        fig.add_trace(go.Scatter(
            x=df2.index,
            y=df2[ytm_col],
            name=bond2_name,
            line=dict(color=BOND2_COLORS["history"], width=2),
            hovertemplate=f'{bond2_name}: %{{y:.2f}}%<extra></extra>'
        ))
    
    # Рассчитать диапазон с будущим
    all_index = list(df1.index) + list(df2.index)
    if all_index:
        x_min, x_max = calculate_future_range(pd.DatetimeIndex(all_index), future_percent)
    else:
        x_min, x_max = None, None
    
    fig.update_layout(
        title="📈 YTM по закрытию дня (история)",
        xaxis_title="Дата",
        yaxis_title="YTM (%)",
        hovermode='x unified',
        template="plotly_white",
        height=350,
        margin=dict(l=60, r=30, t=50, b=40),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        )
    )
    
    if x_min and x_max:
        fig.update_xaxes(range=[x_min, x_max])
    
    # Добавляем сетку
    fig.update_xaxes(
        showgrid=True,
        gridwidth=1,
        gridcolor='rgba(200, 200, 200, 0.3)',
        griddash='dot'
    )
    fig.update_yaxes(
        showgrid=True,
        gridwidth=1,
        gridcolor='rgba(200, 200, 200, 0.3)',
        griddash='dot'
    )
    
    return fig


def create_daily_spread_chart(
    spread_df: pd.DataFrame,
    stats: Optional[Dict] = None,
    x_range: Optional[Tuple] = None,
    future_percent: float = 0.15
) -> go.Figure:
    """
    Создать график спреда по дневным данным
    
    Args:
        spread_df: DataFrame со спредом
        stats: Статистика спреда (mean, p10, p25, p75, p90)
        x_range: Диапазон оси X (для синхронизации)
        future_percent: Процент места для будущего
        
    Returns:
        Plotly Figure
    """
    fig = go.Figure()
    
    if not spread_df.empty and 'spread' in spread_df.columns:
        # Линия спреда
        fig.add_trace(go.Scatter(
            x=spread_df['date'] if 'date' in spread_df.columns else spread_df.index,
            y=spread_df['spread'],
            name='Спред',
            line=dict(color=SPREAD_COLOR, width=2),
            fill='tozeroy',
            fillcolor='rgba(155, 89, 182, 0.1)',
            hovertemplate='Спред: %{y:.1f} б.п.<extra></extra>'
        ))
    
    # Перцентили
    if stats:
        # Среднее
        if 'mean' in stats:
            fig.add_hline(
                y=stats['mean'],
                line_dash='dot',
                line_color='gray',
                annotation_text=f"Среднее: {stats['mean']:.1f}",
                annotation_position="left"
            )
        
        # P25
        if 'p25' in stats:
            fig.add_hline(
                y=stats['p25'],
                line_dash='dash',
                line_color='green',
                annotation_text=f"P25: {stats['p25']:.1f}",
                annotation_position="left"
            )
        
        # P75
        if 'p75' in stats:
            fig.add_hline(
                y=stats['p75'],
                line_dash='dash',
                line_color='red',
                annotation_text=f"P75: {stats['p75']:.1f}",
                annotation_position="left"
            )
    
    # Диапазон с будущим
    if spread_df is not None and len(spread_df) > 0:
        x_vals = spread_df['date'] if 'date' in spread_df.columns else spread_df.index
        x_min, x_max = calculate_future_range(pd.DatetimeIndex(x_vals), future_percent)
        if x_min and x_max:
            fig.update_xaxes(range=[x_min, x_max])
    
    fig.update_layout(
        title="📉 Спред доходности (дневные данные)",
        xaxis_title="Дата",
        yaxis_title="Спред (б.п.)",
        hovermode='x unified',
        template="plotly_white",
        height=300,
        margin=dict(l=60, r=30, t=50, b=40)
    )
    
    # Добавляем сетку
    fig.update_xaxes(
        showgrid=True,
        gridwidth=1,
        gridcolor='rgba(200, 200, 200, 0.3)',
        griddash='dot'
    )
    fig.update_yaxes(
        showgrid=True,
        gridwidth=1,
        gridcolor='rgba(200, 200, 200, 0.3)',
        griddash='dot'
    )
    
    return fig


def create_combined_ytm_chart(
    daily_df1: pd.DataFrame,
    daily_df2: pd.DataFrame,
    intraday_df1: pd.DataFrame,
    intraday_df2: pd.DataFrame,
    bond1_name: str,
    bond2_name: str,
    candle_days: int = 30,
    x_range: Optional[Tuple] = None,
    future_percent: float = 0.15
) -> go.Figure:
    """
    Создать склеенный график YTM (история + свечи)
    
    Использует категориальную ось X (без неторговых дней).
    
    Логика склейки:
    - Граница = сегодня - candle_days
    - До границы: дневные YTM (YIELDCLOSE)
    - После границы: свечи YTM
    
    Args:
        daily_df1: DataFrame с дневными YTM облигации 1
        daily_df2: DataFrame с дневными YTM облигации 2
        intraday_df1: DataFrame с intraday YTM облигации 1
        intraday_df2: DataFrame с intraday YTM облигации 2
        bond1_name: Название облигации 1
        bond2_name: Название облигации 2
        candle_days: Период свечей в днях (определяет границу склейки)
        x_range: Диапазон оси X (для синхронизации) - игнорируется для категориальной оси
        future_percent: Процент места для будущего - не используется
        
    Returns:
        Plotly Figure
    """
    from datetime import datetime, timedelta
    
    fig = go.Figure()
    
    ytm_col = 'ytm'
    ytm_intraday_col = 'ytm_close'
    
    # Рассчитываем границу склейки
    today = datetime.now().date()
    boundary_date = today - timedelta(days=candle_days)
    boundary_dt = pd.Timestamp(boundary_date)
    
    # === КАТЕГОРИАЛЬНАЯ ОСЬ ===
    # Собираем все точки в один список
    all_points = []  # [(idx, date_label, ytm1, ytm2, is_intraday), ...]
    
    # История (дневные) - до границы
    if not daily_df1.empty and ytm_col in daily_df1.columns:
        daily_before_boundary = daily_df1[daily_df1.index < boundary_dt]
        for i, (idx, row) in enumerate(daily_before_boundary.iterrows()):
            ytm2_val = None
            if not daily_df2.empty and ytm_col in daily_df2.columns:
                daily2_before = daily_df2[daily_df2.index < boundary_dt]
                if idx in daily2_before.index:
                    ytm2_val = daily2_before.loc[idx, ytm_col]
            
            date_label = idx.strftime('%d.%m.%y') if hasattr(idx, 'strftime') else str(idx)[:10]
            all_points.append({
                'idx': len(all_points),
                'date': idx,
                'label': date_label,
                'ytm1': row[ytm_col],
                'ytm2': ytm2_val,
                'is_intraday': False
            })
    
    # Intraday (свечи) - все данные
    if not intraday_df1.empty and ytm_intraday_col in intraday_df1.columns:
        for idx, row in intraday_df1.iterrows():
            ytm2_val = None
            value2_val = None
            if not intraday_df2.empty and ytm_intraday_col in intraday_df2.columns:
                if idx in intraday_df2.index:
                    ytm2_val = intraday_df2.loc[idx, ytm_intraday_col]
                    value2_val = intraday_df2.loc[idx, 'value'] if 'value' in intraday_df2.columns else None
            
            # Для intraday показываем дату и время
            if hasattr(idx, 'strftime'):
                date_label = idx.strftime('%d.%m %H:%M')
            else:
                date_label = str(idx)[:16]
            
            # Объём торгов в рублях (value) для обеих облигаций
            value1_val = row.get('value') if 'value' in row else None
            
            all_points.append({
                'idx': len(all_points),
                'date': idx,
                'label': date_label,
                'ytm1': row[ytm_intraday_col],
                'ytm2': ytm2_val,
                'value1': value1_val,
                'value2': value2_val,
                'is_intraday': True
            })
    
    if not all_points:
        return fig
    
    # Разделяем на историю и intraday для разных стилей линий
    history_points = [p for p in all_points if not p['is_intraday']]
    intraday_points = [p for p in all_points if p['is_intraday']]
    
    x_indices = [p['idx'] for p in all_points]
    date_labels = [p['label'] for p in all_points]
    
    # Тики оси X
    n_points = len(all_points)
    tick_step = max(1, n_points // 12)
    tickvals = x_indices[::tick_step]
    ticktext = [date_labels[i] for i in tickvals]
    
    # Облигация 1 - история (пунктир) - первый trace, добавляем дату внизу
    if history_points:
        fig.add_trace(go.Scatter(
            x=[p['idx'] for p in history_points],
            y=[p['ytm1'] for p in history_points],
            name=f"{bond1_name} (дневн.)",
            line=dict(color=BOND1_COLORS["history"], width=1, dash='dash'),
            customdata=[p['label'] for p in history_points],
            hovertemplate=f'{bond1_name} (дневн.): %{{y:.2f}}%<br><br>📅 %{{customdata}}<extra></extra>'
        ))
    
    # Облигация 1 - intraday (сплошная) - без даты
    if intraday_points:
        fig.add_trace(go.Scatter(
            x=[p['idx'] for p in intraday_points],
            y=[p['ytm1'] for p in intraday_points],
            name=f"{bond1_name} (свечи)",
            line=dict(color=BOND1_COLORS["intraday"], width=1),
            hovertemplate=f'{bond1_name} (свечи): %{{y:.2f}}%<extra></extra>'
        ))
    
    # Облигация 2 - история (пунктир) - без даты
    if history_points:
        ytm2_history = [p['ytm2'] for p in history_points]
        if any(v is not None for v in ytm2_history):
            fig.add_trace(go.Scatter(
                x=[p['idx'] for p in history_points],
                y=ytm2_history,
                name=f"{bond2_name} (дневн.)",
                line=dict(color=BOND2_COLORS["history"], width=1, dash='dash'),
                hovertemplate=f'{bond2_name} (дневн.): %{{y:.2f}}%<extra></extra>'
            ))
    
    # Облигация 2 - intraday (сплошная) - без даты
    if intraday_points:
        ytm2_intraday = [p['ytm2'] for p in intraday_points]
        if any(v is not None for v in ytm2_intraday):
            fig.add_trace(go.Scatter(
                x=[p['idx'] for p in intraday_points],
                y=ytm2_intraday,
                name=f"{bond2_name} (свечи)",
                line=dict(color=BOND2_COLORS["intraday"], width=1),
                hovertemplate=f'{bond2_name} (свечи): %{{y:.2f}}%<extra></extra>'
            ))
    
    # Объём торгов в рублях (value) - два набора столбиков
    # Светло-голубой для облигации 1, светло-розовый для облигации 2
    
    def format_value(val):
        """Форматирование объёма в млн/тыс. руб."""
        if val is None:
            return ''
        if val >= 1_000_000:
            return f'{val/1_000_000:.1f} млн ₽'
        elif val >= 1_000:
            return f'{val/1_000:.0f} тыс. ₽'
        else:
            return f'{val:.0f} ₽'
    
    # Объём облигации 1 (светло-голубой)
    value1_points = [p for p in intraday_points if p.get('value1') is not None and p.get('value1') > 0]
    if value1_points:
        fig.add_trace(go.Bar(
            x=[p['idx'] for p in value1_points],
            y=[p['value1'] for p in value1_points],
            name=f'{bond1_name} объём',
            marker_color='rgba(52, 152, 219, 0.3)',
            marker_line_width=0,  # Убираем белый абрис
            yaxis='y2',
            hovertemplate='Объём: %{y:,.0f} ₽<extra></extra>'
        ))
    
    # Объём облигации 2 (светло-розовый)
    value2_points = [p for p in intraday_points if p.get('value2') is not None and p.get('value2') > 0]
    if value2_points:
        fig.add_trace(go.Bar(
            x=[p['idx'] for p in value2_points],
            y=[p['value2'] for p in value2_points],
            name=f'{bond2_name} объём',
            marker_color='rgba(231, 76, 60, 0.3)',
            marker_line_width=0,  # Убираем белый абрис
            yaxis='y2',
            hovertemplate='Объём: %{y:,.0f} ₽<extra></extra>'
        ))
    
    # Подпись о границе склейки
    boundary_str = boundary_date.strftime('%Y-%m-%d')
    
    # Проверяем, есть ли данные об объёме
    has_value1 = any(p.get('value1') is not None and p.get('value1') > 0 for p in intraday_points)
    has_value2 = any(p.get('value2') is not None and p.get('value2') > 0 for p in intraday_points)
    has_value = has_value1 or has_value2
    
    fig.update_layout(
        title=f"📈 YTM (история + свечи, граница: {boundary_str})",
        xaxis_title="Дата/Время",
        yaxis_title="YTM (%)",
        hovermode='x unified',
        template="plotly_white",
        height=350,
        margin=dict(l=60, r=60 if has_value else 30, t=50, b=40),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
        # Вторая ось Y для объёма (если есть данные)
        yaxis2=dict(
            title="Объём (₽)",
            overlaying="y",
            side="right",
            showgrid=False,
            visible=has_value
        ) if has_value else {}
    )
    
    # Категориальная ось X
    fig.update_xaxes(
        showgrid=True,
        gridwidth=1,
        gridcolor='rgba(200, 200, 200, 0.3)',
        griddash='dot',
        tickmode='array',
        tickvals=tickvals,
        ticktext=ticktext
    )
    fig.update_yaxes(
        showgrid=True,
        gridwidth=1,
        gridcolor='rgba(200, 200, 200, 0.3)',
        griddash='dot'
    )
    
    return fig


def create_intraday_spread_chart(
    spread_df: pd.DataFrame,
    daily_stats: Optional[Dict] = None,
    x_range: Optional[Tuple] = None,
    future_percent: float = 0.15
) -> go.Figure:
    """
    Создать график intraday спреда с перцентилями от дневных данных
    
    Использует категориальную ось X (без неторговых дней).
    
    Args:
        spread_df: DataFrame со спредом
        daily_stats: Статистика от ДНЕВНЫХ данных (mean, p10, p25, p75, p90)
        x_range: Диапазон оси X - игнорируется для категориальной оси
        future_percent: Процент места для будущего - не используется
        
    Returns:
        Plotly Figure
    """
    fig = go.Figure()
    
    # === КАТЕГОРИАЛЬНАЯ ОСЬ ===
    if not spread_df.empty and 'spread' in spread_df.columns:
        n_points = len(spread_df)
        x_indices = list(range(n_points))
        
        # Подписи оси X
        x_vals = spread_df['datetime'] if 'datetime' in spread_df.columns else spread_df.index
        date_labels = [d.strftime('%d.%m %H:%M') if hasattr(d, 'strftime') else str(d)[:16] for d in x_vals]
        
        # Тики
        tick_step = max(1, n_points // 12)
        tickvals = x_indices[::tick_step]
        ticktext = [date_labels[i] for i in tickvals]
        
        # Спред - единственный trace, добавляем дату внизу
        fig.add_trace(go.Scatter(
            x=x_indices,
            y=spread_df['spread'],
            name='Спред',
            line=dict(color=SPREAD_COLOR, width=2),
            customdata=date_labels,
            hovertemplate=f'Спред: %{{y:.1f}} б.п.<br><br>📅 %{{customdata}}<extra></extra>'
        ))
    else:
        tickvals = []
        ticktext = []
    
    # Перцентили от ДНЕВНЫХ данных (референс)
    if daily_stats:
        # P10
        if 'p10' in daily_stats:
            fig.add_hline(
                y=daily_stats['p10'],
                line_dash='dash',
                line_color='darkgreen',
                annotation_text=f"P10: {daily_stats['p10']:.1f}",
                annotation_position="left"
            )
        
        # P25
        if 'p25' in daily_stats:
            fig.add_hline(
                y=daily_stats['p25'],
                line_dash='dot',
                line_color='green',
                annotation_text=f"P25: {daily_stats['p25']:.1f}",
                annotation_position="left"
            )
        
        # Среднее
        if 'mean' in daily_stats:
            fig.add_hline(
                y=daily_stats['mean'],
                line_dash='dot',
                line_color='gray',
                annotation_text=f"Среднее: {daily_stats['mean']:.1f}",
                annotation_position="left"
            )
        
        # P75
        if 'p75' in daily_stats:
            fig.add_hline(
                y=daily_stats['p75'],
                line_dash='dot',
                line_color='red',
                annotation_text=f"P75: {daily_stats['p75']:.1f}",
                annotation_position="left"
            )
        
        # P90
        if 'p90' in daily_stats:
            fig.add_hline(
                y=daily_stats['p90'],
                line_dash='dash',
                line_color='darkred',
                annotation_text=f"P90: {daily_stats['p90']:.1f}",
                annotation_position="left"
            )
    
    fig.update_layout(
        title="📉 Спред (intraday) + перцентили от дневных данных",
        xaxis_title="Время",
        yaxis_title="Спред (б.п.)",
        hovermode='x unified',
        template="plotly_white",
        height=300,
        margin=dict(l=60, r=30, t=50, b=40)
    )
    
    # Категориальная ось X
    fig.update_xaxes(
        showgrid=True,
        gridwidth=1,
        gridcolor='rgba(200, 200, 200, 0.3)',
        griddash='dot',
        tickmode='array',
        tickvals=tickvals if tickvals else [],
        ticktext=ticktext if ticktext else []
    )
    fig.update_yaxes(
        showgrid=True,
        gridwidth=1,
        gridcolor='rgba(200, 200, 200, 0.3)',
        griddash='dot'
    )
    
    return fig


# ============================================
# ПРОФЕССИОНАЛЬНЫЙ АНАЛИЗ СПРЕДА (Z-Score)
# ============================================

def create_spread_analytics_chart(
    df1: pd.DataFrame,
    df2: pd.DataFrame,
    bond1_name: str,
    bond2_name: str,
    window: int = 30,
    z_threshold: float = 2.0
) -> go.Figure:
    """
    Создать профессиональную панель анализа спреда с Z-Score.
    
    Две панели:
    1. Доходности YTM обеих облигаций
    2. Спред + Rolling Mean + ±Z Sigma границы
    
    Использует категориальную ось X (без неторговых дней).
    
    Args:
        df1: DataFrame с YTM облигации 1 (длинная)
        df2: DataFrame с YTM облигации 2 (короткая)
        bond1_name: Название облигации 1
        bond2_name: Название облигации 2
        window: Окно для rolling расчётов (дней)
        z_threshold: Порог Z-Score для границ (обычно 2.0)
        
    Returns:
        Plotly Figure с двумя панелями
    """
    
    # Создаём subplot с двумя панелями
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.08,
        row_heights=[0.5, 0.5],
        subplot_titles=(
            "Доходности YTM",
            f"Анализ спреда (Rolling {window} дн., Z-Score ±{z_threshold})"
        )
    )
    
    ytm_col = 'ytm'

    # --- Подготовка данных ---
    if not df1.empty and ytm_col in df1.columns and not df2.empty and ytm_col in df2.columns:
        # Удаляем дубликаты в индексах перед объединением
        df1_clean = df1[~df1.index.duplicated(keep='last')][[ytm_col]].copy()
        df2_clean = df2[~df2.index.duplicated(keep='last')][[ytm_col]].copy()

        # Объединяем по индексу с помощью join
        combined = df1_clean.join(df2_clean, lsuffix='_long', rsuffix='_short', how='inner')
        combined.columns = ['ytm_long', 'ytm_short']
        combined = combined.dropna()
        
        if len(combined) > 0:
            # Расчёт спреда
            combined['spread'] = (combined['ytm_long'] - combined['ytm_short']) * 100  # б.п.
            
            # Rolling статистика
            combined['rolling_mean'] = combined['spread'].rolling(window=window).mean()
            combined['rolling_std'] = combined['spread'].rolling(window=window).std()
            combined['z_score'] = (combined['spread'] - combined['rolling_mean']) / combined['rolling_std']
            
            # Границы ±Z sigma
            combined['upper_band'] = combined['rolling_mean'] + z_threshold * combined['rolling_std']
            combined['lower_band'] = combined['rolling_mean'] - z_threshold * combined['rolling_std']
            
            # === КАТЕГОРИАЛЬНАЯ ОСЬ ===
            # x = порядковый номер торговой сессии
            n_points = len(combined)
            x_indices = list(range(n_points))
            
            # Подписи оси X (даты)
            dates = combined.index
            date_labels = [d.strftime('%d.%m.%y') if hasattr(d, 'strftime') else str(d)[:10] for d in dates]
            
            # Выбираем тики (каждый N-й, но не больше ~15 тиков)
            tick_step = max(1, n_points // 15)
            tickvals = x_indices[::tick_step]
            ticktext = [date_labels[i] for i in tickvals]
            
            # --- ПАНЕЛЬ 1: Доходности ---
            # Первый trace: добавляем дату внизу (для unified hover)
            fig.add_trace(
                go.Scatter(
                    x=x_indices,
                    y=combined['ytm_long'],
                    name=bond1_name,
                    line=dict(color=BOND1_COLORS["history"], width=2),
                    customdata=date_labels,
                    hovertemplate=f'{bond1_name}: %{{y:.2f}}%<br><br>📅 %{{customdata}}<extra></extra>'
                ),
                row=1, col=1
            )
            
            # Второй trace: без даты
            fig.add_trace(
                go.Scatter(
                    x=x_indices,
                    y=combined['ytm_short'],
                    name=bond2_name,
                    line=dict(color=BOND2_COLORS["history"], width=2),
                    hovertemplate=f'{bond2_name}: %{{y:.2f}}%<extra></extra>'
                ),
                row=1, col=1
            )
            
            # --- ПАНЕЛЬ 2: Спред и анализ ---
            # Верхняя граница - первый trace, добавляем дату внизу
            fig.add_trace(
                go.Scatter(
                    x=x_indices,
                    y=combined['upper_band'],
                    name=f"+{z_threshold}σ",
                    line=dict(color='rgba(255, 0, 0, 0.4)', dash='dot', width=1),
                    showlegend=True,
                    customdata=date_labels,
                    hovertemplate=f'+{z_threshold}σ: %{{y:.1f}} б.п.<br><br>📅 %{{customdata}}<extra></extra>'
                ),
                row=2, col=1
            )
            
            # Нижняя граница с заливкой - без даты
            fig.add_trace(
                go.Scatter(
                    x=x_indices,
                    y=combined['lower_band'],
                    name=f"-{z_threshold}σ",
                    line=dict(color='rgba(0, 180, 0, 0.4)', dash='dot', width=1),
                    fill='tonexty',
                    fillcolor='rgba(128, 128, 128, 0.08)',
                    showlegend=True,
                    hovertemplate=f'-{z_threshold}σ: %{{y:.1f}} б.п.<extra></extra>'
                ),
                row=2, col=1
            )
            
            # Rolling Mean - без даты
            fig.add_trace(
                go.Scatter(
                    x=x_indices,
                    y=combined['rolling_mean'],
                    name=f"MA({window})",
                    line=dict(color='gray', dash='dash', width=1),
                    hovertemplate=f'MA({window}): %{{y:.1f}} б.п.<extra></extra>'
                ),
                row=2, col=1
            )
            
            # Спред - без даты
            fig.add_trace(
                go.Scatter(
                    x=x_indices,
                    y=combined['spread'],
                    name="Спред",
                    line=dict(color=SPREAD_COLOR, width=2),
                    hovertemplate=f'Спред: %{{y:.1f}} б.п.<extra></extra>'
                ),
                row=2, col=1
            )
            
            # Текущая точка с сигналом
            last_spread = combined['spread'].iloc[-1]
            last_zscore = combined['z_score'].iloc[-1]
            last_idx = x_indices[-1]
            last_date_label = date_labels[-1]
            
            # Цвет по Z-Score
            if last_zscore > z_threshold:
                marker_color = 'red'
                signal = "ПРОДАВАТЬ"
            elif last_zscore < -z_threshold:
                marker_color = 'green'
                signal = "ПОКУПАТЬ"
            else:
                marker_color = 'gray'
                signal = "Нейтрально"
            
            fig.add_trace(
                go.Scatter(
                    x=[last_idx],
                    y=[last_spread],
                    mode='markers+text',
                    marker=dict(size=12, color=marker_color, symbol='diamond'),
                    text=[f"Z={last_zscore:.1f}"],
                    textposition="top center",
                    textfont=dict(size=10, color=marker_color),
                    name=f"Текущий: {last_spread:.1f} б.п.",
                    customdata=[last_date_label],
                    hovertemplate=f'<b>{last_date_label}</b><br>{signal}<br>Спред: {last_spread:.1f} б.п.<br>Z: {last_zscore:.2f}<extra></extra>'
                ),
                row=2, col=1
            )
    
    # Оформление
    fig.update_layout(
        title="📊 Профессиональный анализ спреда",
        template="plotly_white",
        height=700,
        hovermode='x unified',
        margin=dict(l=60, r=30, t=60, b=40),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        )
    )

    # Сетка (пунктир) и категориальная ось X
    fig.update_xaxes(
        showgrid=True,
        gridwidth=1,
        gridcolor='rgba(200, 200, 200, 0.3)',
        griddash='dot',
        tickmode='array',
        tickvals=tickvals if 'tickvals' in dir() else [],
        ticktext=ticktext if 'ticktext' in dir() else [],
        row=1, col=1
    )
    fig.update_xaxes(
        showgrid=True,
        gridwidth=1,
        gridcolor='rgba(200, 200, 200, 0.3)',
        griddash='dot',
        tickmode='array',
        tickvals=tickvals if 'tickvals' in dir() else [],
        ticktext=ticktext if 'ticktext' in dir() else [],
        title_text="Дата",
        row=2, col=1
    )
    fig.update_yaxes(
        showgrid=True,
        gridwidth=1,
        gridcolor='rgba(200, 200, 200, 0.3)',
        griddash='dot',
        title_text="YTM (%)",
        row=1, col=1
    )
    fig.update_yaxes(
        showgrid=True,
        gridwidth=1,
        gridcolor='rgba(200, 200, 200, 0.3)',
        griddash='dot',
        title_text="Спред (б.п.)",
        row=2, col=1
    )
    
    return fig


def apply_zoom_range(fig: go.Figure, x_range: Optional[Tuple]) -> go.Figure:
    """
    Применить диапазон zoom к графику
    
    Args:
        fig: Plotly Figure
        x_range: (x_min, x_max) tuple или None
        
    Returns:
        Plotly Figure с обновлённым диапазоном
    """
    if x_range and x_range[0] and x_range[1]:
        fig.update_xaxes(range=[x_range[0], x_range[1]])
    return fig