"""
OFZ Analytics - Аналитика спредов ОФЗ
Главный файл приложения Streamlit
"""
import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, date, timedelta
from typing import Dict, List, Any, Optional
import logging
import sys
import os

# Добавляем путь к модулям
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import AppConfig, BacktestConfig, BondConfig
from api.moex_trading import TradingChecker, TradingStatus
from api.moex_history import HistoryFetcher
from core.spread import SpreadCalculator, SpreadStats
from core.signals import SignalGenerator, TradingSignal, SignalType
from components.charts import ChartBuilder

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Конфигурация страницы
st.set_page_config(
    page_title="OFZ Spread Analytics",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS стили
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        margin-bottom: 1rem;
    }
    .metric-card {
        background: #f8f9fa;
        padding: 15px;
        border-radius: 10px;
        border-left: 4px solid #1f77b4;
    }
    .signal-buy {
        background: linear-gradient(135deg, #d4edda, #c3e6cb);
        border-left: 4px solid #28a745;
    }
    .signal-sell {
        background: linear-gradient(135deg, #f8d7da, #f5c6cb);
        border-left: 4px solid #dc3545;
    }
    .signal-neutral {
        background: linear-gradient(135deg, #fff3cd, #ffeeba);
        border-left: 4px solid #ffc107;
    }
    .stMetric > div {
        background: #f8f9fa;
        padding: 10px;
        border-radius: 8px;
    }
</style>
""", unsafe_allow_html=True)


def get_years_to_maturity(maturity_str: str) -> float:
    """Вычисляет годы до погашения"""
    try:
        maturity = datetime.strptime(maturity_str, '%Y-%m-%d')
        return round((maturity - datetime.now()).days / 365.25, 1)
    except:
        return 0


def format_bond_label(bond: BondConfig, ytm: float = None, duration_years: float = None) -> str:
    """Форматирует метку облигации с YTM, дюрацией и годами до погашения"""
    years = get_years_to_maturity(bond.maturity_date)
    parts = [f"{bond.name}"]
    
    if ytm is not None:
        parts.append(f"YTM: {ytm:.2f}%")
    if duration_years is not None:
        parts.append(f"Дюр: {duration_years:.1f}г.")
    parts.append(f"{years}г. до погашения")
    
    return " | ".join(parts)


def init_session_state():
    """Инициализация состояния сессии"""
    if 'config' not in st.session_state:
        st.session_state.config = AppConfig()
    
    if 'selected_bond1' not in st.session_state:
        st.session_state.selected_bond1 = 0
    
    if 'selected_bond2' not in st.session_state:
        st.session_state.selected_bond2 = 1
    
    if 'period' not in st.session_state:
        st.session_state.period = 365
    
    if 'auto_refresh' not in st.session_state:
        st.session_state.auto_refresh = False
    
    if 'refresh_interval' not in st.session_state:
        st.session_state.refresh_interval = 60
    
    if 'last_update' not in st.session_state:
        st.session_state.last_update = None


@st.cache_resource
def get_trading_checker():
    """Получить экземпляр TradingChecker (кэшируется)"""
    return TradingChecker()


@st.cache_resource
def get_history_fetcher():
    """Получить экземпляр HistoryFetcher (кэшируется)"""
    return HistoryFetcher()


@st.cache_resource
def get_spread_calculator():
    """Получить экземпляр SpreadCalculator (кэшируется)"""
    return SpreadCalculator()


@st.cache_resource
def get_signal_generator():
    """Получить экземпляр SignalGenerator (кэшируется)"""
    return SignalGenerator()


@st.cache_data(ttl=300)
def fetch_trading_data_cached(secid: str) -> Dict:
    """Получить торговые данные с кэшированием"""
    fetcher = get_history_fetcher()
    return fetcher.get_trading_data(secid)


@st.cache_data(ttl=300)
def fetch_historical_data_cached(secid: str, days: int) -> pd.DataFrame:
    """Получить исторические данные с кэшированием"""
    fetcher = get_history_fetcher()
    start_date = date.today() - timedelta(days=days)
    return fetcher.fetch_ytm_history(secid, start_date=start_date)


def calculate_spread_stats(spread_series: pd.Series) -> Dict:
    """Вычисляет статистику спреда"""
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
        'current': spread_series.iloc[-1]
    }


def generate_signal(current_spread: float, p10: float, p25: float, p75: float, p90: float) -> Dict:
    """Генерирует торговый сигнал"""
    if current_spread < p25:
        return {
            'signal': 'SELL_BUY',
            'action': 'ПРОДАТЬ Облигацию 1, КУПИТЬ Облигацию 2',
            'reason': f'Спред {current_spread:.2f} б.п. ниже P25 ({p25:.2f} б.п.) — Облигация 1 переоценена относительно Облигации 2',
            'color': '#FF6B6B',
            'strength': 'Сильный' if current_spread < p10 else 'Средний'
        }
    elif current_spread > p75:
        return {
            'signal': 'BUY_SELL',
            'action': 'КУПИТЬ Облигацию 1, ПРОДАТЬ Облигацию 2',
            'reason': f'Спред {current_spread:.2f} б.п. выше P75 ({p75:.2f} б.п.) — Облигация 1 недооценена относительно Облигации 2',
            'color': '#4ECDC4',
            'strength': 'Сильный' if current_spread > p90 else 'Средний'
        }
    else:
        return {
            'signal': 'NEUTRAL',
            'action': 'Удерживать позиции',
            'reason': f'Спред {current_spread:.2f} б.п. в нормальном диапазоне [P25={p25:.2f}, P75={p75:.2f}]',
            'color': '#95A5A6',
            'strength': 'Нет сигнала'
        }


def create_charts(df1: pd.DataFrame, df2: pd.DataFrame, merged_df: pd.DataFrame, stats: Dict, bond1_name: str, bond2_name: str):
    """Создаёт графики с Plotly"""
    import plotly.graph_objects as go
    
    # График доходностей
    fig_yields = go.Figure()
    fig_yields.add_trace(go.Scatter(
        x=df1.index, y=df1['ytm'],
        name=bond1_name, line=dict(color='#3498DB', width=2)
    ))
    fig_yields.add_trace(go.Scatter(
        x=df2.index, y=df2['ytm'],
        name=bond2_name, line=dict(color='#E74C3C', width=2)
    ))
    fig_yields.update_layout(
        title='Доходность к погашению (YTM)',
        xaxis_title='Дата',
        yaxis_title='Доходность, %',
        hovermode='x unified',
        height=400,
        margin=dict(l=0, r=0, t=40, b=0)
    )
    
    # График спреда
    fig_spread = go.Figure()
    
    # Линии перцентилей
    fig_spread.add_hline(y=stats['mean'], line_dash='dash', line_color='gray',
                         annotation_text=f"Среднее: {stats['mean']:.2f}")
    fig_spread.add_hline(y=stats['p25'], line_dash='dot', line_color='green',
                         annotation_text=f"P25: {stats['p25']:.2f}")
    fig_spread.add_hline(y=stats['p75'], line_dash='dot', line_color='red',
                         annotation_text=f"P75: {stats['p75']:.2f}")
    
    # Основной график спреда
    fig_spread.add_trace(go.Scatter(
        x=merged_df['date'],
        y=merged_df['spread'],
        name='Спред',
        line=dict(color='#9B59B6', width=2),
        fill='tozeroy',
        fillcolor='rgba(155, 89, 182, 0.1)'
    ))
    
    # Текущая точка
    fig_spread.add_trace(go.Scatter(
        x=[merged_df['date'].iloc[-1]],
        y=[merged_df['spread'].iloc[-1]],
        mode='markers',
        marker=dict(size=12, color='yellow', line=dict(width=2, color='black')),
        name='Текущий'
    ))
    
    fig_spread.update_layout(
        title='Спред доходности (базисные пункты)',
        xaxis_title='Дата',
        yaxis_title='Спред, б.п.',
        hovermode='x unified',
        height=400,
        margin=dict(l=0, r=0, t=40, b=0)
    )
    
    return fig_yields, fig_spread


def main():
    """Главная функция"""
    init_session_state()
    
    config = st.session_state.config
    bonds = list(config.bonds.values())
    
    # Боковая панель
    with st.sidebar:
        st.header("⚙️ Настройки")
        
        # Получаем данные для отображения в dropdown (пробуем торговые)
        bond_labels = []
        bond_trading_data = {}
        
        for b in bonds:
            data = fetch_trading_data_cached(b.isin)
            bond_trading_data[b.isin] = data
            if data.get('has_data') and data.get('yield'):
                bond_labels.append(format_bond_label(b, data['yield'], data.get('duration_years')))
            else:
                bond_labels.append(format_bond_label(b))
        
        bond1_idx = st.selectbox(
            "Облигация 1",
            range(len(bonds)),
            format_func=lambda i: bond_labels[i],
            index=st.session_state.selected_bond1
        )
        st.session_state.selected_bond1 = bond1_idx
        
        bond2_idx = st.selectbox(
            "Облигация 2",
            range(len(bonds)),
            format_func=lambda i: bond_labels[i],
            index=st.session_state.selected_bond2
        )
        st.session_state.selected_bond2 = bond2_idx
        
        # Период
        period = st.radio(
            "Период анализа",
            [365, 730],
            format_func=lambda x: f"{x // 365} год(а)",
            index=0 if st.session_state.period == 365 else 1
        )
        st.session_state.period = period
        
        st.divider()
        
        # Настройки автообновления
        st.subheader("🔄 Автообновление")
        auto_refresh = st.toggle(
            "Включить автообновление",
            value=st.session_state.auto_refresh
        )
        st.session_state.auto_refresh = auto_refresh
        
        if auto_refresh:
            refresh_interval = st.slider(
                "Интервал (секунды)",
                min_value=30,
                max_value=300,
                value=st.session_state.refresh_interval,
                step=30
            )
            st.session_state.refresh_interval = refresh_interval
            
            if st.session_state.last_update:
                st.caption(f"Последнее обновление: {st.session_state.last_update.strftime('%H:%M:%S')}")
        
        st.divider()
        
        # Очистка кэша
        if st.button("🗑️ Очистить кэш и обновить", use_container_width=True):
            st.cache_data.clear()
            st.rerun()
    
    # Заголовок
    st.title("📊 OFZ Spread Analytics")
    st.markdown("Анализ спредов облигаций ОФЗ с данными Московской биржи")
    
    # Получение данных
    bond1 = bonds[bond1_idx]
    bond2 = bonds[bond2_idx]
    
    # Загрузка данных
    with st.spinner("Загрузка данных с MOEX..."):
        # Исторические данные всегда нужны для графиков
        df1 = fetch_historical_data_cached(bond1.isin, period)
        df2 = fetch_historical_data_cached(bond2.isin, period)
        
        # Пробуем получить торговые данные
        trading1 = bond_trading_data.get(bond1.isin, {})
        trading2 = bond_trading_data.get(bond2.isin, {})
        
        # Определяем режим работы
        is_trading = trading1.get('has_data') and trading1.get('yield') is not None
        
        if is_trading:
            # Биржа работает — используем торговые данные
            current1 = trading1
            current2 = trading2
            status_text = "🟢 Торговая сессия"
            status_color = "#2ECC71"
            source_text = "Торговые данные"
        else:
            # Торгов нет — используем исторические
            is_trading = False
            status_text = "🔴 Торги не проводятся"
            status_color = "#E74C3C"
            source_text = "Исторические данные"
            
            current1 = None
            current2 = None
            
            if not df1.empty:
                last_row1 = df1.iloc[-1]
                current1 = {
                    'isin': bond1.isin,
                    'yield': last_row1['ytm'],
                    'duration_years': df1.get('duration_years', pd.Series([None])).iloc[-1] if 'duration_years' in df1.columns else None,
                    'price': None,
                    'date': df1.index[-1]
                }
            
            if not df2.empty:
                last_row2 = df2.iloc[-1]
                current2 = {
                    'isin': bond2.isin,
                    'yield': last_row2['ytm'],
                    'duration_years': df2.get('duration_years', pd.Series([None])).iloc[-1] if 'duration_years' in df2.columns else None,
                    'price': None,
                    'date': df2.index[-1]
                }
    
    # Индикатор режима работы
    st.markdown(f"""
    <div style="background-color: {status_color}20; padding: 10px 15px; border-radius: 5px; 
                border-left: 4px solid {status_color}; display: inline-block;">
        <strong>{status_text}</strong> 
        <span style="color: gray; font-size: 0.9em;">| Источник: {source_text}</span>
    </div>
    """, unsafe_allow_html=True)
    
    # Индикатор автообновления
    if st.session_state.auto_refresh:
        st.info(f"🔄 Автообновление включено (каждые {st.session_state.refresh_interval} сек.)")
    
    # Отображение текущих данных
    col1, col2 = st.columns(2)
    
    years1 = get_years_to_maturity(bond1.maturity_date)
    years2 = get_years_to_maturity(bond2.maturity_date)
    
    with col1:
        if current1:
            title1 = format_bond_label(bond1, current1['yield'], current1.get('duration_years'))
            st.subheader(f"📈 {title1}")
            metric_col1, metric_col2, metric_col3 = st.columns(3)
            with metric_col1:
                st.metric("YTM", f"{current1['yield']:.2f}%" if current1['yield'] else "Н/Д")
            with metric_col2:
                price_val = current1.get('price')
                st.metric("Цена", f"{price_val:.2f}%" if price_val else "Н/Д")
            with metric_col3:
                st.metric("До погашения", f"{years1}г.")
            
            # Дата данных (для исторических)
            if current1.get('date'):
                st.caption(f"ISIN: {bond1.isin} | Данные от: {current1['date'].strftime('%d.%m.%Y')}")
            else:
                dur = current1.get('duration_years')
                st.caption(f"ISIN: {bond1.isin} | Дюрация: {dur:.1f}г." if dur else f"ISIN: {bond1.isin}")
        else:
            st.subheader(f"📈 {bond1.name}")
            st.error("Данные недоступны")
    
    with col2:
        if current2:
            title2 = format_bond_label(bond2, current2['yield'], current2.get('duration_years'))
            st.subheader(f"📈 {title2}")
            metric_col1, metric_col2, metric_col3 = st.columns(3)
            with metric_col1:
                st.metric("YTM", f"{current2['yield']:.2f}%" if current2['yield'] else "Н/Д")
            with metric_col2:
                price_val = current2.get('price')
                st.metric("Цена", f"{price_val:.2f}%" if price_val else "Н/Д")
            with metric_col3:
                st.metric("До погашения", f"{years2}г.")
            
            # Дата данных (для исторических)
            if current2.get('date'):
                st.caption(f"ISIN: {bond2.isin} | Данные от: {current2['date'].strftime('%d.%m.%Y')}")
            else:
                dur = current2.get('duration_years')
                st.caption(f"ISIN: {bond2.isin} | Дюрация: {dur:.1f}г." if dur else f"ISIN: {bond2.isin}")
        else:
            st.subheader(f"📈 {bond2.name}")
            st.error("Данные недоступны")
    
    st.divider()
    
    # Проверка исторических данных
    if df1.empty or df2.empty:
        st.error("Не удалось загрузить исторические данные для одной или обеих облигаций")
        st.stop()
    
    # Объединение данных
    merged_df = pd.merge(
        df1.reset_index()[['date', 'ytm']],
        df2.reset_index()[['date', 'ytm']],
        on='date',
        suffixes=('_1', '_2')
    )
    merged_df['spread'] = (merged_df['ytm_1'] - merged_df['ytm_2']) * 100  # в базисных пунктах
    
    # Статистика
    stats = calculate_spread_stats(merged_df['spread'])
    
    # Торговый сигнал
    signal = generate_signal(
        stats['current'], 
        stats['p10'], 
        stats['p25'], 
        stats['p75'], 
        stats['p90']
    )
    
    # Отображение сигнала
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown(f"""
        <div style="background-color: {signal['color']}20; padding: 20px; border-radius: 10px; border-left: 5px solid {signal['color']};">
            <h3 style="margin:0; color: {signal['color']};">📈 {signal['signal']}</h3>
            <p style="margin:5px 0 0 0; font-weight: bold;">{signal['action']}</p>
            <p style="margin:5px 0 0 0; font-size: 0.9em;">{signal['reason']}</p>
            <p style="margin:5px 0 0 0; font-size: 0.8em; color: gray;">Сила сигнала: {signal['strength']}</p>
        </div>
        """, unsafe_allow_html=True)
    
    st.divider()
    
    # Графики (друг под другом)
    fig_yields, fig_spread = create_charts(df1, df2, merged_df, stats, bond1.name, bond2.name)
    
    st.plotly_chart(fig_yields, use_container_width=True)
    st.plotly_chart(fig_spread, use_container_width=True)
    
    # Статистика спреда
    st.subheader("📊 Статистика спреда")
    
    stat_col1, stat_col2, stat_col3, stat_col4 = st.columns(4)
    with stat_col1:
        st.metric("Текущий спред", f"{stats['current']:.2f} б.п.")
        st.metric("Среднее", f"{stats['mean']:.2f} б.п.")
    with stat_col2:
        st.metric("P10", f"{stats['p10']:.2f} б.п.")
        st.metric("P25", f"{stats['p25']:.2f} б.п.")
    with stat_col3:
        st.metric("P75", f"{stats['p75']:.2f} б.п.")
        st.metric("P90", f"{stats['p90']:.2f} б.п.")
    with stat_col4:
        st.metric("Минимум", f"{stats['min']:.2f} б.п.")
        st.metric("Максимум", f"{stats['max']:.2f} б.п.")
    
    # История данных
    with st.expander("📋 История данных (последние 10 записей)"):
        display_df = merged_df.tail(10).copy()
        display_df['date'] = display_df['date'].dt.strftime('%d.%m.%Y')
        st.dataframe(
            display_df.style.format({
                'ytm_1': '{:.3f}',
                'ytm_2': '{:.3f}',
                'spread': '{:.2f}'
            }),
            use_container_width=True
        )
    
    # Обновление времени последнего обновления
    st.session_state.last_update = datetime.now()
    
    # Автообновление
    if st.session_state.auto_refresh:
        import time
        time.sleep(st.session_state.refresh_interval)
        st.rerun()


if __name__ == "__main__":
    main()
