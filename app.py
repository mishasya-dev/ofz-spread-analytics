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
import time

# Добавляем путь к модулям
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import AppConfig, BondConfig, CANDLE_INTERVAL_CONFIG
from api.moex_candles import CandleInterval
from api.moex_history import fetch_ytm_history, get_trading_data
from api.moex_candles import fetch_candles
from api.moex_zcyc import fetch_ns_params_history
from api.moex_client import MOEXClient
from core.db import get_db_facade, get_ytm_repo
from components.charts import (
    create_combined_ytm_chart,
    create_intraday_spread_chart,
    create_spread_analytics_chart,
    apply_zoom_range,
    create_g_spread_dashboard,
    create_g_spread_chart_single
)
# ZCYCFetcher удалён - используем функции из api.moex_zcyc
from services.g_spread_calculator import (
    calculate_g_spread_stats,
    generate_g_spread_signal
)
from services.spread_calculator import (
    calculate_spread_stats,
    generate_signal,
    prepare_spread_dataframe
)
from services.data_loader import update_database_full
from services.state_manager import sync_from_url, sync_to_url, load_last_pair, save_last_pair
from core.db import get_g_spread_repo, init_database
from version import format_version_badge
from core.cointegration import CointegrationAnalyzer, format_cointegration_report
from core.cointegration_service import get_cointegration_service

# Настройка логирования
import os
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs', 'app.log')
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_FILE, encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)


# Импортируем унифицированные функции логирования
from utils.action_logger import (
    log_call, 
    log_call_simple,
    log_widget_change, 
    log_button_press as log_button_press_action,
    log_action,
    LogBlock
)
from utils.bond_utils import (
    BondItem,
    get_years_to_maturity,
    format_bond_label,
    get_bonds_list as get_bonds_list_from_dict,
    bond_config_to_dict
)


def log_button_press(button_name: str, details: str = None):
    """Обёртка для совместимости с существующим кодом"""
    log_button_press_action(button_name, details)


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
    /* Version badge in sidebar */
    .version-badge-full {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 12px 16px;
        border-radius: 12px;
        margin-bottom: 12px;
        box-shadow: 0 3px 12px rgba(102, 126, 234, 0.35);
        text-align: center;
    }
    .version-badge-full .version-main {
        font-size: 1.3rem;
        font-weight: 700;
        margin-bottom: 8px;
        letter-spacing: 0.5px;
    }
    .version-badge-full .version-details {
        display: flex;
        justify-content: space-around;
        font-size: 0.75rem;
        opacity: 0.95;
        margin-bottom: 6px;
        gap: 8px;
    }
    .version-badge-full .version-details span {
        background: rgba(255,255,255,0.15);
        padding: 2px 8px;
        border-radius: 10px;
    }
    .version-badge-full .version-commit {
        font-size: 0.7rem;
        opacity: 0.7;
        font-family: monospace;
    }
</style>
""", unsafe_allow_html=True)


def init_session_state():
    """Инициализация состояния сессии"""
    # Инициализация БД (создание таблиц при необходимости)
    init_database()
    
    # Загрузка настроек из URL (делаем ДО установки defaults)
    sync_from_url()
    
    if 'config' not in st.session_state:
        st.session_state.config = AppConfig()
    
    # Загрузка облигаций из БД
    # При первом запуске OFZCache загрузит список с MOEX и пометит все как избранные
    db = get_db_facade()
    favorites = db.get_favorite_bonds_as_config()

    if not favorites:
        # Первый запуск - загружаем список ОФЗ с MOEX
        # OFZCache пометит все как избранные при первой загрузке
        from core.ofz_cache import OFZCache
        cache = OFZCache()
        cache.get_ofz_list()  # Загрузит и пометит все как избранные
        favorites = db.get_favorite_bonds_as_config()
        logger.info(f"Первый запуск: загружено {len(favorites)} облигаций как избранные")

    if favorites:
        current_keys = set(st.session_state.get('bonds', {}).keys())
        new_keys = set(favorites.keys())
        if current_keys != new_keys:
            st.session_state.bonds = favorites
            logger.info(f"Обновлён список облигаций: {len(favorites)} избранное")
    
    # Восстановление последней пары облигаций из localStorage
    if 'selected_bond1' not in st.session_state or 'selected_bond2' not in st.session_state:
        last_pair = load_last_pair()
        isins = list(st.session_state.get('bonds', {}).keys())
        
        if last_pair and isins:
            b1_isin = last_pair.get('b1')
            b2_isin = last_pair.get('b2')
            
            if b1_isin and b1_isin in isins:
                st.session_state.selected_bond1 = isins.index(b1_isin)
            else:
                st.session_state.selected_bond1 = 0
            
            if b2_isin and b2_isin in isins:
                st.session_state.selected_bond2 = isins.index(b2_isin)
            else:
                st.session_state.selected_bond2 = 1 if len(isins) > 1 else 0
        else:
            st.session_state.selected_bond1 = 0
            st.session_state.selected_bond2 = 1 if favorites and len(favorites) > 1 else 0
    
    # Единый период (30 дней - 2 года, по умолчанию 1 год)
    if 'period' not in st.session_state:
        st.session_state.period = 365
    
    # Интервал свечей для intraday графиков
    if 'candle_interval' not in st.session_state:
        st.session_state.candle_interval = "60"
    
    # Период свечей (динамический, зависит от интервала)
    if 'candle_days' not in st.session_state:
        st.session_state.candle_days = 30  # дефолт для 1 час
    

    
    if 'auto_refresh' not in st.session_state:
        st.session_state.auto_refresh = False
    
    if 'refresh_interval' not in st.session_state:
        st.session_state.refresh_interval = 60
    
    if 'last_update' not in st.session_state:
        st.session_state.last_update = None
    
    if 'updating_db' not in st.session_state:
        st.session_state.updating_db = False
    
    # Параметры для Spread Analytics
    if 'spread_window' not in st.session_state:
        st.session_state.spread_window = 30
    
    if 'z_threshold' not in st.session_state:
        st.session_state.z_threshold = 2.0

    # Параметры для G-Spread Analytics
    if 'g_spread_period' not in st.session_state:
        st.session_state.g_spread_period = 365
    
    if 'g_spread_window' not in st.session_state:
        st.session_state.g_spread_window = 30
    
    if 'g_spread_z_threshold' not in st.session_state:
        st.session_state.g_spread_z_threshold = 2.0

    # Результат валидации YTM
    if 'ytm_validation' not in st.session_state:
        st.session_state.ytm_validation = None


def get_bonds_list() -> List[BondItem]:
    """Получить список облигаций для отображения"""
    bonds_dict = st.session_state.get('bonds', {})
    return get_bonds_list_from_dict(bonds_dict)


# MOEXClient кэшируется как resource
@st.cache_resource
def get_moex_client():
    """Получить глобальный MOEXClient (кэшируется)"""
    return MOEXClient()


# Удаляем старые getter'ы - используем функции напрямую
# get_history_fetcher, get_candle_fetcher, get_zcyc_fetcher удалены


@st.cache_data(ttl=300)
def fetch_trading_data_cached(secid: str) -> Dict:
    """Получить торговые данные с кэшированием"""
    from services.data_loader import fetch_trading_data
    return fetch_trading_data(secid)


@st.cache_data(ttl=300)
def fetch_historical_data_cached(secid: str, days: int) -> pd.DataFrame:
    """
    Получить исторические данные за указанный период.
    
    Обёртка над data_loader.fetch_historical_data с Streamlit кэшированием.
    """
    from services.data_loader import fetch_historical_data as _fetch
    return _fetch(secid, days)


@st.cache_data(ttl=60)
def fetch_candle_data_cached(isin: str, bond_config_dict: Dict, interval: str, days: int) -> pd.DataFrame:
    """
    Получить данные свечей за указанный период.
    
    Обёртка над data_loader.fetch_candle_data с Streamlit кэшированием.
    bond_config_dict - словарь с параметрами облигации.
    """
    from services.data_loader import fetch_candle_data as _fetch
    return _fetch(isin, bond_config_dict, interval, days)


# ==========================================
# G-SPREAD: NELSON-SIEGEL PARAMS
# ==========================================

# get_zcyc_fetcher удалён - используем функции напрямую из api.moex_zcyc


@st.cache_data(ttl=3600)  # Кэш на 1 час
def fetch_ns_params_cached(days: int = 365, force_load: bool = False) -> pd.DataFrame:
    """
    Загрузить параметры Nelson-Siegel из БД (БЕЗ MOEX загрузки!)
    
    Для загрузки с MOEX используйте fetch_ns_params_from_moex()
    
    Args:
        days: Количество дней для фильтрации при загрузке из БД
        force_load: Игнорируется (для совместимости)
        
    Returns:
        DataFrame с колонками: b1, b2, b3, t1 (индекс = date)
    """
    g_spread_repo = get_g_spread_repo()
    
    # Загружаем из БД
    start_date = date.today() - timedelta(days=days)
    ns_df = g_spread_repo.load_ns_params(start_date=start_date)
    
    if not ns_df.empty:
        logger.info(f"NS params из БД: {len(ns_df)} записей")
    
    return ns_df


def fetch_ns_params_from_moex(progress_callback=None, days: int = 730) -> int:
    """
    Загрузить параметры Nelson-Siegel с MOEX в БД
    
    Загружает данные ПО ДНЯМ за указанный период (по умолчанию 2 года).
    Занимает ~1 минуту для 2 лет (~500 торговых дней).
    
    Args:
        progress_callback: Функция для отображения прогресса (current, total, date)
        days: Количество дней для загрузки (по умолчанию 730 = 2 года)
        
    Returns:
        Количество загруженных записей
    """
    g_spread_repo = get_g_spread_repo()
    
    # Проверяем последнюю дату в БД
    last_date = g_spread_repo.get_last_ns_params_date()
    
    if last_date:
        # Продолжаем с последней даты + 1
        start_date = last_date + timedelta(days=1)
        logger.info(f"Возобновление загрузки с {start_date} (последняя дата в БД: {last_date})")
    else:
        # Загружаем последние N дней
        start_date = None  # Будет использоваться days параметр
        logger.info(f"Начало загрузки за последние {days} дней")
    
    # Загружаем с MOEX по дням через новый API
    with MOEXClient() as client:
        ns_df = fetch_ns_params_history(
            start_date=start_date,
            save_callback=g_spread_repo.save_ns_params,
            progress_callback=progress_callback,
            days=days,
            client=client
        )
    
    return g_spread_repo.count_ns_params()


@st.cache_data(show_spinner=False)  # Без TTL - исторические данные не меняются
def _fetch_zcyc_cached(isin: str, start_date_str: str, end_date_str: str) -> pd.DataFrame:
    """
    Кэшированная загрузка ZCYC данных
    
    Исторические данные не меняются, поэтому TTL не нужен.
    
    Логика:
    1. Проверка БД → возврат имеющихся записей
    2. Дозагрузка только недостающих дней с MOEX
    3. Сохранение новых данных в БД
    4. Кэширование результата в Streamlit
    
    При смене слайдера (те же даты) - возврат из кэша Streamlit мгновенно.
    
    Args:
        isin: ISIN облигации
        start_date_str: Начальная дата (строка для хэширования)
        end_date_str: Конечная дата (строка для хэширования)
        
    Returns:
        DataFrame с ZCYC данными
    """
    from api.moex_zcyc import get_zcyc_history_parallel
    from datetime import datetime as dt
    
    start_date = dt.strptime(start_date_str, '%Y-%m-%d').date()
    end_date = dt.strptime(end_date_str, '%Y-%m-%d').date()
    
    repo = get_g_spread_repo()
    
    # Загружаем данные с MOEX (с кэшированием в БД)
    zcyc_df = get_zcyc_history_parallel(
        start_date, end_date,
        isin=isin,
        save_callback=repo.save_zcyc,
        max_workers=5
    )
    
    return zcyc_df


@log_call()
def calculate_bond_g_spread(
    isin: str,
    daily_df: pd.DataFrame,
    ns_params_df: pd.DataFrame,
    window: int = 30,
    maturity_date: date = None,
    use_duration: bool = False,
    zcyc_period: int = None
) -> Tuple[pd.DataFrame, float]:
    """
    Рассчитать G-spread для облигации с Z-Score и ADF тестом
    
    ИСПОЛЬЗУЕТ ТОЧНЫЕ ДАННЫЕ MOEX:
    - trdyield: рыночная YTM облигации
    - clcyield: теоретическая КБД от MOEX
    - G-spread = trdyield - clcyield (уже рассчитан MOEX!)
    
    КЭШИРОВАНИЕ:
    - zcyc_history_raw: исходные данные MOEX для ВСЕХ облигаций
    - Проверяем zcyc_history_raw, дозагружаем недостающие даты
    - g_spreads таблица НЕ используется (устарела)
    
    ПЕРИОД ZCYC:
    - Определяется параметром zcyc_period (по умолчанию 365 дней)
    - НЕ зависит от daily_df! ZCYC загружается за полный период
    - daily_df используется только для ограничения графика (опционально)
    
    Args:
        isin: ISIN облигации
        daily_df: DataFrame с YTM облигации (для ограничения графика, НЕ периода ZCYC)
        ns_params_df: DataFrame с параметрами NS (НЕ ИСПОЛЬЗУЕТСЯ)
        window: Окно для rolling Z-Score
        maturity_date: Дата погашения (НЕ ИСПОЛЬЗУЕТСЯ)
        use_duration: НЕ ИСПОЛЬЗУЕТСЯ (MOEX использует дюрацию)
        zcyc_period: Период ZCYC в днях (по умолчанию 365)
        
    Returns:
        (DataFrame с G-spread, p_value ADF теста)
    """
    from statsmodels.tsa.stattools import adfuller
    
    # Период ZCYC — НЕ зависит от daily_df!
    # ZCYC всегда загружаем за указанный период
    zcyc_days = zcyc_period or st.session_state.get('g_spread_period', 365)
    end_date = date.today()
    start_date = end_date - timedelta(days=zcyc_days)
    
    logger.info(f"ZCYC период для {isin}: {start_date} - {end_date} ({zcyc_days} дней)")
    
    # Кэшированная загрузка ZCYC из БД (zcyc_history_raw) или MOEX
    # _fetch_zcyc_cached сам проверит данные и дозагрузит недостающие даты
    zcyc_df = _fetch_zcyc_cached(
        isin,
        start_date.strftime('%Y-%m-%d'),
        end_date.strftime('%Y-%m-%d')
    )
    
    if zcyc_df.empty:
        logger.warning(f"Нет ZCYC данных для {isin}")
        return pd.DataFrame(), 1.0
    
    logger.info(f"Загружено {len(zcyc_df)} записей ZCYC для {isin}")
    
    # G-spread уже рассчитан MOEX!
    # Нужно только добавить Z-score
    
    df = zcyc_df.copy()
    df = df.sort_values('date').reset_index(drop=True)
    
    # Rolling Z-Score (сохраняем также mean и std для графиков)
    roll = df['g_spread_bp'].rolling(window=window)
    df['rolling_mean'] = roll.mean()
    df['rolling_std'] = roll.std()
    df['z_score'] = (df['g_spread_bp'] - df['rolling_mean']) / df['rolling_std']
    
    # ADF тест
    p_value = 1.0
    try:
        g_spread_clean = df['g_spread_bp'].dropna()
        if len(g_spread_clean) >= 20:
            adf_result = adfuller(g_spread_clean)
            p_value = adf_result[1]
    except Exception as e:
        logger.warning(f"ADF тест не удался: {e}")
    
    # Формируем результат
    result_df = df.copy()
    result_df = result_df.set_index('date')
    
    # Добавляем колонки для совместимости с UI
    result_df = result_df.rename(columns={
        'trdyield': 'ytm_bond',
        'clcyield': 'ytm_kbd',
        'duration_days': 'duration_days'
    })
    
    # Добавляем duration_years
    result_df['duration_years'] = result_df['duration_days'] / 365.25
    
    # НЕ сохраняем в g_spreads - это дублирование zcyc_history_raw
    # zcyc_history_raw уже содержит все данные от MOEX
    
    return result_df, p_value


def main():
    """Главная функция"""
    init_session_state()
    
    bonds = get_bonds_list()
    
    # ==========================================
    # БОКОВАЯ ПАНЕЛЬ
    # ==========================================
    with st.sidebar:
        # Значок версии над настройками
        st.markdown(format_version_badge(), unsafe_allow_html=True)
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
        
        # Проверка и корректировка индексов (гарантируем валидный диапазон)
        max_idx = len(bonds) - 1
        st.session_state.selected_bond1 = max(0, min(st.session_state.selected_bond1, max_idx))
        st.session_state.selected_bond2 = max(0, min(st.session_state.selected_bond2, max_idx))
        
        # Выбор облигаций
        bond1_idx = st.selectbox(
            "Облигация 1",
            range(len(bonds)),
            format_func=lambda i: bond_labels[i],
            key="selected_bond1",
            on_change=lambda: log_widget_change("selected_bond1", bonds[st.session_state.selected_bond1].isin if st.session_state.selected_bond1 < len(bonds) else None)
        )
        
        bond2_idx = st.selectbox(
            "Облигация 2",
            range(len(bonds)),
            format_func=lambda i: bond_labels[i],
            key="selected_bond2",
            on_change=lambda: log_widget_change("selected_bond2", bonds[st.session_state.selected_bond2].isin if st.session_state.selected_bond2 < len(bonds) else None)
        )
        
        # Предупреждение при выборе одинаковых облигаций
        if bond1_idx == bond2_idx:
            st.warning("⚠️ Выбраны одинаковые облигации. Спред всегда будет равен 0. Выберите разные облигации для анализа.")
        
        st.divider()
        
        # Единый период (1 месяц - 2 года)
        st.subheader("📅 Период")
        period = st.slider(
            "Период анализа (дней)",
            min_value=30,
            max_value=730,
            key="period",
            step=30,
            format="%d дней",
            on_change=lambda: log_widget_change("period")
        )
        
        st.divider()
        
        # Настройки Spread Analytics
        st.subheader("📈 Spread Analytics")
        spread_window = st.slider(
            "Окно rolling (дней)",
            min_value=5,
            max_value=90,
            key="spread_window",
            step=5,
            on_change=lambda: log_widget_change("spread_window")
        )
        
        z_threshold = st.slider(
            "Z-Score порог (σ)",
            min_value=1.0,
            max_value=3.0,
            key="z_threshold",
            step=0.1,
            format="%.1fσ",
            on_change=lambda: log_widget_change("z_threshold")
        )
        
        st.divider()
        
        # Настройки G-Spread Analytics
        st.subheader("📈 G-Spread Анализ")
        
        g_spread_period = st.slider(
            "Период G-Spread (дней)",
            min_value=30,
            max_value=730,
            key="g_spread_period",
            step=30,
            format="%d дней",
            on_change=lambda: log_widget_change("g_spread_period")
        )
        
        g_spread_window = st.slider(
            "Окно rolling (дней)",
            min_value=5,
            max_value=90,
            key="g_spread_window",
            step=5,
            on_change=lambda: log_widget_change("g_spread_window")
        )
        
        g_spread_z_threshold = st.slider(
            "Z-Score порог (σ)",
            min_value=1.0,
            max_value=3.0,
            key="g_spread_z_threshold",
            step=0.1,
            format="%.1fσ",
            on_change=lambda: log_widget_change("g_spread_z_threshold")
        )
        
        st.divider()
        
        # Интервал свечей (intraday) - radio
        st.subheader("⏱️ Интервал свечей")
        interval_options = {"1": "1 мин", "10": "10 мин", "60": "1 час"}
        candle_interval = st.radio(
            "Интервал для intraday графиков",
            options=["1", "10", "60"],
            format_func=lambda x: interval_options[x],
            key="candle_interval",
            horizontal=True,
            label_visibility="collapsed",
            on_change=lambda: log_widget_change("candle_interval", interval_options.get(st.session_state.candle_interval))
        )
        
        # Период свечей (динамический слайдер)
        st.subheader("📊 Период свечей")
        candle_config = CANDLE_INTERVAL_CONFIG[candle_interval]

        # Динамический максимум: минимум из настройки и периода анализа
        max_candle_days = min(candle_config["max_days"], period)
        min_candle_days = candle_config["min_days"]

        # Если диапазон допустим (min < max), показываем слайдер
        if min_candle_days < max_candle_days:
            # Корректируем текущее значение если оно вне диапазона
            current_candle_days = st.session_state.get('candle_days', min_candle_days)
            if current_candle_days < min_candle_days or current_candle_days > max_candle_days:
                st.session_state.candle_days = min_candle_days

            candle_days = st.slider(
                "Период свечей (дней)",
                min_value=min_candle_days,
                max_value=max_candle_days,
                key="candle_days",
                step=candle_config["step_days"],
                format="%d дн.",
                on_change=lambda: log_widget_change("candle_days")
            )
            # Пояснение
            st.caption(f"Макс. {candle_config['max_days']} дн. для {candle_config['name']} (ограничен периодом анализа: {period} дн.)")
        else:
            # Диапазон вырожден - фиксированное значение
            candle_days = min_candle_days
            st.session_state.candle_days = candle_days
            st.info(f"📅 Период свечей: **{candle_days} дн.** (ограничен периодом анализа)")
            st.caption(f"Увеличьте период анализа для изменения периода свечей")
        
        st.divider()
        
        # Автообновление
        st.subheader("🔄 Автообновление")
        auto_refresh = st.toggle(
            "Включить",
            key="auto_refresh",
            on_change=lambda: log_widget_change("auto_refresh")
        )
        
        if auto_refresh:
            refresh_interval = st.slider(
                "Интервал (сек)",
                min_value=30,
                max_value=300,
                key="refresh_interval",
                step=30,
                on_change=lambda: log_widget_change("refresh_interval")
            )
            
            if st.session_state.last_update:
                st.caption(f"Последнее: {st.session_state.last_update.strftime('%H:%M:%S')}")
        
        st.divider()
        
        # Управление БД
        st.subheader("🗄️ База данных")
        
        db = get_db_facade()
        db_stats = db.get_stats()
        
        with st.expander("📊 Статистика БД", expanded=False):
            st.write(f"**Облигаций:** {db_stats['bonds_count']}")
            st.write(f"**Дневных YTM:** {db_stats['daily_ytm_count']}")
            st.write(f"**Intraday YTM:** {db_stats['intraday_ytm_count']}")
        
        if st.button("🔄 Обновить БД", width="stretch", on_click=lambda: log_button_press("Обновить БД")):
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
        
        if st.button("🗑️ Очистить кэш", width="stretch", on_click=lambda: log_button_press("Очистить кэш")):
            st.cache_data.clear()
            st.rerun()
        
        st.divider()
        
        # Переключатель уровня логирования
        st.subheader("📜 Логи")
        log_level = st.radio(
            "Уровень",
            options=["INFO", "DEBUG"],
            horizontal=True,
            key="log_level",
            index=1,  # По умолчанию DEBUG
            on_change=lambda: log_widget_change("log_level")
        )
        
        if log_level == "DEBUG":
            logging.getLogger().setLevel(logging.DEBUG)
        else:
            logging.getLogger().setLevel(logging.INFO)
        
        st.divider()
        
        # Валидация YTM
        st.subheader("🔍 Валидация YTM")
        
        # Количество дней для проверки
        validation_days = st.slider(
            "Дней для проверки",
            min_value=1,
            max_value=30,
            value=5,
            step=1,
            on_change=lambda: log_widget_change("validation_days")
        )
        
        # Получаем текущие облигации для валидации
        bond1_for_val = bonds[bond1_idx] if bonds else None
        bond2_for_val = bonds[bond2_idx] if len(bonds) > 1 else None
        
        # Сброс валидации при смене инструментов
        current_isins = frozenset([b.isin for b in [bond1_for_val, bond2_for_val] if b])
        if st.session_state.get('validation_isins') != current_isins:
            st.session_state.ytm_validation = None
            st.session_state.validation_isins = current_isins
        
        # Определяем состояние кнопки
        validation_state = st.session_state.ytm_validation
        
        # Кнопка всегда с текстом проверки, но разный цвет
        if validation_state is None:
            button_label = "🔍 Проверить расчёт YTM"
            button_color = "normal"
        elif validation_state.get('valid', True):
            button_label = "✅ Расчётный YTM OK!"
            button_color = "green"
        else:
            button_label = "❌ Расчётный YTM fail!"
            button_color = "red"
        
        # Рисуем кнопку с нужным цветом
        if button_color == "green":
            st.markdown("""
            <style>
                div.stButton > button[kind="primary"] {
                    background-color: #28a745 !important;
                    border-color: #28a745 !important;
                }
                div.stButton > button[kind="primary"]:hover {
                    background-color: #218838 !important;
                    border-color: #1e7e34 !important;
                }
            </style>
            """, unsafe_allow_html=True)
            button_pressed = st.button(button_label, width="stretch", type="primary")
        elif button_color == "red":
            st.markdown("""
            <style>
                div.stButton > button[kind="secondary"] {
                    background-color: #dc3545 !important;
                    border-color: #dc3545 !important;
                    color: white !important;
                }
                div.stButton > button[kind="secondary"]:hover {
                    background-color: #c82333 !important;
                    border-color: #bd2130 !important;
                }
            </style>
            """, unsafe_allow_html=True)
            button_pressed = st.button(button_label, width="stretch", type="secondary")
        else:
            button_pressed = st.button(button_label, width="stretch", type="secondary")
        
        if button_pressed:
            log_button_press("Проверить расчёт YTM", f"bonds={bond1_for_val.isin if bond1_for_val else None}/{bond2_for_val.isin if bond2_for_val else None}")
            ytm_repo = get_ytm_repo()
            results = []
            all_valid = True
            
            if bond1_for_val:
                v1 = ytm_repo.validate_ytm_accuracy(bond1_for_val.isin, candle_interval, validation_days)
                results.append((bond1_for_val.name, v1))
                if not v1['valid']:
                    all_valid = False
            
            if bond2_for_val:
                v2 = ytm_repo.validate_ytm_accuracy(bond2_for_val.isin, candle_interval, validation_days)
                results.append((bond2_for_val.name, v2))
                if not v2['valid']:
                    all_valid = False
            
            st.session_state.ytm_validation = {
                'valid': all_valid,
                'results': results
            }
            st.rerun()
        
        # Показываем детали валидации
        if validation_state and validation_state.get('results'):
            with st.expander("📋 Детали валидации", expanded=True):
                for bond_name, v in validation_state['results']:
                    if v.get('reason'):
                        st.info(f"**{bond_name}**: {v['reason']}")
                    elif v.get('days_checked', 0) > 0:
                        status = "✅" if v['valid'] else "⚠️"
                        st.write(f"**{bond_name}**: {status}")
                        st.write(f"  • Проверено дней: {v['days_checked']}")
                        st.write(f"  • Валидных дней: {v['valid_days']}/{v['days_checked']}")
                        st.write(f"  • Среднее расхождение: {v['avg_diff_bp']:.2f} б.п.")
                        st.write(f"  • Max расхождение: {v['max_diff_bp']:.2f} б.п. ({v['max_diff_date']})")
                        
                        # Таблица по дням
                        if v.get('details'):
                            st.write("  **По дням:**")
                            for d in v['details']:
                                day_status = "✅" if d['valid'] else "⚠️"
                                candle_time = d.get('time', '—')
                                weekday = d.get('weekday', '')
                                # Направление расхождения
                                diff_dir = "↑" if d['calculated'] > d['official'] else "↓"
                                st.write(f"    {day_status} {d['date']} ({weekday}) {candle_time}: {d['diff_bp']:.2f} б.п. {diff_dir} (расч={d['calculated']:.4f}, офиц={d['official']:.4f})")
    
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
        # Дневные данные (для Spread Analytics и статистики)
        daily_df1 = fetch_historical_data_cached(bond1.isin, period)
        daily_df2 = fetch_historical_data_cached(bond2.isin, period)
        
        # Дневные данные для G-Spread (с отдельным периодом)
        # Если периоды совпадают, переиспользуем данные
        if st.session_state.g_spread_period == period:
            g_spread_df1_raw = daily_df1
            g_spread_df2_raw = daily_df2
        else:
            g_spread_df1_raw = fetch_historical_data_cached(bond1.isin, st.session_state.g_spread_period)
            g_spread_df2_raw = fetch_historical_data_cached(bond2.isin, st.session_state.g_spread_period)
        
        # Intraday данные
        # candle_days уже установлен в sidebar
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
    
    # ==========================================
    # ГРАФИК: SPREAD ANALYTICS (Z-SCORE)
    # ==========================================
    st.subheader("📊 Spread Analytics с Z-Score")
    
    # Логируем количество данных для графика
    logger.info(f"Spread Analytics: daily_df1={len(daily_df1)}, daily_df2={len(daily_df2)}, period={period}")
    
    # Показываем фактический период данных
    if not daily_df1.empty and not daily_df2.empty:
        df1_start = daily_df1.index.min().strftime('%d.%m.%Y')
        df1_end = daily_df1.index.max().strftime('%d.%m.%Y')
        df2_start = daily_df2.index.min().strftime('%d.%m.%Y')
        df2_end = daily_df2.index.max().strftime('%d.%m.%Y')
        
        # После inner join период определяется "младшей" облигацией
        actual_start = max(daily_df1.index.min(), daily_df2.index.min()).strftime('%d.%m.%Y')
        
        st.caption(f"📅 {bond1.name}: {df1_start} — {df1_end} ({len(daily_df1)} дн.) | "
                   f"{bond2.name}: {df2_start} — {df2_end} ({len(daily_df2)} дн.)")
        st.caption(f"📊 Общий период после объединения: с **{actual_start}** (по дате более позднего выпуска)")
    
    fig_analytics = create_spread_analytics_chart(
        daily_df1, daily_df2,
        bond1.name, bond2.name,
        window=st.session_state.spread_window,
        z_threshold=st.session_state.z_threshold
    )
    # key для принудительной перерисовки при изменении периода или облигаций
    chart_key = f"spread_analytics_{period}_{bond1.isin}_{bond2.isin}_{len(daily_df1)}_{len(daily_df2)}"
    st.plotly_chart(fig_analytics, width="stretch", key=chart_key)
    
    # Легенда сигналов
    st.markdown("""
    **Сигналы:** 🟢 BUY (спред < -{threshold}σ) | 🔴 SELL (спред > +{threshold}σ) | ⚪ Neutral
    
    **Интерпретация:**
    - BUY: спред аномально низкий → ожидается расширение (покупаем длинную, продаём короткую)
    - SELL: спред аномально высокий → ожидается сужение (продаём длинную, покупаем короткую)
    """.format(threshold=st.session_state.z_threshold))
    
    # ==========================================
    # АНАЛИЗ КОИНТЕГРАЦИИ
    # ==========================================
    with st.expander("📊 Анализ коинтеграции (ADF + Engle-Granger)", expanded=False):
        st.markdown("""
        **Что проверяем:**
        1. Являются ли YTM обоих облигаций нестационарными (должны быть!)
        2. Существует ли долгосрочная равновесная связь (коинтеграция)
        3. Как быстро спред возвращается к среднему (half-life)
        """)

        # Кнопка принудительного обновления
        col_refresh, col_status = st.columns([1, 3])
        with col_refresh:
            refresh_clicked = st.button("🔄 Обновить", key="refresh_cointegration", on_click=lambda: log_button_press("Обновить коинтеграцию"))

        # Получаем сервис коинтеграции
        coint_service = get_cointegration_service()

        # Подготовка данных
        ytm1_series = daily_df1['ytm'].dropna() if not daily_df1.empty else pd.Series()
        ytm2_series = daily_df2['ytm'].dropna() if not daily_df2.empty else pd.Series()

        # Ключ для отслеживания изменений пары/периода
        coint_key = f"coint_result_{bond1.isin}_{bond2.isin}_{period}"

        # Определяем нужно ли пересчитывать
        need_refresh = refresh_clicked or st.session_state.get(coint_key) is None

        if need_refresh and len(ytm1_series) >= 30 and len(ytm2_series) >= 30:
            with st.spinner("Анализ коинтеграции..."):
                try:
                    result = coint_service.get_or_calculate(
                        bond1.isin, bond2.isin, period,
                        ytm1_series, ytm2_series,
                        force_refresh=refresh_clicked
                    )
                    st.session_state[coint_key] = result
                except ImportError:
                    st.error("❌ **statsmodels не установлен.**")
                    st.code("pip install statsmodels", language="bash")
                    st.session_state[coint_key] = None
                except Exception as e:
                    st.error(f"❌ Ошибка анализа: {e}")
                    logger.error(f"Cointegration analysis error: {e}", exc_info=True)
                    st.session_state[coint_key] = None

        # Показываем результат
        result = st.session_state.get(coint_key)

        if result:
            # Статус кэша
            with col_status:
                if result.get('from_cache', False):
                    st.caption("📦 Из кэша (нажмите 'Обновить' для пересчёта)")
                else:
                    st.caption("✨ Свежий расчёт")

            # Отчёт
            st.markdown(format_cointegration_report(result, bond1.name, bond2.name))
        elif len(ytm1_series) < 30 or len(ytm2_series) < 30:
            st.warning(f"⚠️ Недостаточно данных для анализа (нужно ≥30, есть: {len(ytm1_series)}, {len(ytm2_series)})")
        else:
            st.info("Нажмите 'Обновить' для запуска анализа")
    
    # ==========================================
    # G-SPREAD АНАЛИЗ (КБД - Кривая Безкупонной Доходности)
    # ==========================================
    with st.expander("📈 G-Spread анализ (YTM vs КБД)", expanded=False):
        st.markdown("""
        **G-Spread** — разница между реальной YTM облигации и теоретической YTM по кривой КБД.
        
        **Данные:** Точные G-spread от MOEX (ZCYC API)
        
        **Интерпретация:**
        - G-spread < 0: Облигация дешевле кривой → ПОКУПКА
        - G-spread > 0: Облигация дороже кривой → ПРОДАЖА
        """)
        
        # Проверка на одинаковые облигации
        same_bonds = (bond1.isin == bond2.isin)
        if same_bonds:
            st.info(f"📊 Показан G-spread для одной облигации: **{bond1.name}**")
        
        try:
            # Рассчитываем G-spread для обеих облигаций
            # Используем точные данные MOEX (trdyield - clcyield)
            # Период ZCYC берётся из слайдера g_spread_period (НЕ зависит от daily_df)
            g_spread_df1, p_value1 = calculate_bond_g_spread(
                bond1.isin, g_spread_df1_raw, pd.DataFrame(),  # ns_params больше не нужен
                window=st.session_state.g_spread_window,
                zcyc_period=st.session_state.g_spread_period
            )
            
            # Если облигации одинаковые, не загружаем данные дважды
            if same_bonds:
                g_spread_df2 = pd.DataFrame()  # Пустой, чтобы не дублировать
                p_value2 = 1.0
            else:
                g_spread_df2, p_value2 = calculate_bond_g_spread(
                    bond2.isin, g_spread_df2_raw, pd.DataFrame(),
                    window=st.session_state.g_spread_window,
                    zcyc_period=st.session_state.g_spread_period
                )
            
            # Метрики G-spread
            if not g_spread_df1.empty or not g_spread_df2.empty:
                # При одинаковых облигациях показываем только одну метрику
                if same_bonds:
                    if not g_spread_df1.empty:
                        gs1_series = g_spread_df1['g_spread_bp']
                        if isinstance(gs1_series, pd.DataFrame):
                            gs1_series = gs1_series.iloc[:, 0]
                        stats1 = calculate_g_spread_stats(gs1_series)
                        current_gs1 = stats1.get('current', 0)
                        signal1 = generate_g_spread_signal(
                            current_gs1, 
                            stats1.get('p10', -50), 
                            stats1.get('p25', -25), 
                            stats1.get('p75', 25), 
                            stats1.get('p90', 50)
                        )
                        st.metric(
                            f"G-Spread {bond1.name}", 
                            f"{current_gs1:.1f} б.п.",
                            delta=f"Mean: {stats1.get('mean', 0):.1f}"
                        )
                        st.markdown(f"<span style='color:{signal1['color']}'>{signal1['signal']}: {signal1['action']}</span>", unsafe_allow_html=True)
                else:
                    # Разные облигации - показываем две метрики
                    col_gs1, col_gs2 = st.columns(2)
                    
                    with col_gs1:
                        if not g_spread_df1.empty:
                            gs1_series = g_spread_df1['g_spread_bp']
                            if isinstance(gs1_series, pd.DataFrame):
                                gs1_series = gs1_series.iloc[:, 0]
                            stats1 = calculate_g_spread_stats(gs1_series)
                            current_gs1 = stats1.get('current', 0)
                            signal1 = generate_g_spread_signal(
                                current_gs1, 
                                stats1.get('p10', -50), 
                                stats1.get('p25', -25), 
                                stats1.get('p75', 25), 
                                stats1.get('p90', 50)
                            )
                            st.metric(
                                f"G-Spread {bond1.name}", 
                                f"{current_gs1:.1f} б.п.",
                                delta=f"Mean: {stats1.get('mean', 0):.1f}"
                            )
                            st.markdown(f"<span style='color:{signal1['color']}'>{signal1['signal']}: {signal1['action']}</span>", unsafe_allow_html=True)
                    
                    with col_gs2:
                        if not g_spread_df2.empty:
                            gs2_series = g_spread_df2['g_spread_bp']
                            if isinstance(gs2_series, pd.DataFrame):
                                gs2_series = gs2_series.iloc[:, 0]
                            stats2 = calculate_g_spread_stats(gs2_series)
                            current_gs2 = stats2.get('current', 0)
                            signal2 = generate_g_spread_signal(
                                current_gs2, 
                                stats2.get('p10', -50), 
                                stats2.get('p25', -25), 
                                stats2.get('p75', 25), 
                                stats2.get('p90', 50)
                            )
                            st.metric(
                                f"G-Spread {bond2.name}", 
                                f"{current_gs2:.1f} б.п.",
                                delta=f"Mean: {stats2.get('mean', 0):.1f}"
                            )
                            st.markdown(f"<span style='color:{signal2['color']}'>{signal2['signal']}: {signal2['action']}</span>", unsafe_allow_html=True)
                
                # Подготовка данных для дашборда (БЕЗ дубликатов при same_bonds)
                if not g_spread_df1.empty and (same_bonds or not g_spread_df2.empty):
                    df_res = pd.DataFrame()
                    
                    # Облигация 1
                    df1_data = g_spread_df1.reset_index()
                    df1_data['ticker'] = bond1.name
                    df1_data['ytm'] = df1_data['ytm_bond']
                    df1_data['ytm_theor'] = df1_data['ytm_kbd']
                    df1_data['g_spread'] = df1_data['g_spread_bp']
                    df1_data['zscore'] = df1_data['z_score']
                    
                    if not same_bonds and not g_spread_df2.empty:
                        # Облигация 2 (только если разные)
                        df2_data = g_spread_df2.reset_index()
                        df2_data['ticker'] = bond2.name
                        df2_data['ytm'] = df2_data['ytm_bond']
                        df2_data['ytm_theor'] = df2_data['ytm_kbd']
                        df2_data['g_spread'] = df2_data['g_spread_bp']
                        df2_data['zscore'] = df2_data['z_score']
                        
                        df_res = pd.concat([df1_data, df2_data], ignore_index=True)
                    else:
                        df_res = df1_data
                    
                    # График G-spread дашборд
                    fig_g_spread = create_g_spread_dashboard(df_res, z_threshold=st.session_state.g_spread_z_threshold)
                    st.plotly_chart(fig_g_spread, width='stretch', key=f'g_spread_dashboard_{bond1.isin}_{bond2.isin}')
                    
                    # График отдельных G-spread
                    if same_bonds:
                        # Только один график
                        if not g_spread_df1.empty:
                            fig_gs1 = create_g_spread_chart_single(
                                g_spread_df1, bond1.name, stats1, p_value1,
                                window=st.session_state.g_spread_window,
                                z_threshold=st.session_state.g_spread_z_threshold
                            )
                            st.plotly_chart(fig_gs1, width='stretch', key=f'g_spread_chart1_{bond1.isin}')
                    else:
                        # Два графика
                        col_chart1, col_chart2 = st.columns(2)
                        with col_chart1:
                            if not g_spread_df1.empty:
                                fig_gs1 = create_g_spread_chart_single(
                                    g_spread_df1, bond1.name, stats1, p_value1,
                                    window=st.session_state.g_spread_window,
                                    z_threshold=st.session_state.g_spread_z_threshold
                                )
                                st.plotly_chart(fig_gs1, width='stretch', key=f'g_spread_chart1_{bond1.isin}')
                        with col_chart2:
                            if not g_spread_df2.empty:
                                fig_gs2 = create_g_spread_chart_single(
                                    g_spread_df2, bond2.name, stats2, p_value2,
                                    window=st.session_state.g_spread_window,
                                    z_threshold=st.session_state.g_spread_z_threshold
                                )
                                st.plotly_chart(fig_gs2, width='stretch', key=f'g_spread_chart2_{bond2.isin}')
            
            elif g_spread_df1.empty and g_spread_df2.empty:
                st.warning("⚠️ Данные G-spread не найдены на MOEX ZCYC API")
        
        except Exception as e:
            st.error(f"Ошибка при расчёте G-spread: {e}")
            logger.error(f"G-spread calculation error: {e}", exc_info=True)
    
    st.divider()
    
    # График 2: YTM склеенный (история + свечи)
    fig2 = create_combined_ytm_chart(
        daily_df1, daily_df2,
        intraday_df1, intraday_df2,
        bond1.name, bond2.name,
        candle_days=candle_days
    )
    chart_key2 = f"combined_ytm_{period}_{candle_days}_{bond1.isin}_{bond2.isin}_{len(daily_df1)}_{len(intraday_df1)}"
    st.plotly_chart(fig2, width="stretch", key=chart_key2)
    
    # График 3: Спред intraday (с перцентилями от дневных данных)
    fig3 = create_intraday_spread_chart(
        intraday_spread_df,
        daily_stats=daily_stats  # Перцентили от дневных!
    )
    chart_key3 = f"intraday_spread_{candle_days}_{bond1.isin}_{bond2.isin}_{len(intraday_spread_df)}"
    st.plotly_chart(fig3, width="stretch", key=chart_key3)
    
    # ==========================================
    # СОХРАНЕНИЕ НАСТРОЕК В URL
    # ==========================================
    sync_to_url()
    
    # ==========================================
    # АВТООБНОВЛЕНИЕ
    # ==========================================
    if st.session_state.auto_refresh:
        interval = st.session_state.refresh_interval or 60
        time.sleep(interval)
        st.session_state.last_update = datetime.now()
        st.rerun()


if __name__ == "__main__":
    main()
