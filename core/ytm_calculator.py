"""
Расчёт доходности к погашению (YTM) для облигаций
"""
from datetime import date, datetime
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
import numpy as np
from scipy import optimize
import logging

logger = logging.getLogger(__name__)


@dataclass
class BondParams:
    """Параметры облигации"""
    isin: str
    name: str
    face_value: float
    coupon_rate: float  # В процентах годовых
    coupon_frequency: int  # Купоны в год
    maturity_date: date
    issue_date: Optional[date] = None
    current_coupon_date: Optional[date] = None
    accrued_interest: float = 0.0


class YTMCalculator:
    """Калькулятор доходности к погашению"""
    
    def __init__(self, day_count_basis: str = "ACT/ACT"):
        """
        Инициализация калькулятора
        
        Args:
            day_count_basis: База расчёта дней (ACT/ACT, ACT/365, 30/360)
        """
        self.day_count_basis = day_count_basis
    
    def calculate_ytm(
        self,
        price: float,
        bond_params: BondParams,
        settlement_date: Optional[date] = None,
        dirty_price: bool = False
    ) -> Optional[float]:
        """
        Рассчитать YTM из цены облигации
        
        Args:
            price: Цена облигации (в % от номинала или абсолютная)
            settlement_date: Дата расчёта
            bond_params: Параметры облигации
            dirty_price: True если цена включает НКД
            
        Returns:
            YTM в процентах годовых или None
        """
        if settlement_date is None:
            settlement_date = date.today()
        
        # Нормализуем цену к номиналу
        if price <= 100:  # Цена в процентах
            clean_price = price * bond_params.face_value / 100
        else:  # Абсолютная цена
            clean_price = price
        
        # Добавляем НКД если цена чистая
        if not dirty_price:
            dirty_price_value = clean_price + bond_params.accrued_interest
        else:
            dirty_price_value = clean_price
        
        # Генерируем денежные потоки
        cash_flows = self._generate_cash_flows(bond_params, settlement_date)
        
        if not cash_flows:
            return None
        
        # Находим YTM методом Ньютона-Рафсона
        try:
            ytm = self._solve_ytm(dirty_price_value, cash_flows)
            return ytm
        except Exception as e:
            logger.debug(f"Ошибка расчёта YTM: {e}")
            return None
    
    def calculate_price_from_ytm(
        self,
        ytm: float,
        bond_params: BondParams,
        settlement_date: Optional[date] = None
    ) -> Optional[float]:
        """
        Рассчитать цену облигации из YTM
        
        Args:
            ytm: Доходность к погашению (в % годовых)
            bond_params: Параметры облигации
            settlement_date: Дата расчёта
            
        Returns:
            Цена в % от номинала или None
        """
        if settlement_date is None:
            settlement_date = date.today()
        
        cash_flows = self._generate_cash_flows(bond_params, settlement_date)
        
        if not cash_flows:
            return None
        
        # Дисконтируем денежные потоки
        price = 0.0
        for cf_date, cf_amount in cash_flows:
            days = (cf_date - settlement_date).days
            years = days / 365.25
            discount_factor = (1 + ytm / 100) ** years
            price += cf_amount / discount_factor
        
        # Вычитаем НКД для получения чистой цены
        clean_price = price - bond_params.accrued_interest
        
        # Возвращаем в процентах от номинала
        return round(clean_price / bond_params.face_value * 100, 4)
    
    def calculate_duration(
        self,
        ytm: float,
        bond_params: BondParams,
        settlement_date: Optional[date] = None
    ) -> Optional[float]:
        """
        Рассчитать дюрацию Маколея
        
        Args:
            ytm: Доходность к погашению
            bond_params: Параметры облигации
            settlement_date: Дата расчёта
            
        Returns:
            Дюрация в годах или None
        """
        if settlement_date is None:
            settlement_date = date.today()
        
        cash_flows = self._generate_cash_flows(bond_params, settlement_date)
        
        if not cash_flows:
            return None
        
        # Рассчитываем цену и взвешенную сумму времён
        price = 0.0
        weighted_time = 0.0
        
        for cf_date, cf_amount in cash_flows:
            days = (cf_date - settlement_date).days
            years = days / 365.25
            discount_factor = (1 + ytm / 100) ** years
            pv = cf_amount / discount_factor
            
            price += pv
            weighted_time += pv * years
        
        if price <= 0:
            return None
        
        duration = weighted_time / price
        return round(duration, 4)
    
    def calculate_modified_duration(
        self,
        ytm: float,
        bond_params: BondParams,
        settlement_date: Optional[date] = None
    ) -> Optional[float]:
        """
        Рассчитать модифицированную дюрацию
        
        Args:
            ytm: Доходность к погашению
            bond_params: Параметры облигации
            settlement_date: Дата расчёта
            
        Returns:
            Модифицированная дюрация или None
        """
        duration = self.calculate_duration(ytm, bond_params, settlement_date)
        
        if duration is None:
            return None
        
        modified_duration = duration / (1 + ytm / 100)
        return round(modified_duration, 4)
    
    def calculate_convexity(
        self,
        ytm: float,
        bond_params: BondParams,
        settlement_date: Optional[date] = None
    ) -> Optional[float]:
        """
        Рассчитать выпуклость (convexity)
        
        Args:
            ytm: Доходность к погашению
            bond_params: Параметры облигации
            settlement_date: Дата расчёта
            
        Returns:
            Выпуклость или None
        """
        if settlement_date is None:
            settlement_date = date.today()
        
        cash_flows = self._generate_cash_flows(bond_params, settlement_date)
        
        if not cash_flows:
            return None
        
        price = 0.0
        convexity_sum = 0.0
        
        for cf_date, cf_amount in cash_flows:
            days = (cf_date - settlement_date).days
            years = days / 365.25
            
            discount_factor = (1 + ytm / 100) ** years
            pv = cf_amount / discount_factor
            
            price += pv
            convexity_sum += pv * years * (years + 1)
        
        if price <= 0:
            return None
        
        convexity = convexity_sum / (price * (1 + ytm / 100) ** 2)
        return round(convexity, 6)
    
    def calculate_accrued_interest(
        self,
        bond_params: BondParams,
        settlement_date: Optional[date] = None
    ) -> float:
        """
        Рассчитать накопленный купонный доход (НКД)
        
        Args:
            bond_params: Параметры облигации
            settlement_date: Дата расчёта
            
        Returns:
            НКД в абсолютном выражении
        """
        if settlement_date is None:
            settlement_date = date.today()
        
        # Если есть текущий НКД, возвращаем его
        if bond_params.accrued_interest > 0:
            return bond_params.accrued_interest
        
        # Иначе рассчитываем (требуется дата предыдущего купона)
        # Упрощённый расчёт: берём годовой купон и делим на период
        coupon_per_period = bond_params.face_value * bond_params.coupon_rate / 100 / bond_params.coupon_frequency
        days_in_period = 365 / bond_params.coupon_frequency
        
        # Предполагаем, что прошло половина периода (упрощение)
        accrued = coupon_per_period * 0.5
        
        return round(accrued, 2)
    
    def estimate_years_to_maturity(
        self,
        maturity_date: date,
        settlement_date: Optional[date] = None
    ) -> float:
        """
        Рассчитать лет до погашения
        
        Args:
            maturity_date: Дата погашения
            settlement_date: Дата расчёта
            
        Returns:
            Количество лет до погашения
        """
        if settlement_date is None:
            settlement_date = date.today()
        
        days = (maturity_date - settlement_date).days
        return round(days / 365.25, 2)
    
    def _generate_cash_flows(
        self,
        bond_params: BondParams,
        settlement_date: date
    ) -> List[tuple]:
        """
        Генерировать денежные потоки облигации
        
        Args:
            bond_params: Параметры облигации
            settlement_date: Дата расчёта
            
        Returns:
            Список (дата, сумма) денежных потоков
        """
        cash_flows = []
        
        if settlement_date >= bond_params.maturity_date:
            return cash_flows
        
        # Купон за период
        coupon_per_period = bond_params.face_value * bond_params.coupon_rate / 100 / bond_params.coupon_frequency
        
        # Период между купонами в днях
        days_between_coupons = int(365 / bond_params.coupon_frequency)
        
        # Начинаем с даты расчёта
        current_date = settlement_date
        
        # Находим следующую купонную дату (упрощённо)
        days_since_last = (settlement_date - date(2020, 1, 1)).days % days_between_coupons
        next_coupon = settlement_date + __import__('datetime').timedelta(
            days=days_between_coupons - days_since_last
        )
        
        # Генерируем купоны до погашения
        current_coupon_date = next_coupon
        
        while current_coupon_date <= bond_params.maturity_date:
            cash_flows.append((current_coupon_date, coupon_per_period))
            current_coupon_date = date(
                current_coupon_date.year,
                current_coupon_date.month,
                current_coupon_date.day
            ) + __import__('datetime').timedelta(days=days_between_coupons)
        
        # Добавляем номинал в дату погашения
        if cash_flows:
            # Заменяем последний купон на купон + номинал
            last_date, last_coupon = cash_flows[-1]
            cash_flows[-1] = (bond_params.maturity_date, last_coupon + bond_params.face_value)
        else:
            # Только номинал
            cash_flows.append((bond_params.maturity_date, bond_params.face_value))
        
        return cash_flows
    
    def _solve_ytm(
        self,
        price: float,
        cash_flows: List[tuple],
        guess: float = 7.0
    ) -> float:
        """
        Найти YTM численным методом
        
        Args:
            price: Грязная цена облигации
            cash_flows: Денежные потоки
            guess: Начальное приближение
            
        Returns:
            YTM в процентах
        """
        def npv(ytm):
            result = 0.0
            settlement_date = date.today()
            
            for cf_date, cf_amount in cash_flows:
                days = (cf_date - settlement_date).days
                years = days / 365.25
                discount_factor = (1 + ytm / 100) ** years
                result += cf_amount / discount_factor
            
            return result - price
        
        try:
            # Используем метод Брента
            result = optimize.brentq(npv, 0.1, 50.0)
            return round(result, 3)
        except ValueError:
            # Если не сошлось, пробуем другой метод
            result = optimize.newton(npv, guess)
            return round(result, 3)


def calculate_ytm_simple(
    price: float,
    coupon_rate: float,
    years_to_maturity: float,
    face_value: float = 1000
) -> float:
    """
    Упрощённый расчёт YTM
    
    Формула: YTM ≈ (C + (F-P)/n) / ((F+P)/2)
    
    Args:
        price: Цена в % от номинала
        coupon_rate: Купонная ставка в %
        years_to_maturity: Лет до погашения
        face_value: Номинал
        
    Returns:
        YTM в процентах
    """
    if years_to_maturity <= 0:
        return coupon_rate
    
    # Нормализуем цену
    if price <= 100:
        price_abs = price * face_value / 100
    else:
        price_abs = price
    
    # Годовой купон
    annual_coupon = face_value * coupon_rate / 100
    
    # Упрощённая формула
    numerator = annual_coupon + (face_value - price_abs) / years_to_maturity
    denominator = (face_value + price_abs) / 2
    
    ytm = (numerator / denominator) * 100
    
    return round(ytm, 2)
