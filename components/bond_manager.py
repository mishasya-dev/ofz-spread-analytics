"""
Компонент выбора инструментов для анализа

Модальное окно для выбора облигаций (версия 0.2.2)

Логика:
- Загружаем список с MOEX API (не из БД)
- Галочки = избранное (хранится в session_state до нажатия "Готово")
- "Готово" = INSERT новых + DELETE убранных в БД
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


@st.dialog("Выбор инструментов для анализа", width="large")
def show_bond_manager_dialog():
    """
    Модальное окно для выбора облигаций

    Логика:
    - Загружаем список с MOEX API (не из БД)
    - Галочки = избранное (хранится в session_state)
    - "Готово" = INSERT новых + DELETE убранных в БД
    - "Отменить" = закрыть без сохранения
    """
    db = get_bond_manager()

    # ========================================
    # ЗАГОЛОВОК + КНОПКА "ОБНОВИТЬ"
    # ========================================
    col_title, col_refresh = st.columns([4, 1])
    with col_title:
        st.markdown("### 📊 Список ОФЗ для торговли")
    with col_refresh:
        if st.button("🔄 Обновить", width="stretch"):
            st.session_state.bond_manager_reload = True
            # Очищаем DataFrame для пересоздания с новыми данными
            if 'bond_manager_df' in st.session_state:
                del st.session_state['bond_manager_df']
            # Очищаем состояние data_editor
            if 'bonds_table_editor' in st.session_state:
                del st.session_state['bonds_table_editor']
            # Генерируем новый UUID, но НЕ сбрасываем last_shown_id
            # Тогда при rerun: open_id != last_shown_id → диалог откроется
            st.session_state.bond_manager_open_id = str(uuid.uuid4())
            st.rerun()

    st.markdown("""
    **Фильтры применены:**
    - ОФЗ-ПД (26xxx, 25xxx, 24xxx серии)
    - Срок до погашения > 0.5 года
    - Торги за последние 10 дней
    - Наличие дюрации
    """)

    # ========================================
    # ЗАГРУЗКА ДАННЫХ С MOEX
    # ========================================
    if 'bond_manager_bonds' not in st.session_state or st.session_state.get('bond_manager_reload', False):
        with st.spinner("Загрузка с MOEX API..."):
            fetcher = get_moex_fetcher()
            try:
                all_bonds = fetcher.fetch_ofz_with_market_data(include_details=False)
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

    # ========================================
    # УПРАВЛЕНИЕ СОСТОЯНИЕМ ГАЛОЧЕК (session_state)
    # ========================================
    # Инициализация при первом открытии или после "Готово/Отменить"
    if st.session_state.get('bond_manager_current_favorites') is None:
        st.session_state.bond_manager_current_favorites = set(
            b.get('isin') for b in db.get_favorite_bonds()
        )

    # Сохраняем исходное состояние для сравнения при "Готово"
    if st.session_state.get('bond_manager_original_favorites') is None:
        st.session_state.bond_manager_original_favorites = set(
            b.get('isin') for b in db.get_favorite_bonds()
        )

    current_favorites = st.session_state.bond_manager_current_favorites or set()
    original_favorites = st.session_state.bond_manager_original_favorites or set()

    # ========================================
    # ВОССТАНОВЛЕНИЕ СОСТОЯНИЯ ЧЕКБОКСОВ
    # ========================================
    # КРИТИЧЕСКИ ВАЖНО: если data_editor уже рендерился в этой сессии,
    # берём состояние чекбоксов из session_state["bonds_table_editor"]
    # Это происходит ДО создания DataFrame!
    if "bonds_table_editor" in st.session_state:
        prev_state = st.session_state["bonds_table_editor"]
        if prev_state is not None and hasattr(prev_state, 'columns') and '⭐' in prev_state.columns:
            # Обновляем current_favourites из предыдущего состояния
            current_favorites = set(prev_state[prev_state['⭐']]['ISIN'])
            st.session_state.bond_manager_current_favorites = current_favorites

    # ========================================
    # СТРОКА С ИНФОРМАЦИЕЙ + КНОПКА "ОЧИСТИТЬ"
    # ========================================
    load_time = st.session_state.get('bond_manager_bonds_time', '')
    
    col_info, col_clear = st.columns([4, 1])
    with col_info:
        st.info(f"⭐ Избранных: **{len(current_favorites)}** | Всего: **{len(bonds)}** | Загружено: {load_time}")
    with col_clear:
        if st.button("🗑️ Очистить", width="stretch"):
            # Очищаем текущий набор (без сохранения в БД)
            st.session_state.bond_manager_current_favorites = set()
            # Удаляем DataFrame чтобы пересоздать с очищенными чекбоксами
            if 'bond_manager_df' in st.session_state:
                del st.session_state.bond_manager_df
            # Очищаем состояние data_editor
            if "bonds_table_editor" in st.session_state:
                del st.session_state["bonds_table_editor"]
            # Генерируем новый UUID для reopen диалога (НЕ сбрасываем last_shown_id)
            st.session_state.bond_manager_open_id = str(uuid.uuid4())
            st.rerun()

    # ========================================
    # ТАБЛИЦА С ГАЛОЧКАМИ
    # ========================================
    # КЛЮЧЕВОЕ ИЗМЕНЕНИЕ: храним DataFrame в session_state и не пересоздаём
    # Это позволяет st.data_editor сохранять состояние чекбоксов между rerun

    need_create_df = False

    # Проверяем, нужно ли создать DataFrame заново
    if 'bond_manager_df' not in st.session_state:
        need_create_df = True
    elif st.session_state.get('bond_manager_reload', False):
        need_create_df = True
    # Проверяем, что ISIN в DataFrame совпадают с загруженными bonds
    elif 'bond_manager_df' in st.session_state:
        existing_df = st.session_state.bond_manager_df
        if existing_df is None or not hasattr(existing_df, 'columns'):
            need_create_df = True
        else:
            existing_isins = set(existing_df['ISIN'].tolist())
            loaded_isins = set(b.get('isin') for b in bonds)
            if existing_isins != loaded_isins:
                need_create_df = True

    if need_create_df:
        # Создаём DataFrame
        df_data = []
        for b in bonds:
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
                "⭐": b.get("isin") in current_favorites,
            })

        df = pd.DataFrame(df_data)

        # Сортируем по дюрации (стабильный порядок, не зависящий от чекбоксов)
        df = df.sort_values(by=["Дюрация, лет"], ascending=True, na_position="last")
        df = df.reset_index(drop=True)

        # Сохраняем в session_state
        st.session_state.bond_manager_df = df

        # Очищаем старое состояние data_editor при создании нового DataFrame
        if "bonds_table_editor" in st.session_state:
            del st.session_state["bonds_table_editor"]

    # Используем DataFrame из session_state
    df = st.session_state.bond_manager_df

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
        width="stretch",
        num_rows="fixed",
        key="bonds_table_editor",
    )
    
    # ========================================
    # СИНХРОНИЗАЦИЯ ГАЛОЧЕК С session_state
    # ========================================
    # Читаем текущее состояние из edited_df и сохраняем в session_state
    new_favorites_from_ui = set(edited_df[edited_df["⭐"]]["ISIN"])
    if new_favorites_from_ui != current_favorites:
        st.session_state.bond_manager_current_favorites = new_favorites_from_ui
        current_favorites = new_favorites_from_ui

    # ========================================
    # КНОПКИ ДЕЙСТВИЙ
    # ========================================
    st.divider()
    col_cancel, col_done = st.columns([1, 1])

    with col_cancel:
        if st.button("❌ Отменить и закрыть", width="stretch"):
            # Очищаем состояние
            st.session_state.bond_manager_open_id = None
            st.session_state.bond_manager_last_shown_id = None
            st.session_state.bond_manager_current_favorites = None
            st.session_state.bond_manager_original_favorites = None
            # Очищаем DataFrame и состояние data_editor
            if 'bond_manager_df' in st.session_state:
                del st.session_state['bond_manager_df']
            if "bonds_table_editor" in st.session_state:
                del st.session_state["bonds_table_editor"]
            st.rerun()

    with col_done:
        if st.button("✅ Готово", width="stretch", type="primary"):
            # Синхронизируем с БД
            new_favorites = current_favorites or set()
            old_favorites = original_favorites or set()
            
            # INSERT новых
            to_add = new_favorites - old_favorites
            # DELETE убранных
            to_remove = old_favorites - new_favorites
            
            added_count = 0
            removed_count = 0
            
            # Добавляем новые в БД
            for isin in to_add:
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
            
            # Очищаем состояние
            st.session_state.bond_manager_open_id = None
            st.session_state.bond_manager_last_shown_id = None
            st.session_state.bond_manager_current_favorites = None
            st.session_state.bond_manager_original_favorites = None
            # Очищаем DataFrame и состояние data_editor
            if 'bond_manager_df' in st.session_state:
                del st.session_state['bond_manager_df']
            if "bonds_table_editor" in st.session_state:
                del st.session_state["bonds_table_editor"]
            st.session_state.cached_favorites_count = len(new_favorites)
            
            # Показываем результат и закрываем
            if added_count or removed_count:
                st.toast(f"✅ Добавлено: {added_count}, Убрано: {removed_count}")
            st.rerun()


def render_bond_manager_button():
    """
    Кнопка для открытия модального окна выбора инструментов

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
    if st.button("📊 Выбор инструментов для анализа", width="stretch"):
        # Генерируем новый ID для этого открытия
        st.session_state.bond_manager_open_id = str(uuid.uuid4())
        # Сбрасываем состояние галочек для нового открытия
        st.session_state.bond_manager_current_favorites = None
        st.session_state.bond_manager_original_favorites = None
        # Очищаем DataFrame для пересоздания
        if 'bond_manager_df' in st.session_state:
            del st.session_state['bond_manager_df']
        # Очищаем состояние data_editor
        if 'bonds_table_editor' in st.session_state:
            del st.session_state['bonds_table_editor']
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
