"""
Сервис для анализа коинтеграции с кэшированием результатов

Использование:
    from core.cointegration_service import CointegrationService

    service = CointegrationService()
    result = service.get_or_calculate(bond1_isin, bond2_isin, period_days, ytm1_series, ytm2_series)

Ключи кэша:
    - bond1_isin + bond2_isin (алфавитный порядок)
    - period_days
    - TTL = 24 часа по умолчанию
"""
import pandas as pd
from typing import Dict, Optional
import logging

from core.cointegration import CointegrationAnalyzer
from core.db import get_db_facade

logger = logging.getLogger(__name__)


class CointegrationService:
    """
    Сервис для анализа коинтеграции с кэшированием.

    Инкапсулирует:
    - Проверку кэша в БД
    - Вызов CointegrationAnalyzer если нужно
    - Сохранение результата в кэш
    """

    def __init__(self, ttl_hours: int = 24):
        """
        Args:
            ttl_hours: Время жизни кэша в часах (default 24)
        """
        self.ttl_hours = ttl_hours
        self.analyzer = CointegrationAnalyzer()
        self.db = get_db_facade()

    def get_or_calculate(
        self,
        bond1_isin: str,
        bond2_isin: str,
        period_days: int,
        ytm1: pd.Series,
        ytm2: pd.Series,
        force_refresh: bool = False
    ) -> Dict:
        """
        Получить результат коинтеграции (из кэша или рассчитать).

        Args:
            bond1_isin: ISIN первой облигации
            bond2_isin: ISIN второй облигации
            period_days: Период анализа в днях
            ytm1: Series с YTM первой облигации
            ytm2: Series с YTM второй облигации
            force_refresh: Принудительно пересчитать (игнорировать кэш)

        Returns:
            Словарь с результатом анализа:
            - n_observations
            - engle_granger
            - adf_ytm1, adf_ytm2, adf_spread
            - kpss_spread
            - half_life
            - hedge_ratio
            - is_cointegrated
            - both_nonstationary
            - recommendation
            - from_cache: True если взято из кэша
        """
        logger.debug(f"get_or_calculate: {bond1_isin}/{bond2_isin} period={period_days} force={force_refresh}")

        # Проверяем кэш
        if not force_refresh:
            cached = self.db.get_cointegration_cache(
                bond1_isin, bond2_isin, period_days, ttl_hours=self.ttl_hours
            )
            if cached is not None:
                cached['from_cache'] = True
                logger.info(f"📦 Из кэша: {bond1_isin}/{bond2_isin} period={period_days}")
                return cached

        # Рассчитываем
        logger.info(f"✨ Расчёт: {bond1_isin}/{bond2_isin} period={period_days}")
        result = self._calculate(ytm1, ytm2)

        # Логируем результат
        if 'error' not in result:
            eg = result.get('engle_granger', {})
            adf1 = result.get('adf_ytm1', {})
            adf2 = result.get('adf_ytm2', {})
            
            p1 = adf1.get('pvalue')
            p2 = adf2.get('pvalue')
            
            p1_str = f"{p1:.4f}" if p1 is not None else "N/A"
            p2_str = f"{p2:.4f}" if p2 is not None else "N/A"
            eg_p_str = f"{eg.get('pvalue'):.4f}" if eg.get('pvalue') is not None else "N/A"
            
            logger.info(f"ADF: ytm1_p={p1_str}, ytm2_p={p2_str}, "
                       f"both_nonstationary={result.get('both_nonstationary')}, "
                       f"n_obs={result.get('n_observations')}")
            logger.info(f"Engle-Granger: p={eg_p_str}, is_cointegrated={result.get('is_cointegrated')}")

        # Сохраняем в кэш (даже если ошибка - сохраняем чтобы не долбить повторно)
        if 'error' not in result:
            self.db.save_cointegration_cache(
                bond1_isin, bond2_isin, period_days, result
            )
            logger.debug(f"Сохранено в кэш: {bond1_isin}/{bond2_isin} period={period_days}")

        result['from_cache'] = False
        return result

    def _calculate(self, ytm1: pd.Series, ytm2: pd.Series) -> Dict:
        """
        Выполнить расчёт коинтеграции.

        Args:
            ytm1: Series с YTM первой облигации
            ytm2: Series с YTM второй облигации

        Returns:
            Словарь с результатом
        """
        # Проверка данных
        if ytm1 is None or ytm2 is None:
            return {'error': 'YTM data is None'}

        ytm1 = ytm1.dropna()
        ytm2 = ytm2.dropna()

        if len(ytm1) < 30 or len(ytm2) < 30:
            return {
                'error': 'Insufficient data',
                'n_observations': min(len(ytm1), len(ytm2)),
                'min_required': 30
            }

        try:
            return self.analyzer.analyze_pair(ytm1, ytm2)
        except Exception as e:
            logger.error(f"Ошибка расчёта коинтеграции: {e}", exc_info=True)
            return {'error': str(e)}

    def clear_cache(
        self,
        bond1_isin: str = None,
        bond2_isin: str = None,
        period_days: int = None
    ) -> int:
        """
        Очистить кэш коинтеграции.

        Args:
            bond1_isin: ISIN первой облигации (опционально)
            bond2_isin: ISIN второй облигации (опционально)
            period_days: Период (опционально)

        Returns:
            Количество удалённых записей
        """
        return self.db.clear_cointegration_cache(bond1_isin, bond2_isin, period_days)


# Singleton для удобства
_service = None


def get_cointegration_service() -> CointegrationService:
    """Получить singleton сервиса коинтеграции"""
    global _service
    if _service is None:
        _service = CointegrationService()
    return _service
