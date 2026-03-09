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
from api.moex_history import HistoryFetcher
from api.moex_candles import CandleFetcher, CandleInterval
from core.database import get_db
from core.db import get_ytm_repo
from components.charts import (
    create_combined_ytm_chart,
    create_intraday_spread_chart,
    create_spread_analytics_chart,
    apply_zoom_range,
    create_g_spread_dashboard,
    create_g_spread_chart_single
)
from api.moex_zcyc import ZCYCFetcher
from services.g_spread_calculator import (
    calculate_g_spread_history,
    calculate_g_spread_stats,
    generate_g_spread_signal,
    enrich_bond_data  # С Z-Score и ADF тестом
)
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


def get_years_to_maturity(maturity_str: str) -> float:
    """Вычисляет годы до погашения"""
    try:
        maturity = datetime.strptime(maturity_str, '%Y-%m-%d')
        return round((maturity - datetime.now()).days / 365.25, 1)
    except (ValueError, TypeError):
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
    # Инициализация БД (создание таблиц при необходимости)
    init_database()
    
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

    # Результат валидации YTM
    if 'ytm_validation' not in st.session_state:
        st.session_state.ytm_validation = None


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


# Максимальный период для кэширования (2 года)
MAX_CACHE_PERIOD_DAYS = 730


@st.cache_data(ttl=300)
def _fetch_all_historical_data(secid: str) -> pd.DataFrame:
    """
    Загрузить ВСЕ исторические данные для ISIN (максимум 730 дней).
    
    Кэшируется по secid (без подчёркивания - чтобы был отдельный кэш для каждого ISIN).
    """
    fetcher = get_history_fetcher()
    db = get_db()
    
    # Всегда загружаем на максимум
    start_date = date.today() - timedelta(days=MAX_CACHE_PERIOD_DAYS)
    
    logger.info(f"_fetch_all_historical_data: secid={secid}, start_date={start_date}")
    
    # Загружаем ВСЕ данные из БД (без фильтрации по start_date)
    db_df = db.load_daily_ytm(secid)
    last_db_date = db.get_last_daily_ytm_date(secid)
    
    logger.info(f"Загружено из БД: {len(db_df)} записей, last_db_date={last_db_date}")
    
    # Проверяем нужно ли обновление
    if not db_df.empty and last_db_date:
        days_since_update = (date.today() - last_db_date).days
        
        if days_since_update <= 1:
            logger.info(f"Данные актуальны для {secid}: {len(db_df)} записей")
            return db_df
        else:
            # Дозагружаем только новые данные
            new_start = last_db_date + timedelta(days=1)
            new_df = fetcher.fetch_ytm_history(secid, start_date=new_start)
            
            if not new_df.empty:
                db.save_daily_ytm(secid, new_df)
                db_df = pd.concat([db_df, new_df])
                db_df = db_df[~db_df.index.duplicated(keep='last')]
                logger.info(f"Дозагружены новые данные: +{len(new_df)} записей")
            return db_df
    
    # БД пуста или устарела - загружаем весь период
    db_df = fetcher.fetch_ytm_history(secid, start_date=start_date)
    
    if not db_df.empty:
        db.save_daily_ytm(secid, db_df)
        logger.info(f"Сохранены дневные YTM в БД для {secid}: {len(db_df)} записей")
    
    return db_df


def fetch_historical_data_cached(secid: str, days: int) -> pd.DataFrame:
    """
    Получить исторические данные за указанный период.
    
    Использует кэшированные данные и фильтрует по периоду.
    """
    # Получаем все данные (из кэша или загружаем)
    all_df = _fetch_all_historical_data(secid)
    
    if all_df.empty:
        return all_df
    
    # Фильтруем по запрошенному периоду (без кэширования)
    start_date = date.today() - timedelta(days=days)
    result_df = all_df[all_df.index.date >= start_date]
    
    logger.info(f"fetch_historical_data_cached: secid={secid}, days={days}, возвращаем {len(result_df)} записей")
    
    return result_df


# Максимальные периоды для свечей по интервалам
MAX_CANDLE_DAYS = {
    "1": 3,    # 1 минута - 3 дня
    "10": 30,  # 10 минут - 30 дней
    "60": 365  # 1 час - 365 дней
}


@st.cache_data(ttl=60)
def _fetch_all_candle_data(isin: str, interval: str) -> pd.DataFrame:
    """
    Загрузить ВСЕ свечи с YTM для ISIN и интервала.
    
    Кэшируется по (isin, interval) - отдельный кэш для каждой пары.
    Без подчёркиваний - чтобы Streamlit правильно хэшировал аргументы.
    """
    from services.candle_processor_ytm_for_bonds import BondYTMProcessor
    
    fetcher = get_candle_fetcher()
    db = get_db()
    ytm_processor = BondYTMProcessor()
    
    # Максимальный период для данного интервала
    max_days = MAX_CANDLE_DAYS.get(interval, 30)
    
    interval_map = {
        "1": CandleInterval.MIN_1,
        "10": CandleInterval.MIN_10,
        "60": CandleInterval.MIN_60,
    }
    candle_interval = interval_map.get(interval, CandleInterval.MIN_60)
    
    logger.info(f"_fetch_all_candle_data: isin={isin}, interval={interval}, max_days={max_days}")
    
    # Загружаем ВСЕ данные из БД (история)
    db_ytm_df = db.load_intraday_ytm(isin, interval)
    
    # Получаем параметры облигации из БД для расчёта YTM
    bond_data = db.load_bond(isin)
    if not bond_data:
        logger.warning(f"Облигация {isin} не найдена в БД")
        return pd.DataFrame()
    
    # Создаём объект для YTM процессора
    class BondConfigAdapter:
        def __init__(self, data):
            self.isin = data.get('isin')
            self.name = data.get('name')
            self.maturity_date = data.get('maturity_date')
            self.coupon_rate = data.get('coupon_rate')
            self.face_value = data.get('face_value', 1000)
            self.coupon_frequency = data.get('coupon_frequency', 2)
            self.issue_date = data.get('issue_date')
            self.day_count_convention = data.get('day_count', 'ACT/ACT')
    
    bond_config = BondConfigAdapter(bond_data)
    
    # Запрашиваем текущий день (сырые свечи)
    raw_today_df = fetcher.fetch_candles(
        isin,
        interval=candle_interval,
        start_date=date.today(),
        end_date=date.today()
    )
    
    # Рассчитываем YTM для текущего дня
    today_df = pd.DataFrame()
    if not raw_today_df.empty:
        today_df = ytm_processor.add_ytm_to_candles(raw_today_df, bond_config)
    
    # Проверяем нужны ли исторические данные
    last_db_datetime = db.get_last_intraday_ytm_datetime(isin, interval)
    
    if db_ytm_df.empty and date.today() > date.today() - timedelta(days=1):
        # БД пуста - загружаем историю
        raw_history_df = fetcher.fetch_candles(
            isin,
            interval=candle_interval,
            start_date=date.today() - timedelta(days=max_days),
            end_date=date.today() - timedelta(days=1)
        )
        
        if not raw_history_df.empty:
            history_df = ytm_processor.add_ytm_to_candles(raw_history_df, bond_config)
            if not history_df.empty and 'ytm_close' in history_df.columns:
                db.save_intraday_ytm(isin, interval, history_df)
                db_ytm_df = history_df
                logger.info(f"Сохранены intraday YTM для {isin}: {len(history_df)} записей")
    
    elif db_ytm_df.empty:
        # БД пуста, но сегодня выходной - возвращаем пустой
        pass
    
    # Сохраняем текущие данные
    if not today_df.empty and 'ytm_close' in today_df.columns:
        db.save_intraday_ytm(isin, interval, today_df)
    
    # Объединяем историю + сегодня
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


def fetch_candle_data_cached(isin: str, bond_config_dict: Dict, interval: str, days: int) -> pd.DataFrame:
    """
    Получить данные свечей за указанный период.
    
    Использует кэшированные данные и фильтрует по периоду.
    bond_config_dict - оставлен для совместимости, данные берутся из БД.
    """
    # Получаем все данные (из кэша или загружаем)
    all_df = _fetch_all_candle_data(isin, interval)
    
    if all_df.empty:
        return all_df
    
    # Фильтруем по запрошенному периоду (без кэширования)
    start_date = date.today() - timedelta(days=days)
    result_df = all_df[all_df.index.date >= start_date]
    
    logger.info(f"fetch_candle_data_cached: isin={isin}, interval={interval}, days={days}, возвращаем {len(result_df)} записей")
    
    return result_df


# ==========================================
# G-SPREAD: NELSON-SIEGEL PARAMS
# ==========================================

@st.cache_resource
def get_zcyc_fetcher():
    """Получить экземпляр ZCYCFetcher (кэшируется)"""
    return ZCYCFetcher()


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


def fetch_ns_params_from_moex(progress_callback=None) -> int:
    """
    Загрузить параметры Nelson-Siegel с MOEX в БД
    
    Загружает данные ПО ДНЯМ с 2014-01-06 по текущую дату.
    Занимает ~5-10 минут для полной истории (~2900 дней).
    
    Args:
        progress_callback: Функция для отображения прогресса (current, total, date)
        
    Returns:
        Количество загруженных записей
    """
    g_spread_repo = get_g_spread_repo()
    fetcher = get_zcyc_fetcher()
    
    # Проверяем последнюю дату в БД
    last_date = g_spread_repo.get_last_ns_params_date()
    
    if last_date:
        # Продолжаем с последней даты + 1
        start_date = last_date + timedelta(days=1)
        logger.info(f"Возобновление загрузки с {start_date} (последняя дата в БД: {last_date})")
    else:
        # Загружаем с начала истории
        start_date = None  # Используется ZCYC_HISTORY_START (2014-01-06)
        logger.info("Начало полной загрузки с 2014-01-06")
    
    # Загружаем с MOEX по дням
    ns_df = fetcher.fetch_ns_params_history(
        start_date=start_date,
        save_callback=g_spread_repo.save_ns_params,
        progress_callback=progress_callback
    )
    
    return g_spread_repo.count_ns_params()


def calculate_bond_g_spread(
    isin: str,
    daily_df: pd.DataFrame,
    ns_params_df: pd.DataFrame,
    window: int = 30
) -> Tuple[pd.DataFrame, float]:
    """
    Рассчитать G-spread для облигации с Z-Score и ADF тестом
    
    Args:
        isin: ISIN облигации
        daily_df: DataFrame с YTM облигации (колонки: ytm, duration_days)
        ns_params_df: DataFrame с параметрами Nelson-Siegel
        window: Окно для rolling Z-Score
        
    Returns:
        (DataFrame с G-spread, p_value ADF теста)
    """
    g_spread_repo = get_g_spread_repo()
    
    # Проверяем есть ли в БД
    g_spread_df = g_spread_repo.load_g_spreads(isin)
    
    if not g_spread_df.empty:
        # Проверяем актуальность
        last_date = g_spread_repo.get_last_g_spread_date(isin)
        if last_date and (date.today() - last_date).days <= 1:
            logger.info(f"G-spread из БД для {isin}: {len(g_spread_df)} записей")
            return g_spread_df, 0.0  # p-value из кэша не храним
    
    # Рассчитываем
    if daily_df.empty or ns_params_df.empty:
        return pd.DataFrame(), 1.0
    
    # Подготовка данных для enrich_bond_data
    # Нужно: date (колонка или индекс), ytm, duration
    bond_data = daily_df.copy()
    
    # Если duration нет, используем примерное значение
    if 'duration_days' not in bond_data.columns:
        bond_data['duration_days'] = 365.25 * 5  # По умолчанию 5 лет
    
    bond_data['duration'] = bond_data['duration_days']
    
    # Сбрасываем индекс если нужно
    if bond_data.index.name == 'date' or bond_data.index.name is None:
        bond_data = bond_data.reset_index()
        if 'index' in bond_data.columns:
            bond_data = bond_data.rename(columns={'index': 'date'})
    
    # NS params: переименовываем для enrich_bond_data
    ns_data = ns_params_df.copy()
    if ns_data.index.name == 'date' or ns_data.index.name is None:
        ns_data = ns_data.reset_index()
        if 'index' in ns_data.columns:
            ns_data = ns_data.rename(columns={'index': 'date'})
    
    # Вызываем enrich_bond_data с Z-Score и ADF тестом
    g_spread_df, p_value = enrich_bond_data(bond_data, ns_data, window=window)
    
    if not g_spread_df.empty:
        # Преобразуем в формат для сохранения и UI
        result_df = g_spread_df.copy()
        
        # Устанавливаем date как индекс если это колонка
        if 'date' in result_df.columns:
            result_df = result_df.set_index('date')
        
        # Выбираем только нужные колонки и переименовываем
        # Важно: g_spread_bp уже есть в enrich_bond_data, дублируем через g_spread
        result_df = result_df.rename(columns={
            'ytm': 'ytm_bond',
            'ytm_theoretical': 'ytm_kbd'
        })
        
        # Убираем дубликат g_spread если есть обе колонки
        if 'g_spread' in result_df.columns and 'g_spread_bp' in result_df.columns:
            result_df = result_df.drop(columns=['g_spread'])
        
        # Оставляем только нужные колонки
        keep_cols = ['ytm_bond', 'ytm_kbd', 'g_spread_bp', 'duration_years', 'z_score']
        result_df = result_df[[c for c in keep_cols if c in result_df.columns]]
        
        # Сохраняем в БД
        saved = g_spread_repo.save_g_spreads(isin, result_df)
        logger.info(f"Сохранено {saved} G-spread для {isin}, ADF p-value: {p_value:.4f}")
        
        return result_df, p_value
    
    return pd.DataFrame(), 1.0


def calculate_spread_stats(spread_series: pd.Series) -> Dict:
    """Вычисляет статистику спреда"""
    if spread_series.empty:
        return {}
    
    # Удаляем NaN для статистики
    clean_series = spread_series.dropna()
    
    if clean_series.empty:
        return {}
    
    return {
        'mean': clean_series.mean(),
        'median': clean_series.median(),
        'std': clean_series.std(),
        'min': clean_series.min(),
        'max': clean_series.max(),
        'p10': clean_series.quantile(0.10),
        'p25': clean_series.quantile(0.25),
        'p75': clean_series.quantile(0.75),
        'p90': clean_series.quantile(0.90),
        'current': clean_series.iloc[-1] if len(clean_series) > 0 else 0
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
    
    # Удаляем дубликаты в индексах перед объединением
    df1_clean = df1[~df1.index.duplicated(keep='last')][[ytm_col]].copy()
    df2_clean = df2[~df2.index.duplicated(keep='last')][[ytm_col]].copy()
    
    # Объединяем по индексу с помощью join
    merged = df1_clean.join(df2_clean, lsuffix='_1', rsuffix='_2', how='inner')
    
    # Переименовываем колонки
    merged.columns = ['ytm1', 'ytm2']
    
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
    from services.candle_processor_ytm_for_bonds import BondYTMProcessor
    
    fetcher = get_history_fetcher()
    candle_fetcher = get_candle_fetcher()
    db = get_db()
    ytm_processor = BondYTMProcessor()
    
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
                
                # Получаем сырые свечи
                raw_df = candle_fetcher.fetch_candles(
                    bond.isin,
                    interval=interval_enum,
                    start_date=date.today() - timedelta(days=days),
                    end_date=date.today()
                )
                
                # Рассчитываем YTM
                df = pd.DataFrame()
                if not raw_df.empty:
                    df = ytm_processor.add_ytm_to_candles(raw_df, bond)
                
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
            key="selected_bond1"  # Автоматическая синхронизация с session_state
        )
        
        bond2_idx = st.selectbox(
            "Облигация 2",
            range(len(bonds)),
            format_func=lambda i: bond_labels[i],
            key="selected_bond2"  # Автоматическая синхронизация с session_state
        )
        
        st.divider()
        
        # Единый период (1 месяц - 2 года)
        st.subheader("📅 Период")
        period = st.slider(
            "Период анализа (дней)",
            min_value=30,
            max_value=730,
            key="period",  # Автоматическая синхронизация с session_state
            step=30,
            format="%d дней"
        )
        
        st.divider()
        
        # Настройки Spread Analytics
        st.subheader("📈 Spread Analytics")
        spread_window = st.slider(
            "Окно rolling (дней)",
            min_value=5,
            max_value=90,
            key="spread_window",  # Автоматическая синхронизация с session_state
            step=5
        )
        
        z_threshold = st.slider(
            "Z-Score порог (σ)",
            min_value=1.0,
            max_value=3.0,
            key="z_threshold",  # Автоматическая синхронизация с session_state
            step=0.1,
            format="%.1fσ"
        )
        
        st.divider()
        
        # Интервал свечей (intraday) - radio
        st.subheader("⏱️ Интервал свечей")
        interval_options = {"1": "1 мин", "10": "10 мин", "60": "1 час"}
        candle_interval = st.radio(
            "Интервал для intraday графиков",
            options=["1", "10", "60"],
            format_func=lambda x: interval_options[x],
            key="candle_interval",  # Автоматическая синхронизация с session_state
            horizontal=True,
            label_visibility="collapsed"
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
                key="candle_days",  # Автоматическая синхронизация с session_state
                step=candle_config["step_days"],
                format="%d дн."
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
            key="auto_refresh"  # Автоматическая синхронизация с session_state
        )
        
        if auto_refresh:
            refresh_interval = st.slider(
                "Интервал (сек)",
                min_value=30,
                max_value=300,
                key="refresh_interval",  # Автоматическая синхронизация с session_state
                step=30
            )
            
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
        
        if st.button("🔄 Обновить БД", width="stretch"):
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
        
        if st.button("🗑️ Очистить кэш", width="stretch"):
            st.cache_data.clear()
            st.rerun()
        
        st.divider()
        
        # Переключатель уровня логирования
        st.subheader("📜 Логи")
        log_level = st.radio(
            "Уровень",
            options=["INFO", "DEBUG"],
            horizontal=True,
            key="log_level"
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
            step=1
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
            refresh_clicked = st.button("🔄 Обновить", key="refresh_cointegration")

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
        
        **Интерпретация:**
        - G-spread < 0: Облигация дешевле кривой → ПОКУПКА
        - G-spread > 0: Облигация дороже кривой → ПРОДАЖА
        
        **Модель Nelson-Siegel:**
        Y(t) = b₁ + b₂·f₁(t) + b₃·f₂(t)
        """)
        
        # Проверяем наличие данных NS в БД
        g_spread_repo = get_g_spread_repo()
        ns_count = g_spread_repo.count_ns_params()
        last_ns_date = g_spread_repo.get_last_ns_params_date()
        
        # Проверяем актуальность данных
        today = date.today()
        need_update = False
        if last_ns_date:
            days_behind = (today - last_ns_date).days
            if days_behind > 1:
                need_update = True
        
        # UI для загрузки
        col_ns_refresh, col_ns_status = st.columns([1, 3])
        
        if ns_count == 0:
            # Данных нет - предупреждение и кнопка загрузки
            st.warning("⚠️ **Параметры КБД не загружены.** Первая загрузка займёт ~5-10 минут (~2900 дней с 2014 года).")
            
            with col_ns_refresh:
                if st.button("📥 Загрузить КБД (~5-10 мин)", key="load_ns_params", type="primary"):
                    st.session_state.loading_ns = True
                    st.rerun()
            
        elif need_update:
            # Данные есть, но не актуальны
            with col_ns_status:
                st.caption(f"⚠️ КБД: {ns_count} записей, последняя: {last_ns_date} (отстает на {days_behind} дн.)")
            
            with col_ns_refresh:
                col_btn1, col_btn2 = st.columns(2)
                with col_btn1:
                    if st.button("▶️ Продолжить", key="continue_ns_params", type="primary"):
                        st.session_state.loading_ns = True
                        st.rerun()
                with col_btn2:
                    if st.button("🔄 Перезагрузить", key="reload_ns_params"):
                        st.session_state.reload_ns = True
                        st.rerun()
        else:
            # Данные актуальны
            with col_ns_status:
                st.caption(f"✅ КБД: {ns_count} записей, последняя: {last_ns_date}")
            
            with col_ns_refresh:
                ns_refresh_clicked = st.button("🔄 Обновить КБД", key="refresh_ns_params")
            
            # Загружаем из БД (быстро)
            ns_params_df = fetch_ns_params_cached(period)
        
        # Обработка загрузки (продолжение или новая)
        if st.session_state.get('loading_ns', False) or st.session_state.get('reload_ns', False):
            # Если перезагрузка - очищаем БД
            if st.session_state.get('reload_ns', False):
                st.info("🗑️ Очистка старых данных...")
                from core.db.connection import get_connection
                conn = get_connection()
                conn.execute('DELETE FROM ns_params')
                conn.commit()
                conn.close()
                st.session_state.reload_ns = False
                st.cache_data.clear()
            
            st.info("🔄 Загрузка параметров Nelson-Siegel с MOEX...")
            
            # Прогресс бар
            progress_bar = st.progress(0)
            progress_text = st.empty()
            
            def update_progress(current, total, day):
                pct = int(100 * current / total)
                progress_bar.progress(pct)
                progress_text.text(f"{current}/{total} дней ({pct}%) — текущая дата: {day}")
            
            try:
                loaded = fetch_ns_params_from_moex(progress_callback=update_progress)
                progress_bar.progress(100)
                progress_text.text(f"✅ Загружено {loaded} записей")
                
                st.success(f"✅ Всего записей КБД: {loaded}")
                st.session_state.loading_ns = False
                st.cache_data.clear()
                time.sleep(1)
                st.rerun()
            except Exception as e:
                st.error(f"Ошибка загрузки КБД: {e}")
                logger.error(f"Ошибка загрузки КБД: {e}", exc_info=True)
                st.session_state.loading_ns = False
        
        # Загружаем ns_params_df если ещё не загружен
        if 'ns_params_df' not in dir() or ns_params_df is None:
            ns_params_df = fetch_ns_params_cached(period) if ns_count > 0 else pd.DataFrame()
        
        try:
            if ns_params_df.empty and ns_count == 0:
                # Не показываем ошибку если данные просто не загружены
                st.info("👆 Нажмите 'Загрузить КБД' для начала работы с G-Spread анализом.")
            else:
                # Рассчитываем G-spread для обеих облигаций
                g_spread_df1, p_value1 = calculate_bond_g_spread(bond1.isin, daily_df1, ns_params_df)
                g_spread_df2, p_value2 = calculate_bond_g_spread(bond2.isin, daily_df2, ns_params_df)
                
                # Метрики G-spread
                if not g_spread_df1.empty or not g_spread_df2.empty:
                    col_gs1, col_gs2 = st.columns(2)
                    
                    with col_gs1:
                        if not g_spread_df1.empty:
                            # Гарантируем что g_spread_bp - это Series
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
                            # Гарантируем что g_spread_bp - это Series
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
                    
                    # Подготовка данных для дашборда
                    if not g_spread_df1.empty and not g_spread_df2.empty:
                        # Создаём DataFrame для дашборда
                        df_res = pd.DataFrame()
                        
                        # Облигация 1
                        df1_data = g_spread_df1.reset_index()
                        df1_data['ticker'] = bond1.name
                        df1_data['ytm'] = df1_data['ytm_bond']
                        df1_data['ytm_theor'] = df1_data['ytm_kbd']
                        df1_data['g_spread'] = df1_data['g_spread_bp']
                        
                        # Z-score
                        mean_gs1 = stats1.get('mean', 0)
                        std_gs1 = stats1.get('std', 1)
                        df1_data['zscore'] = (df1_data['g_spread_bp'] - mean_gs1) / std_gs1
                        
                        # Облигация 2
                        df2_data = g_spread_df2.reset_index()
                        df2_data['ticker'] = bond2.name
                        df2_data['ytm'] = df2_data['ytm_bond']
                        df2_data['ytm_theor'] = df2_data['ytm_kbd']
                        df2_data['g_spread'] = df2_data['g_spread_bp']
                        
                        # Z-score
                        mean_gs2 = stats2.get('mean', 0)
                        std_gs2 = stats2.get('std', 1)
                        df2_data['zscore'] = (df2_data['g_spread_bp'] - mean_gs2) / std_gs2
                        
                        df_res = pd.concat([df1_data, df2_data], ignore_index=True)
                        
                        # График G-spread дашборд
                        fig_g_spread = create_g_spread_dashboard(df_res)
                        st.plotly_chart(fig_g_spread, use_container_width=True)
                        
                        # Дополнительно: график отдельных G-spread
                        col_chart1, col_chart2 = st.columns(2)
                        with col_chart1:
                            fig_gs1 = create_g_spread_chart_single(g_spread_df1, bond1.name, stats1)
                            st.plotly_chart(fig_gs1, use_container_width=True)
                        with col_chart2:
                            fig_gs2 = create_g_spread_chart_single(g_spread_df2, bond2.name, stats2)
                            st.plotly_chart(fig_gs2, use_container_width=True)
                
                elif not ns_params_df.empty:
                    st.info("Рассчитываем G-spread...")
                
        except Exception as e:
            st.error(f"Ошибка при загрузке КБД: {e}")
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
    # АВТООБНОВЛЕНИЕ
    # ==========================================
    if st.session_state.auto_refresh:
        interval = st.session_state.refresh_interval or 60
        time.sleep(interval)
        st.session_state.last_update = datetime.now()
        st.rerun()


if __name__ == "__main__":
    main()
