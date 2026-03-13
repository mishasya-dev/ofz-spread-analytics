"""
Компонент выбора инструментов для анализа

Модальное окно для выбора облигаций (версия 0.3.0)

Логика:
- Список ОФЗ кэшируется в БД (таблица bonds, метаданные в cache_metadata)
- TTL кэша: 24 часа
- Автообновление по расписанию или по кнопке
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

# Импортируем унифицированные функции логирования
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.action_logger import (
    log_widget_change, 
    log_button_press, 
    log_action,
    LogBlock
)


def get_bond_manager():
    """Получить менеджер БД"""
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from core.db import get_db_facade
    return get_db_facade()


def get_ofz_cache():
    """Получить кэш ОФЗ"""
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from core.ofz_cache import OFZCache
    return OFZCache()


@st.dialog("Выбор инструментов для анализа", width="large")
def show_bond_manager_dialog():
    """
    Модальное окно для выбора облигаций

    Логика:
    - Загружаем список из кэша БД (не напрямую с MOEX)
    - Если кэш устарел - фоновое обновление
    - Кнопка "Обновить" - принудительное обновление с MOEX
    - Галочки = избранное (хранится в session_state)
    - "Готово" = INSERT новых + DELETE убранных в БД
    - "Отменить" = закрыть без сохранения
    """
    db = get_bond_manager()
    cache = get_ofz_cache()

    # ========================================
    # ЗАГОЛОВОК + КНОПКА "ОБНОВИТЬ"
    # ========================================
    col_title, col_refresh = st.columns([4, 1])
    with col_title:
        st.markdown("### 📊 Список ОФЗ для торговли")
    with col_refresh:
        if st.button("🔄 Обновить", width="stretch"):
            log_button_press("Обновить список ОФЗ")
            st.session_state.bond_manager_reload = True
            # Очищаем DataFrame для пересоздания с новыми данными
            if 'bond_manager_df' in st.session_state:
                del st.session_state['bond_manager_df']
            # Увеличиваем версию data_editor для пересоздания
            st.session_state.bond_editor_version = st.session_state.get('bond_editor_version', 0) + 1
            # Генерируем новый UUID, но НЕ сбрасываем last_shown_id
            # Тогда при rerun: open_id != last_shown_id → диалог откроется
            st.session_state.bond_manager_open_id = str(uuid.uuid4())
            st.rerun()

    st.markdown("""
    **Фильтры применены:**
    - ОФЗ-ПД (26xxx, 25xxx, 24xxx серии)
    - Срок до погашения > 0.5 года
    - Наличие дюрации
    """)

    # ========================================
    # ЗАГРУЗКА ДАННЫХ (ИЗ КЭША ИЛИ MOEX)
    # ========================================
    # Информация о кэше
    cache_info = cache.get_cache_info()
    
    # Показываем статус кэша
    if cache_info['updated_at']:
        cache_status = "⚠️ (устарел)" if cache_info['is_expired'] else "✅"
        cache_time = cache_info['updated_at'].strftime('%d.%m %H:%M')
        st.caption(f"📦 Кэш: {cache_time} ({cache_info['count']} облигаций) {cache_status}")
    else:
        st.caption("📦 Кэш: пустой")

    # Принудительное обновление по кнопке
    if st.session_state.get('bond_manager_reload', False):
        with st.spinner("Обновление с MOEX API..."):
            try:
                count = cache.refresh_sync()
                st.session_state.bond_manager_reload = False
                # После обновления загружаем свежие данные
                st.session_state.bond_manager_bonds = cache.load_cached()
                st.toast(f"✅ Загружено {count} облигаций")
            except Exception as e:
                st.error(f"Ошибка загрузки: {e}")
                return
        bonds = st.session_state.bond_manager_bonds
    # Загрузка из кэша (автообновление если устарел)
    elif 'bond_manager_bonds' not in st.session_state:
        with st.spinner("Загрузка..." if cache_info['count'] == 0 else None):
            try:
                bonds = cache.get_ofz_list()
                st.session_state.bond_manager_bonds = bonds
            except Exception as e:
                st.error(f"Ошибка загрузки: {e}")
                return
    else:
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
    # берём состояние чекбоксов из session_state
    # Используем динамический key с версией
    editor_version = st.session_state.get('bond_editor_version', 0)
    editor_key = f"bonds_table_editor_{editor_version}"
    
    if editor_key in st.session_state:
        prev_state = st.session_state[editor_key]
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
            log_button_press("Очистить избранное")
            # Очищаем текущий набор (без сохранения в БД)
            st.session_state.bond_manager_current_favorites = set()
            # Удаляем DataFrame чтобы пересоздать с очищенными чекбоксами
            if 'bond_manager_df' in st.session_state:
                del st.session_state.bond_manager_df
            # Увеличиваем версию data_editor для принудительного пересоздания
            st.session_state.bond_editor_version = st.session_state.get('bond_editor_version', 0) + 1
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
        if editor_key in st.session_state:
            del st.session_state[editor_key]

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
        key=editor_key,
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
            log_button_press("Отменить и закрыть")
            # Очищаем состояние
            st.session_state.bond_manager_open_id = None
            st.session_state.bond_manager_last_shown_id = None
            st.session_state.bond_manager_current_favorites = None
            st.session_state.bond_manager_original_favorites = None
            # Очищаем DataFrame и состояние data_editor
            if 'bond_manager_df' in st.session_state:
                del st.session_state['bond_manager_df']
            if editor_key in st.session_state:
                del st.session_state[editor_key]
            st.rerun()

    with col_done:
        if st.button("✅ Готово", width="stretch", type="primary"):
            # Синхронизируем с БД
            new_favorites = current_favorites or set()
            old_favorites = original_favorites or set()
            
            # Логируем действие
            log_button_press("Готово", f"added={len(new_favorites - old_favorites)}, removed={len(old_favorites - new_favorites)}")
            
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
            
            # Убираем из избранного (не удаляем запись!)
            for isin in to_remove:
                db.set_favorite(isin, False)
                removed_count += 1
            
            # Очищаем состояние
            st.session_state.bond_manager_open_id = None
            st.session_state.bond_manager_last_shown_id = None
            st.session_state.bond_manager_current_favorites = None
            st.session_state.bond_manager_original_favorites = None
            # Очищаем DataFrame и состояние data_editor
            if 'bond_manager_df' in st.session_state:
                del st.session_state['bond_manager_df']
            if editor_key in st.session_state:
                del st.session_state[editor_key]
            st.session_state.cached_favorites_count = len(new_favorites)
            
            # Запускаем анализ коинтеграции для нового набора избранного
            if len(new_favorites) >= 2:
                st.session_state.cointegration_needs_update = True
                st.session_state.cointegration_favorites = list(new_favorites)
            
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
        log_button_press("Выбор инструментов для анализа")
        # Генерируем новый ID для этого открытия
        st.session_state.bond_manager_open_id = str(uuid.uuid4())
        # Сбрасываем состояние галочек для нового открытия
        st.session_state.bond_manager_current_favorites = None
        st.session_state.bond_manager_original_favorites = None
        # Очищаем DataFrame для пересоздания
        if 'bond_manager_df' in st.session_state:
            del st.session_state['bond_manager_df']
        # Сбрасываем версию data_editor
        st.session_state.bond_editor_version = 0
        # Очищаем список облигаций для перезагрузки из кэша
        if 'bond_manager_bonds' in st.session_state:
            del st.session_state['bond_manager_bonds']
        # Кэшируем количество избранных
        from core.db import get_db_facade
        db = get_db_facade()
        st.session_state.cached_favorites_count = len(db.get_favorite_bonds())
        st.rerun()
    
    # Проверяем нужно ли открыть диалог
    current_id = st.session_state.bond_manager_open_id
    last_shown = st.session_state.bond_manager_last_shown_id
    
    if current_id and current_id != last_shown:
        # Это новое открытие - показываем диалог
        st.session_state.bond_manager_last_shown_id = current_id
        show_bond_manager_dialog()
