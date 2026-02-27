"""
Сервисы для OFZ Spread Analytics

Сервисы инкапсулируют бизнес-логику и работу с внешними API.
"""
from .candle_service import CandleService, get_candle_service

__all__ = [
    'CandleService',
    'get_candle_service',
]
