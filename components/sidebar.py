"""
Компонент боковой панели

Содержит все элементы управления в sidebar.
"""
import streamlit as st
from typing import List, Dict, Any, Tuple
from datetime import date, timedelta


def get_bonds_list() -> List:
    """
    Получить список облигаций для отображения
    
    Returns:
        Список объектов BondItem
    """
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


def get_years_to_maturity(maturity_str: str) -> float:
    """Вычисляет годы до погашения"""
    from datetime import datetime
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


def render_bond_selection(
    bonds: List,
    bond_trading_data: Dict[str, Dict]
) -> Tuple[int, int]:
    """
    Рендерит селекторы выбора облигаций
    
    Args:
        bonds: Список облигаций
        bond_trading_data: Данные торгов по ISIN
    
    Returns:
        Кортеж (bond1_idx, bond2_idx)
    """
    bond_labels = []
    
    for b in bonds:
        data = bond_trading_data.get(b.isin, {})
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
    
    return bond1_idx, bond2_idx


def render_period_selector(data_mode: str, candle_interval: str = "60") -> int:
    """
    Рендерит селектор периода
    
    Args:
        data_mode: 'daily' или 'intraday'
        candle_interval: Интервал свечей
    
    Returns:
        Выбранный период в днях
    """
    if data_mode == "daily":
        period = st.radio(
            "Период анализа",
            [365, 730],
            format_func=lambda x: f"{x // 365} год(а)",
            index=0 if st.session_state.period == 365 else 1
        )
        st.session_state.period = period
    else:
        # Для внутридневного режима
        interval_limits = {
            "1": {"max": 3, "default": 1},
            "10": {"max": 30, "default": 7},
            "60": {"max": 365, "default": 30},
        }
        
        limits = interval_limits.get(candle_interval, {"max": 30, "default": 7})
        
        period = st.slider(
            f"Дней истории (макс {limits['max']} для {candle_interval} мин)",
            min_value=1,
            max_value=limits['max'],
            value=min(st.session_state.get('intraday_period', limits['default']), limits['max']),
            step=1
        )
        st.session_state.intraday_period = period
    
    return period


def render_auto_refresh(data_mode: str):
    """Рендерит настройки автообновления"""
    st.subheader("🔄 Автообновление")
    
    auto_refresh = st.toggle(
        "Включить автообновление",
        value=st.session_state.auto_refresh
    )
    st.session_state.auto_refresh = auto_refresh
    
    if auto_refresh:
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
            from datetime import datetime
            st.caption(f"Последнее обновление: {st.session_state.last_update.strftime('%H:%M:%S')}")


def render_intraday_options():
    """Рендерит опции для intraday режима"""
    st.divider()
    st.subheader("💾 Сохранение данных")
    
    from core.database import get_saved_data_info, cleanup_old_data
    
    save_data = st.toggle(
        "Сохранять снимки данных",
        value=st.session_state.save_data,
        help="Сохраняет текущие YTM и спред каждые N секунд"
    )
    st.session_state.save_data = save_data
    
    if st.session_state.saved_count > 0:
        st.caption(f"Сохранено снимков: {st.session_state.saved_count}")
    
    with st.expander("📁 Сохранённые данные"):
        info = get_saved_data_info()
        st.write(f"Всего файлов: {info['total_files']}")
        if info['newest']:
            st.write(f"Последние данные: {info['newest']}")
        
        if st.button("🗑️ Очистить старые данные", key="cleanup_data"):
            cleanup_old_data(days_to_keep=7)
            st.success("Старые данные удалены!")
