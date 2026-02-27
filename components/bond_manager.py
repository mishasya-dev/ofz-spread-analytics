"""
Компонент управления облигациями

Модальное окно для выбора избранных облигаций (версия 0.2.2)

Логика:
- Загружаем список с MOEX API (не из БД)
- Галочки = избранное (сравниваем с БД)
- Изменения только в памяти
- "Готово" = INSERT новых + DELETE убранных
- "Отменить" = закрыть без сохранения
"""
import streamlit as st
import pandas as pd
import requests
import uuid
from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


def get_bond_manager():
    """Получить менеджер БД"""
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from core.database import get_db
    return get_db()


def get_moex_fetcher():
    """Получить fetcher для MOEX"""
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from api.moex_bonds import MOEXBondsFetcher
    return MOEXBondsFetcher()


@st.dialog("Управление облигациями", width="large")
def show_bond_manager_dialog():
    """
    Модальное окно для управления списком облигаций

    Логика:
    - Загружаем список с MOEX API (не из БД)
    - Галочки = избранное (сравниваем с БД)
    - Изменения только в памяти
    - "Готово" = INSERT новых + DELETE убранных
    - "Отменить" = закрыть без сохранения
    """
    db = get_bond_manager()

    # Заголовок с информацией
    st.markdown("""
    ### 📊 Список ОФЗ для торговли
    
    **Фильтры применены:**
    - ОФЗ-ПД (26xxx, 25xxx, 24xxx серии)
    - Срок до погашения > 0.5 года
    - Торги за последние 10 дней
    - Наличие дюрации
    """)

    # Загружаем список облигаций с MOEX
    if 'bond_manager_bonds' not in st.session_state or st.session_state.get('bond_manager_reload', False):
        with st.spinner("Загрузка с MOEX API..."):
            fetcher = get_moex_fetcher()
            try:
                # Получаем все ОФЗ с рыночными данными
                all_bonds = fetcher.fetch_ofz_with_market_data(include_details=False)
                
                # Фильтруем
                from api.moex_bonds import filter_ofz_for_trading
                filtered_bonds = filter_ofz_for_trading(all_bonds)
                
                st.session_state.bond_manager_bonds = filtered_bonds
                st.session_state.bond_manager_reload = False
                st.session_state.bond_manager_bonds_time = datetime.now().strftime('%H:%M:%S')
            except Exception as e:
                st.error(f"Ошибка загрузки: {e}")
                return
            finally:
                fetcher.close()
    
    bonds = st.session_state.bond_manager_bonds
    
    if not bonds:
        st.warning("Нет облигаций. Проверьте соединение с MOEX.")
        return

    # Получаем список избранных из БД (только ISIN)
    original_favorites = set(b.get('isin') for b in db.get_favorite_bonds())
    favorite_isins = original_favorites.copy()  # Копия для модификации
    
    # Показываем счётчик
    load_time = st.session_state.get('bond_manager_bonds_time', '')
    st.info(f"⭐ Избранных: **{len(original_favorites)}** | Всего: **{len(bonds)}** | Загружено: {load_time}")

    # Проверяем флаг "очистить всё"
    clear_all_triggered = st.session_state.get('bond_manager_clear_all', False)
    if clear_all_triggered:
        st.session_state.bond_manager_clear_all = False  # Сбрасываем флаг
        favorite_isins = set()  # Временно пустой набор для отображения

    # Создаём DataFrame для data_editor
    df_data = []
    for b in bonds:
        # Вычисляем годы до погашения для отображения
        maturity_str = b.get("maturity_date", "")
        years_to_maturity = ""
        if maturity_str:
            try:
                maturity_dt = datetime.strptime(maturity_str, "%Y-%m-%d")
                years_to_maturity = round((maturity_dt - datetime.now()).days / 365.25, 1)
            except:
                pass

        df_data.append({
            "ISIN": b.get("isin"),
            "Название": b.get("name") or b.get("short_name") or b.get("isin"),
            "Купон, %": b.get("coupon_rate"),
            "Погашение": maturity_str,
            "До погаш., лет": years_to_maturity,
            "Дюрация, лет": b.get("duration_years"),
            "YTM, %": b.get("last_ytm"),
            "⭐": b.get("isin") in favorite_isins,
        })

    df = pd.DataFrame(df_data)
    
    # Сортируем: избранное первыми, потом по дюрации
    df = df.sort_values(by=["⭐", "Дюрация, лет"], ascending=[False, True], na_position="last")

    # Отображаем редактируемую таблицу
    edited_df = st.data_editor(
        df,
        column_config={
            "ISIN": st.column_config.TextColumn("ISIN", width="medium"),
            "Название": st.column_config.TextColumn("Название", width="medium"),
            "Купон, %": st.column_config.NumberColumn("Купон, %", format="%.2f%%", width="small"),
            "Погашение": st.column_config.TextColumn("Погашение", width="small"),
            "До погащ., лет": st.column_config.NumberColumn("До погащ., лет", format="%.1f", width="small"),
            "Дюрация, лет": st.column_config.NumberColumn("Дюрация, лет", format="%.1f", width="small"),
            "YTM, %": st.column_config.NumberColumn("YTM, %", format="%.2f%%", width="small"),
            "⭐": st.column_config.CheckboxColumn("⭐", default=False, width="tiny"),
        },
        hide_index=True,
        use_container_width=True,
        num_rows="fixed",
        key="bonds_table_editor",
    )
    
    # Кнопка "Очистить избранное" - снимает все галочки
    if st.button("🗑️ Очистить избранное", use_container_width=True):
        st.session_state.bond_manager_clear_all = True
        st.rerun()

    # Кнопки действий
    st.divider()
    col_done, col_cancel, col_refresh = st.columns([1, 1, 1])

    with col_done:
        if st.button("✅ Готово", use_container_width=True, type="primary"):
            # Синхронизируем с БД
            new_favorites = set(edited_df[edited_df["⭐"]]["ISIN"])
            old_favorites = original_favorites  # Сравниваем с исходным состоянием БД
            
            # INSERT новых
            to_add = new_favorites - old_favorites
            # DELETE убранных
            to_remove = old_favorites - new_favorites
            
            added_count = 0
            removed_count = 0
            
            # Добавляем новые в БД
            for isin in to_add:
                # Находим данные облигации
                bond_data = next((b for b in bonds if b.get('isin') == isin), None)
                if bond_data:
                    db.save_bond({
                        'isin': isin,
                        'name': bond_data.get('name') or bond_data.get('short_name') or isin,
                        'short_name': bond_data.get('short_name') or isin,
                        'coupon_rate': bond_data.get('coupon_rate'),
                        'maturity_date': bond_data.get('maturity_date'),
                        'issue_date': bond_data.get('issue_date'),
                        'face_value': bond_data.get('face_value', 1000),
                        'coupon_frequency': bond_data.get('coupon_frequency', 2),
                        'day_count': bond_data.get('day_count', 'ACT/ACT'),
                        'is_favorite': 1,
                        'last_price': bond_data.get('last_price'),
                        'last_ytm': bond_data.get('last_ytm'),
                        'duration_years': bond_data.get('duration_years'),
                        'duration_days': bond_data.get('duration_days'),
                    })
                    added_count += 1
            
            # Удаляем убранные из БД
            for isin in to_remove:
                db.delete_bond(isin)
                removed_count += 1
            
            # Обновляем кэш
            st.session_state.cached_favorites_count = len(new_favorites)
            st.session_state.bond_manager_open_id = None
            st.session_state.bond_manager_last_shown_id = None
            
            # Показываем результат и закрываем
            if added_count or removed_count:
                st.toast(f"✅ Добавлено: {added_count}, Убрано: {removed_count}")
            st.rerun()
    
    with col_cancel:
        if st.button("❌ Отменить и закрыть", use_container_width=True):
            st.session_state.bond_manager_open_id = None
            st.session_state.bond_manager_last_shown_id = None
            st.rerun()
    
    with col_refresh:
        if st.button("🔄 Обновить", use_container_width=True):
            st.session_state.bond_manager_reload = True
            st.rerun()


def render_bond_manager_button():
    """
    Кнопка для открытия модального окна управления облигациями

    Разместить в sidebar
    
    Логика управления диалогом:
    - bond_manager_open_id: уникальный ID для каждого открытия
    - bond_manager_last_shown_id: ID последнего показанного диалога
    - Если ID совпадают -> диалог уже показывали, не открываем снова
    """
    # Инициализируем состояние
    if 'bond_manager_open_id' not in st.session_state:
        st.session_state.bond_manager_open_id = None
    if 'bond_manager_last_shown_id' not in st.session_state:
        st.session_state.bond_manager_last_shown_id = None
    
    # Кнопка открытия
    if st.button("📊 Управление облигациями", use_container_width=True):
        # Генерируем новый ID для этого открытия
        st.session_state.bond_manager_open_id = str(uuid.uuid4())
        # Кэшируем количество избранных
        from core.database import get_db
        db = get_db()
        st.session_state.cached_favorites_count = len(db.get_favorite_bonds())
        st.rerun()
    
    # Проверяем нужно ли открыть диалог
    current_id = st.session_state.bond_manager_open_id
    last_shown = st.session_state.bond_manager_last_shown_id
    
    if current_id and current_id != last_shown:
        # Это новое открытие - показываем диалог
        st.session_state.bond_manager_last_shown_id = current_id
        show_bond_manager_dialog()
    # Если current_id == last_shown -> диалог уже показывали для этого ID
    # При следующем rerun диалог не откроется снова
