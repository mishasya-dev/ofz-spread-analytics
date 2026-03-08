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
    has_value = bool(has_value1 or has_value2)  # Convert to Python bool for Plotly
    
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
    Создать панель анализа спреда с Z-Score.
    
    Один график с двумя Y-осями (domain):
    - Верхняя часть: Доходности YTM обеих облигаций
    - Нижняя часть: Спред + Rolling Mean + ±Z Sigma границы
    
    Spike line работает по всему графику благодаря единой X-оси.
    
    Args:
        df1: DataFrame с YTM облигации 1 (длинная)
        df2: DataFrame с YTM облигации 2 (короткая)
        bond1_name: Название облигации 1
        bond2_name: Название облигации 2
        window: Окно для rolling расчётов (дней)
        z_threshold: Порог Z-Score для границ (обычно 2.0)
        
    Returns:
        Plotly Figure с двумя панелями на одном графике
    """
    
    fig = go.Figure()
    
    # Инициализируем переменные для пустого случая
    tickvals = []
    ticktext = []
    
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
            n_points = len(combined)
            x_indices = list(range(n_points))
            
            # Подписи оси X (даты)
            dates = combined.index
            date_labels = [d.strftime('%d.%m.%y') if hasattr(d, 'strftime') else str(d)[:10] for d in dates]
            
            # Выбираем тики (каждый N-й, но не больше ~15 тиков)
            tick_step = max(1, n_points // 15)
            tickvals = x_indices[::tick_step]
            ticktext = [date_labels[i] for i in tickvals]
            
            # --- ВЕРХНЯЯ ПАНЕЛЬ: YTM (yaxis='y') ---
            # Невидимый trace для даты (первым!)
            # Используем среднее значение YTM для позиционирования
            ytm_avg = (combined['ytm_long'].mean() + combined['ytm_short'].mean()) / 2
            fig.add_trace(go.Scatter(
                x=x_indices,
                y=[ytm_avg] * n_points,
                name='',
                showlegend=False,
                hoverinfo='skip',
                mode='lines',
                line=dict(color='rgba(0,0,0,0)', width=0),
                customdata=date_labels,
                hovertemplate=f'<b>📅 %{{customdata}}</b><extra></extra>'
            ))
            
            # Bond1
            fig.add_trace(go.Scatter(
                x=x_indices,
                y=combined['ytm_long'],
                name=bond1_name,
                line=dict(color=BOND1_COLORS["history"], width=2),
                customdata=date_labels,
                hovertemplate=f'{bond1_name}: %{{y:.2f}}%<extra></extra>'
            ))
            
            # Bond2
            fig.add_trace(go.Scatter(
                x=x_indices,
                y=combined['ytm_short'],
                name=bond2_name,
                line=dict(color=BOND2_COLORS["history"], width=2),
                customdata=date_labels,
                hovertemplate=f'{bond2_name}: %{{y:.2f}}%<extra></extra>'
            ))
            
            # --- НИЖНЯЯ ПАНЕЛЬ: Спред (yaxis='y2') ---
            # Невидимый trace для даты (первым в нижней панели!)
            spread_avg = combined['spread'].mean()
            fig.add_trace(go.Scatter(
                x=x_indices,
                y=[spread_avg] * n_points,
                name='',
                yaxis='y2',
                showlegend=False,
                hoverinfo='skip',
                mode='lines',
                line=dict(color='rgba(0,0,0,0)', width=0),
                customdata=date_labels,
                hovertemplate=f'<b>📅 %{{customdata}}</b><extra></extra>'
            ))
            
            # Верхняя граница
            fig.add_trace(go.Scatter(
                x=x_indices,
                y=combined['upper_band'],
                name=f"+{z_threshold}σ",
                yaxis='y2',
                line=dict(color='rgba(255, 0, 0, 0.4)', dash='dot', width=1),
                showlegend=True,
                customdata=date_labels,
                hovertemplate=f'+{z_threshold}σ: %{{y:.1f}} б.п.<extra></extra>'
            ))
            
            # Нижняя граница с заливкой
            fig.add_trace(go.Scatter(
                x=x_indices,
                y=combined['lower_band'],
                name=f"-{z_threshold}σ",
                yaxis='y2',
                line=dict(color='rgba(0, 180, 0, 0.4)', dash='dot', width=1),
                fill='tonexty',
                fillcolor='rgba(128, 128, 128, 0.1)',
                showlegend=True,
                customdata=date_labels,
                hovertemplate=f'-{z_threshold}σ: %{{y:.1f}} б.п.<extra></extra>'
            ))
            
            # Rolling Mean
            fig.add_trace(go.Scatter(
                x=x_indices,
                y=combined['rolling_mean'],
                name=f"MA({window})",
                yaxis='y2',
                line=dict(color='gray', dash='dash', width=1),
                customdata=date_labels,
                hovertemplate=f'MA({window}): %{{y:.1f}} б.п.<extra></extra>'
            ))
            
            # Спред
            fig.add_trace(go.Scatter(
                x=x_indices,
                y=combined['spread'],
                name="Спред",
                yaxis='y2',
                line=dict(color=SPREAD_COLOR, width=2),
                customdata=date_labels,
                hovertemplate=f'Спред: %{{y:.1f}} б.п.<extra></extra>'
            ))
            
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
            
            fig.add_trace(go.Scatter(
                x=[last_idx],
                y=[last_spread],
                mode='markers+text',
                name=f"Текущий: {last_spread:.1f} б.п.",
                yaxis='y2',
                marker=dict(size=12, color=marker_color, symbol='diamond'),
                text=[f"Z={last_zscore:.1f}"],
                textposition="top center",
                textfont=dict(size=10, color=marker_color),
                customdata=[last_date_label],
                hovertemplate=f'{signal}<br>Спред: {last_spread:.1f} б.п.<br>Z: {last_zscore:.2f}<extra></extra>'
            ))
    
    # --- Оформление с двумя Y-осями ---
    # Вычисляем диапазоны для Y-осей
    ytm_min = combined['ytm_long'].min() if 'combined' in dir() and len(combined) > 0 else 13
    ytm_max = combined['ytm_long'].max() if 'combined' in dir() and len(combined) > 0 else 16
    spread_min = combined['spread'].min() if 'combined' in dir() and len(combined) > 0 else -50
    spread_max = combined['spread'].max() if 'combined' in dir() and len(combined) > 0 else 150
    
    # Padding
    ytm_padding = (ytm_max - ytm_min) * 0.1
    spread_padding = (spread_max - spread_min) * 0.1
    
    fig.update_layout(
        title="Анализ спреда",
        template="plotly_white",
        height=700,
        hovermode='x unified',
        margin=dict(l=60, r=60, t=60, b=80),  # Увеличен bottom для дат
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
        # YTM ось (верхняя панель)
        yaxis=dict(
            domain=[0.52, 1.0],
            title=dict(text="YTM (%)", standoff=10),
            range=[ytm_min - ytm_padding, ytm_max + ytm_padding],
            showgrid=True,
            gridwidth=1,
            gridcolor='rgba(200, 200, 200, 0.3)',
            griddash='dot'
        ),
        # Спред ось (нижняя панель)
        yaxis2=dict(
            domain=[0.0, 0.48],
            title=dict(text="Спред (б.п.)", standoff=10),
            range=[spread_min - spread_padding, spread_max + spread_padding],
            showgrid=True,
            gridwidth=1,
            gridcolor='rgba(200, 200, 200, 0.3)',
            griddash='dot'
        ),
        # X-ось (привязана к нижней панели yaxis2)
        xaxis=dict(
            domain=[0.0, 1.0],
            anchor='y2',  # Привязываем к нижней оси Y
            showgrid=True,
            gridwidth=1,
            gridcolor='rgba(200, 200, 200, 0.3)',
            griddash='dot',
            tickmode='array',
            tickvals=tickvals,
            ticktext=ticktext,
            side='bottom'
        ),
        # Разделительная линия между панелями
        shapes=[
            dict(
                type='line',
                xref='paper', yref='paper',
                x0=0, y0=0.5, x1=1, y1=0.5,
                line=dict(color='rgba(100, 100, 100, 0.3)', width=1, dash='solid')
            )
        ],
        # Аннотации для заголовков панелей
        annotations=[
            dict(
                text="Доходности YTM",
                x=0.01, y=1.0,
                xref='paper', yref='paper',
                showarrow=False,
                font=dict(size=12, color='rgba(100, 100, 100, 0.8)'),
                yanchor='bottom'
            ),
            dict(
                text=f"Анализ спреда (Rolling {window} дн., Z-Score ±{z_threshold})",
                x=0.5, y=-0.08,
                xref='paper', yref='paper',
                showarrow=False,
                font=dict(size=13)
            )
        ]
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


# ============================================
# G-SPREAD ДАШБОРД
# ============================================

def create_g_spread_dashboard(
    df_res: pd.DataFrame,
    title: str = "YTM ОФЗ vs Теоретическая КБД"
) -> go.Figure:
    """
    Создать дашборд G-spread с двумя графиками:
    1. Верхний: YTM облигации vs YTM_КБД (теоретическая)
    2. Нижний: Z-Score G-spread с сигналами
    
    Args:
        df_res: DataFrame с колонками:
            - date: дата
            - ticker: идентификатор облигации
            - ytm: реальная доходность облигации (%)
            - ytm_theor: теоретическая YTM по КБД (%)
            - zscore: Z-Score G-spread
            - g_spread: G-spread (б.п.)
            
    Returns:
        Plotly Figure
    """
    tickers = df_res['ticker'].unique()
    
    fig = make_subplots(
        rows=2, cols=1, 
        shared_xaxes=True, 
        vertical_spacing=0.05, 
        row_heights=[0.7, 0.3],
        subplot_titles=(title, "Z-Score G-Spread (Сигналы)")
    )

    colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b']

    for i, ticker in enumerate(tickers):
        data = df_res[df_res['ticker'] == ticker].copy()
        color = colors[i % len(colors)]

        # ВЕРХНИЙ ГРАФИК: Реальная доходность
        fig.add_trace(
            go.Scatter(
                x=data['date'], 
                y=data['ytm'], 
                name=f"ОФЗ {ticker} (Рынок)", 
                line=dict(color=color, width=2),
                legendgroup=ticker
            ), 
            row=1, col=1
        )
        
        # ВЕРХНИЙ ГРАФИК: Персональная КБД (пунктир)
        if 'ytm_theor' in data.columns:
            fig.add_trace(
                go.Scatter(
                    x=data['date'], 
                    y=data['ytm_theor'], 
                    name=f"КБД для {ticker}", 
                    line=dict(color=color, dash='dot', width=1), 
                    opacity=0.6,
                    legendgroup=ticker,
                    showlegend=True
                ), 
                row=1, col=1
            )

        # НИЖНИЙ ГРАФИК: Z-Score
        if 'zscore' in data.columns:
            fig.add_trace(
                go.Scatter(
                    x=data['date'], 
                    y=data['zscore'], 
                    name=f"Z-Score {ticker}", 
                    line=dict(color=color, width=1.5),
                    showlegend=False,
                    legendgroup=ticker
                ), 
                row=2, col=1
            )

    # Линии сигналов на нижнем графике
    fig.add_hline(
        y=2, 
        line_dash="dash", 
        line_color="red", 
        row=2, col=1, 
        annotation_text="SELL",
        annotation_position="right",
        annotation_font_color="red"
    )
    fig.add_hline(
        y=-2, 
        line_dash="dash", 
        line_color="green", 
        row=2, col=1, 
        annotation_text="BUY",
        annotation_position="right",
        annotation_font_color="green"
    )
    
    # Нулевая линия
    fig.add_hline(
        y=0, 
        line_dash="dot", 
        line_color="gray", 
        row=2, col=1,
        opacity=0.5
    )
    
    fig.update_layout(
        height=700, 
        hovermode="x unified", 
        template="plotly_white",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        )
    )
    
    # Оформление осей
    fig.update_yaxes(title_text="YTM (%)", row=1, col=1)
    fig.update_yaxes(title_text="Z-Score", row=2, col=1)
    fig.update_xaxes(title_text="Дата", row=2, col=1)
    
    return fig


def create_g_spread_chart_single(
    g_spread_df: pd.DataFrame,
    bond_name: str,
    stats: Optional[Dict] = None
) -> go.Figure:
    """
    Создать график G-spread для одной облигации с перцентилями
    
    Args:
        g_spread_df: DataFrame с колонками:
            - date (индекс или колонка)
            - ytm_bond: YTM облигации (%)
            - ytm_kbd: YTM по КБД (%)
            - g_spread_bp: G-spread (б.п.)
        bond_name: Название облигации
        stats: Статистика {p25, p75, mean, current}
        
    Returns:
        Plotly Figure
    """
    fig = go.Figure()
    
    # Сброс индекса если нужно
    if 'date' not in g_spread_df.columns:
        g_spread_df = g_spread_df.reset_index()
    
    # G-spread
    fig.add_trace(go.Scatter(
        x=g_spread_df['date'],
        y=g_spread_df['g_spread_bp'],
        name='G-spread',
        line=dict(color='#9B59B6', width=2),
        fill='tozeroy',
        fillcolor='rgba(155, 89, 182, 0.1)'
    ))
    
    # Перцентили
    if stats:
        if 'p25' in stats:
            fig.add_hline(
                y=stats['p25'],
                line_dash='dot',
                line_color='green',
                annotation_text=f"P25: {stats['p25']:.0f}",
                annotation_position='left'
            )
        if 'p75' in stats:
            fig.add_hline(
                y=stats['p75'],
                line_dash='dot',
                line_color='red',
                annotation_text=f"P75: {stats['p75']:.0f}",
                annotation_position='left'
            )
        if 'mean' in stats:
            fig.add_hline(
                y=stats['mean'],
                line_dash='dash',
                line_color='gray',
                annotation_text=f"Mean: {stats['mean']:.0f}",
                annotation_position='left'
            )
        
        # Текущая точка
        if 'current' in stats:
            last_date = g_spread_df['date'].iloc[-1]
            fig.add_trace(go.Scatter(
                x=[last_date],
                y=[stats['current']],
                mode='markers',
                marker=dict(size=12, color='yellow', line=dict(width=2, color='black')),
                name='Текущий',
                showlegend=False
            ))
    
    fig.update_layout(
        title=f"G-spread: {bond_name}",
        xaxis_title="Дата",
        yaxis_title="G-spread (б.п.)",
        hovermode='x unified',
        template="plotly_white",
        height=400
    )
    
    return fig
