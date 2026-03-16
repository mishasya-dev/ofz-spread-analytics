"""
Компонент боковой панели v0.3.0

Содержит все элементы управления в sidebar для unified 4-chart layout.
"""
import streamlit as st
from typing import List, Dict, Any, Tuple, Callable, Optional

from config import CANDLE_INTERVAL_CONFIG
from utils.bond_utils import BondItem, get_years_to_maturity, format_bond_label, get_bonds_list as get_bonds_list_from_dict
from utils.action_logger import log_widget_change, log_button_press
from components.styles import apply_validation_button_style


def get_bonds_list() -> List[BondItem]:
    """
    Получить список облигаций для отображения

    Returns:
        Список объектов BondItem
    """
    bonds_dict = st.session_state.get('bonds', {})
    return get_bonds_list_from_dict(bonds_dict)


def render_bond_selection(
    bonds: List[BondItem],
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
        key="selected_bond1"
    )

    bond2_idx = st.selectbox(
        "Облигация 2",
        range(len(bonds)),
        format_func=lambda i: bond_labels[i],
        key="selected_bond2"
    )

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
        key="period",
        step=30,
        format="%d дней"
    )

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
        key="candle_interval",
        horizontal=True,
        label_visibility="collapsed"
    )

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

    # Если максимум меньше или равен минимуму, корректируем
    # (слайдер требует min < max)
    if max_days <= min_days:
        min_days = max(1, max_days - 1)

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


def render_auto_refresh() -> Tuple[bool, bool]:
    """
    Рендерит настройки автообновления

    Returns:
        auto_refresh: Включено ли автообновление
        skip_candles: Пропускать загрузку свечей при auto-refresh
    """
    st.subheader("🔄 Автообновление")

    auto_refresh = st.toggle(
        "Включить",
        key="auto_refresh"
    )

    skip_candles = False
    if auto_refresh:
        refresh_interval = st.slider(
            "Интервал (сек)",
            min_value=30,
            max_value=300,
            key="refresh_interval",
            step=30
        )

        skip_candles = st.checkbox(
            "Быстрое обновление (без свечей)",
            value=False,
            key="skip_candles",
            help="При включении загружаются только текущие котировки без свечей"
        )

        if st.session_state.last_update:
            st.caption(f"Последнее: {st.session_state.last_update.strftime('%H:%M:%S')}")

    return auto_refresh, skip_candles


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

    if st.button("🔄 Обновить БД", width="stretch"):
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
    if st.button("🗑️ Очистить кэш", width="stretch"):
        st.cache_data.clear()
        st.rerun()


def render_spread_analytics_settings() -> Tuple[int, float]:
    """
    Рендерит настройки Spread Analytics (window, z_threshold)
    
    Returns:
        Кортеж (spread_window, z_threshold)
    """
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
    
    return spread_window, z_threshold


def render_g_spread_settings() -> Tuple[int, int, float]:
    """
    Рендерит настройки G-Spread Analytics
    
    Returns:
        Кортеж (g_spread_period, g_spread_window, g_spread_z_threshold)
    """
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
    
    return g_spread_period, g_spread_window, g_spread_z_threshold


def render_ytm_validation(
    bonds: List[BondItem],
    bond1_idx: int,
    bond2_idx: int,
    candle_interval: str
):
    """
    Рендерит UI валидации YTM
    
    Логика валидации находится в core/db/ytm_repo.py:validate_ytm_accuracy()
    Эта функция только отображает UI.
    
    Args:
        bonds: Список облигаций
        bond1_idx: Индекс первой облигации
        bond2_idx: Индекс второй облигации
        candle_interval: Интервал свечей
    """
    from core.db import get_ytm_repo
    
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
    apply_validation_button_style(button_color)
    
    if button_color == "green":
        button_pressed = st.button(button_label, width="stretch", type="primary")
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


def render_sidebar(
    bonds: List[BondItem],
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


__all__ = [
    'get_bonds_list',
    'render_bond_selection',
    'render_period_selector',
    'render_spread_analytics_settings',
    'render_g_spread_settings',
    'render_ytm_validation',
    'render_candle_interval_selector',
    'render_candle_period_selector',
    'render_auto_refresh',
    'render_db_panel',
    'render_cache_clear',
    'render_sidebar',
]
