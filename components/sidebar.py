"""
Компонент боковой панели v0.3.0

Содержит все элементы управления в sidebar для unified 4-chart layout.
"""
import streamlit as st
from typing import List, Dict, Any, Tuple, Callable, Optional
from datetime import datetime

from config import CANDLE_INTERVAL_CONFIG


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
            self.day_count_convention = data.get('day_count_convention') or data.get('day_count', 'ACT/ACT')
    
    return [BondItem(bond_data) for bond_data in bonds_dict.values()]


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


def render_period_selector() -> int:
    """
    Рендерит слайдер выбора периода (единственный для всех графиков)
    
    Returns:
        Выбранный период в днях
    """
    st.subheader("📅 Период")
    
    period = st.slider(
        "Период анализа (дней)",
        min_value=30,
        max_value=730,
        value=st.session_state.period,
        step=30,
        format="%d дней"
    )
    st.session_state.period = period
    
    return period


def render_candle_interval_selector() -> str:
    """
    Рендерит radio-селектор интервала свечей для графиков 3+4
    
    Returns:
        Выбранный интервал ('1', '10', '60')
    """
    st.subheader("⏱️ Интервал свечей")
    
    interval_options = {
        "1": "1 мин",
        "10": "10 мин", 
        "60": "1 час"
    }
    
    candle_interval = st.radio(
        "Интервал для графиков 3+4",
        options=["1", "10", "60"],
        format_func=lambda x: interval_options[x],
        index=["1", "10", "60"].index(st.session_state.candle_interval),
        horizontal=True,
        label_visibility="collapsed"
    )
    st.session_state.candle_interval = candle_interval
    
    return candle_interval


def render_candle_period_selector(
    candle_interval: str,
    analysis_period: int
) -> int:
    """
    Рендерит слайдер периода свечей с динамическими ограничениями
    
    Args:
        candle_interval: Выбранный интервал свечей ('1', '10', '60')
        analysis_period: Период анализа (ограничивает максимум)
    
    Returns:
        Выбранный период свечей в днях
    """
    st.subheader("📊 Период свечей")
    
    config = CANDLE_INTERVAL_CONFIG[candle_interval]
    
    # Динамический максимум: минимум из настройки и периода анализа
    max_days = min(config["max_days"], analysis_period)
    min_days = config["min_days"]
    
    # Если максимум меньше минимума, корректируем
    if max_days < min_days:
        max_days = min_days
    
    # Значение по умолчанию - минимум
    default_days = min_days
    current_value = st.session_state.get('candle_days', default_days)
    
    # Корректируем текущее значение если оно вне диапазона
    if current_value < min_days or current_value > max_days:
        current_value = min_days
    
    # Форматирование для отображения
    def format_days(x):
        if x == 1:
            return "1 день"
        elif 2 <= x <= 4:
            return f"{x} дня"
        elif x >= 5:
            return f"{x} дней"
        return f"{x}"
    
    candle_days = st.slider(
        "Период свечей (дней)",
        min_value=min_days,
        max_value=max_days,
        value=current_value,
        step=config["step_days"],
        format=format_days
    )
    
    st.session_state.candle_days = candle_days
    
    # Пояснение
    st.caption(f"Макс. {config['max_days']} дн. для {config['name']} (ограничен периодом анализа: {analysis_period} дн.)")
    
    return candle_days


def render_auto_refresh() -> bool:
    """
    Рендерит настройки автообновления
    
    Returns:
        Включено ли автообновление
    """
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
    
    return auto_refresh


def render_db_panel(
    db_stats: Dict[str, int],
    on_update_db: Optional[Callable] = None
):
    """
    Рендерит панель управления базой данных
    
    Args:
        db_stats: Статистика БД (bonds_count, daily_ytm_count, intraday_ytm_count)
        on_update_db: Callback функция для обновления БД
    """
    st.subheader("🗄️ База данных")
    
    with st.expander("📊 Статистика БД", expanded=False):
        st.write(f"**Облигаций:** {db_stats.get('bonds_count', 0)}")
        st.write(f"**Дневных YTM:** {db_stats.get('daily_ytm_count', 0)}")
        st.write(f"**Intraday YTM:** {db_stats.get('intraday_ytm_count', 0)}")
    
    if st.button("🔄 Обновить БД", use_container_width=True):
        st.session_state.updating_db = True
    
    if st.session_state.get('updating_db', False):
        st.info("Обновление БД...")
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        if on_update_db:
            def update_progress(progress, message):
                progress_bar.progress(progress)
                status_text.text(message)
            
            try:
                result = on_update_db(progress_callback=update_progress)
                progress_bar.progress(1.0)
                status_text.text("Готово!")
                st.success(f"✅ Дневных: {result.get('daily_ytm_saved', 0)}, Intraday: {result.get('intraday_ytm_saved', 0)}")
                st.session_state.updating_db = False
                st.cache_data.clear()
            except Exception as e:
                st.error(f"Ошибка: {e}")
                st.session_state.updating_db = False


def render_cache_clear():
    """Рендерит кнопку очистки кэша"""
    if st.button("🗑️ Очистить кэш", use_container_width=True):
        st.cache_data.clear()
        st.rerun()


def render_sidebar(
    bonds: List,
    bond_trading_data: Dict[str, Dict],
    fetch_trading_data_func: Callable,
    db_stats: Dict[str, int],
    on_update_db: Optional[Callable] = None
) -> Tuple[int, int, int, str, int, bool]:
    """
    Рендерит полную боковую панель
    
    Args:
        bonds: Список облигаций
        bond_trading_data: Данные торгов по ISIN (заполняется внутри)
        fetch_trading_data_func: Функция для получения торговых данных
        db_stats: Статистика БД
        on_update_db: Callback для обновления БД
    
    Returns:
        Кортеж (bond1_idx, bond2_idx, period, candle_interval, candle_days, auto_refresh)
    """
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
    
    for b in bonds:
        data = fetch_trading_data_func(b.isin)
        bond_trading_data[b.isin] = data
        if data.get('has_data') and data.get('yield'):
            bond_labels.append(format_bond_label(b, data['yield'], data.get('duration_years')))
        else:
            bond_labels.append(format_bond_label(b))
    
    # Выбор облигаций
    bond1_idx, bond2_idx = render_bond_selection(bonds, bond_trading_data)
    
    st.divider()
    
    # Период анализа
    period = render_period_selector()
    
    st.divider()
    
    # Интервал свечей (radio)
    candle_interval = render_candle_interval_selector()
    
    # Период свечей (слайдер с динамическими ограничениями)
    candle_days = render_candle_period_selector(candle_interval, period)
    
    st.divider()
    
    # Автообновление
    auto_refresh = render_auto_refresh()
    
    st.divider()
    
    # Панель БД
    render_db_panel(db_stats, on_update_db)
    
    st.divider()
    
    # Очистка кэша
    render_cache_clear()
    
    return bond1_idx, bond2_idx, period, candle_interval, candle_days, auto_refresh
