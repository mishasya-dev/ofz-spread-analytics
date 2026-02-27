"""
Расчёт доходности к погашению (YTM) для облигаций ОФЗ
"""
from datetime import date, datetime, timedelta
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
import math
import logging

logger = logging.getLogger(__name__)


@dataclass
class BondParams:
    """Параметры облигации для расчёта YTM"""
    isin: str
    name: str
    face_value: float
    coupon_rate: float  # В процентах годовых
    coupon_frequency: int  # Купоны в год (обычно 2 для ОФЗ)
    maturity_date: date
    issue_date: Optional[date] = None
    day_count_convention: str = "ACT/ACT"


class YTMCalculator:
    """
    Калькулятор доходности к погашению (YTM)
    
    Использует итеративный метод Ньютона-Рафсона для решения уравнения:
    Price = Sum(CF_i / (1 + YTM)^t_i)
    """
    
    def __init__(self, max_iterations: int = 100, tolerance: float = 1e-6):
        """
        Инициализация
        
        Args:
            max_iterations: Максимальное число итераций
            tolerance: Точность расчёта
        """
        self.max_iterations = max_iterations
        self.tolerance = tolerance
    
    def calculate_ytm(
        self,
        price_percent: float,
        bond_params: BondParams,
        settlement_date: Optional[date] = None,
        accrued_interest: float = 0.0
    ) -> Optional[float]:
        """
        Рассчитать YTM из цены облигации
        
        Args:
            price_percent: Чистая цена в процентах от номинала (например, 72.5)
            bond_params: Параметры облигации
            settlement_date: Дата расчёта (по умолчанию сегодня)
            accrued_interest: Накопленный купонный доход (НКД) в рублях
            
        Returns:
            YTM в процентах годовых или None
        """
        if settlement_date is None:
            settlement_date = date.today()
        
        # Проверка даты погашения
        if settlement_date >= bond_params.maturity_date:
            logger.warning(f"{bond_params.isin}: Дата погашения уже прошла")
            return None
        
        # Конвертируем цену в абсолютное значение
        clean_price = price_percent * bond_params.face_value / 100
        dirty_price = clean_price + accrued_interest
        
        # Генерируем денежные потоки
        cash_flows = self._generate_cash_flows(bond_params, settlement_date)
        
        if not cash_flows:
            return None
        
        # Решаем уравнение для YTM
        try:
            ytm = self._solve_ytm_newton(dirty_price, cash_flows, settlement_date)
            return round(ytm, 3)
        except Exception as e:
            logger.debug(f"Ошибка расчёта YTM для {bond_params.isin}: {e}")
            return None
    
    def calculate_ytm_simple(
        self,
        price_percent: float,
        bond_params: BondParams,
        settlement_date: Optional[date] = None
    ) -> float:
        """
        Упрощённый расчёт YTM (формула приблизительной доходности)
        
        YTM ≈ (C + (F - P) / n) / ((F + P) / 2)
        
        Args:
            price_percent: Цена в процентах от номинала
            bond_params: Параметры облигации
            settlement_date: Дата расчёта
            
        Returns:
            YTM в процентах годовых
        """
        if settlement_date is None:
            settlement_date = date.today()
        
        # Лет до погашения
        days_to_maturity = (bond_params.maturity_date - settlement_date).days
        years_to_maturity = days_to_maturity / 365.25
        
        if years_to_maturity <= 0:
            return bond_params.coupon_rate
        
        # Годовой купон в рублях
        annual_coupon = bond_params.face_value * bond_params.coupon_rate / 100
        
        # Цена в рублях
        price_abs = price_percent * bond_params.face_value / 100
        
        # Формула приблизительной доходности
        numerator = annual_coupon + (bond_params.face_value - price_abs) / years_to_maturity
        denominator = (bond_params.face_value + price_abs) / 2
        
        ytm = (numerator / denominator) * 100
        
        return round(ytm, 2)
    
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
        
        # Возвращаем в процентах от номинала
        return round(price / bond_params.face_value * 100, 4)
    
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
        
        MD = D / (1 + YTM)
        """
        duration = self.calculate_duration(ytm, bond_params, settlement_date)
        
        if duration is None:
            return None
        
        modified_duration = duration / (1 + ytm / 100)
        return round(modified_duration, 4)
    
    def calculate_accrued_interest(
        self,
        bond_params: BondParams,
        settlement_date: Optional[date] = None,
        last_coupon_date: Optional[date] = None
    ) -> float:
        """
        Рассчитать накопленный купонный доход (НКД)
        
        Args:
            bond_params: Параметры облигации
            settlement_date: Дата расчёта
            last_coupon_date: Дата последнего купона
            
        Returns:
            НКД в рублях
        """
        if settlement_date is None:
            settlement_date = date.today()
        
        # Купон за период в рублях
        coupon_per_period = bond_params.face_value * bond_params.coupon_rate / 100 / bond_params.coupon_frequency
        
        # Дней между купонами
        days_between_coupons = 365 // bond_params.coupon_frequency
        
        if last_coupon_date:
            days_since_last = (settlement_date - last_coupon_date).days
        else:
            # Упрощение: предполагаем середину купонного периода
            days_since_last = days_between_coupons // 2
        
        # НКД
        accrued = coupon_per_period * days_since_last / days_between_coupons
        
        return round(accrued, 2)
    
    def _generate_cash_flows(
        self,
        bond_params: BondParams,
        settlement_date: date
    ) -> List[tuple]:
        """
        Генерировать денежные потоки облигации
        
        Returns:
            Список (дата, сумма) денежных потоков
        """
        cash_flows = []
        
        # Купон за период в рублях
        coupon_per_period = bond_params.face_value * bond_params.coupon_rate / 100 / bond_params.coupon_frequency
        
        # Дней между купонами
        days_between_coupons = 365 // bond_params.coupon_frequency
        
        # Находим следующую купонную дату
        # Для ОФЗ купоны обычно платятся 2 раза в год
        # Находим ближайшую дату купона от даты погашения
        
        maturity = bond_params.maturity_date
        current_date = settlement_date
        
        # Генерируем купонные даты от погашения назад
        coupon_dates = []
        temp_date = maturity
        
        while temp_date > settlement_date:
            coupon_dates.append(temp_date)
            # Отнимаем полгода
            temp_date = self._subtract_period(temp_date, bond_params.coupon_frequency)
        
        # Сортируем по возрастанию
        coupon_dates.sort()
        
        # Добавляем купоны
        for coupon_date in coupon_dates[:-1]:
            cash_flows.append((coupon_date, coupon_per_period))
        
        # Последний платёж = купон + номинал
        if coupon_dates:
            last_date = coupon_dates[-1]
            cash_flows.append((last_date, coupon_per_period + bond_params.face_value))
        
        return cash_flows
    
    def _subtract_period(self, dt: date, frequency: int) -> date:
        """
        Отнять один купонный период от даты
        
        Args:
            dt: Дата
            frequency: Купоны в год (2 = полугодовые)
            
        Returns:
            Новая дата
        """
        months_to_subtract = 12 // frequency
        
        year = dt.year
        month = dt.month - months_to_subtract
        
        if month <= 0:
            month += 12
            year -= 1
        
        # Корректируем день (например, 31 марта - 6 мес = 30 сентября)
        day = min(dt.day, 28)  # Безопасный день
        
        return date(year, month, day)
    
    def _solve_ytm_newton(
        self,
        price: float,
        cash_flows: List[tuple],
        settlement_date: date,
        initial_guess: float = 10.0
    ) -> float:
        """
        Найти YTM методом Ньютона-Рафсона
        
        f(ytm) = Sum(CF_i / (1 + ytm)^t_i) - Price = 0
        f'(ytm) = -Sum(t_i * CF_i / (1 + ytm)^(t_i + 1))
        """
        ytm = initial_guess
        
        for _ in range(self.max_iterations):
            # Вычисляем f(ytm) и f'(ytm)
            f_value = 0.0
            f_derivative = 0.0
            
            for cf_date, cf_amount in cash_flows:
                days = (cf_date - settlement_date).days
                years = days / 365.25
                
                discount = (1 + ytm / 100) ** years
                f_value += cf_amount / discount
                
                # Производная
                f_derivative -= years * cf_amount / (discount * (1 + ytm / 100))
            
            f_value -= price
            
            # Проверка сходимости
            if abs(f_value) < self.tolerance:
                return ytm
            
            # Шаг Ньютона
            if abs(f_derivative) < 1e-10:
                # Защита от деления на ноль
                break
            
            delta = f_value / f_derivative
            ytm = ytm - delta * 100  # Масштабируем для процентов
            
            # Ограничения
            ytm = max(0.1, min(50.0, ytm))
        
        # Если не сошлось, используем бисекцию
        return self._solve_ytm_bisection(price, cash_flows, settlement_date)
    
    def _solve_ytm_bisection(
        self,
        price: float,
        cash_flows: List[tuple],
        settlement_date: date,
        low: float = 0.1,
        high: float = 50.0
    ) -> float:
        """
        Найти YTM методом бисекции (более надёжный)
        """
        for _ in range(self.max_iterations):
            mid = (low + high) / 2
            
            # Вычисляем NPV при mid
            npv = 0.0
            for cf_date, cf_amount in cash_flows:
                days = (cf_date - settlement_date).days
                years = days / 365.25
                discount = (1 + mid / 100) ** years
                npv += cf_amount / discount
            
            npv -= price
            
            if abs(npv) < self.tolerance:
                return mid
            
            if npv > 0:
                low = mid
            else:
                high = mid
        
        return mid


def calculate_ytm_from_price(
    price_percent: float,
    bond_config: Any,
    settlement_date: Optional[date] = None
) -> Optional[float]:
    """
    Удобная функция для расчёта YTM из цены
    
    Args:
        price_percent: Цена в % от номинала
        bond_config: Конфигурация облигации (BondConfig)
        settlement_date: Дата расчёта
        
    Returns:
        YTM в % годовых
    """
    # Конвертируем BondConfig в BondParams
    try:
        maturity = datetime.strptime(bond_config.maturity_date, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        logger.warning(f"Неверная дата погашения: {bond_config.maturity_date}")
        return None
    
    params = BondParams(
        isin=bond_config.isin,
        name=bond_config.name,
        face_value=bond_config.face_value,
        coupon_rate=bond_config.coupon_rate,
        coupon_frequency=bond_config.coupon_frequency,
        maturity_date=maturity,
        day_count_convention=getattr(bond_config, 'day_count_convention', 'ACT/ACT')
    )
    
    calculator = YTMCalculator()
    return calculator.calculate_ytm(price_percent, params, settlement_date)


def calculate_simple_ytm(
    price_percent: float,
    coupon_rate: float,
    years_to_maturity: float,
    face_value: float = 1000
) -> float:
    """
    Быстрый упрощённый расчёт YTM
    
    YTM ≈ (C + (F - P) / n) / ((F + P) / 2)
    """
    if years_to_maturity <= 0:
        return coupon_rate
    
    price_abs = price_percent * face_value / 100
    annual_coupon = face_value * coupon_rate / 100
    
    numerator = annual_coupon + (face_value - price_abs) / years_to_maturity
    denominator = (face_value + price_abs) / 2
    
    ytm = (numerator / denominator) * 100
    
    return round(ytm, 2)
