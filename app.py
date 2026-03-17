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
# DEPRECATED: from api.moex_zcyc import fetch_ns_params_history
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
from components.styles import apply_main_styles
apply_main_styles()


def init_session_state():
    """Инициализация состояния сессии"""
    # Инициализация БД (создание таблиц при необходимости)
    init_database()
    
    # Загрузка настроек из URL (делаем ДО установки defaults)
    sync_from_url()
    
    if 'config' not in st.session_state:
        st.session_state.config = AppConfig()
    
    # Загрузка облигаций из БД (только один раз при старте сессии)
    # Это prevents конфликты между вкладками - каждая вкладка имеет свой список
    if 'bonds' not in st.session_state or 'favorites_loaded' not in st.session_state:
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

        st.session_state.bonds = favorites
        st.session_state.favorites_loaded = True
        logger.info(f"Загружено облигаций: {len(favorites)} избранное")
    
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
            bonds_dict = st.session_state.get('bonds', {})
            st.session_state.selected_bond1 = 0
            st.session_state.selected_bond2 = 1 if len(bonds_dict) > 1 else 0
    
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
def fetch_trading_data_batch_cached(isins: tuple) -> Dict[str, Dict]:
    """
    Получить торговые данные для списка облигаций (batch) с кэшированием.

    Использует параллельные запросы - намного быстрее чем по одному.
    isins передаётся как tuple т.к. список не хэшируется для кэша.
    """
    from services.data_loader import fetch_trading_data_batch
    return fetch_trading_data_batch(list(isins))


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
# G-SPREAD: ZCYC DATA
# ==========================================

# NS params функции удалены - не используются (moex_zcyc.py предоставляет всё нужное)


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
    
    ОБЁРТКА над calculate_g_spread_from_zcyc с загрузкой данных.
    
    Args:
        isin: ISIN облигации
        daily_df: DataFrame с YTM облигации (НЕ ИСПОЛЬЗУЕТСЯ - для совместимости)
        ns_params_df: DataFrame с параметрами NS (НЕ ИСПОЛЬЗУЕТСЯ)
        window: Окно для rolling Z-Score
        maturity_date: Дата погашения (НЕ ИСПОЛЬЗУЕТСЯ)
        use_duration: НЕ ИСПОЛЬЗУЕТСЯ
        zcyc_period: Период ZCYC в днях (по умолчанию 365)
        
    Returns:
        (DataFrame с G-spread, p_value ADF теста)
    """
    from services.g_spread_calculator import calculate_g_spread_from_zcyc
    
    # Период ZCYC — НЕ зависит от daily_df!
    zcyc_days = zcyc_period or st.session_state.get('g_spread_period', 365)
    end_date = date.today()
    start_date = end_date - timedelta(days=zcyc_days)
    
    logger.info(f"ZCYC период для {isin}: {start_date} - {end_date} ({zcyc_days} дней)")
    
    # Кэшированная загрузка ZCYC из БД или MOEX
    zcyc_df = _fetch_zcyc_cached(
        isin,
        start_date.strftime('%Y-%m-%d'),
        end_date.strftime('%Y-%m-%d')
    )
    
    if zcyc_df.empty:
        logger.warning(f"Нет ZCYC данных для {isin}")
        return pd.DataFrame(), 1.0
    
    logger.info(f"Загружено {len(zcyc_df)} записей ZCYC для {isin}")
    
    # Делегируем расчёт сервису
    return calculate_g_spread_from_zcyc(zcyc_df, window=window)


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
        from components.bond_manager import render_bond_manager_button, refresh_favorites_from_db
        render_bond_manager_button()
        
        # Кнопка обновления избранного (для синхронизации между вкладками)
        col_refresh, col_count = st.columns([1, 2])
        with col_refresh:
            if st.button("🔄", help="Обновить избранное из БД"):
                count = refresh_favorites_from_db()
                if count > 0:
                    st.toast(f"✅ Загружено {count} облигаций")
                st.rerun()
        with col_count:
            st.caption(f"⭐ {len(st.session_state.get('bonds', {}))} облигаций")
        
        st.divider()
        
        # Проверяем есть ли облигации
        if not bonds:
            st.warning("Нет избранных облигаций. Нажмите 'Управление облигациями' для выбора.")
            st.stop()
        
        # Получаем данные для dropdown (batch запрос - быстрее чем по одному)
        bond_labels = []
        bond_trading_data = {}
        
        # Batch загрузка торговых данных для всех облигаций
        all_isins = tuple(b.isin for b in bonds)
        bond_trading_data = fetch_trading_data_batch_cached(all_isins)
        
        for b in bonds:
            data = bond_trading_data.get(b.isin, {"isin": b.isin, "has_data": False})
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
        from components.sidebar import render_spread_analytics_settings, render_g_spread_settings, render_auto_refresh
        spread_window, z_threshold = render_spread_analytics_settings()
        
        st.divider()
        
        # Настройки G-Spread Analytics
        g_spread_period, g_spread_window, g_spread_z_threshold = render_g_spread_settings()
        
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
        auto_refresh, skip_candles = render_auto_refresh()
        
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
        from components.sidebar import render_ytm_validation
        render_ytm_validation(bonds, bond1_idx, bond2_idx, candle_interval)
    
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
    
    # Проверяем флаг быстрого обновления
    skip_candles = st.session_state.get('skip_candles', False)
    
    with st.spinner("Загрузка котировок..." if skip_candles else "Загрузка данных с MOEX..."):
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
        
        # Intraday данные - пропускаем при быстром обновлении
        if skip_candles:
            # Используем закэшированные данные или пустой DataFrame
            intraday_df1 = st.session_state.get('cached_intraday_df1', pd.DataFrame())
            intraday_df2 = st.session_state.get('cached_intraday_df2', pd.DataFrame())
        else:
            # candle_days уже установлен в sidebar
            intraday_df1 = fetch_candle_data_cached(bond1.isin, bond_config_to_dict(bond1), candle_interval, candle_days)
            intraday_df2 = fetch_candle_data_cached(bond2.isin, bond_config_to_dict(bond2), candle_interval, candle_days)
            # Кэшируем для быстрого обновления
            st.session_state.cached_intraday_df1 = intraday_df1
            st.session_state.cached_intraday_df2 = intraday_df2
    
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
            
            # ==========================================
            # INTRADAY ДАННЫЕ (если включено автообновление)
            # ==========================================
            intraday_df = pd.DataFrame()
            if st.session_state.auto_refresh:
                from api.moex_zcyc import fetch_current_bond_quotes
                
                # Получаем репозиторий для работы с БД
                intraday_repo = get_g_spread_repo()
                
                # Получаем текущие котировки
                isins = [bond1.isin]
                if not same_bonds:
                    isins.append(bond2.isin)
                
                current_quotes = fetch_current_bond_quotes(isins=isins)
                
                if not current_quotes.empty:
                    # Сохраняем в БД
                    intraday_repo.save_intraday_quotes(current_quotes)
                    logger.info(f"Сохранены intraday котировки для {isins}")
                
                # Загружаем последние intraday данные только для выбранных облигаций
                # (most_recent=True по умолчанию - берёт max tradedate)
                intraday_df = intraday_repo.load_intraday_quotes(isins=isins)
                logger.info(f"Загружено {len(intraday_df)} intraday записей из БД для {isins}")
                if not intraday_df.empty:
                    logger.debug(f"intraday_df columns: {list(intraday_df.columns)}")
                    logger.debug(f"intraday_df sample:\n{intraday_df.head()}")
            
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
                    
                    # Добавляем intraday данные (если есть)
                    intraday_rows = []
                    intraday_res = pd.DataFrame()
                    logger.info(f"Проверка intraday данных: empty={intraday_df.empty}, len={len(intraday_df)}")
                    if not intraday_df.empty:
                        # Получаем последние rolling_mean/std для расчёта Z-score
                        last_rolling_mean_1 = None
                        last_rolling_std_1 = None
                        last_rolling_mean_2 = None
                        last_rolling_std_2 = None
                        
                        if 'rolling_mean' in g_spread_df1.columns and 'rolling_std' in g_spread_df1.columns:
                            last_rolling_mean_1 = g_spread_df1['rolling_mean'].iloc[-1]
                            last_rolling_std_1 = g_spread_df1['rolling_std'].iloc[-1]
                        
                        if not same_bonds and not g_spread_df2.empty:
                            if 'rolling_mean' in g_spread_df2.columns and 'rolling_std' in g_spread_df2.columns:
                                last_rolling_mean_2 = g_spread_df2['rolling_mean'].iloc[-1]
                                last_rolling_std_2 = g_spread_df2['rolling_std'].iloc[-1]
                        
                        for _, row in intraday_df.iterrows():
                            # Определяем rolling параметры по ISIN
                            if row['secid'] == bond1.isin:
                                rm = last_rolling_mean_1
                                rs = last_rolling_std_1
                            else:
                                rm = last_rolling_mean_2
                                rs = last_rolling_std_2
                            
                            # Рассчитываем Z-score
                            g_spread = row['g_spread_bp']
                            if rm is not None and rs is not None and rs > 0 and pd.notna(g_spread):
                                zscore = (g_spread - rm) / rs
                            else:
                                zscore = np.nan
                            
                            intraday_rows.append({
                                'date': row['datetime'],
                                'ticker': row['shortname'],
                                'ytm': row['trdyield'],
                                'ytm_theor': row['clcyield'],
                                'g_spread': g_spread,
                                'zscore': zscore
                            })
                        
                        if intraday_rows:
                            intraday_res = pd.DataFrame(intraday_rows)
                            # Убираем FutureWarning: явно указываем типы колонок
                            for col in ['ytm', 'ytm_theor', 'g_spread', 'zscore']:
                                if col in intraday_res.columns:
                                    intraday_res[col] = intraday_res[col].astype(float)
                            # НЕ добавляем в df_res - передаём отдельно для intraday отображения
                            logger.info(f"Подготовлено {len(intraday_rows)} intraday точек для графиков")
                    
                    # График G-spread дашборд (передаём intraday отдельно)
                    fig_g_spread = create_g_spread_dashboard(
                        df_res, 
                        z_threshold=st.session_state.g_spread_z_threshold,
                        intraday_df=intraday_res if intraday_rows else None
                    )
                    st.plotly_chart(fig_g_spread, width='stretch', key=f'g_spread_dashboard_{bond1.isin}_{bond2.isin}')
                    
                    # Разделяем intraday данные по облигациям для отдельных графиков
                    intraday_bond1 = pd.DataFrame()
                    intraday_bond2 = pd.DataFrame()
                    if not intraday_df.empty:
                        intraday_bond1 = intraday_df[intraday_df['secid'] == bond1.isin].copy()
                        if not same_bonds:
                            intraday_bond2 = intraday_df[intraday_df['secid'] == bond2.isin].copy()
                        logger.info(f"intraday_bond1: {len(intraday_bond1)} записей, intraday_bond2: {len(intraday_bond2)} записей")
                    
                    # График отдельных G-spread
                    if same_bonds:
                        # Только один график
                        if not g_spread_df1.empty:
                            fig_gs1 = create_g_spread_chart_single(
                                g_spread_df1, bond1.name, stats1, p_value1,
                                window=st.session_state.g_spread_window,
                                z_threshold=st.session_state.g_spread_z_threshold,
                                intraday_df=intraday_bond1 if not intraday_bond1.empty else None
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
                                    z_threshold=st.session_state.g_spread_z_threshold,
                                    intraday_df=intraday_bond1 if not intraday_bond1.empty else None
                                )
                                st.plotly_chart(fig_gs1, width='stretch', key=f'g_spread_chart1_{bond1.isin}')
                        with col_chart2:
                            if not g_spread_df2.empty:
                                fig_gs2 = create_g_spread_chart_single(
                                    g_spread_df2, bond2.name, stats2, p_value2,
                                    window=st.session_state.g_spread_window,
                                    z_threshold=st.session_state.g_spread_z_threshold,
                                    intraday_df=intraday_bond2 if not intraday_bond2.empty else None
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
