"""
Модели данных для OFZ Spread Analytics

Содержит единые dataclass модели для облигаций.
"""
from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from datetime import datetime, date


@dataclass
class Bond:
    """
    Единая модель облигации
    
    Используется везде в приложении вместо разных форматов:
    - BondConfig из config.py
    - BondItem из app.py
    - Dict из БД
    """
    # Обязательные поля
    isin: str
    
    # Идентификация
    name: str = ""
    short_name: str = ""
    
    # Параметры облигации
    coupon_rate: Optional[float] = None
    maturity_date: str = ""
    issue_date: str = ""
    face_value: float = 1000.0
    coupon_frequency: int = 2
    day_count_convention: str = "ACT/ACT"
    
    # Статус
    is_favorite: bool = False
    
    # Рыночные данные
    last_price: Optional[float] = None
    last_ytm: Optional[float] = None
    duration_years: Optional[float] = None
    duration_days: Optional[float] = None
    last_trade_date: Optional[str] = None
    
    # Метаданные
    last_updated: Optional[str] = None
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Bond':
        """
        Создать Bond из словаря (из БД или session_state)
        
        Args:
            data: Словарь с данными облигации
        
        Returns:
            Bond объект
        """
        return cls(
            isin=data.get('isin', ''),
            name=data.get('name') or data.get('short_name') or data.get('isin', ''),
            short_name=data.get('short_name', ''),
            coupon_rate=data.get('coupon_rate'),
            maturity_date=data.get('maturity_date', ''),
            issue_date=data.get('issue_date', ''),
            face_value=data.get('face_value', 1000),
            coupon_frequency=data.get('coupon_frequency', 2),
            day_count_convention=data.get('day_count_convention') or data.get('day_count', 'ACT/ACT'),
            is_favorite=bool(data.get('is_favorite', 0)),
            last_price=data.get('last_price'),
            last_ytm=data.get('last_ytm'),
            duration_years=data.get('duration_years'),
            duration_days=data.get('duration_days'),
            last_trade_date=data.get('last_trade_date'),
            last_updated=data.get('last_updated'),
        )
    
    @classmethod
    def from_db_row(cls, row: Dict[str, Any]) -> 'Bond':
        """
        Создать Bond из строки БД (sqlite3.Row)
        
        Args:
            row: Строка из БД (с ключами как в таблице bonds)
        
        Returns:
            Bond объект
        """
        return cls.from_dict(row)
    
    @classmethod
    def from_config(cls, isin: str, bond_config: Any) -> 'Bond':
        """
        Создать Bond из BondConfig (config.py)
        
        Args:
            isin: ISIN облигации
            bond_config: Объект BondConfig из config.py
        
        Returns:
            Bond объект
        """
        return cls(
            isin=isin,
            name=getattr(bond_config, 'name', ''),
            short_name=getattr(bond_config, 'name', ''),
            coupon_rate=getattr(bond_config, 'coupon_rate', None),
            maturity_date=getattr(bond_config, 'maturity_date', ''),
            issue_date=getattr(bond_config, 'issue_date', ''),
            face_value=getattr(bond_config, 'face_value', 1000),
            coupon_frequency=getattr(bond_config, 'coupon_frequency', 2),
            day_count_convention=getattr(bond_config, 'day_count_convention', 'ACT/ACT'),
            is_favorite=True,  # Облигации из config по умолчанию избранные
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Преобразовать в словарь (для session_state, БД)
        
        Returns:
            Словарь с данными облигации
        """
        return {
            'isin': self.isin,
            'name': self.name,
            'short_name': self.short_name,
            'coupon_rate': self.coupon_rate,
            'maturity_date': self.maturity_date,
            'issue_date': self.issue_date,
            'face_value': self.face_value,
            'coupon_frequency': self.coupon_frequency,
            'day_count_convention': self.day_count_convention,
            'is_favorite': 1 if self.is_favorite else 0,
            'last_price': self.last_price,
            'last_ytm': self.last_ytm,
            'duration_years': self.duration_years,
            'duration_days': self.duration_days,
            'last_trade_date': self.last_trade_date,
            'last_updated': self.last_updated,
        }
    
    def to_db_dict(self) -> Dict[str, Any]:
        """
        Преобразовать в словарь для сохранения в БД
        
        Returns:
            Словарь для INSERT/UPDATE в таблицу bonds
        """
        return {
            'isin': self.isin,
            'name': self.name,
            'short_name': self.short_name,
            'coupon_rate': self.coupon_rate,
            'maturity_date': self.maturity_date,
            'issue_date': self.issue_date,
            'face_value': self.face_value,
            'coupon_frequency': self.coupon_frequency,
            'day_count': self.day_count_convention,
            'is_favorite': 1 if self.is_favorite else 0,
            'last_price': self.last_price,
            'last_ytm': self.last_ytm,
            'duration_years': self.duration_years,
            'duration_days': self.duration_days,
            'last_trade_date': self.last_trade_date,
        }
    
    def get_display_name(self) -> str:
        """
        Получить имя для отображения в UI
        
        Returns:
            Имя облигации (name → short_name → isin)
        """
        return self.name or self.short_name or self.isin
    
    def get_years_to_maturity(self) -> float:
        """
        Вычислить годы до погашения
        
        Returns:
            Годы до погашения или 0 если дата некорректна
        """
        if not self.maturity_date:
            return 0
        try:
            maturity = datetime.strptime(self.maturity_date, '%Y-%m-%d')
            return round((maturity - datetime.now()).days / 365.25, 1)
        except (ValueError, TypeError):
            return 0
    
    def format_label(
        self,
        ytm: float = None,
        duration_years: float = None
    ) -> str:
        """
        Форматировать метку для UI
        
        Args:
            ytm: YTM для отображения (если None, используется last_ytm)
            duration_years: Дюрация для отображения
        
        Returns:
            Строка с меткой облигации
        """
        years = self.get_years_to_maturity()
        display_name = self.get_display_name()
        parts = [display_name]
        
        ytm_val = ytm if ytm is not None else self.last_ytm
        if ytm_val is not None:
            parts.append(f"YTM: {ytm_val:.2f}%")
        
        dur_val = duration_years if duration_years is not None else self.duration_years
        if dur_val is not None:
            parts.append(f"Дюр: {dur_val:.1f}г.")
        
        parts.append(f"{years}г. до погашения")
        
        return " | ".join(parts)


@dataclass
class BondPair:
    """
    Пара облигаций для анализа спреда
    """
    bond1: Bond
    bond2: Bond
    
    def get_spread_bp(self) -> Optional[float]:
        """
        Вычислить текущий спред в базисных пунктах
        
        Returns:
            Спред в б.п. или None если YTM нет
        """
        if self.bond1.last_ytm is None or self.bond2.last_ytm is None:
            return None
        return (self.bond1.last_ytm - self.bond2.last_ytm) * 100
    
    def get_label(self) -> str:
        """
        Получить метку пары
        
        Returns:
            Строка с меткой пары
        """
        return f"{self.bond1.get_display_name()} / {self.bond2.get_display_name()}"
