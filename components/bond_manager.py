"""
Компонент управления облигациями

Модальное окно для выбора избранных облигаций (версия 0.2.0)
"""
import streamlit as st
import pandas as pd
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
            all_bonds = fetcher.fetch_ofz_with_market_data(include_details=True)

            # Фильтруем
            from api.moex_bonds import filter_ofz_for_trading
            filtered_bonds = filter_ofz_for_trading(all_bonds)

            # Сохраняем в БД
            for bond in filtered_bonds:
                db.save_bond({
                    'isin': bond['isin'],
                    'name': bond.get('name'),
                    'short_name': bond.get('short_name'),
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
    except:
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
            with st.spinner("Загрузка данных с MOEX..."):
                fetcher = get_moex_fetcher()
                try:
                    # Получаем все ОФЗ с рыночными данными
                    all_bonds = fetcher.fetch_ofz_with_market_data(include_details=True)

                    # Фильтруем
                    from api.moex_bonds import filter_ofz_for_trading
                    filtered_bonds = filter_ofz_for_trading(all_bonds)

                    # Сохраняем/обновляем в БД
                    for bond in filtered_bonds:
                        # Сохраняем текущий статус избранного
                        existing = db.load_bond(bond['isin'])
                        is_favorite = existing.get('is_favorite', 0) if existing else 0

                        db.save_bond({
                            'isin': bond['isin'],
                            'name': bond.get('name'),
                            'short_name': bond.get('short_name'),
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

                    st.success(f"Обновлено {len(filtered_bonds)} облигаций")
                    st.rerun()

                except Exception as e:
                    st.error(f"Ошибка обновления: {e}")
                finally:
                    fetcher.close()

    with col_info:
        favorites = db.get_favorite_bonds()
        st.info(f"⭐ Избранных: **{len(favorites)}** | Выберите облигации для отображения в sidebar")

    st.divider()

    # Загружаем облигации
    bonds = db.get_all_bonds()

    if not bonds:
        st.warning("Нет облигаций в базе данных. Нажмите 'Обновить с MOEX'")
        return

    # Создаём DataFrame для отображения
    df_data = []
    for b in bonds:
        df_data.append({
            "ISIN": b.get("isin"),
            "Название": b.get("name") or b.get("short_name"),
            "Купон": format_coupon(b.get("coupon_rate")),
            "Погашение": format_maturity(b.get("maturity_date")),
            "Дюрация": format_duration(b.get("duration_years")),
            "YTM": format_ytm(b.get("last_ytm")),
            "⭐": "⭐" if b.get("is_favorite") else "☆",
            "is_favorite": b.get("is_favorite"),
            "duration_years_raw": b.get("duration_years") or 0,
        })

    df = pd.DataFrame(df_data)

    # Сортировка
    sort_col = st.selectbox(
        "Сортировать по",
        ["Дюрации", "YTM", "Купону", "Погашению", "Названию"],
        index=0,
        horizontal=True
    )

    sort_map = {
        "Дюрации": "duration_years_raw",
        "YTM": "YTM",
        "Купону": "Купон",
        "Погашению": "Погашение",
        "Названию": "Название",
    }

    ascending = True
    df = df.sort_values(by=sort_map[sort_col], ascending=ascending)

    # Отображаем таблицу
    # Используем columns для заголовка
    header_col1, header_col2, header_col3, header_col4, header_col5, header_col6, header_col7 = st.columns(
        [3, 2, 1, 2, 1, 1, 0.5]
    )

    with header_col1:
        st.markdown("**ISIN**")
    with header_col2:
        st.markdown("**Название**")
    with header_col3:
        st.markdown("**Купон**")
    with header_col4:
        st.markdown("**Погашение**")
    with header_col5:
        st.markdown("**Дюр.**")
    with header_col6:
        st.markdown("**YTM**")
    with header_col7:
        st.markdown("**⭐**")

    st.divider()

    # Отображаем облигации
    for idx, row in df.iterrows():
        col1, col2, col3, col4, col5, col6, col7 = st.columns(
            [3, 2, 1, 2, 1, 1, 0.5]
        )

        isin = row["ISIN"]
        is_favorite = row["is_favorite"]

        with col1:
            st.code(isin, language=None)

        with col2:
            st.write(row["Название"])

        with col3:
            st.write(row["Купон"])

        with col4:
            st.write(row["Погашение"])

        with col5:
            st.write(row["Дюрация"])

        with col6:
            st.write(row["YTM"])

        with col7:
            # Кнопка избранного
            btn_label = "⭐" if is_favorite else "☆"
            btn_type = "primary" if is_favorite else "secondary"

            if st.button(
                btn_label,
                key=f"fav_{isin}",
                type=btn_type,
                help="Нажмите, чтобы добавить/удалить из избранного"
            ):
                # Автосохранение
                db.set_favorite(isin, not is_favorite)
                st.rerun()

        st.divider()

    # Итого
    st.markdown(f"**Всего облигаций:** {len(df)}")


def render_bond_manager_button():
    """
    Кнопка для открытия модального окна управления облигациями

    Разместить в sidebar
    """
    if st.button("📊 Управление облигациями", use_container_width=True):
        show_bond_manager_dialog()
