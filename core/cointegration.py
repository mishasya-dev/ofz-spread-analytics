"""
Анализ коинтеграции для пар облигаций ОФЗ.

Включает:
- Engle-Granger тест на коинтеграцию (bidirectional)
- ADF тест на стационарность
- Расчёт half-life для mean reversion
- Расчёт hedge ratio для pair trading

Важно: Коинтеграция проверяется только между нестационарными рядами!
"""
import logging
from typing import Dict, Optional, Tuple
from dataclasses import dataclass, field
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

# Проверка доступности statsmodels
try:
    from statsmodels.tsa.stattools import coint, adfuller
    from statsmodels.regression.linear_model import OLS
    import statsmodels.api as sm
    STATSMODELS_AVAILABLE = True
except ImportError:
    STATSMODELS_AVAILABLE = False
    logger.warning("statsmodels not installed. Cointegration analysis unavailable.")


# Минимум наблюдений для надёжного анализа
MIN_OBSERVATIONS = 30


@dataclass
class CointegrationResult:
    """Результат анализа коинтеграции пары."""
    
    # Основные результаты
    is_cointegrated: bool
    pvalue: float
    coint_statistic: float
    critical_values: Dict[str, float] = field(default_factory=dict)
    n_observations: int = 0
    
    # Стационарность исходных рядов
    ytm1_adf_pvalue: Optional[float] = None
    ytm2_adf_pvalue: Optional[float] = None
    both_nonstationary: bool = False
    
    # Метрики mean reversion
    half_life: Optional[float] = None
    hedge_ratio: Optional[float] = None
    
    # Дополнительная информация
    direction: str = "ytm1_ytm2"
    error: Optional[str] = None
    
    def to_dict(self) -> Dict:
        """Сериализация в словарь для БД."""
        return {
            'is_cointegrated': self.is_cointegrated,
            'pvalue': self.pvalue,
            'coint_statistic': self.coint_statistic,
            'critical_values': self.critical_values,
            'n_observations': self.n_observations,
            'ytm1_adf_pvalue': self.ytm1_adf_pvalue,
            'ytm2_adf_pvalue': self.ytm2_adf_pvalue,
            'both_nonstationary': self.both_nonstationary,
            'half_life': self.half_life,
            'hedge_ratio': self.hedge_ratio,
            'direction': self.direction,
            'error': self.error
        }


def clean_series(series: pd.Series, name: str = "series") -> pd.Series:
    """
    Очистка ряда: сортировка по дате, удаление дублей.
    
    Args:
        series: Временной ряд с DatetimeIndex
        name: Имя для логирования
        
    Returns:
        Очищенный ряд
    """
    s = series.copy()
    s.index = pd.to_datetime(s.index)
    s = s.sort_index()
    
    if s.index.duplicated().any():
        count = s.index.duplicated().sum()
        logger.warning(f"[{name}] Удалено {count} дубликатов дат")
        s = s[~s.index.duplicated(keep='last')]
    
    return s


def synchronize_series(
    ytm1: pd.Series,
    ytm2: pd.Series
) -> Tuple[pd.Series, pd.Series]:
    """
    Синхронизация двух рядов по общим датам (inner join).
    
    Для стат. тестов используем только dropna - 
    заполнение пропусков исказит результаты.
    
    Args:
        ytm1: YTM первой облигации
        ytm2: YTM второй облигации
        
    Returns:
        Кортеж синхронизированных рядов
    """
    s1 = clean_series(ytm1, "YTM_1")
    s2 = clean_series(ytm2, "YTM_2")
    
    # Inner join по датам
    combined = pd.concat([s1.rename('y'), s2.rename('x')], axis=1).dropna()
    
    n_before = max(len(s1), len(s2))
    n_after = len(combined)
    
    if n_after < n_before:
        logger.info(f"Синхронизация: {n_before} → {n_after} общих дат")
    
    return combined['y'], combined['x']


def adf_test(series: pd.Series) -> Dict:
    """
    Augmented Dickey-Fuller тест на стационарность.
    
    H0: ряд имеет unit root (нестационарен)
    H1: ряд стационарен
    
    Args:
        series: Временной ряд
        
    Returns:
        Dict с pvalue и is_stationary
    """
    if not STATSMODELS_AVAILABLE:
        return {'error': 'statsmodels not installed'}
    
    series = series.dropna()
    
    if len(series) < MIN_OBSERVATIONS:
        return {'error': f'Недостаточно данных (минимум {MIN_OBSERVATIONS})'}
    
    # Константный ряд
    if series.std() < 1e-10:
        return {'pvalue': 0.0, 'is_stationary': True}
    
    try:
        result = adfuller(series, autolag='AIC')
        pvalue = result[1]
        
        return {
            'pvalue': pvalue,
            'is_stationary': pvalue < 0.05,
            'is_nonstationary': pvalue >= 0.05
        }
    except Exception as e:
        return {'error': str(e)}


def calculate_half_life(spread: pd.Series) -> Optional[float]:
    """
    Расчёт half-life mean reversion.
    
    Показывает, за сколько периодов спред
    вернётся на половину расстояния к среднему.
    
    Args:
        spread: Спред (стационарный)
        
    Returns:
        Half-life в днях или None
    """
    if not STATSMODELS_AVAILABLE:
        return None
    
    try:
        spread = spread.dropna()
        if len(spread) < MIN_OBSERVATIONS:
            return None
        
        # Lagged spread
        spread_lag = spread.shift(1)
        spread_diff = spread - spread_lag
        
        # Убираем NaN
        valid = ~(spread_lag.isna() | spread_diff.isna())
        spread_lag = spread_lag[valid]
        spread_diff = spread_diff[valid]
        
        if len(spread_lag) < 20:
            return None
        
        # OLS: Δspread = α + β * spread_lag + ε
        X = sm.add_constant(spread_lag)
        model = OLS(spread_diff, X).fit()
        
        beta = model.params.iloc[1]
        
        # Если beta >= 0, mean reversion нет
        if beta >= 0:
            return float('inf')
        
        # Half-life = -ln(2) / ln(1 + beta)
        return -np.log(2) / np.log(1 + beta)
        
    except Exception:
        return None


def calculate_hedge_ratio(ytm1: pd.Series, ytm2: pd.Series) -> Optional[float]:
    """
    Расчёт коэффициента хеджирования через OLS.
    
    Hedge ratio показывает пропорцию позиций в pair trading.
    
    Args:
        ytm1: YTM первой облигации
        ytm2: YTM второй облигации
        
    Returns:
        Hedge ratio или None
    """
    if not STATSMODELS_AVAILABLE:
        return None
    
    try:
        ytm1_sync, ytm2_sync = synchronize_series(ytm1, ytm2)
        
        if len(ytm1_sync) < MIN_OBSERVATIONS:
            return None
        
        # OLS: ytm1 = α + β * ytm2 + ε
        X = sm.add_constant(ytm2_sync)
        model = OLS(ytm1_sync, X).fit()
        
        return model.params.iloc[1]
        
    except Exception:
        return None


def calculate_z_score(spread: pd.Series, window: int = 20) -> pd.Series:
    """
    Расчёт Z-score для поиска точек входа.
    
    Z-score показывает, на сколько стандартных
    отклонений спред отклонился от скользящего среднего.
    
    Args:
        spread: Спред
        window: Окно для расчёта (по умолчанию 20 дней)
        
    Returns:
        Series с Z-score
    """
    mean = spread.rolling(window=window).mean()
    std = spread.rolling(window=window).std()
    return (spread - mean) / std


def get_recommendation(
    is_cointegrated: bool,
    both_nonstationary: bool,
    half_life: Optional[float]
) -> Dict:
    """
    Рекомендация по торговой стратегии.
    
    Args:
        is_cointegrated: Коинтегрирована ли пара
        both_nonstationary: Оба ряда нестационарны
        half_life: Half-life спреда
        
    Returns:
        Dict с recommendation
    """
    if not both_nonstationary:
        return {
            'strategy': 'Не применимо',
            'reason': 'Один или оба YTM ряда стационарны',
            'risk': 'high'
        }
    
    if not is_cointegrated:
        return {
            'strategy': 'Не рекомендуется',
            'reason': 'Пара не коинтегрирована',
            'risk': 'high'
        }
    
    if half_life is None or half_life == float('inf'):
        return {
            'strategy': 'С осторожностью',
            'reason': 'Mean reversion очень медленная',
            'risk': 'medium'
        }
    
    if half_life < 5:
        speed, risk = 'очень быстрая', 'low'
    elif half_life < 15:
        speed, risk = 'быстрая', 'low'
    elif half_life < 30:
        speed, risk = 'умеренная', 'medium'
    else:
        speed, risk = 'медленная', 'high'
    
    return {
        'strategy': 'Pair Trading (Mean Reversion)',
        'reason': f'Mean reversion {speed} (half-life: {half_life:.1f} дней)',
        'risk': risk,
        'half_life_days': half_life
    }


def run_cointegration_analysis(
    ytm1: pd.Series,
    ytm2: pd.Series,
    significance_level: float = 0.05,
    bidirectional: bool = True
) -> CointegrationResult:
    """
    Полный анализ коинтеграции для пары ОФЗ.
    
    Workflow:
    1. Синхронизация по датам
    2. ADF тест на стационарность (ряды должны быть нестационарны)
    3. Engle-Granger тест (bidirectional опционально)
    4. Расчёт half-life и hedge ratio
    
    Args:
        ytm1: YTM первой облигации (Series с DatetimeIndex)
        ytm2: YTM второй облигации
        significance_level: Уровень значимости (по умолчанию 0.05)
        bidirectional: Проверять оба направления и брать лучший результат
        
    Returns:
        CointegrationResult с результатами анализа
    """
    if not STATSMODELS_AVAILABLE:
        return CointegrationResult(
            is_cointegrated=False,
            pvalue=1.0,
            coint_statistic=0.0,
            error='statsmodels not installed'
        )
    
    # 1. Синхронизация
    ytm1_sync, ytm2_sync = synchronize_series(ytm1, ytm2)
    
    if len(ytm1_sync) < MIN_OBSERVATIONS:
        return CointegrationResult(
            is_cointegrated=False,
            pvalue=1.0,
            coint_statistic=0.0,
            n_observations=len(ytm1_sync),
            error=f'Недостаточно данных ({len(ytm1_sync)} < {MIN_OBSERVATIONS})'
        )
    
    # 2. ADF тесты на стационарность
    adf1 = adf_test(ytm1_sync)
    adf2 = adf_test(ytm2_sync)
    
    both_nonstationary = (
        adf1.get('is_nonstationary', False) and 
        adf2.get('is_nonstationary', False)
    )
    
    # 3. Engle-Granger тест
    try:
        # Направление 1: ytm1 ~ ytm2
        t_stat1, pval1, crit1 = coint(ytm1_sync, ytm2_sync, trend='c')
        
        if bidirectional:
            # Направление 2: ytm2 ~ ytm1
            t_stat2, pval2, crit2 = coint(ytm2_sync, ytm1_sync, trend='c')
            
            # Берём лучший результат (минимальный p-value)
            if pval2 < pval1:
                t_stat, pval, crit = t_stat2, pval2, crit2
                direction = 'ytm2_ytm1'
            else:
                t_stat, pval, crit = t_stat1, pval1, crit1
                direction = 'ytm1_ytm2'
        else:
            t_stat, pval, crit, direction = t_stat1, pval1, crit1, 'ytm1_ytm2'
            
    except Exception as e:
        return CointegrationResult(
            is_cointegrated=False,
            pvalue=1.0,
            coint_statistic=0.0,
            n_observations=len(ytm1_sync),
            both_nonstationary=both_nonstationary,
            error=str(e)
        )
    
    is_cointegrated = pval < significance_level
    
    # 4. Спред и метрики
    spread = (ytm1_sync - ytm2_sync) * 100  # в базисных пунктах
    half_life = calculate_half_life(spread) if is_cointegrated else None
    hedge_ratio = calculate_hedge_ratio(ytm1_sync, ytm2_sync) if is_cointegrated else None
    
    return CointegrationResult(
        is_cointegrated=is_cointegrated,
        pvalue=pval,
        coint_statistic=t_stat,
        critical_values={
            '1%': crit[0],
            '5%': crit[1],
            '10%': crit[2]
        },
        n_observations=len(ytm1_sync),
        ytm1_adf_pvalue=adf1.get('pvalue'),
        ytm2_adf_pvalue=adf2.get('pvalue'),
        both_nonstationary=both_nonstationary,
        half_life=half_life,
        hedge_ratio=hedge_ratio,
        direction=direction
    )


# =============================================================================
# LEGACY: Класс-обёртка для обратной совместимости
# =============================================================================

class CointegrationAnalyzer:
    """
    Класс-обёртка для обратной совместимости.
    
    Deprecated: Используйте функции run_cointegration_analysis() напрямую.
    """
    
    def __init__(self, significance_level: float = 0.05):
        self.significance_level = significance_level
    
    def adf_test(self, series: pd.Series) -> Dict:
        """ADF тест (legacy interface)."""
        result = adf_test(series)
        if 'error' in result:
            return result
        return {
            'test': 'ADF',
            'pvalue': result['pvalue'],
            'is_stationary': result.get('is_stationary', False),
            'is_nonstationary': result.get('is_nonstationary', False),
            'interpretation': self._interpret_adf(result['pvalue'])
        }
    
    def _interpret_adf(self, pvalue: float) -> str:
        """Интерпретация ADF теста."""
        if pvalue < 0.01:
            return f"Сильная стационарность (p={pvalue:.4f})"
        elif pvalue < 0.05:
            return f"Ряд стационарен (p={pvalue:.4f})"
        elif pvalue < 0.10:
            return f"Слабая стационарность (p={pvalue:.4f})"
        else:
            return f"Ряд нестационарен (p={pvalue:.4f})"
    
    def engle_granger_test(
        self,
        ytm1: pd.Series,
        ytm2: pd.Series,
        trend: str = 'c',
        bidirectional: bool = True
    ) -> Dict:
        """Engle-Granger тест (legacy interface)."""
        result = run_cointegration_analysis(
            ytm1, ytm2, 
            self.significance_level, 
            bidirectional
        )
        
        interp = self._interpret_coint(result.pvalue, result.both_nonstationary)
        
        return {
            'test': 'Engle-Granger',
            'coint_statistic': result.coint_statistic,
            'pvalue': result.pvalue,
            'critical_values': result.critical_values,
            'is_cointegrated': result.is_cointegrated,
            'ytm1_adf_pvalue': result.ytm1_adf_pvalue,
            'ytm2_adf_pvalue': result.ytm2_adf_pvalue,
            'ytm1_stationary': result.ytm1_adf_pvalue and result.ytm1_adf_pvalue < 0.05,
            'ytm2_stationary': result.ytm2_adf_pvalue and result.ytm2_adf_pvalue < 0.05,
            'both_nonstationary': result.both_nonstationary,
            'n_observations': result.n_observations,
            'direction': result.direction,
            'interpretation': interp
        }
    
    def _interpret_coint(self, pvalue: float, both_nonstationary: bool) -> str:
        """Интерпретация Engle-Granger теста."""
        if not both_nonstationary:
            return "⚠️ Один или оба ряда стационарны. Коинтеграция не применима."
        
        if pvalue < 0.01:
            return f"✅ Сильная коинтеграция (p={pvalue:.4f})"
        elif pvalue < 0.05:
            return f"✅ Коинтеграция есть (p={pvalue:.4f})"
        elif pvalue < 0.10:
            return f"⚠️ Слабая коинтеграция (p={pvalue:.4f})"
        else:
            return f"❌ Коинтеграции нет (p={pvalue:.4f})"
    
    def calculate_half_life(self, spread: pd.Series) -> Optional[float]:
        """Расчёт half-life."""
        return calculate_half_life(spread)
    
    def calculate_hedge_ratio(self, ytm1: pd.Series, ytm2: pd.Series) -> Optional[float]:
        """Расчёт hedge ratio."""
        return calculate_hedge_ratio(ytm1, ytm2)
    
    def analyze_pair(self, ytm1: pd.Series, ytm2: pd.Series) -> Dict:
        """Полный анализ пары (legacy interface)."""
        result = run_cointegration_analysis(
            ytm1, ytm2, 
            self.significance_level,
            bidirectional=True
        )
        
        if result.error:
            return {
                'error': result.error,
                'n_observations': result.n_observations
            }
        
        recommendation = get_recommendation(
            result.is_cointegrated,
            result.both_nonstationary,
            result.half_life
        )
        
        # Синхронизируем для дополнительных расчётов
        ytm1_sync, ytm2_sync = synchronize_series(ytm1, ytm2)
        spread = (ytm1_sync - ytm2_sync) * 100
        
        return {
            'n_observations': result.n_observations,
            'engle_granger': self.engle_granger_test(ytm1, ytm2),
            'adf_ytm1': self.adf_test(ytm1_sync),
            'adf_ytm2': self.adf_test(ytm2_sync),
            'adf_spread': self.adf_test(spread),
            'kpss_spread': {},  # Удалено, оставлено для совместимости
            'half_life': result.half_life,
            'hedge_ratio': result.hedge_ratio,
            'is_cointegrated': result.is_cointegrated,
            'both_nonstationary': result.both_nonstationary,
            'recommendation': recommendation
        }


# =============================================================================
# LEGACY: Функция форматирования (deprecated)
# =============================================================================

def format_cointegration_report(result: Dict, bond1_name: str = "BOND1", bond2_name: str = "BOND2") -> str:
    """
    Форматирование отчёта для Streamlit (DEPRECATED).
    
    Deprecated: Используйте app.py:format_cointegration_details() вместо.
    Эта функция оставлена для обратной совместимости.
    
    Args:
        result: Результат анализа от analyze_pair()
        bond1_name: Название первой облигации
        bond2_name: Название второй облигации
    """
    if 'error' in result:
        return f"❌ **Ошибка:** {result['error']}"
    
    lines = []
    lines.append("### 📊 Анализ коинтеграции\n")
    
    eg = result.get('engle_granger', {})
    is_cointegrated = result.get('is_cointegrated', False)
    
    if 'error' not in eg:
        lines.append("**Проверка BOND (должны быть нестационарны):**")
        bond1_stat = "❌ стационарен" if eg.get('ytm1_stationary') else "✅ нестационарен"
        bond2_stat = "❌ стационарен" if eg.get('ytm2_stationary') else "✅ нестационарен"
        pval1 = eg.get('ytm1_adf_pvalue')
        pval2 = eg.get('ytm2_adf_pvalue')
        lines.append(f"- {bond1_name}: {bond1_stat}" + (f" (p={pval1:.4f})" if pval1 else ""))
        lines.append(f"- {bond2_name}: {bond2_stat}" + (f" (p={pval2:.4f})" if pval2 else ""))
        lines.append("")
        
        lines.append("**Engle-Granger тест:**")
        lines.append(f"- Statistic: `{eg['coint_statistic']:.3f}`")
        lines.append(f"- p-value: `{eg['pvalue']:.4f}`")
        lines.append(f"- **{eg['interpretation']}**")
        lines.append("")
    
    if is_cointegrated:
        half_life = result.get('half_life')
        if half_life is not None and half_life != float('inf'):
            lines.append(f"**Half-life:** `{half_life:.1f}` дней")
            lines.append("")
        
        hedge_ratio = result.get('hedge_ratio')
        if hedge_ratio is not None:
            lines.append(f"**Hedge Ratio:** `{hedge_ratio:.4f}`")
            lines.append(f"> На каждые **{abs(hedge_ratio):.2f} единицы {bond2_name}** нужно взять **1 единицу {bond1_name}**")
            lines.append("")
    
    rec = result.get('recommendation', {})
    if rec:
        emoji = "✅" if rec.get('risk') == 'low' else "⚠️" if rec.get('risk') == 'medium' else "❌"
        lines.append(f"{emoji} **{rec.get('strategy', '')}**")
        lines.append(f"- {rec.get('reason', '')}")
    
    return "\n".join(lines)
