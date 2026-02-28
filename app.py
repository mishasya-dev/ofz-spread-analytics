"""
OFZ Analytics - Аналитика спредов ОФЗ
Главный файл приложения Streamlit
Версия 0.3.0 - Unified Charts
"""
import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, date, timedelta
from typing import Dict, List, Any, Optional, Tuple
import logging
import sys
import os

# Добавляем путь к модулям
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import AppConfig, BondConfig
from api.moex_history import HistoryFetcher
from api.moex_candles import CandleFetcher, CandleInterval
from core.database import get_db
from components.charts import (
    create_daily_ytm_chart,
    create_daily_spread_chart,
    create_combined_ytm_chart,
    create_intraday_spread_chart,
    apply_zoom_range
)

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
</style>
""", unsafe_allow_html=True)


def get_years_to_maturity(maturity_str: str) -> float:
    """Вычисляет годы до погашения"""
    try:
        maturity = datetime.strptime(maturity_str, '%Y-%m-%d')
        return round((maturity - datetime.now()).days / 365.25, 1)
    except:
        return 0


def format_bond_label(bond, ytm: float = None, duration_years: float = None) -> str:
    """Форматирует метку облигации с YTM, дюрацией и годами до погашения"""
    years = get_years_to_maturity(bond.maturity_date)
    display_name = bond.name or getattr(bond, 'short_name', None) or bond.isin
    parts = [f"{display_name}"]
    
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
    
    # Миграция при первом запуске
    if 'bonds_loaded' not in st.session_state:
        db = get_db()
        config = st.session_state.config
        migrated = db.migrate_config_bonds(config.bonds)
        if migrated > 0:
            logger.info(f"Мигрировано {migrated} облигаций из config.py в БД")
        st.session_state.bonds_loaded = True
    
    # Загрузка/обновление облигаций из БД
    db = get_db()
    favorites = db.get_favorite_bonds_as_config()
    
    if favorites:
        current_keys = set(st.session_state.get('bonds', {}).keys())
        new_keys = set(favorites.keys())
        if current_keys != new_keys:
            st.session_state.bonds = favorites
            logger.info(f"Обновлён список облигаций: {len(favorites)} избранное")
    else:
        if 'bonds' not in st.session_state:
            config = st.session_state.config
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
    
    if 'selected_bond1' not in st.session_state:
        st.session_state.selected_bond1 = 0
    
    if 'selected_bond2' not in st.session_state:
        st.session_state.selected_bond2 = 1
    
    # Единый период (30 дней - 2 года, по умолчанию 1 год)
    if 'period' not in st.session_state:
        st.session_state.period = 365
    
    # Интервал свечей для графиков 3+4
    if 'candle_interval' not in st.session_state:
        st.session_state.candle_interval = "60"
    
    # Zoom ranges для связанных графиков
    if 'daily_zoom_range' not in st.session_state:
        st.session_state.daily_zoom_range = None
    
    if 'intraday_zoom_range' not in st.session_state:
        st.session_state.intraday_zoom_range = None
    
    if 'auto_refresh' not in st.session_state:
        st.session_state.auto_refresh = False
    
    if 'refresh_interval' not in st.session_state:
        st.session_state.refresh_interval = 60
    
    if 'last_update' not in st.session_state:
        st.session_state.last_update = None
    
    if 'updating_db' not in st.session_state:
        st.session_state.updating_db = False


def get_bonds_list() -> List:
    """Получить список облигаций для отображения"""
    bonds_dict = st.session_state.get('bonds', {})
    
    class BondItem:
        def __init__(self, data):
            self.isin = data.get('isin')
            self.name = data.get('name') or data.get('short_name') or data.get('isin', '')
            self.short_name = data.get('short_name', '')
            self.maturity_date = data.get('maturity_date', '')
            self.coupon_rate = data.get('coupon_rate')
            self.face_value = data.get('face_value', 1000)
            self.coupon_frequency = data.get('coupon_frequency', 2)
            self.issue_date = data.get('issue_date', '')
            self.day_count_convention = data.get('day_count_convention', 'ACT/ACT')
    
    return [BondItem(bond_data) for bond_data in bonds_dict.values()]


@st.cache_resource
def get_history_fetcher():
    """Получить экземпляр HistoryFetcher (кэшируется)"""
    return HistoryFetcher()


@st.cache_resource
def get_candle_fetcher():
    """Получить экземпляр CandleFetcher (кэшируется)"""
    return CandleFetcher()


@st.cache_data(ttl=300)
def fetch_trading_data_cached(secid: str) -> Dict:
    """Получить торговые данные с кэшированием"""
    fetcher = get_history_fetcher()
    return fetcher.get_trading_data(secid)


@st.cache_data(ttl=300)
def fetch_historical_data_cached(secid: str, days: int) -> pd.DataFrame:
    """Получить исторические данные с кэшированием"""
    fetcher = get_history_fetcher()
    db = get_db()
    start_date = date.today() - timedelta(days=days)
    
    # Проверяем наличие данных в БД
    db_df = db.load_daily_ytm(secid, start_date=start_date)
    last_db_date = db.get_last_daily_ytm_date(secid)
    
    if not db_df.empty and last_db_date:
        days_since_update = (date.today() - last_db_date).days
        
        if days_since_update <= 1:
            logger.info(f"Загружены дневные YTM из БД для {secid}: {len(db_df)} записей")
            return db_df
        else:
            new_start = last_db_date + timedelta(days=1)
            new_df = fetcher.fetch_ytm_history(secid, start_date=new_start)
            
            if not new_df.empty:
                db.save_daily_ytm(secid, new_df)
                db_df = pd.concat([db_df, new_df])
                db_df = db_df[~db_df.index.duplicated(keep='last')]
    else:
        db_df = fetcher.fetch_ytm_history(secid, start_date=start_date)
        
        if not db_df.empty:
            db.save_daily_ytm(secid, db_df)
            logger.info(f"Сохранены дневные YTM в БД для {secid}: {len(db_df)} записей")
    
    return db_df


@st.cache_data(ttl=60)
def fetch_candle_data_cached(isin: str, bond_config_dict: Dict, interval: str, days: int) -> pd.DataFrame:
    """Получить данные свечей с YTM с кэшированием"""
    fetcher = get_candle_fetcher()
    db = get_db()
    
    bond_config = BondConfig(**bond_config_dict)
    
    interval_map = {
        "1": CandleInterval.MIN_1,
        "10": CandleInterval.MIN_10,
        "60": CandleInterval.MIN_60,
    }
    
    candle_interval = interval_map.get(interval, CandleInterval.MIN_60)
    start_date = date.today() - timedelta(days=days)
    
    # Загружаем из БД
    db_ytm_df = db.load_intraday_ytm(isin, interval, start_date=start_date, end_date=date.today() - timedelta(days=1))
    
    # Запрашиваем текущий день
    today_df = fetcher.fetch_candles(
        isin,
        bond_config=bond_config,
        interval=candle_interval,
        start_date=date.today(),
        end_date=date.today()
    )
    
    # Если в БД нет данных, загружаем историю
    if db_ytm_df.empty and days > 1:
        history_df = fetcher.fetch_candles(
            isin,
            bond_config=bond_config,
            interval=candle_interval,
            start_date=start_date,
            end_date=date.today() - timedelta(days=1)
        )
        
        if not history_df.empty and 'ytm_close' in history_df.columns:
            db.save_intraday_ytm(isin, interval, history_df)
            logger.info(f"Сохранены intraday YTM в БД для {isin}: {len(history_df)} записей")
        
        db_ytm_df = history_df
    
    # Сохраняем текущие данные
    if not today_df.empty and 'ytm_close' in today_df.columns:
        db.save_intraday_ytm(isin, interval, today_df)
    
    # Объединяем
    if not db_ytm_df.empty and not today_df.empty:
        result_df = pd.concat([db_ytm_df, today_df])
        result_df = result_df[~result_df.index.duplicated(keep='last')]
    elif not today_df.empty:
        result_df = today_df
    elif not db_ytm_df.empty:
        result_df = db_ytm_df
    else:
        result_df = pd.DataFrame()
    
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
        'current': spread_series.iloc[-1] if len(spread_series) > 0 else 0
    }


def generate_signal(current_spread: float, p10: float, p25: float, p75: float, p90: float) -> Dict:
    """Генерирует торговый сигнал"""
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


def bond_config_to_dict(bond) -> Dict:
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


def prepare_spread_dataframe(df1: pd.DataFrame, df2: pd.DataFrame, is_intraday: bool = False) -> pd.DataFrame:
    """Подготовить DataFrame со спредом"""
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


def update_database_full(bonds_list: List = None, progress_callback=None) -> Dict:
    """Полное обновление базы данных"""
    fetcher = get_history_fetcher()
    candle_fetcher = get_candle_fetcher()
    db = get_db()
    
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
    
    total_steps = len(bonds) * 4
    current_step = 0
    
    # Дневные YTM
    for bond in bonds:
        try:
            if progress_callback:
                progress_callback(current_step / total_steps, f"Загрузка дневных YTM: {bond.name}")
            
            df = fetcher.fetch_ytm_history(bond.isin, start_date=date.today() - timedelta(days=730))
            if not df.empty:
                saved = db.save_daily_ytm(bond.isin, df)
                stats['daily_ytm_saved'] += saved
        except Exception as e:
            stats['errors'].append(f"Daily YTM {bond.name}: {str(e)}")
        
        current_step += 1
    
    # Intraday YTM
    intervals = [
        ("60", CandleInterval.MIN_60, 30),
        ("10", CandleInterval.MIN_10, 7),
        ("1", CandleInterval.MIN_1, 3),
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
    
    bonds = get_bonds_list()
    
    # ==========================================
    # БОКОВАЯ ПАНЕЛЬ
    # ==========================================
    with st.sidebar:
        st.header("⚙️ Настройки")
        
        # Кнопка управления облигациями
        from components.bond_manager import render_bond_manager_button
        render_bond_manager_button()
        
        st.divider()
        
        # Проверяем есть ли облигации
        if not bonds:
            st.warning("Нет избранных облигаций. Нажмите 'Управление облигациями' для выбора.")
            st.stop()
        
        # Получаем данные для dropdown
        bond_labels = []
        bond_trading_data = {}
        
        for b in bonds:
            data = fetch_trading_data_cached(b.isin)
            bond_trading_data[b.isin] = data
            if data.get('has_data') and data.get('yield'):
                bond_labels.append(format_bond_label(b, data['yield'], data.get('duration_years')))
            else:
                bond_labels.append(format_bond_label(b))
        
        # Выбор облигаций
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
        
        st.divider()
        
        # Единый период (1 месяц - 2 года)
        st.subheader("📅 Период")
        period = st.slider(
            "Период анализа",
            min_value=30,
            max_value=730,
            value=st.session_state.period,
            step=30,
            format_func=lambda x: f"{x // 30} мес." if x < 365 else f"{x // 365} год(а)"
        )
        st.session_state.period = period
        
        st.divider()
        
        # Интервал свечей (для графиков 3+4)
        st.subheader("⏱️ Интервал свечей")
        candle_interval = st.select_slider(
            "Интервал для графиков 3+4",
            options=["1", "10", "60"],
            format_func=lambda x: {"1": "1 минута", "10": "10 минут", "60": "1 час"}[x],
            value=st.session_state.candle_interval
        )
        st.session_state.candle_interval = candle_interval
        
        # Информация о периоде для свечей
        max_candle_days = {"1": 3, "10": 30, "60": 365}
        st.caption(f"Макс. период для {candle_interval} мин: {max_candle_days[candle_interval]} дней")
        
        st.divider()
        
        # Автообновление
        st.subheader("🔄 Автообновление")
        auto_refresh = st.toggle(
            "Включить",
            value=st.session_state.auto_refresh
        )
        st.session_state.auto_refresh = auto_refresh
        
        if auto_refresh:
            refresh_interval = st.slider(
                "Интервал (сек)",
                min_value=30,
                max_value=300,
                value=st.session_state.refresh_interval,
                step=30
            )
            st.session_state.refresh_interval = refresh_interval
            
            if st.session_state.last_update:
                st.caption(f"Последнее: {st.session_state.last_update.strftime('%H:%M:%S')}")
        
        st.divider()
        
        # Управление БД
        st.subheader("🗄️ База данных")
        
        db = get_db()
        db_stats = db.get_stats()
        
        with st.expander("📊 Статистика БД", expanded=False):
            st.write(f"**Облигаций:** {db_stats['bonds_count']}")
            st.write(f"**Дневных YTM:** {db_stats['daily_ytm_count']}")
            st.write(f"**Intraday YTM:** {db_stats['intraday_ytm_count']}")
        
        if st.button("🔄 Обновить БД", use_container_width=True):
            st.session_state.updating_db = True
        
        if st.session_state.get('updating_db', False):
            st.info("Обновление БД...")
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            def update_progress(progress, message):
                progress_bar.progress(progress)
                status_text.text(message)
            
            try:
                result = update_database_full(progress_callback=update_progress)
                progress_bar.progress(1.0)
                status_text.text("Готово!")
                st.success(f"✅ Дневных: {result['daily_ytm_saved']}, Intraday: {result['intraday_ytm_saved']}")
                st.session_state.updating_db = False
                st.cache_data.clear()
            except Exception as e:
                st.error(f"Ошибка: {e}")
                st.session_state.updating_db = False
        
        st.divider()
        
        if st.button("🗑️ Очистить кэш", use_container_width=True):
            st.cache_data.clear()
            st.rerun()
    
    # ==========================================
    # ЗАГОЛОВОК
    # ==========================================
    st.markdown("""
    <div style="display: flex; align-items: center; margin-bottom: 10px;">
        <h1 style="margin: 0;">📊 OFZ Spread Analytics</h1>
    </div>
    <p style="margin: 0; color: #666;">Анализ спредов облигаций ОФЗ v0.3.0</p>
    """, unsafe_allow_html=True)
    
    # ==========================================
    # ЗАГРУЗКА ДАННЫХ
    # ==========================================
    bond1 = bonds[bond1_idx]
    bond2 = bonds[bond2_idx]
    
    with st.spinner("Загрузка данных с MOEX..."):
        # Дневные данные (для графиков 1+2 и статистики)
        daily_df1 = fetch_historical_data_cached(bond1.isin, period)
        daily_df2 = fetch_historical_data_cached(bond2.isin, period)
        
        # Intraday данные (для графиков 3+4)
        candle_days = min(period, {"1": 3, "10": 30, "60": 365}[candle_interval])
        intraday_df1 = fetch_candle_data_cached(bond1.isin, bond_config_to_dict(bond1), candle_interval, candle_days)
        intraday_df2 = fetch_candle_data_cached(bond2.isin, bond_config_to_dict(bond2), candle_interval, candle_days)
    
    # ==========================================
    # РАСЧЁТ СПРЕДОВ И СТАТИСТИКИ
    # ==========================================
    # Спред по дневным данным (корректная статистика)
    daily_spread_df = prepare_spread_dataframe(daily_df1, daily_df2, is_intraday=False)
    daily_stats = calculate_spread_stats(daily_spread_df['spread']) if not daily_spread_df.empty else {}
    
    # Спред по intraday данным
    intraday_spread_df = prepare_spread_dataframe(intraday_df1, intraday_df2, is_intraday=True)
    
    # ==========================================
    # МЕТРИКИ
    # ==========================================
    trading1 = bond_trading_data.get(bond1.isin, {})
    trading2 = bond_trading_data.get(bond2.isin, {})
    
    is_trading = trading1.get('has_data') and trading1.get('yield') is not None
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        ytm1 = trading1.get('yield') if is_trading else (daily_df1['ytm'].iloc[-1] if not daily_df1.empty else None)
        st.metric("YTM Облигация 1", f"{ytm1:.2f}%" if ytm1 else "—")
    
    with col2:
        ytm2 = trading2.get('yield') if is_trading else (daily_df2['ytm'].iloc[-1] if not daily_df2.empty else None)
        st.metric("YTM Облигация 2", f"{ytm2:.2f}%" if ytm2 else "—")
    
    with col3:
        current_spread = daily_stats.get('current', 0)
        st.metric("Спред (дневной)", f"{current_spread:.1f} б.п.")
    
    with col4:
        if daily_stats:
            signal = generate_signal(
                current_spread,
                daily_stats['p10'],
                daily_stats['p25'],
                daily_stats['p75'],
                daily_stats['p90']
            )
            st.metric(f"Сигнал: {signal['signal']}", signal['strength'])
        else:
            st.metric("Сигнал", "Нет данных")
    
    # Статус биржи
    if is_trading:
        st.success("🟢 Торговая сессия открыта")
    else:
        st.info("🔴 Торги не проводятся")
    
    # ==========================================
    # ГРАФИКИ
    # ==========================================
    st.divider()
    
    # График 1: YTM дневные
    fig1 = create_daily_ytm_chart(
        daily_df1, daily_df2,
        bond1.name, bond2.name,
        x_range=st.session_state.daily_zoom_range
    )
    
    # Отлавливаем zoom на графике 1
    daily_ytm_chart = st.plotly_chart(fig1, on_select="rerun", use_container_width=True)
    
    # Обрабатываем zoom
    if daily_ytm_chart and daily_ytm_chart.selection:
        x_range = daily_ytm_chart.selection.get('x_range')
        if x_range:
            st.session_state.daily_zoom_range = tuple(x_range)
    
    # График 2: Спред дневной (синхронизирован с 1)
    fig2 = create_daily_spread_chart(
        daily_spread_df,
        stats=daily_stats,
        x_range=st.session_state.daily_zoom_range
    )
    st.plotly_chart(fig2, use_container_width=True)
    
    # Кнопка сброса zoom
    if st.session_state.daily_zoom_range:
        if st.button("🔄 Сбросить масштаб графиков 1-2"):
            st.session_state.daily_zoom_range = None
            st.rerun()
    
    st.divider()
    
    # График 3: YTM склеенный (история + свечи)
    fig3 = create_combined_ytm_chart(
        daily_df1, daily_df2,
        intraday_df1, intraday_df2,
        bond1.name, bond2.name,
        x_range=st.session_state.intraday_zoom_range
    )
    
    intraday_ytm_chart = st.plotly_chart(fig3, on_select="rerun", use_container_width=True)
    
    # Обрабатываем zoom
    if intraday_ytm_chart and intraday_ytm_chart.selection:
        x_range = intraday_ytm_chart.selection.get('x_range')
        if x_range:
            st.session_state.intraday_zoom_range = tuple(x_range)
    
    # График 4: Спред intraday (с перцентилями от дневных данных)
    fig4 = create_intraday_spread_chart(
        intraday_spread_df,
        daily_stats=daily_stats,  # Перцентили от дневных!
        x_range=st.session_state.intraday_zoom_range
    )
    st.plotly_chart(fig4, use_container_width=True)
    
    # Кнопка сброса zoom
    if st.session_state.intraday_zoom_range:
        if st.button("🔄 Сбросить масштаб графиков 3-4"):
            st.session_state.intraday_zoom_range = None
            st.rerun()
    
    # ==========================================
    # АВТООБНОВЛЕНИЕ
    # ==========================================
    if st.session_state.auto_refresh:
        time.sleep(st.session_state.refresh_interval)
        st.session_state.last_update = datetime.now()
        st.rerun()


if __name__ == "__main__":
    main()
