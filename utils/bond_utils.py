"""
Утилиты для работы с облигациями

Содержит класс BondItem и вспомогательные функции.
"""
from datetime import datetime
from typing import Dict, List, Any, Optional


def get_years_to_maturity(maturity_str: str) -> float:
    """
    Вычисляет годы до погашения.

    Args:
        maturity_str: Дата погашения в формате 'YYYY-MM-DD'

    Returns:
        Количество лет до погашения (может быть отрицательным для просроченных)
    """
    try:
        maturity = datetime.strptime(maturity_str, '%Y-%m-%d')
        return round((maturity - datetime.now()).days / 365.25, 1)
    except (ValueError, TypeError):
        return 0


class BondItem:
    """
    Класс для представления облигации в UI.

    Используется для совместимости с разными источниками данных:
    - config.py BondConfig
    - База данных
    - API MOEX
    """

    def __init__(self, data: Dict[str, Any]):
        """
        Инициализация из словаря.

        Args:
            data: Словарь с данными облигации
        """
        self.isin = data.get('isin', '')
        self.name = data.get('name') or data.get('short_name') or data.get('isin', '')
        self.short_name = data.get('short_name', '')
        self.maturity_date = data.get('maturity_date', '')
        self.coupon_rate = data.get('coupon_rate')
        self.face_value = data.get('face_value', 1000)
        self.coupon_frequency = data.get('coupon_frequency', 2)
        self.issue_date = data.get('issue_date', '')
        self.day_count_convention = data.get('day_count_convention', 'ACT/ACT')

        # Дополнительные поля из БД
        self.last_price = data.get('last_price')
        self.last_ytm = data.get('last_ytm')
        self.duration_years = data.get('duration_years')
        self.is_favorite = data.get('is_favorite', False)

    @property
    def years_to_maturity(self) -> float:
        """Годы до погашения"""
        return get_years_to_maturity(self.maturity_date)

    def format_label(
        self,
        ytm: Optional[float] = None,
        duration_years: Optional[float] = None
    ) -> str:
        """
        Форматирует метку для отображения в UI.

        Args:
            ytm: Доходность к погашению (опционально)
            duration_years: Дюрация в годах (опционально)

        Returns:
            Строка вида "ОФЗ 26240 | YTM: 14.50% | Дюр: 15.5г. | 12.3г. до погашения"
        """
        display_name = self.name or self.short_name or self.isin
        parts = [f"{display_name}"]

        if ytm is not None:
            parts.append(f"YTM: {ytm:.2f}%")
        if duration_years is not None:
            parts.append(f"Дюр: {duration_years:.1f}г.")
        parts.append(f"{self.years_to_maturity}г. до погашения")

        return " | ".join(parts)

    def to_dict(self) -> Dict[str, Any]:
        """Конвертировать в словарь"""
        return {
            'isin': self.isin,
            'name': self.name,
            'short_name': self.short_name,
            'maturity_date': self.maturity_date,
            'coupon_rate': self.coupon_rate,
            'face_value': self.face_value,
            'coupon_frequency': self.coupon_frequency,
            'issue_date': self.issue_date,
            'day_count_convention': self.day_count_convention,
            'last_price': self.last_price,
            'last_ytm': self.last_ytm,
            'duration_years': self.duration_years,
            'is_favorite': self.is_favorite,
        }

    def to_bond_config_dict(self) -> Dict[str, Any]:
        """
        Конвертировать в словарь для BondConfig.

        Используется для передачи в функции расчёта YTM.
        """
        return {
            'isin': self.isin,
            'name': self.name,
            'maturity_date': self.maturity_date,
            'coupon_rate': self.coupon_rate,
            'face_value': self.face_value,
            'coupon_frequency': self.coupon_frequency,
            'issue_date': self.issue_date,
            'day_count_convention': self.day_count_convention
        }


def get_bonds_list(bonds_dict: Dict[str, Dict]) -> List[BondItem]:
    """
    Получить список BondItem из словаря облигаций.

    Args:
        bonds_dict: Словарь {isin: bond_data_dict}

    Returns:
        Список объектов BondItem
    """
    return [BondItem(bond_data) for bond_data in bonds_dict.values()]


def format_bond_label(
    bond: BondItem,
    ytm: Optional[float] = None,
    duration_years: Optional[float] = None
) -> str:
    """
    Форматирует метку облигации (обёртка над методом BondItem.format_label).

    Args:
        bond: Объект BondItem
        ytm: Доходность к погашению (опционально)
        duration_years: Дюрация в годах (опционально)

    Returns:
        Форматированная строка
    """
    return bond.format_label(ytm, duration_years)
