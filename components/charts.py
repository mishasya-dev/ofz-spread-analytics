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

# Цвета для облигаций
BOND_COLORS = [
    "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728",
    "#9467bd", "#8c564b", "#e377c2", "#7f7f7f",
    "#bcbd22", "#17becf", "#aec7e8", "#ffbb78",
    "#98df8a", "#ff9896", "#c5b0d5", "#c49c94"
]

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