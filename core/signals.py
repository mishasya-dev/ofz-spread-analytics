"""
Генерация торговых сигналов на основе спредов
"""
import pandas as pd
import numpy as np
from datetime import date, datetime
from typing import Optional, Dict, List, Tuple, Any
from dataclasses import dataclass
from enum import Enum
import logging

from .spread import SpreadStats, SpreadCalculator

logger = logging.getLogger(__name__)


class SignalType(Enum):
    """Тип торгового сигнала"""
    STRONG_BUY = "STRONG_BUY"       # Сильная покупка (спред ниже P10)
    BUY = "BUY"                     # Покупка (спред ниже P25)
    NEUTRAL = "NEUTRAL"             # Нейтрально
    SELL = "SELL"                   # Продажа (спред выше P75)
    STRONG_SELL = "STRONG_SELL"     # Сильная продажа (спред выше P90)
    NO_DATA = "NO_DATA"             # Недостаточно данных


class SignalDirection(Enum):
    """Направление позиции"""
    LONG_SHORT = "LONG_SHORT"   # Покупать длинную, продавать короткую
    SHORT_LONG = "SHORT_LONG"   # Продавать длинную, покупать короткую
    FLAT = "FLAT"               # Без позиции


@dataclass
class TradingSignal:
    """Торговый сигнал"""
    pair_name: str              # Название пары
    bond_long: str              # ISIN длинной облигации
    bond_short: str             # ISIN короткой облигации
    signal_type: SignalType     # Тип сигнала
    direction: SignalDirection  # Направление
    confidence: float           # Уверенность 0-1
    spread_bp: float            # Текущий спред
    spread_mean: float          # Средний спред
    spread_zscore: float        # Z-score спреда
    percentile_rank: float      # Перцентиль-ранг
    expected_return_bp: float   # Ожидаемый возврат в б.п.
    timestamp: datetime         # Время сигнала
    expires_at: Optional[datetime] = None  # Время истечения
    
    def to_dict(self) -> Dict[str, Any]:
        """Конвертировать в словарь"""
        return {
            "pair_name": self.pair_name,
            "bond_long": self.bond_long,
            "bond_short": self.bond_short,
            "signal_type": self.signal_type.value,
            "direction": self.direction.value,
            "confidence": round(self.confidence, 3),
            "spread_bp": self.spread_bp,
            "spread_mean": self.spread_mean,
            "spread_zscore": self.spread_zscore,
            "percentile_rank": self.percentile_rank,
            "expected_return_bp": self.expected_return_bp,
            "timestamp": self.timestamp.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None
        }


@dataclass
class SignalConfig:
    """Конфигурация сигналов"""
    percentile_entry_low: float = 10.0   # P10 - сильный вход
    percentile_entry_mid: float = 25.0   # P25 - умеренный вход
    percentile_exit_mid: float = 75.0    # P75 - умеренный выход
    percentile_exit_high: float = 90.0   # P90 - сильный выход
    min_confidence: float = 0.3          # Минимальная уверенность
    zscore_threshold: float = 1.5        # Порог Z-score
    lookback_days: int = 252             # Окно для перцентилей
    signal_expiry_hours: int = 4         # Время жизни сигнала (часы)


class SignalGenerator:
    """Генератор торговых сигналов"""
    
    def __init__(self, config: Optional[SignalConfig] = None):
        """
        Инициализация
        
        Args:
            config: Конфигурация сигналов
        """
        self.config = config or SignalConfig()
        self.spread_calculator = SpreadCalculator(self.config.lookback_days)
    
    def generate_signal(
        self,
        spread_series: pd.Series,
        bond_long: str,
        bond_short: str,
        pair_name: Optional[str] = None
    ) -> TradingSignal:
        """
        Сгенерировать торговый сигнал
        
        Args:
            spread_series: История спредов
            bond_long: ISIN длинной облигации
            bond_short: ISIN короткой облигации
            pair_name: Название пары
            
        Returns:
            TradingSignal
        """
        if pair_name is None:
            pair_name = f"{bond_long}_{bond_short}"
        
        # Очищаем данные
        spread_series = spread_series.dropna()
        
        if len(spread_series) < 20:
            return self._create_no_data_signal(bond_long, bond_short, pair_name)
        
        # Рассчитываем статистику
        try:
            stats = self.spread_calculator.calculate_spread_stats(spread_series)
        except ValueError:
            return self._create_no_data_signal(bond_long, bond_short, pair_name)
        
        # Определяем перцентиль-ранг
        percentile_rank = self.spread_calculator.get_spread_percentile_rank(
            stats.current, spread_series
        )
        
        # Определяем тип сигнала и направление
        signal_type, direction, confidence = self._classify_signal(
            stats.current, 
            stats.percentile_10,
            stats.percentile_25,
            stats.percentile_75,
            stats.percentile_90,
            stats.zscore
        )
        
        # Рассчитываем ожидаемый возврат
        expected_return = self._calculate_expected_return(
            stats.current,
            stats.mean,
            direction
        )
        
        # Время истечения сигнала
        expires_at = datetime.now() + pd.Timedelta(hours=self.config.signal_expiry_hours)
        
        return TradingSignal(
            pair_name=pair_name,
            bond_long=bond_long,
            bond_short=bond_short,
            signal_type=signal_type,
            direction=direction,
            confidence=confidence,
            spread_bp=stats.current,
            spread_mean=stats.mean,
            spread_zscore=stats.zscore,
            percentile_rank=percentile_rank,
            expected_return_bp=expected_return,
            timestamp=datetime.now(),
            expires_at=expires_at
        )
    
    def generate_all_signals(
        self,
        spread_history: Dict[str, pd.DataFrame],
        pairs: List[Tuple[str, str]]
    ) -> List[TradingSignal]:
        """
        Сгенерировать сигналы для всех пар
        
        Args:
            spread_history: История спредов {pair_key: DataFrame}
            pairs: Список пар (ISIN_long, ISIN_short)
            
        Returns:
            Список TradingSignal
        """
        signals = []
        
        for bond_long, bond_short in pairs:
            pair_key = f"{bond_long}_{bond_short}"
            
            if pair_key not in spread_history:
                logger.warning(f"Нет истории для пары {pair_key}")
                continue
            
            df = spread_history[pair_key]
            
            if "spread_bp" not in df.columns:
                logger.warning(f"Нет данных спреда для пары {pair_key}")
                continue
            
            signal = self.generate_signal(
                df["spread_bp"],
                bond_long,
                bond_short,
                pair_key
            )
            
            signals.append(signal)
        
        return signals
    
    def filter_signals(
        self,
        signals: List[TradingSignal],
        min_confidence: Optional[float] = None,
        exclude_neutral: bool = True
    ) -> List[TradingSignal]:
        """
        Отфильтровать сигналы
        
        Args:
            signals: Список сигналов
            min_confidence: Минимальная уверенность
            exclude_neutral: Исключить нейтральные
            
        Returns:
            Отфильтрованный список
        """
        if min_confidence is None:
            min_confidence = self.config.min_confidence
        
        filtered = []
        
        for signal in signals:
            # Пропускаем NO_DATA
            if signal.signal_type == SignalType.NO_DATA:
                continue
            
            # Пропускаем нейтральные если нужно
            if exclude_neutral and signal.signal_type == SignalType.NEUTRAL:
                continue
            
            # Проверяем уверенность
            if signal.confidence < min_confidence:
                continue
            
            filtered.append(signal)
        
        return filtered
    
    def get_active_signals(
        self,
        signals: List[TradingSignal]
    ) -> List[TradingSignal]:
        """
        Получить активные (не истёкшие) сигналы
        
        Args:
            signals: Список сигналов
            
        Returns:
            Список активных сигналов
        """
        now = datetime.now()
        
        return [
            s for s in signals
            if s.expires_at is None or s.expires_at > now
        ]
    
    def _classify_signal(
        self,
        current: float,
        p10: float,
        p25: float,
        p75: float,
        p90: float,
        zscore: float
    ) -> Tuple[SignalType, SignalDirection, float]:
        """
        Классифицировать сигнал
        
        Args:
            current: Текущий спред
            p10, p25, p75, p90: Перцентили
            zscore: Z-score
            
        Returns:
            (SignalType, SignalDirection, confidence)
        """
        # Спред ниже P10 - сильная покупка (спред слишком узкий, ожидаем расширение)
        if current <= p10:
            confidence = min(1.0, abs(zscore) / 3)
            return SignalType.STRONG_BUY, SignalDirection.LONG_SHORT, max(0.7, confidence)
        
        # Спред между P10 и P25 - покупка
        if current <= p25:
            confidence = 0.4 + 0.3 * (p25 - current) / (p25 - p10)
            return SignalType.BUY, SignalDirection.LONG_SHORT, confidence
        
        # Спред между P75 и P90 - продажа
        if current >= p75:
            confidence = 0.4 + 0.3 * (current - p75) / (p90 - p75)
            return SignalType.SELL, SignalDirection.SHORT_LONG, confidence
        
        # Спред выше P90 - сильная продажа (спред слишком широкий, ожидаем сужение)
        if current >= p90:
            confidence = min(1.0, abs(zscore) / 3)
            return SignalType.STRONG_SELL, SignalDirection.SHORT_LONG, max(0.7, confidence)
        
        # Нейтральная зона
        return SignalType.NEUTRAL, SignalDirection.FLAT, 0.2
    
    def _calculate_expected_return(
        self,
        current: float,
        mean: float,
        direction: SignalDirection
    ) -> float:
        """
        Рассчитать ожидаемый возврат
        
        При возврате к среднему:
        - LONG_SHORT: покупаем спред, ждём расширения
        - SHORT_LONG: продаём спред, ждём сужения
        
        Args:
            current: Текущий спред
            mean: Средний спред
            direction: Направление
            
        Returns:
            Ожидаемый возврат в б.п.
        """
        if direction == SignalDirection.FLAT:
            return 0.0
        
        # Возврат к среднему
        expected_move = mean - current
        
        if direction == SignalDirection.LONG_SHORT:
            # Покупаем спред, прибыль при расширении (current < mean)
            return round(expected_move, 2)
        else:
            # Продаём спред, прибыль при сужении (current > mean)
            return round(-expected_move, 2)
    
    def _create_no_data_signal(
        self,
        bond_long: str,
        bond_short: str,
        pair_name: str
    ) -> TradingSignal:
        """Создать сигнал NO_DATA"""
        return TradingSignal(
            pair_name=pair_name,
            bond_long=bond_long,
            bond_short=bond_short,
            signal_type=SignalType.NO_DATA,
            direction=SignalDirection.FLAT,
            confidence=0.0,
            spread_bp=0.0,
            spread_mean=0.0,
            spread_zscore=0.0,
            percentile_rank=50.0,
            expected_return_bp=0.0,
            timestamp=datetime.now()
        )


def generate_signal_from_spread(
    spread_series: pd.Series,
    bond_long: str,
    bond_short: str
) -> TradingSignal:
    """
    Быстрая генерация сигнала из серии спредов
    
    Args:
        spread_series: История спредов
        bond_long: ISIN длинной облигации
        bond_short: ISIN короткой облигации
        
    Returns:
        TradingSignal
    """
    generator = SignalGenerator()
    return generator.generate_signal(spread_series, bond_long, bond_short)
