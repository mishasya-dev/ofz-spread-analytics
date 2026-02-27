"""
Бэктестинг торговых сигналов
"""
import pandas as pd
import numpy as np
from datetime import date, datetime, timedelta
from typing import Optional, Dict, List, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
import logging

from .signals import SignalType, SignalDirection, TradingSignal
from .spread import SpreadCalculator

logger = logging.getLogger(__name__)


class PositionState(Enum):
    """Состояние позиции"""
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    STOPPED = "STOPPED"
    TAKEN = "TAKEN"


@dataclass
class Position:
    """Торговая позиция"""
    pair_name: str
    direction: SignalDirection
    entry_date: date
    entry_spread: float
    entry_ytm_long: float
    entry_ytm_short: float
    size: float  # Размер позиции в рублях
    state: PositionState = PositionState.OPEN
    exit_date: Optional[date] = None
    exit_spread: Optional[float] = None
    exit_ytm_long: Optional[float] = None
    exit_ytm_short: Optional[float] = None
    pnl_bp: float = 0.0
    pnl_rub: float = 0.0
    holding_days: int = 0
    stop_loss_bp: Optional[float] = None
    take_profit_bp: Optional[float] = None
    exit_reason: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Конвертировать в словарь"""
        return {
            "pair_name": self.pair_name,
            "direction": self.direction.value,
            "entry_date": self.entry_date.isoformat(),
            "entry_spread": self.entry_spread,
            "exit_date": self.exit_date.isoformat() if self.exit_date else None,
            "exit_spread": self.exit_spread,
            "pnl_bp": round(self.pnl_bp, 2),
            "pnl_rub": round(self.pnl_rub, 2),
            "holding_days": self.holding_days,
            "state": self.state.value,
            "exit_reason": self.exit_reason
        }


@dataclass
class BacktestResult:
    """Результаты бэктестинга"""
    # Основные метрики
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    
    # Доходность
    total_pnl_bp: float = 0.0
    total_pnl_rub: float = 0.0
    total_pnl_percent: float = 0.0
    
    # Средние значения
    avg_pnl_bp: float = 0.0
    avg_winning_bp: float = 0.0
    avg_losing_bp: float = 0.0
    avg_holding_days: float = 0.0
    
    # Риск-метрики
    max_drawdown_bp: float = 0.0
    max_drawdown_rub: float = 0.0
    sharpe_ratio: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    
    # Кривая капитала
    equity_curve: List[float] = field(default_factory=list)
    trade_dates: List[date] = field(default_factory=list)
    
    # Позиции
    positions: List[Position] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Конвертировать в словарь"""
        return {
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "win_rate": round(self.win_rate, 2),
            "total_pnl_bp": round(self.total_pnl_bp, 2),
            "total_pnl_rub": round(self.total_pnl_rub, 2),
            "total_pnl_percent": round(self.total_pnl_percent, 2),
            "avg_pnl_bp": round(self.avg_pnl_bp, 2),
            "avg_winning_bp": round(self.avg_winning_bp, 2),
            "avg_losing_bp": round(self.avg_losing_bp, 2),
            "avg_holding_days": round(self.avg_holding_days, 1),
            "max_drawdown_bp": round(self.max_drawdown_bp, 2),
            "max_drawdown_rub": round(self.max_drawdown_rub, 2),
            "sharpe_ratio": round(self.sharpe_ratio, 3),
            "profit_factor": round(self.profit_factor, 3),
            "positions": [p.to_dict() for p in self.positions]
        }


@dataclass
class BacktestConfig:
    """Конфигурация бэктестинга"""
    initial_capital: float = 1_000_000.0
    position_size_pct: float = 0.25    # 25% капитала на позицию
    commission_rate: float = 0.0005    # 0.05% комиссия
    spread_cost_bp: float = 0.5        # 0.5 б.п. затраты на спред
    
    max_holding_days: int = 10         # Максимум дней удержания
    stop_loss_bp: float = 20.0         # Стоп-лосс в б.п.
    take_profit_bp: float = 30.0       # Тейк-профит в б.п.
    
    entry_percentile_low: float = 10.0  # P10 для входа
    entry_percentile_high: float = 90.0 # P90 для входа
    exit_percentile: float = 50.0       # P50 для выхода
    
    min_history_days: int = 100         # Минимум истории для сигналов


class Backtester:
    """Бэктестер торговых стратегий"""
    
    def __init__(self, config: Optional[BacktestConfig] = None):
        """
        Инициализация
        
        Args:
            config: Конфигурация бэктестинга
        """
        self.config = config or BacktestConfig()
        self.spread_calculator = SpreadCalculator()
    
    def run_backtest(
        self,
        spread_history: pd.DataFrame,
        ytm_long_history: pd.Series,
        ytm_short_history: pd.Series,
        pair_name: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> BacktestResult:
        """
        Запустить бэктест
        
        Args:
            spread_history: DataFrame с историей спредов (index=date, column='spread_bp')
            ytm_long_history: Series с историей YTM длинной облигации
            ytm_short_history: Series с историей YTM короткой облигации
            pair_name: Название пары
            start_date: Начальная дата
            end_date: Конечная дата
            
        Returns:
            BacktestResult с результатами
        """
        # Подготовка данных
        df = self._prepare_data(spread_history, ytm_long_history, ytm_short_history)
        
        if df.empty or len(df) < self.config.min_history_days:
            logger.warning(f"Недостаточно данных для бэктеста {pair_name}")
            return BacktestResult()
        
        # Фильтрация по датам
        if start_date:
            df = df[df.index >= pd.Timestamp(start_date)]
        if end_date:
            df = df[df.index <= pd.Timestamp(end_date)]
        
        # Расчёт перцентилей
        df = self._calculate_rolling_percentiles(df)
        
        # Симуляция торговли
        positions = self._simulate_trading(df, pair_name)
        
        # Расчёт результатов
        result = self._calculate_results(positions)
        
        return result
    
    def run_multi_pair_backtest(
        self,
        spread_data: Dict[str, pd.DataFrame],
        ytm_data: Dict[str, pd.DataFrame],
        pairs: List[Tuple[str, str]],
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> Dict[str, BacktestResult]:
        """
        Запустить бэктест для нескольких пар
        
        Args:
            spread_data: История спредов {pair_key: DataFrame}
            ytm_data: История YTM {ISIN: DataFrame}
            pairs: Список пар (ISIN_long, ISIN_short)
            start_date: Начальная дата
            end_date: Конечная дата
            
        Returns:
            Словарь {pair_key: BacktestResult}
        """
        results = {}
        
        for bond_long, bond_short in pairs:
            pair_key = f"{bond_long}_{bond_short}"
            
            if pair_key not in spread_data:
                logger.warning(f"Нет данных спреда для {pair_key}")
                continue
            
            if bond_long not in ytm_data or bond_short not in ytm_data:
                logger.warning(f"Нет YTM данных для {pair_key}")
                continue
            
            spread_df = spread_data[pair_key]
            ytm_long = ytm_data[bond_long]["ytm"]
            ytm_short = ytm_data[bond_short]["ytm"]
            
            result = self.run_backtest(
                spread_df,
                ytm_long,
                ytm_short,
                pair_key,
                start_date,
                end_date
            )
            
            results[pair_key] = result
        
        return results
    
    def calculate_strategy_metrics(
        self,
        results: Dict[str, BacktestResult]
    ) -> Dict[str, Any]:
        """
        Рассчитать агрегированные метрики стратегии
        
        Args:
            results: Результаты по парам
            
        Returns:
            Агрегированные метрики
        """
        if not results:
            return {}
        
        total_trades = sum(r.total_trades for r in results.values())
        total_winning = sum(r.winning_trades for r in results.values())
        total_pnl_bp = sum(r.total_pnl_bp for r in results.values())
        total_pnl_rub = sum(r.total_pnl_rub for r in results.values())
        
        win_rate = (total_winning / total_trades * 100) if total_trades > 0 else 0
        
        # Лучшие и худшие пары
        sorted_by_pnl = sorted(
            [(k, v.total_pnl_bp) for k, v in results.items()],
            key=lambda x: x[1],
            reverse=True
        )
        
        return {
            "total_pairs": len(results),
            "total_trades": total_trades,
            "total_winning": total_winning,
            "win_rate": round(win_rate, 2),
            "total_pnl_bp": round(total_pnl_bp, 2),
            "total_pnl_rub": round(total_pnl_rub, 2),
            "avg_pnl_per_pair": round(total_pnl_bp / len(results), 2),
            "best_pair": sorted_by_pnl[0] if sorted_by_pnl else None,
            "worst_pair": sorted_by_pnl[-1] if sorted_by_pnl else None,
            "profitable_pairs": sum(1 for r in results.values() if r.total_pnl_bp > 0)
        }
    
    def _prepare_data(
        self,
        spread_history: pd.DataFrame,
        ytm_long_history: pd.Series,
        ytm_short_history: pd.Series
    ) -> pd.DataFrame:
        """Подготовить данные для бэктеста"""
        # Извлекаем серию спредов
        if isinstance(spread_history, pd.DataFrame):
            if "spread_bp" in spread_history.columns:
                spread_series = spread_history["spread_bp"]
            else:
                spread_series = spread_history.iloc[:, 0]
        else:
            spread_series = spread_history
        
        # Объединяем данные
        df = pd.DataFrame({
            "spread_bp": spread_series,
            "ytm_long": ytm_long_history,
            "ytm_short": ytm_short_history
        })
        
        df = df.dropna()
        
        return df
    
    def _calculate_rolling_percentiles(self, df: pd.DataFrame) -> pd.DataFrame:
        """Рассчитать скользящие перцентили"""
        lookback = 252  # Торговых дней
        
        # Функция для расчёта перцентилей
        def rolling_percentile(series, window, percentile):
            return series.rolling(window, min_periods=20).quantile(percentile / 100)
        
        df["p10"] = rolling_percentile(df["spread_bp"], lookback, 10)
        df["p25"] = rolling_percentile(df["spread_bp"], lookback, 25)
        df["p50"] = rolling_percentile(df["spread_bp"], lookback, 50)
        df["p75"] = rolling_percentile(df["spread_bp"], lookback, 75)
        df["p90"] = rolling_percentile(df["spread_bp"], lookback, 90)
        
        # Среднее и стандартное отклонение
        df["spread_mean"] = df["spread_bp"].rolling(lookback, min_periods=20).mean()
        df["spread_std"] = df["spread_bp"].rolling(lookback, min_periods=20).std()
        
        return df
    
    def _simulate_trading(
        self,
        df: pd.DataFrame,
        pair_name: str
    ) -> List[Position]:
        """Симулировать торговлю"""
        positions = []
        current_position: Optional[Position] = None
        capital = self.config.initial_capital
        equity_curve = [capital]
        
        for i in range(len(df)):
            current_date = df.index[i].date() if hasattr(df.index[i], 'date') else df.index[i]
            row = df.iloc[i]
            
            # Пропускаем если нет перцентилей
            if pd.isna(row.get("p10")) or pd.isna(row.get("p90")):
                continue
            
            # Управление открытой позицией
            if current_position and current_position.state == PositionState.OPEN:
                current_position = self._manage_position(
                    current_position, row, current_date, capital
                )
                
                if current_position.state != PositionState.OPEN:
                    positions.append(current_position)
                    capital += current_position.pnl_rub
                    equity_curve.append(capital)
                    current_position = None
            
            # Открытие новой позиции
            if current_position is None:
                signal = self._check_entry_signal(row)
                
                if signal:
                    position_size = capital * self.config.position_size_pct
                    current_position = Position(
                        pair_name=pair_name,
                        direction=signal,
                        entry_date=current_date,
                        entry_spread=row["spread_bp"],
                        entry_ytm_long=row["ytm_long"],
                        entry_ytm_short=row["ytm_short"],
                        size=position_size,
                        stop_loss_bp=self.config.stop_loss_bp,
                        take_profit_bp=self.config.take_profit_bp
                    )
        
        return positions
    
    def _check_entry_signal(self, row: pd.Series) -> Optional[SignalDirection]:
        """Проверить сигнал на вход"""
        spread = row["spread_bp"]
        p10 = row.get("p10")
        p90 = row.get("p90")
        
        if pd.isna(p10) or pd.isna(p90):
            return None
        
        # Спред ниже P10 - покупка (ожидаем расширение)
        if spread <= p10:
            return SignalDirection.LONG_SHORT
        
        # Спред выше P90 - продажа (ожидаем сужение)
        if spread >= p90:
            return SignalDirection.SHORT_LONG
        
        return None
    
    def _manage_position(
        self,
        position: Position,
        row: pd.Series,
        current_date: date,
        capital: float
    ) -> Position:
        """Управление открытой позицией"""
        current_spread = row["spread_bp"]
        spread_change = current_spread - position.entry_spread
        p50 = row.get("p50", position.entry_spread)
        
        # Расчёт P&L в базисных пунктах
        if position.direction == SignalDirection.LONG_SHORT:
            # Длинная позиция по спреду - прибыль при росте спреда
            pnl_bp = spread_change
        else:
            # Короткая позиция по спреду - прибыль при падении спреда
            pnl_bp = -spread_change
        
        position.holding_days = (current_date - position.entry_date).days
        
        # Проверка стоп-лосса
        if pnl_bp <= -self.config.stop_loss_bp:
            position.state = PositionState.STOPPED
            position.exit_reason = "STOP_LOSS"
            position.exit_spread = current_spread
            position.exit_date = current_date
            position.pnl_bp = pnl_bp - self.config.spread_cost_bp
            position.pnl_rub = self._calculate_pnl_rub(position, capital)
            return position
        
        # Проверка тейк-профита
        if pnl_bp >= self.config.take_profit_bp:
            position.state = PositionState.TAKEN
            position.exit_reason = "TAKE_PROFIT"
            position.exit_spread = current_spread
            position.exit_date = current_date
            position.pnl_bp = pnl_bp - self.config.spread_cost_bp
            position.pnl_rub = self._calculate_pnl_rub(position, capital)
            return position
        
        # Выход по возврату к среднему
        if position.direction == SignalDirection.LONG_SHORT:
            # Закрытие когда спред вернулся к P50 сверху
            if current_spread >= p50:
                position.state = PositionState.CLOSED
                position.exit_reason = "MEAN_REVERSION"
                position.exit_spread = current_spread
                position.exit_date = current_date
                position.pnl_bp = pnl_bp - self.config.spread_cost_bp
                position.pnl_rub = self._calculate_pnl_rub(position, capital)
                return position
        else:
            # Закрытие когда спред вернулся к P50 снизу
            if current_spread <= p50:
                position.state = PositionState.CLOSED
                position.exit_reason = "MEAN_REVERSION"
                position.exit_spread = current_spread
                position.exit_date = current_date
                position.pnl_bp = pnl_bp - self.config.spread_cost_bp
                position.pnl_rub = self._calculate_pnl_rub(position, capital)
                return position
        
        # Максимум дней удержания
        if position.holding_days >= self.config.max_holding_days:
            position.state = PositionState.CLOSED
            position.exit_reason = "MAX_HOLDING"
            position.exit_spread = current_spread
            position.exit_date = current_date
            position.pnl_bp = pnl_bp - self.config.spread_cost_bp
            position.pnl_rub = self._calculate_pnl_rub(position, capital)
            return position
        
        return position
    
    def _calculate_pnl_rub(self, position: Position, capital: float) -> float:
        """Рассчитать P&L в рублях"""
        # Упрощённый расчёт: P&L_bp * размер_позиции / 10000
        # 1 б.п. = 0.01% от позиции
        pnl_rub = position.pnl_bp * position.size / 10000
        
        # Вычитаем комиссию
        commission = position.size * self.config.commission_rate * 2  # Вход + выход
        pnl_rub -= commission
        
        return pnl_rub

    def _calculate_results(self, positions: List[Position]) -> BacktestResult:
        """Рассчитать итоговые метрики"""
        if not positions:
            return BacktestResult()
        
        result = BacktestResult()
        result.positions = positions
        result.total_trades = len(positions)
        
        # Подсчёт выигрышей/проигрышей
        for pos in positions:
            result.total_pnl_bp += pos.pnl_bp
            result.total_pnl_rub += pos.pnl_rub
            
            if pos.pnl_bp > 0:
                result.winning_trades += 1
            else:
                result.losing_trades += 1
        
        # Win rate
        result.win_rate = result.winning_trades / result.total_trades * 100
        
        # Средние значения
        result.avg_pnl_bp = result.total_pnl_bp / result.total_trades
        result.avg_holding_days = np.mean([p.holding_days for p in positions])
        
        if result.winning_trades > 0:
            result.avg_winning_bp = np.mean([p.pnl_bp for p in positions if p.pnl_bp > 0])
        
        if result.losing_trades > 0:
            result.avg_losing_bp = np.mean([p.pnl_bp for p in positions if p.pnl_bp <= 0])
        
        # Profit Factor
        gross_profit = sum(p.pnl_bp for p in positions if p.pnl_bp > 0)
        gross_loss = abs(sum(p.pnl_bp for p in positions if p.pnl_bp <= 0))
        result.profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0
        
        # P&L в процентах
        result.total_pnl_percent = result.total_pnl_rub / self.config.initial_capital * 100
        
        # Max Drawdown
        cumulative_pnl = 0
        max_pnl = 0
        max_drawdown = 0
        
        for pos in positions:
            cumulative_pnl += pos.pnl_bp
            max_pnl = max(max_pnl, cumulative_pnl)
            drawdown = max_pnl - cumulative_pnl
            max_drawdown = max(max_drawdown, drawdown)
        
        result.max_drawdown_bp = max_drawdown
        
        return result


def quick_backtest(
    spread_series: pd.Series,
    pair_name: str = "TEST"
) -> Dict[str, Any]:
    """
    Быстрый бэктест
    
    Args:
        spread_series: История спредов
        pair_name: Название пары
        
    Returns:
        Словарь с результатами
    """
    backtester = Backtester()
    df = pd.DataFrame({"spread_bp": spread_series})
    result = backtester.run_backtest(
        df,
        spread_series,  # Заглушки YTM
        spread_series,
        pair_name
    )
    return result.to_dict()
