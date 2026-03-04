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
    apply_zoom_range
)
from version import format_version_badge
from core.cointegration import CointegrationAnalyzer
from core.cointegration_service import get_cointegration_service

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
    
    # Состояние анализа коинтеграции
    if 'cointegration_needs_update' not in st.session_state:
        st.session_state.cointegration_needs_update = False
    
    if 'cointegration_results' not in st.session_state:
        st.session_state.cointegration_results = {}
    
    if 'cointegration_running' not in st.session_state:
        st.session_state.cointegration_running = False
    
    # Проверка при первом запуске: если избранное есть, а результатов нет — запустить анализ
    if 'cointegration_initialized' not in st.session_state:
        st.session_state.cointegration_initialized = True
        db = get_db()
        cached_count = len(db.get_cointegrated_pairs())
        favorites_count = len(db.get_favorite_bonds())
        
        # Если есть избранное (>=2), но результатов нет — нужен анализ
        if favorites_count >= 2 and cached_count == 0:
            st.session_state.cointegration_needs_update = True
            favorite_isins = [b['isin'] for b in db.get_favorite_bonds()]
            st.session_state.cointegration_favorites = favorite_isins
            logger.info(f"Автозапуск анализа коинтеграции: {favorites_count} облигаций, {cached_count} результатов")


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


def run_cointegration_analysis_for_favorites(favorite_isins: List[str]) -> Dict:
    """
    Запускает анализ коинтеграции для всех пар избранных облигаций.
    
    Args:
        favorite_isins: Список ISIN избранных облигаций
        
    Returns:
        Словарь с результатами по парам
    """
    from core.cointegration_service import CointegrationService
    
    if len(favorite_isins) < 2:
        return {}
    
    service = CointegrationService()
    db = get_db()
    
    # Загружаем кэшированные результаты
    service.load_cached_results(db, max_age_hours=24)
    
    # Запускаем анализ синхронно (для простоты)
    pairs = service.generate_pairs(favorite_isins)
    results = {}
    
    for isin1, isin2 in pairs:
        key = service.get_pair_key(isin1, isin2)
        
        # Проверяем кэш
        cached = service.get_result(isin1, isin2)
        if cached and not cached.error:
            results[key] = cached
            continue
        
        # Анализируем
        result = service.analyze_pair(isin1, isin2, db)
        results[key] = result
        
        # Сохраняем в БД
        db.save_cointegration_result(result.to_dict())
    
    return {k: v.to_dict() for k, v in results.items()}


def get_cointegration_status_html(result: Dict, bond1_name: str, bond2_name: str) -> str:
    """
    Формирует HTML блок со статусом коинтеграции.
    
    Args:
        result: Результат анализа
        bond1_name: Имя первой облигации
        bond2_name: Имя второй облигации
        
    Returns:
        HTML строка со статусом
    """
    if not result:
        return ""
    
    is_cointegrated = result.get('is_cointegrated', False)
    pvalue = result.get('pvalue')
    data_days = result.get('data_days', 0)
    low_data = result.get('low_data', False)
    error = result.get('error')
    half_life = result.get('half_life')
    hedge_ratio = result.get('hedge_ratio')
    
    if error:
        return f'<span style="color: #999;">⚠️ {error}</span>'
    
    if is_cointegrated:
        status_color = '#28a745'
        status_icon = '✅'
        status_text = 'Тест коинтеграции пройден'
        pval_text = f'p={pvalue:.4f}' if pvalue else ''
    else:
        status_color = '#dc3545'
        status_icon = '❌'
        status_text = 'Тест коинтеграции не пройден'
        pval_text = f'p={pvalue:.4f}' if pvalue else ''
    
    data_warning = ' ⚠️ мало данных' if low_data else ''
    
    # Первая строка - статус
    status_line = f'''
    <div style="display: inline-flex; align-items: center; gap: 8px; padding: 8px 12px; 
                background: {status_color}15; border-radius: 8px; border-left: 3px solid {status_color};">
        <span style="font-size: 1.2em;">{status_icon}</span>
        <span style="font-weight: 500; color: {status_color};">{status_text}</span>
        <span style="color: #666; font-size: 0.9em;">{pval_text}</span>
        <span style="color: #888; font-size: 0.85em;">({data_days} дн.{data_warning})</span>
    </div>'''
    
    # Вторая строка - метрики (только если коинтегрированы)
    if is_cointegrated and (half_life or hedge_ratio):
        metrics_parts = []
        if half_life and half_life != float('inf'):
            metrics_parts.append(f'⏱️ Half-life: <strong>{half_life:.1f} дней</strong>')
        if hedge_ratio:
            metrics_parts.append(f'⚖️ Hedge ratio: <strong>{hedge_ratio:.4f}</strong>')
        
        if metrics_parts:
            metrics_line = f'''
    <div style="padding: 6px 12px; color: #666; font-size: 0.9em;">
        {'    '.join(metrics_parts)}
    </div>'''
            return status_line + metrics_line
    
    return status_line


def run_single_cointegration_analysis(isin1: str, isin2: str, period: int) -> Optional[Dict]:
    """
    Запускает анализ коинтеграции для одной пары за указанный период.
    
    Args:
        isin1: ISIN первой облигации
        isin2: ISIN второй облигации
        period: Период анализа в днях
        
    Returns:
        Словарь с результатом или None при ошибке
    """
    from core.cointegration_service import CointegrationService
    
    try:
        service = CointegrationService()
        db = get_db()
        
        result = service.analyze_pair(isin1, isin2, db, period_days=period)
        
        if result and not result.error:
            result_dict = result.to_dict()
            result_dict['period_days'] = period  # Сохраняем запрошенный период
            db.save_cointegration_result(result_dict)
            return result_dict
        elif result:
            return result.to_dict()
    except Exception as e:
        logger.error(f"Ошибка анализа коинтеграции: {e}", exc_info=True)
    
    return None


def format_cointegration_details(result: Dict, bond1_name: str, bond2_name: str) -> str:
    """
    Форматирует подробный отчёт коинтеграции для expandable блока.
    
    Args:
        result: Результат анализа
        bond1_name: Имя первой облигации
        bond2_name: Имя второй облигации
        
    Returns:
        Markdown строка с отчётом
    """
    if not result:
        return "Нет данных для отображения."
    
    error = result.get('error')
    if error:
        return f"❌ **Ошибка:** {error}"
    
    lines = []
    
    # Секция "Что проверяем"
    lines.append("**Что проверяем:**")
    lines.append("- Являются ли YTM обоих облигаций нестационарными (должны быть!)")
    lines.append("- Существует ли долгосрочная равновесная связь (коинтеграция)")
    lines.append("- Как быстро спред возвращается к среднему (half-life)")
    lines.append("")
    
    # Проверка стационарности
    adf_pval1 = result.get('adf_bond1_pvalue')
    adf_pval2 = result.get('adf_bond2_pvalue')
    both_nonstationary = result.get('both_nonstationary', False)
    
    lines.append("**Проверка облигаций (должны быть нестационарны):**")
    
    if adf_pval1 is not None:
        stat1 = "❌ стационарен" if adf_pval1 < 0.05 else "✅ нестационарен"
        lines.append(f"- {bond1_name}: {stat1} (p={adf_pval1:.4f})")
    
    if adf_pval2 is not None:
        stat2 = "❌ стационарен" if adf_pval2 < 0.05 else "✅ нестационарен"
        lines.append(f"- {bond2_name}: {stat2} (p={adf_pval2:.4f})")
    
    lines.append("")
    
    # Engle-Granger тест
    pvalue = result.get('pvalue')
    is_cointegrated = result.get('is_cointegrated', False)
    
    lines.append("**Engle-Granger тест:**")
    if pvalue is not None:
        coint_status = "✅ Коинтеграция есть" if is_cointegrated else "❌ Коинтеграции нет"
        lines.append(f"- p-value: `{pvalue:.4f}`")
        lines.append(f"- **{coint_status}** (p={pvalue:.4f})")
    lines.append("")
    
    # Half-life и Hedge Ratio (только если коинтегрированы)
    if is_cointegrated:
        half_life = result.get('half_life')
        hedge_ratio = result.get('hedge_ratio')
        
        if half_life is not None and half_life != float('inf'):
            lines.append(f"**Half-life:** `{half_life:.1f}` дней")
        
        if hedge_ratio is not None:
            lines.append(f"**Hedge Ratio:** `{hedge_ratio:.4f}`")
            lines.append(f"> На каждые **{abs(hedge_ratio):.2f} единицы {bond2_name}** нужно взять **1 единицу {bond1_name}**")
        
        lines.append("")
        
        # Рекомендация по стратегии
        half_life = result.get('half_life')
        if half_life is not None and half_life != float('inf'):
            if half_life <= 10:
                risk = "низкий"
                emoji = "✅"
            elif half_life <= 30:
                risk = "средний"
                emoji = "⚠️"
            else:
                risk = "высокий"
                emoji = "⚠️"
            
            lines.append(f"{emoji} **Pair Trading (Mean Reversion)**")
            lines.append(f"- Коинтеграция подтверждена. Mean reversion {'сильная' if half_life <= 10 else 'умеренная' if half_life <= 30 else 'слабая'} (half-life: {half_life:.1f} дней)")
    
    return "\n".join(lines)


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
    
    logger.info(f"fetch_historical_data_cached: secid={secid}, days={days}, start_date={start_date}")
    
    # Проверяем наличие данных в БД
    db_df = db.load_daily_ytm(secid, start_date=start_date)
    last_db_date = db.get_last_daily_ytm_date(secid)
    
    logger.info(f"Загружено из БД: {len(db_df)} записей, last_db_date={last_db_date}")
    
    # Проверяем покрытие периода (как в fetch_candle_data_cached)
    need_reload = False
    if not db_df.empty:
        db_min_date = db_df.index.min().date() if hasattr(db_df.index.min(), 'date') else db_df.index.min()
        if db_min_date > start_date:
            need_reload = True
            logger.info(f"Данные в БД начинаются с {db_min_date}, нужно с {start_date} - перезагружаем")
    
    if not db_df.empty and last_db_date and not need_reload:
        days_since_update = (date.today() - last_db_date).days
        
        if days_since_update <= 1:
            logger.info(f"Загружены дневные YTM из БД для {secid}: {len(db_df)} записей")
            # Фильтруем по запрошенному периоду
            db_df = db_df[db_df.index.date >= start_date]
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
    elif need_reload:
        # Данных недостаточно - дозагружаем недостающий период
        # db_min_date уже вычислен выше
        db_min_date = db_df.index.min().date() if hasattr(db_df.index.min(), 'date') else db_df.index.min()
        
        # Загружаем только недостающий период (от start_date до db_min_date - 1 день)
        history_end = db_min_date - timedelta(days=1)
        logger.info(f"Дозагружаем период с {start_date} по {history_end}")
        
        new_df = fetcher.fetch_ytm_history(secid, start_date=start_date, end_date=history_end)
        
        logger.info(f"Загружено с MOEX: {len(new_df)} записей")
        
        if not new_df.empty:
            db.save_daily_ytm(secid, new_df)
            # Объединяем: старые данные + новые
            db_df = pd.concat([new_df, db_df])
            db_df = db_df[~db_df.index.duplicated(keep='last')]
            logger.info(f"Дозагружены дневные YTM для {secid}: +{len(new_df)} записей, всего {len(db_df)}")
    else:
        # БД пуста - загружаем весь период
        db_df = fetcher.fetch_ytm_history(secid, start_date=start_date)
        
        if not db_df.empty:
            db.save_daily_ytm(secid, db_df)
            logger.info(f"Сохранены дневные YTM в БД для {secid}: {len(db_df)} записей")
    
    # Фильтруем по запрошенному периоду перед возвратом
    if not db_df.empty:
        db_df = db_df[db_df.index.date >= start_date]
    
    logger.info(f"Возвращаем: {len(db_df)} записей для периода {days} дней")
    
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
    
    # Проверяем нужно ли обновить историю
    # Условия: 1) БД пуста ИЛИ 2) данных меньше чем нужно (по датам)
    need_history = False
    history_start = start_date  # По умолчанию загружаем весь период
    
    if days > 1:
        if db_ytm_df.empty:
            need_history = True
        else:
            # Проверяем покрытие периода
            db_min_date = db_ytm_df.index.min().date() if hasattr(db_ytm_df.index.min(), 'date') else db_ytm_df.index.min()
            if db_min_date > start_date:
                need_history = True
                # ОПТИМИЗАЦИЯ: загружаем только недостающий период
                history_start = start_date
                history_end = db_min_date - timedelta(days=1)
                logger.info(f"Данные в БД с {db_min_date}, нужно с {start_date} - дозагружаем")
    
    if need_history:
        # Если БД не пуста, дозагружаем только недостающий период
        if not db_ytm_df.empty:
            history_df = fetcher.fetch_candles(
                isin,
                bond_config=bond_config,
                interval=candle_interval,
                start_date=history_start,
                end_date=history_end
            )
            
            if not history_df.empty and 'ytm_close' in history_df.columns:
                # Добавляем к существующим данным (не удаляем!)
                db.save_intraday_ytm(isin, interval, history_df)
                db_ytm_df = pd.concat([history_df, db_ytm_df])
                db_ytm_df = db_ytm_df[~db_ytm_df.index.duplicated(keep='last')]
                logger.info(f"Дозагружены intraday YTM для {isin}: {len(history_df)} записей")
        else:
            # БД пуста - загружаем весь период
            history_df = fetcher.fetch_candles(
                isin,
                bond_config=bond_config,
                interval=candle_interval,
                start_date=start_date,
                end_date=date.today() - timedelta(days=1)
            )
            
            if not history_df.empty and 'ytm_close' in history_df.columns:
                db.save_intraday_ytm(isin, interval, history_df)
                db_ytm_df = history_df
                logger.info(f"Сохранены intraday YTM в БД для {isin}: {len(history_df)} записей")
    
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
            button_pressed = st.button(button_label, use_container_width=True, type="primary")
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
            button_pressed = st.button(button_label, use_container_width=True, type="secondary")
        else:
            button_pressed = st.button(button_label, use_container_width=True, type="secondary")
        
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
    # АНАЛИЗ КОИНТЕГРАЦИИ (фоновый запуск)
    # ==========================================
    if st.session_state.get('cointegration_needs_update', False):
        favorite_isins = st.session_state.get('cointegration_favorites', [])
        if len(favorite_isins) >= 2:
            with st.spinner("Анализ коинтеграции пар..."):
                results = run_cointegration_analysis_for_favorites(favorite_isins)
                st.session_state.cointegration_results = results
                st.session_state.cointegration_needs_update = False
                logger.info(f"Анализ коинтеграции завершён: {len(results)} пар")
    
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
    # ОТОБРАЖЕНИЕ РЕЗУЛЬТАТОВ КОИНТЕГРАЦИИ
    # ==========================================
    # Получаем результат для текущей пары из БД
    db = get_db()
    coint_result = db.load_cointegration_result(bond1.isin, bond2.isin)
    
    # Проверяем, нужен ли перерасчёт (период изменился)
    needs_refresh = False
    if coint_result:
        cached_days = coint_result.get('data_days', 0)
        # Если текущий период значительно отличается от кэшированного (>30 дней разницы)
        if abs(period - cached_days) > 30:
            needs_refresh = True
    
    # Кнопка обновления (показываем если есть результат)
    col_status, col_btn = st.columns([4, 1])
    
    with col_status:
        if coint_result:
            status_html = get_cointegration_status_html(coint_result, bond1.name, bond2.name)
            st.markdown(f"""
            <div style="margin-bottom: 8px;">
                {status_html}
            </div>
            """, unsafe_allow_html=True)
    
    with col_btn:
        if coint_result:
            btn_label = "🔄 Обновить" if needs_refresh else "↻ Обновить"
            if st.button(btn_label, key="refresh_cointegration", help="Пересчитать коинтеграцию за текущий период"):
                with st.spinner("Пересчёт коинтеграции..."):
                    new_result = run_single_cointegration_analysis(bond1.isin, bond2.isin, period)
                    if new_result:
                        st.success("✅ Обновлено!")
                        st.rerun()
                    else:
                        st.error("Ошибка при расчёте")
    
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
    st.plotly_chart(fig_analytics, use_container_width=True, key=chart_key)
    
    # Легенда сигналов
    st.markdown("""
    **Сигналы:** 🟢 BUY (спред < -{threshold}σ) | 🔴 SELL (спред > +{threshold}σ) | ⚪ Neutral
    
    **Интерпретация:**
    - BUY: спред аномально низкий → ожидается расширение (покупаем длинную, продаём короткую)
    - SELL: спред аномально высокий → ожидается сужение (продаём длинную, покупаем короткую)
    """.format(threshold=st.session_state.z_threshold))
    
    # ==========================================
    # ПОДРОБНОСТИ АНАЛИЗА (ADF)
    # ==========================================
    with st.expander("📊 Подробности анализа (ADF)"):
        if coint_result:
            st.markdown(format_cointegration_details(coint_result, bond1.name, bond2.name))
        else:
            st.info("Нет данных коинтеграции для текущей пары. Результаты появятся после фонового анализа всех пар избранного.")
    
    st.divider()
    
    # График 2: YTM склеенный (история + свечи)
    fig2 = create_combined_ytm_chart(
        daily_df1, daily_df2,
        intraday_df1, intraday_df2,
        bond1.name, bond2.name,
        candle_days=candle_days
    )
    chart_key2 = f"combined_ytm_{period}_{candle_days}_{bond1.isin}_{bond2.isin}_{len(daily_df1)}_{len(intraday_df1)}"
    st.plotly_chart(fig2, use_container_width=True, key=chart_key2)
    
    # График 3: Спред intraday (с перцентилями от дневных данных)
    fig3 = create_intraday_spread_chart(
        intraday_spread_df,
        daily_stats=daily_stats  # Перцентили от дневных!
    )
    chart_key3 = f"intraday_spread_{candle_days}_{bond1.isin}_{bond2.isin}_{len(intraday_spread_df)}"
    st.plotly_chart(fig3, use_container_width=True, key=chart_key3)
    
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
