"""
Компонент управления облигациями

Модальное окно для выбора избранных облигаций (версия 0.2.0)
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


def load_bonds_for_display() -> List[Dict[str, Any]]:
    """
    Загрузить облигации для отображения в модальном окне

    Сначала из БД, если пусто - загрузить с MOEX и сохранить
    """
    db = get_bond_manager()

    # Проверяем есть ли облигации в БД
    bonds = db.get_all_bonds()

    if not bonds:
        # Загружаем с MOEX
        st.info("Загружаем список облигаций с MOEX...")
        fetcher = get_moex_fetcher()

        try:
            # Получаем все ОФЗ с рыночными данными
            all_bonds = fetcher.fetch_ofz_with_market_data(include_details=False)

            # Фильтруем
            from api.moex_bonds import filter_ofz_for_trading
            filtered_bonds = filter_ofz_for_trading(all_bonds)

            # Сохраняем в БД
            for bond in filtered_bonds:
                db.save_bond({
                    'isin': bond['isin'],
                    'name': bond.get('name') or bond.get('short_name') or bond['isin'],
                    'short_name': bond.get('short_name') or bond['isin'],
                    'coupon_rate': bond.get('coupon_rate'),
                    'maturity_date': bond.get('maturity_date'),
                    'issue_date': bond.get('issue_date'),
                    'face_value': bond.get('face_value', 1000),
                    'coupon_frequency': bond.get('coupon_frequency', 2),
                    'day_count': bond.get('day_count', 'ACT/ACT'),
                    'is_favorite': 0,
                    'last_price': bond.get('last_price'),
                    'last_ytm': bond.get('last_ytm'),
                    'duration_years': bond.get('duration_years'),
                    'duration_days': bond.get('duration_days'),
                    'last_trade_date': bond.get('last_trade_date'),
                })

            bonds = db.get_all_bonds()
            st.success(f"Загружено {len(bonds)} облигаций")

        except Exception as e:
            logger.error(f"Ошибка загрузки облигаций: {e}")
            st.error(f"Ошибка загрузки: {e}")
            return []
        finally:
            fetcher.close()

    return bonds


def format_duration(duration_years: Optional[float]) -> str:
    """Форматировать дюрацию"""
    if duration_years is None:
        return "Н/Д"
    return f"{duration_years:.1f}г."


def format_ytm(ytm: Optional[float]) -> str:
    """Форматировать YTM"""
    if ytm is None:
        return "Н/Д"
    return f"{ytm:.2f}%"


def format_coupon(coupon: Optional[float]) -> str:
    """Форматировать купон"""
    if coupon is None:
        return "Н/Д"
    return f"{coupon:.2f}%"


def format_maturity(maturity_date: Optional[str]) -> str:
    """Форматировать дату погашения"""
    if not maturity_date:
        return "Н/Д"
    try:
        dt = datetime.strptime(maturity_date, "%Y-%m-%d")
        years = (dt - datetime.now()).days / 365.25
        return f"{dt.strftime('%d.%m.%Y')} ({years:.1f}г.)"
    except (ValueError, TypeError) as e:
        logger.debug(f"Ошибка парсинга даты погашения: {maturity_date}, {e}")
        return maturity_date


@st.dialog("Управление облигациями", width="large")
def show_bond_manager_dialog():
    """
    Модальное окно для управления списком облигаций

    Функции:
    - Показать все отфильтрованные облигации
    - Отметить/снять избранное (автосохранение)
    - Сортировка по колонкам
    """
    db = get_bond_manager()

    # CSS для читаемости
    st.markdown("""
    <style>
        .bond-table-row {
            padding: 10px 0;
            border-bottom: 1px solid #eee;
        }
        .bond-isin {
            font-family: monospace;
            background: #f0f0f0;
            padding: 2px 6px;
            border-radius: 4px;
            color: #333 !important;
        }
        .stMarkdown p {
            color: #333 !important;
        }
    </style>
    """, unsafe_allow_html=True)

    # Заголовок с информацией
    st.markdown("""
    ### 📊 Список ОФЗ для торговли
    
    **Фильтры применены:**
    - ОФЗ-ПД (26xxx, 25xxx, 24xxx серии)
    - Срок до погашения > 0.5 года
    - Торги за последние 10 дней
    - Наличие дюрации
    """)

    # Кнопка обновления с MOEX
    col_refresh, col_info = st.columns([1, 3])

    with col_refresh:
        if st.button("🔄 Обновить с MOEX", use_container_width=True):
            fetcher = None
            status_placeholder = st.empty()
            status_placeholder.info("Подключение к MOEX API...")
            
            try:
                fetcher = get_moex_fetcher()
                status_placeholder.info("Получение списка ОФЗ...")
                
                # Получаем все ОФЗ с рыночными данными
                all_bonds = fetcher.fetch_ofz_with_market_data(include_details=False)
                
                if not all_bonds:
                    status_placeholder.warning("MOEX не вернул данные. Проверьте соединение.")
                    return
                
                status_placeholder.info(f"Получено {len(all_bonds)} облигаций")
                
                # Фильтруем
                from api.moex_bonds import filter_ofz_for_trading
                filtered_bonds = filter_ofz_for_trading(all_bonds)
                
                if not filtered_bonds:
                    status_placeholder.warning("Нет облигаций, соответствующих фильтрам.")
                    return
                
                status_placeholder.info(f"После фильтрации: {len(filtered_bonds)}")
                
                # Сохраняем/обновляем в БД
                saved_count = 0
                progress_bar = st.progress(0)
                
                for i, bond in enumerate(filtered_bonds):
                    progress_bar.progress((i + 1) / len(filtered_bonds))
                    
                    # Сохраняем текущий статус избранного
                    existing = db.load_bond(bond['isin'])
                    is_favorite = existing.get('is_favorite', 0) if existing else 0
                    
                    db.save_bond({
                        'isin': bond['isin'],
                        'name': bond.get('name') or bond.get('short_name') or bond['isin'],
                        'short_name': bond.get('short_name') or bond['isin'],
                        'coupon_rate': bond.get('coupon_rate'),
                        'maturity_date': bond.get('maturity_date'),
                        'issue_date': bond.get('issue_date'),
                        'face_value': bond.get('face_value', 1000),
                        'coupon_frequency': bond.get('coupon_frequency', 2),
                        'day_count': bond.get('day_count', 'ACT/ACT'),
                        'is_favorite': is_favorite,
                        'last_price': bond.get('last_price'),
                        'last_ytm': bond.get('last_ytm'),
                        'duration_years': bond.get('duration_years'),
                        'duration_days': bond.get('duration_days'),
                        'last_trade_date': bond.get('last_trade_date'),
                    })
                    saved_count += 1
                
                progress_bar.empty()
                st.success(f"Обновлено {saved_count} облигаций")
                # Переоткрываем диалог с новыми данными
                st.session_state.bond_manager_open_id = str(uuid.uuid4())
                st.session_state.bond_manager_last_shown_id = None
                st.rerun()
                
            except requests.exceptions.Timeout:
                st.error("Таймаут подключения к MOEX. Попробуйте позже.")
            except requests.exceptions.ConnectionError as e:
                st.error(f"Ошибка соединения: {e}")
            except Exception as e:
                import traceback
                st.error(f"Ошибка обновления: {e}")
                with st.expander("Детали ошибки"):
                    st.code(traceback.format_exc())
            finally:
                if fetcher:
                    fetcher.close()

    with col_info:
        # Используем кэшированное количество избранных (обновляется только при открытии диалога)
        favorites_count = st.session_state.get('cached_favorites_count', 0)
        fav_col1, fav_col2 = st.columns([3, 1])
        with fav_col1:
            st.info(f"⭐ Избранных: **{favorites_count}** | Выберите облигации для отображения в sidebar")
        with fav_col2:
            if favorites_count > 0:
                if st.button("🗑️ Очистить", key="clear_favorites", help="Убрать все облигации из избранного"):
                    cleared = db.clear_all_favorites()
                    if cleared > 0:
                        # Обновляем кэш и закрываем диалог
                        st.session_state.cached_favorites_count = 0
                        st.session_state.bond_manager_open_id = None
                        st.session_state.bond_manager_last_shown_id = None
                        st.rerun()

    st.divider()

    # Загружаем облигации
    bonds = db.get_all_bonds()

    if not bonds:
        st.warning("Нет облигаций в базе данных. Нажмите 'Обновить с MOEX'")
        return

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
            "⭐": b.get("is_favorite", 0) == 1,
        })

    df = pd.DataFrame(df_data)
    
    # Сортируем по дюрации по умолчанию
    df = df.sort_values(by="Дюрация, лет", ascending=True, na_position="last")

    # Отображаем редактируемую таблицу
    edited_df = st.data_editor(
        df,
        column_config={
            "ISIN": st.column_config.TextColumn("ISIN", width="medium"),
            "Название": st.column_config.TextColumn("Название", width="medium"),
            "Купон, %": st.column_config.NumberColumn("Купон, %", format="%.2f%%", width="small"),
            "Погашение": st.column_config.TextColumn("Погашение", width="small"),
            "До погаш., лет": st.column_config.NumberColumn("До погаш., лет", format="%.1f", width="small"),
            "Дюрация, лет": st.column_config.NumberColumn("Дюрация, лет", format="%.1f", width="small"),
            "YTM, %": st.column_config.NumberColumn("YTM, %", format="%.2f%%", width="small"),
            "⭐": st.column_config.CheckboxColumn("⭐", default=False, width="tiny"),
        },
        hide_index=True,
        use_container_width=True,
        num_rows="fixed",
        key="bonds_table_editor",
    )
    
    # Проверяем изменения в колонке избранного (сохраняем без rerun)
    if not df.empty and not edited_df.empty:
        # Создаём словарь исходных состояний по ISIN
        original_favorites = dict(zip(df["ISIN"], df["⭐"]))
        # Сохраняем изменения в БД
        for _, row in edited_df.iterrows():
            isin = row["ISIN"]
            new_favorite = row["⭐"]
            if isin in original_favorites and original_favorites[isin] != new_favorite:
                db.set_favorite(isin, new_favorite)
        # Без rerun - диалог остаётся открытым, счётчик обновится при следующем открытии

    # Итого
    st.markdown(f"**Всего облигаций:** {len(df)}")
    
    st.divider()
    
    # Кнопка закрытия (сбрасывает флаг открытия)
    if st.button("✅ Готово", use_container_width=True, type="primary"):
        st.session_state.bond_manager_open_id = None
        st.session_state.bond_manager_last_shown_id = None
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
        # Кэшируем количество избранных (обновится только при следующем открытии)
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
    # При следующем rerun (от X или клика вне) диалог не откроется снова
