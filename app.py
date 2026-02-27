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
from core.database import (
    get_db, DatabaseManager,
    save_intraday_snapshot, load_intraday_history, 
    get_saved_data_info, cleanup_old_data
)
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
        color: #333;
    }
    .stMetric label {
        color: #555 !important;
    }
    .stMetric [data-testid="stMetricValue"] {
        color: #333 !important;
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
    
    # Миграция и загрузка облигаций из БД
    if 'bonds_loaded' not in st.session_state:
        db = get_db()
        # Миграция при первом запуске
        config = st.session_state.config
        migrated = db.migrate_config_bonds(config.bonds)
        if migrated > 0:
            logger.info(f"Мигрировано {migrated} облигаций из config.py в БД")
        
        # Загружаем избранные облигации из БД
        favorites = db.get_favorite_bonds_as_config()
        
        if favorites:
            st.session_state.bonds = favorites
        else:
            # Если нет избранного - используем config
            st.session_state.bonds = {
                isin: {
                    'isin': isin,
                    'name': bond.name,
                    'maturity_date': bond.maturity_date,
                    'coupon_rate': bond.coupon_rate,
                    'face_value': bond.face_value,
                    'coupon_frequency': bond.coupon_frequency,
                    'issue_date': bond.issue_date,
                    'day_count_convention': getattr(bond, 'day_count_convention', 'ACT/ACT'),
                }
                for isin, bond in config.bonds.items()
            }
        
        st.session_state.bonds_loaded = True
    
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
    
    if 'save_data' not in st.session_state:
        st.session_state.save_data = False
    
    if 'intraday_refresh_interval' not in st.session_state:
        st.session_state.intraday_refresh_interval = 30  # секунды для intraday
    
    if 'saved_count' not in st.session_state:
        st.session_state.saved_count = 0
    
    if 'updating_db' not in st.session_state:
        st.session_state.updating_db = False


def get_bonds_list() -> List:
    """Получить список облигаций для отображения"""
    bonds_dict = st.session_state.get('bonds', {})
    
    # Преобразуем в список объектов с атрибутами
    class BondItem:
        def __init__(self, data):
            self.isin = data.get('isin')
            self.name = data.get('name', '')
            self.maturity_date = data.get('maturity_date', '')
            self.coupon_rate = data.get('coupon_rate')
            self.face_value = data.get('face_value', 1000)
            self.coupon_frequency = data.get('coupon_frequency', 2)
            self.issue_date = data.get('issue_date', '')
            self.day_count_convention = data.get('day_count_convention', 'ACT/ACT')
    
    return [BondItem(bond_data) for bond_data in bonds_dict.values()]


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
    """
    Получить исторические данные с кэшированием
    
    Приоритет:
    1. Загрузить YTM из БД (если есть)
    2. Если нет - загрузить с MOEX и сохранить в БД
    """
    fetcher = get_history_fetcher()
    db = get_db()
    start_date = date.today() - timedelta(days=days)
    
    # Проверяем наличие данных в БД
    db_df = db.load_daily_ytm(secid, start_date=start_date)
    
    # Получаем последнюю дату в БД
    last_db_date = db.get_last_daily_ytm_date(secid)
    
    if not db_df.empty and last_db_date:
        # Есть данные в БД, проверяем актуальность
        days_since_update = (date.today() - last_db_date).days
        
        if days_since_update <= 1:
            # Данные актуальны - возвращаем из БД
            logger.info(f"Загружены дневные YTM из БД для {secid}: {len(db_df)} записей")
            return db_df
        else:
            # Нужно обновить - загружаем недостающие данные с MOEX
            new_start = last_db_date + timedelta(days=1)
            new_df = fetcher.fetch_ytm_history(secid, start_date=new_start)
            
            if not new_df.empty:
                # Сохраняем новые данные в БД
                db.save_daily_ytm(secid, new_df)
                # Объединяем
                db_df = pd.concat([db_df, new_df])
                db_df = db_df[~db_df.index.duplicated(keep='last')]
    else:
        # Данных в БД нет - загружаем все с MOEX
        db_df = fetcher.fetch_ytm_history(secid, start_date=start_date)
        
        if not db_df.empty:
            # Сохраняем в БД
            db.save_daily_ytm(secid, db_df)
            logger.info(f"Сохранены дневные YTM в БД для {secid}: {len(db_df)} записей")
    
    return db_df


@st.cache_data(ttl=60)
def fetch_candle_data_cached(isin: str, bond_config_dict: Dict, interval: str, days: int) -> pd.DataFrame:
    """
    Получить данные свечей с YTM с кэшированием в SQLite
    
    Алгоритм:
    1. Проверить рассчитанные YTM в БД (intraday_ytm)
    2. Загрузить исторические данные из БД
    3. Запросить с MOEX только за текущий день (и рассчитать YTM)
    4. Объединить и сохранить новые данные
    """
    fetcher = get_candle_fetcher()
    db = get_db()
    
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
    
    # 1. Загружаем рассчитанные YTM из БД
    db_ytm_df = db.load_intraday_ytm(isin, interval, start_date=start_date, end_date=date.today() - timedelta(days=1))
    
    # 2. Всегда запрашиваем данные за текущий день с MOEX (рассчитываем YTM)
    today_df = fetcher.fetch_candles(
        isin,
        bond_config=bond_config,
        interval=candle_interval,
        start_date=date.today(),
        end_date=date.today()
    )
    
    # 3. Если в БД нет данных, загружаем все исторические
    if db_ytm_df.empty and days > 1:
        history_df = fetcher.fetch_candles(
            isin,
            bond_config=bond_config,
            interval=candle_interval,
            start_date=start_date,
            end_date=date.today() - timedelta(days=1)
        )
        
        # Сохраняем рассчитанные YTM в БД
        if not history_df.empty and 'ytm_close' in history_df.columns:
            db.save_intraday_ytm(isin, interval, history_df)
            logger.info(f"Сохранены intraday YTM в БД для {isin}: {len(history_df)} записей")
        
        db_ytm_df = history_df
    elif not db_ytm_df.empty:
        # Проверяем есть ли пропуски в данных (как в начале, так и в конце)
        first_db_datetime = db_ytm_df.index[0] if not db_ytm_df.empty else None
        last_db_datetime = db_ytm_df.index[-1] if not db_ytm_df.empty else None
        needed_end = date.today() - timedelta(days=1)
        
        # 1. Проверяем пропуски в начале (запрашиваемый период больше имеющегося)
        if first_db_datetime is not None:
            first_db_date = first_db_datetime.date() if hasattr(first_db_datetime, 'date') else first_db_datetime
            if isinstance(first_db_date, datetime):
                first_db_date = first_db_date.date()
            
            if first_db_date > start_date:
                # Есть пропуски в начале - загружаем недостающие исторические данные
                logger.info(f"Загрузка недостающих исторических данных: {start_date} -> {first_db_date - timedelta(days=1)}")
                history_fill_df = fetcher.fetch_candles(
                    isin,
                    bond_config=bond_config,
                    interval=candle_interval,
                    start_date=start_date,
                    end_date=first_db_date - timedelta(days=1)
                )
                
                if not history_fill_df.empty and 'ytm_close' in history_fill_df.columns:
                    db.save_intraday_ytm(isin, interval, history_fill_df)
                    db_ytm_df = pd.concat([history_fill_df, db_ytm_df])
        
        # 2. Проверяем пропуски в конце (последние данные устарели)
        if last_db_datetime is not None:
            last_db_date = last_db_datetime.date() if hasattr(last_db_datetime, 'date') else last_db_datetime
            if isinstance(last_db_date, datetime):
                last_db_date = last_db_date.date()
            
            if (needed_end - last_db_date).days > 1:
                # Есть пропуски в конце - загружаем недостающие данные
                fill_start = last_db_date + timedelta(days=1) if isinstance(last_db_date, date) else start_date
                fill_df = fetcher.fetch_candles(
                    isin,
                    bond_config=bond_config,
                    interval=candle_interval,
                    start_date=fill_start,
                    end_date=needed_end
                )
                
                if not fill_df.empty and 'ytm_close' in fill_df.columns:
                    db.save_intraday_ytm(isin, interval, fill_df)
                    db_ytm_df = pd.concat([db_ytm_df, fill_df])
    
    # 4. Сохраняем текущие данные (если есть YTM)
    if not today_df.empty and 'ytm_close' in today_df.columns:
        db.save_intraday_ytm(isin, interval, today_df)
    
    # 5. Объединяем исторические + текущие данные
    if not db_ytm_df.empty and not today_df.empty:
        result_df = pd.concat([db_ytm_df, today_df])
        result_df = result_df[~result_df.index.duplicated(keep='last')]
    elif not today_df.empty:
        result_df = today_df
    elif not db_ytm_df.empty:
        result_df = db_ytm_df
    else:
        result_df = pd.DataFrame()
    
    # Сортируем по времени
    if not result_df.empty:
        result_df = result_df.sort_index()
    
    return result_df


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


def update_database_full(bonds_list: List = None, progress_callback=None) -> Dict:
    """
    Полное обновление базы данных
    
    Загружает:
    - Дневные YTM для всех облигаций (1 год)
    - Intraday YTM для всех облигаций и интервалов
    
    Спреды рассчитываются на лету из YTM при отображении графиков.
    
    Args:
        bonds_list: Список облигаций (если None - из session_state)
        progress_callback: Функция для отчёта о прогрессе
    
    Returns:
        Статистика обновления
    """
    from api.moex_candles import CandleInterval
    
    fetcher = get_history_fetcher()
    candle_fetcher = get_candle_fetcher()
    db = get_db()
    
    # Получаем облигации
    if bonds_list is None:
        bonds_list = get_bonds_list()
    
    if not bonds_list:
        return {'daily_ytm_saved': 0, 'intraday_ytm_saved': 0, 'errors': ['Нет облигаций']}
    
    bonds = bonds_list
    stats = {
        'daily_ytm_saved': 0,
        'intraday_ytm_saved': 0,
        'errors': []
    }
    
    # total_steps: дневные YTM + intraday (3 интервала для каждой)
    total_steps = len(bonds) * 4
    current_step = 0
    
    # 1. Дневные YTM для всех облигаций (1 год)
    for bond in bonds:
        try:
            if progress_callback:
                progress_callback(current_step / total_steps, f"Загрузка дневных YTM: {bond.name}")
            
            df = fetcher.fetch_ytm_history(bond.isin, start_date=date.today() - timedelta(days=365))
            if not df.empty:
                saved = db.save_daily_ytm(bond.isin, df)
                stats['daily_ytm_saved'] += saved
        except Exception as e:
            stats['errors'].append(f"Daily YTM {bond.name}: {str(e)}")
        
        current_step += 1
    
    # 2. Intraday YTM для всех облигаций и интервалов
    intervals = [
        ("60", CandleInterval.MIN_60, 30),  # часовые за 30 дней
        ("10", CandleInterval.MIN_10, 7),   # 10-минутные за 7 дней
        ("1", CandleInterval.MIN_1, 3),     # минутные за 3 дня
    ]
    
    for bond in bonds:
        for interval_str, interval_enum, days in intervals:
            try:
                if progress_callback:
                    progress_callback(current_step / total_steps, f"Загрузка {interval_str}мин свечей: {bond.name}")
                
                df = candle_fetcher.fetch_candles(
                    bond.isin,
                    bond_config=bond,
                    interval=interval_enum,
                    start_date=date.today() - timedelta(days=days),
                    end_date=date.today()
                )
                
                if not df.empty and 'ytm_close' in df.columns:
                    saved = db.save_intraday_ytm(bond.isin, interval_str, df)
                    stats['intraday_ytm_saved'] += saved
            except Exception as e:
                stats['errors'].append(f"Intraday YTM {bond.name} {interval_str}min: {str(e)}")
            
            current_step += 1
    
    if progress_callback:
        progress_callback(1.0, "Готово!")
    
    return stats


def main():
    """Главная функция"""
    init_session_state()
    
    # Получаем облигации из БД (через session_state)
    bonds = get_bonds_list()
    
    # ==========================================
    # БОКОВАЯ ПАНЕЛЬ
    # ==========================================
    with st.sidebar:
        st.header("⚙️ Настройки")
        
        # Кнопка управления облигациями (версия 0.2.0)
        from components.bond_manager import render_bond_manager_button
        render_bond_manager_button()
        
        st.divider()
        
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
        
        # Проверяем есть ли облигации
        if not bonds:
            st.warning("Нет избранных облигаций. Нажмите 'Управление облигациями' для выбора.")
            st.stop()
        
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
            # 10 минут: макс 30 дней
            # 1 час: макс 365 дней (год) - пагинация работает
            if candle_interval == "1":
                max_days = 3
                default_days = 1
            elif candle_interval == "10":
                max_days = 30
                default_days = 7
            else:  # 60 минут (1 час)
                max_days = 365
                default_days = 30
            
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
            # Разные интервалы для разных режимов
            if data_mode == "intraday":
                refresh_interval = st.slider(
                    "Интервал обновления (секунды)",
                    min_value=10,
                    max_value=120,
                    value=st.session_state.intraday_refresh_interval,
                    step=10,
                    help="Для intraday режима рекомендуется 10-30 секунд"
                )
                st.session_state.intraday_refresh_interval = refresh_interval
            else:
                refresh_interval = st.slider(
                    "Интервал обновления (секунды)",
                    min_value=60,
                    max_value=300,
                    value=st.session_state.refresh_interval,
                    step=30
                )
                st.session_state.refresh_interval = refresh_interval
            
            if st.session_state.last_update:
                st.caption(f"Последнее обновление: {st.session_state.last_update.strftime('%H:%M:%S')}")
        
        # Сохранение данных (только для intraday)
        if data_mode == "intraday":
            st.divider()
            st.subheader("💾 Сохранение данных")
            
            save_data = st.toggle(
                "Сохранять снимки данных",
                value=st.session_state.save_data,
                help="Сохраняет текущие YTM и спред каждые N секунд"
            )
            st.session_state.save_data = save_data
            
            if st.session_state.saved_count > 0:
                st.caption(f"Сохранено снимков: {st.session_state.saved_count}")
            
            # Информация о сохранённых данных
            with st.expander("📁 Сохранённые данные"):
                info = get_saved_data_info()
                st.write(f"Всего файлов: {info['total_files']}")
                if info['newest']:
                    st.write(f"Последние данные: {info['newest']}")
                
                if st.button("🗑️ Очистить старые данные", key="cleanup_data"):
                    cleanup_old_data(days_to_keep=7)
                    st.success("Старые данные удалены!")
        
        st.divider()
        
        # ==========================================
        # УПРАВЛЕНИЕ БАЗОЙ ДАННЫХ
        # ==========================================
        st.subheader("🗄️ База данных")
        
        db = get_db()
        db_stats = db.get_stats()
        
        # Показываем статистику БД
        with st.expander("📊 Статистика БД", expanded=False):
            st.write(f"**Облигаций:** {db_stats['bonds_count']}")
            st.write(f"**Дневных YTM:** {db_stats['daily_ytm_count']}")
            st.write(f"**Intraday YTM:** {db_stats['intraday_ytm_count']}")
            st.write(f"**Спредов:** {db_stats['spreads_count']}")
            st.write(f"**Свечей:** {db_stats['candles_count']}")
            
            if db_stats.get('last_daily_ytm'):
                st.write(f"**Последний дневной YTM:** {db_stats['last_daily_ytm']}")
            if db_stats.get('last_intraday_ytm'):
                st.write(f"**Последний intraday YTM:** {db_stats['last_intraday_ytm'][:16]}")
            
            # Intraday по интервалам
            if db_stats.get('intraday_by_interval'):
                interval_names = {"1": "1 мин", "10": "10 мин", "60": "1 час"}
                st.write("**Intraday по интервалам:**")
                for intv, cnt in db_stats['intraday_by_interval'].items():
                    st.write(f"  - {interval_names.get(intv, intv)}: {cnt}")
        
        # Кнопка обновления БД
        if st.button("🔄 Обновить БД", use_container_width=True, help="Загрузить все данные с MOEX и сохранить в БД"):
            st.session_state.updating_db = True
        
        if st.session_state.get('updating_db', False):
            st.info("Начинаем обновление базы данных...")
            
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            def update_progress(progress, message):
                progress_bar.progress(progress)
                status_text.text(message)
            
            try:
                result = update_database_full(progress_callback=update_progress)
                
                progress_bar.progress(1.0)
                status_text.text("Обновление завершено!")
                
                st.success(f"""
                ✅ База данных обновлена!
                
                - Дневных YTM: {result['daily_ytm_saved']}
                - Intraday YTM: {result['intraday_ytm_saved']}
                """)
                
                if result['errors']:
                    with st.expander("⚠️ Ошибки", expanded=False):
                        for err in result['errors'][:10]:  # Показываем первые 10
                            st.warning(err)
                
                st.session_state.updating_db = False
                st.cache_data.clear()
                
            except Exception as e:
                st.error(f"Ошибка обновления БД: {e}")
                st.session_state.updating_db = False
        
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
        interval_display = st.session_state.intraday_refresh_interval if data_mode == "intraday" else st.session_state.refresh_interval
        st.info(f"🔄 Автообновление включено (каждые {interval_display} сек.)")
    
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
    
    # ==========================================
    # СОХРАНЕНИЕ ДАННЫХ (intraday режим)
    # ==========================================
    if data_mode == "intraday" and st.session_state.save_data and current1 and current2:
        try:
            save_intraday_snapshot(
                bond1_data={
                    'isin': bond1.isin,
                    'name': bond1.name,
                    'ytm': current1.get('yield'),
                    'price': current1.get('price')
                },
                bond2_data={
                    'isin': bond2.isin,
                    'name': bond2.name,
                    'ytm': current2.get('yield'),
                    'price': current2.get('price')
                },
                spread_data={
                    'spread_bp': stats['current'],
                    'signal': signal['signal'],
                    'p25': stats['p25'],
                    'p75': stats['p75']
                },
                interval=candle_interval
            )
            st.session_state.saved_count += 1
        except Exception as e:
            logger.warning(f"Ошибка сохранения данных: {e}")
    
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
