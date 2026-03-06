"""
Расчёт YTM для облигаций из цен свечей

Отделён от API (moex_candles.py) для:
1. Чистого разделения ответственности
2. Возможности использовать разные источники данных
3. Лёгкого тестирования бизнес-логики
"""
from datetime import date, timedelta
from typing import Optional, Dict, Any
import pandas as pd
import logging

from core.ytm_calculator import YTMCalculator, BondParams

logger = logging.getLogger(__name__)


def get_t1_settlement_date(trade_date: date) -> date:
    """
    Получить дату расчётов (settlement date) для режима Т+1
    
    Торги ОФЗ проходят в режиме Т+1:
    - Понедельник -> Вторник (+1)
    - Вторник -> Среда (+1)
    - Среда -> Четверг (+1)
    - Четверг -> Пятница (+1)
    - Пятница -> Понедельник (+3)
    
    Args:
        trade_date: Дата сделки (дата свечи)
        
    Returns:
        Дата расчётов (settlement date)
    """
    weekday = trade_date.weekday()  # 0=Пн, 4=Пт
    
    if weekday == 4:  # Пятница
        return trade_date + timedelta(days=3)  # -> Понедельник
    else:
        return trade_date + timedelta(days=1)  # -> Следующий день


class BondYTMProcessor:
    """
    Расчёт YTM для облигаций из цен свечей
    
    Используется после получения сырых свечей из API.
    Добавляет колонку ytm_close к DataFrame.
    """
    
    def __init__(self):
        """Инициализация процессора"""
        self._ytm_calculator = YTMCalculator()
        self._bond_params_cache: Dict[str, BondParams] = {}
    
    def add_ytm_to_candles(
        self,
        candles_df: pd.DataFrame,
        bond_config: Any
    ) -> pd.DataFrame:
        """
        Добавить YTM к DataFrame свечей
        
        Args:
            candles_df: DataFrame с сырыми свечами (close, datetime index)
            bond_config: Конфигурация облигации (BondConfig или Bond)
            
        Returns:
            DataFrame с добавленной колонкой ytm_close
        """
        if candles_df.empty:
            return candles_df
        
        if 'close' not in candles_df.columns:
            logger.warning("DataFrame не содержит колонку 'close'")
            return candles_df
        
        # Создаём BondParams
        bond_params = self._get_bond_params(bond_config)
        if bond_params is None:
            logger.warning(f"Не удалось создать параметры для {bond_config.isin}")
            return candles_df
        
        # Копируем DataFrame
        result_df = candles_df.copy()
        
        # Рассчитываем YTM для каждой свечи
        ytm_close_list = []
        
        for idx, row in result_df.iterrows():
            trade_date = self._extract_trade_date(idx)
            settlement_date = get_t1_settlement_date(trade_date)
            
            # Рассчитываем НКД на settlement date
            accrued_interest = self._ytm_calculator.calculate_accrued_interest_for_date(
                bond_params, settlement_date
            )
            
            # Рассчитываем YTM
            ytm = self._safe_calculate_ytm(
                row.get('close'),
                bond_params,
                accrued_interest,
                settlement_date
            )
            ytm_close_list.append(ytm)
        
        result_df['ytm_close'] = ytm_close_list
        
        # Добавляем алиас для совместимости
        result_df['ytm'] = result_df['ytm_close']
        
        logger.debug(f"Рассчитан YTM для {len(result_df)} свечей, {bond_config.isin}")
        
        return result_df
    
    def calculate_ytm_for_price(
        self,
        price: float,
        bond_config: Any,
        trade_date: date
    ) -> Optional[float]:
        """
        Рассчитать YTM для одной цены
        
        Args:
            price: Цена в % от номинала
            bond_config: Конфигурация облигации
            trade_date: Дата сделки
            
        Returns:
            YTM в % годовых или None
        """
        if price is None or price <= 0:
            return None
        
        bond_params = self._get_bond_params(bond_config)
        if bond_params is None:
            return None
        
        # T+1 settlement
        settlement_date = get_t1_settlement_date(trade_date)
        
        # НКД на settlement date
        accrued_interest = self._ytm_calculator.calculate_accrued_interest_for_date(
            bond_params, settlement_date
        )
        
        return self._safe_calculate_ytm(
            price,
            bond_params,
            accrued_interest,
            settlement_date
        )
    
    def _get_bond_params(self, bond_config: Any) -> Optional[BondParams]:
        """
        Создать BondParams из конфигурации облигации
        
        Использует кэширование для оптимизации.
        """
        isin = bond_config.isin
        
        if isin in self._bond_params_cache:
            return self._bond_params_cache[isin]
        
        # Парсим дату погашения
        try:
            maturity_str = bond_config.maturity_date
            if isinstance(maturity_str, str):
                from datetime import datetime
                maturity = datetime.strptime(maturity_str, "%Y-%m-%d").date()
            else:
                maturity = maturity_str
        except (ValueError, TypeError) as e:
            logger.warning(f"Неверная дата погашения для {isin}: {bond_config.maturity_date}")
            return None
        
        # Парсим дату выпуска если есть
        issue_date = None
        if hasattr(bond_config, 'issue_date') and bond_config.issue_date:
            try:
                if isinstance(bond_config.issue_date, str):
                    from datetime import datetime
                    issue_date = datetime.strptime(bond_config.issue_date, "%Y-%m-%d").date()
                else:
                    issue_date = bond_config.issue_date
            except (ValueError, TypeError):
                pass
        
        params = BondParams(
            isin=isin,
            name=getattr(bond_config, 'name', isin),
            face_value=getattr(bond_config, 'face_value', 1000),
            coupon_rate=bond_config.coupon_rate,
            coupon_frequency=getattr(bond_config, 'coupon_frequency', 2),
            maturity_date=maturity,
            issue_date=issue_date,
            day_count_convention=getattr(bond_config, 'day_count_convention', 'ACT/ACT')
        )
        
        self._bond_params_cache[isin] = params
        return params
    
    def _extract_trade_date(self, idx) -> date:
        """Извлечь дату сделки из индекса"""
        if hasattr(idx, 'date'):
            return idx.date()
        if isinstance(idx, pd.Timestamp):
            return idx.date()
        if isinstance(idx, date):
            return idx
        # Fallback
        return date.today()
    
    def _safe_calculate_ytm(
        self,
        price: float,
        bond_params: BondParams,
        accrued_interest: float,
        settlement_date: date
    ) -> Optional[float]:
        """
        Безопасный расчёт YTM с обработкой ошибок
        """
        if price is None or price <= 0:
            return None
        
        try:
            ytm = self._ytm_calculator.calculate_ytm(
                price,
                bond_params,
                settlement_date=settlement_date,
                accrued_interest=accrued_interest
            )
            return ytm
        except Exception as e:
            logger.debug(f"Ошибка расчёта YTM: {e}")
            # Пробуем упрощённый расчёт
            try:
                return self._ytm_calculator.calculate_ytm_simple(
                    price, bond_params, settlement_date
                )
            except Exception:
                return None


# Удобная функция для быстрого использования
def calculate_ytm_for_bond_price(
    price: float,
    bond_config: Any,
    trade_date: Optional[date] = None
) -> Optional[float]:
    """
    Рассчитать YTM для цены облигации
    
    Args:
        price: Цена в % от номинала
        bond_config: Конфигурация облигации
        trade_date: Дата сделки (по умолчанию сегодня)
        
    Returns:
        YTM в % годовых
    """
    if trade_date is None:
        trade_date = date.today()
    
    processor = BondYTMProcessor()
    return processor.calculate_ytm_for_price(price, bond_config, trade_date)
