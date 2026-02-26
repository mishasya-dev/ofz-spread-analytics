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
from api.moex_candles import CandleFetcher, CandleInterval
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
    .mode-badge {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 15px;
        font-size: 0.85em;
        font-weight: bold;
        margin-left: 10px;
    }
    .mode-daily {
        background: #3498db;
        color: white;
    }
    .mode-intraday {
        background: #e74c3c;
        color: white;
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
    
    if 'data_mode' not in st.session_state:
        st.session_state.data_mode = "daily"  # "daily" или "intraday"
    
    if 'candle_interval' not in st.session_state:
        st.session_state.candle_interval = "60"  # "1", "10", "60"


@st.cache_resource
def get_trading_checker():
    """Получить экземпляр TradingChecker (кэшируется)"""
    return TradingChecker()


@st.cache_resource
def get_history_fetcher():
    """Получить экземпляр HistoryFetcher (кэшируется)"""
    return HistoryFetcher()


@st.cache_resource
def get_candle_fetcher():
    """Получить экземпляр CandleFetcher (кэшируется)"""
    return CandleFetcher()


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


@st.cache_data(ttl=60)
def fetch_candle_data_cached(isin: str, bond_config_dict: Dict, interval: str, days: int) -> pd.DataFrame:
    """Получить данные свечей с YTM с кэшированием"""
    fetcher = get_candle_fetcher()
    
    # Восстанавливаем BondConfig из словаря
    bond_config = BondConfig(**bond_config_dict)
    
    # Маппинг интервала
    interval_map = {
        "1": CandleInterval.MIN_1,    # 1 минута
        "10": CandleInterval.MIN_10,  # 10 минут
        "60": CandleInterval.MIN_60,  # 1 час
    }
    
    candle_interval = interval_map.get(interval, CandleInterval.MIN_60)
    
    start_date = date.today() - timedelta(days=days)
    
    return fetcher.fetch_candles(
        isin,
        bond_config=bond_config,
        interval=candle_interval,
        start_date=start_date,
        end_date=date.today()
    )


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


def create_ytm_chart(df1: pd.DataFrame, df2: pd.DataFrame, bond1_name: str, bond2_name: str, is_intraday: bool = False):
    """Создаёт график YTM"""
    import plotly.graph_objects as go
    
    fig = go.Figure()
    
    # Определяем колонки
    ytm_col1 = 'ytm_close' if 'ytm_close' in df1.columns else 'ytm'
    ytm_col2 = 'ytm_close' if 'ytm_close' in df2.columns else 'ytm'
    
    fig.add_trace(go.Scatter(
        x=df1.index, y=df1[ytm_col1],
        name=bond1_name, line=dict(color='#3498DB', width=2)
    ))
    fig.add_trace(go.Scatter(
        x=df2.index, y=df2[ytm_col2],
        name=bond2_name, line=dict(color='#E74C3C', width=2)
    ))
    
    title = 'Доходность к погашению (YTM) - Внутридневные данные' if is_intraday else 'Доходность к погашению (YTM)'
    x_title = 'Время' if is_intraday else 'Дата'
    
    fig.update_layout(
        title=title,
        xaxis_title=x_title,
        yaxis_title='Доходность, %',
        hovermode='x unified',
        height=400,
        margin=dict(l=0, r=0, t=40, b=0)
    )
    
    return fig


def create_spread_chart(merged_df: pd.DataFrame, stats: Dict, is_intraday: bool = False):
    """Создаёт график спреда"""
    import plotly.graph_objects as go
    
    fig = go.Figure()
    
    # Линии перцентилей
    fig.add_hline(y=stats['mean'], line_dash='dash', line_color='gray',
                  annotation_text=f"Среднее: {stats['mean']:.2f}")
    fig.add_hline(y=stats['p25'], line_dash='dot', line_color='green',
                  annotation_text=f"P25: {stats['p25']:.2f}")
    fig.add_hline(y=stats['p75'], line_dash='dot', line_color='red',
                  annotation_text=f"P75: {stats['p75']:.2f}")
    
    # Основной график спреда
    fig.add_trace(go.Scatter(
        x=merged_df['datetime'] if 'datetime' in merged_df.columns else merged_df['date'],
        y=merged_df['spread'],
        name='Спред',
        line=dict(color='#9B59B6', width=2),
        fill='tozeroy',
        fillcolor='rgba(155, 89, 182, 0.1)'
    ))
    
    # Текущая точка
    x_current = merged_df['datetime'].iloc[-1] if 'datetime' in merged_df.columns else merged_df['date'].iloc[-1]
    fig.add_trace(go.Scatter(
        x=[x_current],
        y=[merged_df['spread'].iloc[-1]],
        mode='markers',
        marker=dict(size=12, color='yellow', line=dict(width=2, color='black')),
        name='Текущий'
    ))
    
    title = 'Спред доходности (базисные пункты) - Внутридневные данные' if is_intraday else 'Спред доходности (базисные пункты)'
    x_title = 'Время' if is_intraday else 'Дата'
    
    fig.update_layout(
        title=title,
        xaxis_title=x_title,
        yaxis_title='Спред, б.п.',
        hovermode='x unified',
        height=400,
        margin=dict(l=0, r=0, t=40, b=0)
    )
    
    return fig


def bond_config_to_dict(bond: BondConfig) -> Dict:
    """Конвертировать BondConfig в словарь для кэширования"""
    return {
        'isin': bond.isin,
        'name': bond.name,
        'maturity_date': bond.maturity_date,
        'coupon_rate': bond.coupon_rate,
        'face_value': bond.face_value,
        'coupon_frequency': bond.coupon_frequency,
        'issue_date': bond.issue_date,
        'day_count_convention': getattr(bond, 'day_count_convention', 'ACT/ACT')
    }


def main():
    """Главная функция"""
    init_session_state()
    
    config = st.session_state.config
    bonds = list(config.bonds.values())
    
    # ==========================================
    # БОКОВАЯ ПАНЕЛЬ
    # ==========================================
    with st.sidebar:
        st.header("⚙️ Настройки")
        
        # Переключатель режима данных
        st.subheader("📊 Режим данных")
        data_mode = st.radio(
            "Источник YTM",
            ["daily", "intraday"],
            format_func=lambda x: "📅 Данные биржи (day close YTM)" if x == "daily" else "⏱️ Внутридневные (свечи)",
            index=0 if st.session_state.data_mode == "daily" else 1
        )
        st.session_state.data_mode = data_mode
        
        # Выбор интервала свечей (только для внутридневного режима)
        if data_mode == "intraday":
            candle_interval = st.select_slider(
                "Интервал свечей",
                options=["1", "10", "60"],
                format_func=lambda x: {
                    "1": "1 минута",
                    "10": "10 минут",
                    "60": "1 час"
                }[x],
                value=st.session_state.candle_interval
            )
            st.session_state.candle_interval = candle_interval
            
            interval_names = {"1": "1-минутных", "10": "10-минутных", "60": "часовых"}
            st.info(f"📊 YTM рассчитывается из цен {interval_names[candle_interval]} свечей")
        
        st.divider()
        
        # Получаем данные для отображения в dropdown
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
        if data_mode == "daily":
            period = st.radio(
                "Период анализа",
                [365, 730],
                format_func=lambda x: f"{x // 365} год(а)",
                index=0 if st.session_state.period == 365 else 1
            )
            st.session_state.period = period
        else:
            # Для внутридневного режима - зависит от интервала
            # 1 минута: макс 3 дня (много данных)
            # 10 минут и 1 час: макс 30 дней
            if candle_interval == "1":
                max_days = 3
                default_days = 1
            else:
                max_days = 30
                default_days = 7
            
            period = st.slider(
                f"Дней истории (макс {max_days} для {candle_interval} мин)",
                min_value=1,
                max_value=max_days,
                value=min(st.session_state.get('intraday_period', default_days), max_days),
                step=1
            )
            st.session_state.intraday_period = period
        
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
    
    # ==========================================
    # ЗАГОЛОВОК
    # ==========================================
    mode_badge = '<span class="mode-badge mode-daily">📅 Дневной режим</span>' if data_mode == "daily" else '<span class="mode-badge mode-intraday">⏱️ Внутридневной режим</span>'
    
    st.markdown(f"""
    <div style="display: flex; align-items: center; margin-bottom: 10px;">
        <h1 style="margin: 0;">📊 OFZ Spread Analytics</h1>
        {mode_badge}
    </div>
    <p style="margin: 0; color: #666;">Анализ спредов облигаций ОФЗ с данными Московской биржи</p>
    """, unsafe_allow_html=True)
    
    # ==========================================
    # ЗАГРУЗКА ДАННЫХ
    # ==========================================
    bond1 = bonds[bond1_idx]
    bond2 = bonds[bond2_idx]
    
    with st.spinner(f"Загрузка {'дневных' if data_mode == 'daily' else 'внутридневных'} данных с MOEX..."):
        
        if data_mode == "daily":
            # === ДНЕВНОЙ РЕЖИМ ===
            df1 = fetch_historical_data_cached(bond1.isin, period)
            df2 = fetch_historical_data_cached(bond2.isin, period)
            
            # Пробуем получить торговые данные
            trading1 = bond_trading_data.get(bond1.isin, {})
            trading2 = bond_trading_data.get(bond2.isin, {})
            
            is_trading = trading1.get('has_data') and trading1.get('yield') is not None
            
            if is_trading:
                current1 = trading1
                current2 = trading2
                status_text = "🟢 Торговая сессия"
                status_color = "#2ECC71"
                source_text = "Торговые данные (YIELDCLOSE)"
            else:
                is_trading = False
                status_text = "🔴 Торги не проводятся"
                status_color = "#E74C3C"
                source_text = "Исторические данные (YIELDCLOSE)"
                
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
            
            is_intraday = False
            
        else:
            # === ВНУТРИДНЕВНОЙ РЕЖИМ ===
            df1 = fetch_candle_data_cached(bond1.isin, bond_config_to_dict(bond1), candle_interval, period)
            df2 = fetch_candle_data_cached(bond2.isin, bond_config_to_dict(bond2), candle_interval, period)
            
            status_text = "⏱️ Внутридневные данные"
            status_color = "#E74C3C"
            source_text = f"Свечи {candle_interval} мин + расчёт YTM из цены"
            
            is_trading = not df1.empty and not df2.empty
            is_intraday = True
            
            # Текущие данные из свечей
            current1 = None
            current2 = None
            
            if not df1.empty and 'ytm_close' in df1.columns:
                last_row1 = df1.iloc[-1]
                ytm_val1 = last_row1['ytm_close']
                if pd.notna(ytm_val1):
                    current1 = {
                        'isin': bond1.isin,
                        'yield': ytm_val1,
                        'duration_years': None,
                        'price': last_row1['close'],
                        'date': df1.index[-1]
                    }
            
            if not df2.empty and 'ytm_close' in df2.columns:
                last_row2 = df2.iloc[-1]
                ytm_val2 = last_row2['ytm_close']
                if pd.notna(ytm_val2):
                    current2 = {
                        'isin': bond2.isin,
                        'yield': ytm_val2,
                        'duration_years': None,
                        'price': last_row2['close'],
                        'date': df2.index[-1]
                    }
    
    # ==========================================
    # ИНДИКАТОР СТАТУСА
    # ==========================================
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
    
    # ==========================================
    # КАРТОЧКИ ОБЛИГАЦИЙ
    # ==========================================
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
                if price_val:
                    st.metric("Цена", f"{price_val:.2f}%")
                else:
                    st.metric("Цена", "Н/Д")
            with metric_col3:
                st.metric("До погашения", f"{years1}г.")
            
            if current1.get('date'):
                if isinstance(current1['date'], pd.Timestamp):
                    date_str = current1['date'].strftime('%d.%m.%Y %H:%M') if is_intraday else current1['date'].strftime('%d.%m.%Y')
                else:
                    date_str = current1['date'].strftime('%d.%m.%Y %H:%M') if is_intraday else current1['date'].strftime('%d.%m.%Y')
                st.caption(f"ISIN: {bond1.isin} | Данные от: {date_str}")
            else:
                dur = current1.get('duration_years')
                st.caption(f"ISIN: {bond1.isin}" + (f" | Дюрация: {dur:.1f}г." if dur else ""))
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
                if price_val:
                    st.metric("Цена", f"{price_val:.2f}%")
                else:
                    st.metric("Цена", "Н/Д")
            with metric_col3:
                st.metric("До погашения", f"{years2}г.")
            
            if current2.get('date'):
                if isinstance(current2['date'], pd.Timestamp):
                    date_str = current2['date'].strftime('%d.%m.%Y %H:%M') if is_intraday else current2['date'].strftime('%d.%m.%Y')
                else:
                    date_str = current2['date'].strftime('%d.%m.%Y %H:%M') if is_intraday else current2['date'].strftime('%d.%m.%Y')
                st.caption(f"ISIN: {bond2.isin} | Данные от: {date_str}")
            else:
                dur = current2.get('duration_years')
                st.caption(f"ISIN: {bond2.isin}" + (f" | Дюрация: {dur:.1f}г." if dur else ""))
        else:
            st.subheader(f"📈 {bond2.name}")
            st.error("Данные недоступны")
    
    st.divider()
    
    # ==========================================
    # ПРОВЕРКА ДАННЫХ
    # ==========================================
    if df1.empty or df2.empty:
        st.error("Не удалось загрузить данные для одной или обеих облигаций")
        st.stop()
    
    # ==========================================
    # ОБЪЕДИНЕНИЕ И РАСЧЁТ СПРЕДА
    # ==========================================
    if is_intraday:
        # Для внутридневных данных
        ytm_col = 'ytm_close'
        
        merged_df = pd.merge(
            df1[[ytm_col]].rename(columns={ytm_col: 'ytm_1'}),
            df2[[ytm_col]].rename(columns={ytm_col: 'ytm_2'}),
            left_index=True,
            right_index=True,
            how='inner'
        )
        merged_df = merged_df.reset_index()
        merged_df = merged_df.rename(columns={'datetime': 'datetime'})
        merged_df['date'] = merged_df['datetime']
    else:
        # Для дневных данных
        merged_df = pd.merge(
            df1.reset_index()[['date', 'ytm']],
            df2.reset_index()[['date', 'ytm']],
            on='date',
            suffixes=('_1', '_2')
        )
    
    merged_df['spread'] = (merged_df['ytm_1'] - merged_df['ytm_2']) * 100  # в базисных пунктах
    
    # ==========================================
    # СТАТИСТИКА И СИГНАЛ
    # ==========================================
    stats = calculate_spread_stats(merged_df['spread'])
    
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
    
    # ==========================================
    # ГРАФИКИ
    # ==========================================
    fig_ytm = create_ytm_chart(df1, df2, bond1.name, bond2.name, is_intraday)
    fig_spread = create_spread_chart(merged_df, stats, is_intraday)
    
    st.plotly_chart(fig_ytm, use_container_width=True)
    st.plotly_chart(fig_spread, use_container_width=True)
    
    # ==========================================
    # СТАТИСТИКА СПРЕДА
    # ==========================================
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
    
    # ==========================================
    # ИСТОРИЯ ДАННЫХ
    # ==========================================
    with st.expander("📋 История данных (последние 10 записей)"):
        display_df = merged_df.tail(10).copy()
        
        if is_intraday and 'datetime' in display_df.columns:
            display_df['datetime'] = display_df['datetime'].dt.strftime('%d.%m.%Y %H:%M')
            display_cols = ['datetime', 'ytm_1', 'ytm_2', 'spread']
        else:
            display_df['date'] = display_df['date'].dt.strftime('%d.%m.%Y')
            display_cols = ['date', 'ytm_1', 'ytm_2', 'spread']
        
        st.dataframe(
            display_df[display_cols].style.format({
                'ytm_1': '{:.3f}',
                'ytm_2': '{:.3f}',
                'spread': '{:.2f}'
            }),
            use_container_width=True
        )
    
    # Обновление времени
    st.session_state.last_update = datetime.now()
    
    # Автообновление
    if st.session_state.auto_refresh:
        import time
        time.sleep(st.session_state.refresh_interval)
        st.rerun()


if __name__ == "__main__":
    main()
