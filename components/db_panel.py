"""
Компонент панели управления базой данных

Содержит статистику БД и кнопки управления.
"""
import streamlit as st
from typing import Dict, List
from datetime import date, timedelta


def render_db_stats(db_stats: Dict):
    """Рендерит статистику БД"""
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


def update_database_full(bonds_list: List = None, progress_callback=None) -> Dict:
    """
    Полное обновление базы данных
    
    Загружает:
    - Дневные YTM для всех облигаций (1 год)
    - Intraday YTM для всех облигаций и интервалов
    
    Args:
        bonds_list: Список облигаций (если None - из session_state)
        progress_callback: Функция для отчёта о прогрессе
    
    Returns:
        Статистика обновления
    """
    from api.moex_candles import CandleInterval
    from api.moex_history import HistoryFetcher
    from api.moex_candles import CandleFetcher
    from core.database import get_db
    from components.sidebar import get_bonds_list
    import logging
    
    logger = logging.getLogger(__name__)
    
    fetcher = HistoryFetcher()
    candle_fetcher = CandleFetcher()
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
    
    # Закрываем соединения
    fetcher.close()
    candle_fetcher.close()
    
    return stats


def render_db_panel():
    """Рендерит панель управления БД"""
    from core.database import get_db
    
    st.subheader("🗄️ База данных")
    
    db = get_db()
    db_stats = db.get_stats()
    
    # Статистика
    render_db_stats(db_stats)
    
    # Кнопка обновления БД
    if st.button("🔄 Обновить БД", help="Загрузить все данные с MOEX и сохранить в БД"):
        st.session_state.updating_db = True
    
    # Процесс обновления
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
                    for err in result['errors'][:10]:
                        st.warning(err)
            
            st.session_state.updating_db = False
            st.cache_data.clear()
            
        except Exception as e:
            st.error(f"Ошибка обновления БД: {e}")
            st.session_state.updating_db = False
    
    st.divider()
    
    # Очистка кэша
    if st.button("🗑️ Очистить кэш и обновить"):
        st.cache_data.clear()
        st.rerun()
