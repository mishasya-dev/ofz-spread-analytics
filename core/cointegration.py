"""
Анализ коинтеграции для пар облигаций

Включает:
- Engle-Granger тест на коинтеграцию (coint) — основной метод
- Augmented Dickey-Fuller (ADF) тест на стационарность
- KPSS тест (дополнительно)
- Расчёт half-life для mean reversion
- Синхронизация данных по датам

Важно: Коинтеграция проверяется только между нестационарными рядами!
Если YTM ряды стационарны — коинтеграция не применима.
"""
import pandas as pd
import numpy as np
from typing import Dict, Tuple, Optional
import logging

logger = logging.getLogger(__name__)

# Импорт statsmodels (опционально)
try:
    from statsmodels.tsa.stattools import coint, adfuller, kpss
    from statsmodels.regression.linear_model import OLS
    import statsmodels.api as sm
    STATSMODELS_AVAILABLE = True
except ImportError:
    STATSMODELS_AVAILABLE = False
    logger.warning("statsmodels not installed. Cointegration analysis unavailable.")


def synchronize_series(
    ytm1: pd.Series,
    ytm2: pd.Series,
    fill_method: str = 'drop'
) -> Tuple[pd.Series, pd.Series]:
    """
    Синхронизация двух временных рядов по датам.
    
    Args:
        ytm1: YTM первой облигации (index = dates)
        ytm2: YTM второй облигации (index = dates)
        fill_method: 'drop' — удалить пропуски, 'ffill' — заполнить предыдущим
        
    Returns:
        Tuple синхронизированных рядов
    """
    # Проверка на дубликаты в индексах
    if ytm1.index.duplicated().any():
        logger.warning(f"ytm1 содержит {ytm1.index.duplicated().sum()} дубликатов дат")
        ytm1 = ytm1[~ytm1.index.duplicated(keep='last')]
    
    if ytm2.index.duplicated().any():
        logger.warning(f"ytm2 содержит {ytm2.index.duplicated().sum()} дубликатов дат")
        ytm2 = ytm2[~ytm2.index.duplicated(keep='last')]
    
    combined = pd.DataFrame({'ytm1': ytm1, 'ytm2': ytm2})
    
    n_before = len(combined)
    
    if fill_method == 'ffill':
        combined = combined.ffill()
    
    combined = combined.dropna()
    
    n_after = len(combined)
    
    if n_before != n_after:
        logger.info(f"Синхронизация: {n_before} → {n_after} записей (потеряно {n_before - n_after})")
    
    return combined['ytm1'], combined['ytm2']


class CointegrationAnalyzer:
    """Анализатор коинтеграции для пар облигаций"""
    
    def __init__(self, significance_level: float = 0.05):
        self.significance_level = significance_level
    
    def adf_test(self, series: pd.Series, max_lags: int = None) -> Dict:
        """
        Augmented Dickey-Fuller тест на стационарность
        
        H0: ряд имеет unit root (нестационарен)
        H1: ряд стационарен
        """
        if not STATSMODELS_AVAILABLE:
            return {'error': 'statsmodels not installed'}
        
        series = series.dropna()
        
        if len(series) < 30:
            return {'error': 'Insufficient data (min 30 observations)'}
        
        # Проверка на константный ряд (или почти константный)
        if series.std() < 1e-10 or series.max() == series.min():
            return {
                'test': 'ADF',
                'error': 'Constant series',
                'is_stationary': True,
                'is_nonstationary': False,
                'interpretation': 'Ряд константный (стационарен)'
            }
        
        try:
            result = adfuller(series, maxlag=max_lags, autolag='AIC')
        except ValueError as e:
            return {
                'test': 'ADF',
                'error': str(e),
                'is_stationary': True,
                'is_nonstationary': False,
                'interpretation': f'Ошибка теста: {e}'
            }
        
        adf_statistic = result[0]
        pvalue = result[1]
        used_lag = result[2]
        n_obs = result[3]
        critical_values = result[4]
        
        is_stationary = pvalue < self.significance_level
        
        return {
            'test': 'ADF',
            'adf_statistic': adf_statistic,
            'pvalue': pvalue,
            'used_lag': used_lag,
            'n_observations': n_obs,
            'critical_values': critical_values,
            'is_stationary': is_stationary,
            'is_nonstationary': not is_stationary,
            'interpretation': self._interpret_adf(adf_statistic, pvalue, critical_values)
        }
    
    def kpss_test(self, series: pd.Series) -> Dict:
        """
        KPSS тест (дополнение к ADF)
        
        H0: ряд стационарен
        H1: ряд имеет unit root
        
        Примечание: гипотезы обратны ADF!
        """
        if not STATSMODELS_AVAILABLE:
            return {'error': 'statsmodels not installed'}
        
        series = series.dropna()
        
        if len(series) < 30:
            return {'error': 'Insufficient data'}
        
        # Проверка на константный ряд
        if series.std() < 1e-10 or series.max() == series.min():
            return {
                'test': 'KPSS',
                'error': 'Constant series',
                'is_stationary': True
            }
        
        try:
            result = kpss(series, regression='c', nlags='auto')
        except (ValueError, np.linalg.LinAlgError) as e:
            return {
                'test': 'KPSS',
                'error': str(e),
                'is_stationary': None
            }
        
        kpss_stat = result[0]
        pvalue = result[1]
        critical_values = result[3]
        
        # Для KPSS: p < 0.05 означает НЕстационарность
        is_stationary = pvalue > self.significance_level
        
        return {
            'test': 'KPSS',
            'kpss_statistic': kpss_stat,
            'pvalue': pvalue,
            'critical_values': critical_values,
            'is_stationary': is_stationary
        }
    
    def engle_granger_test(
        self,
        ytm1: pd.Series,
        ytm2: pd.Series,
        trend: str = 'c',
        bidirectional: bool = True
    ) -> Dict:
        """
        Engle-Granger тест на коинтеграцию.
        
        H0: ряды НЕ коинтегрированы
        H1: ряды коинтегрированы
        
        Важно: оба ряда должны быть нестационарны!
        
        Args:
            ytm1: YTM первой облигации
            ytm2: YTM второй облигации
            trend: тип тренда ('c' = константа)
            bidirectional: проверять оба направления и брать лучший результат
        """
        if not STATSMODELS_AVAILABLE:
            return {'error': 'statsmodels not installed'}
        
        # Синхронизация
        ytm1_sync, ytm2_sync = synchronize_series(ytm1, ytm2)
        
        if len(ytm1_sync) < 30:
            return {'error': 'Insufficient data after synchronization'}
        
        # Проверка стационарности исходных рядов
        adf1 = self.adf_test(ytm1_sync)
        adf2 = self.adf_test(ytm2_sync)
        
        both_nonstationary = (
            adf1.get('is_nonstationary', False) and 
            adf2.get('is_nonstationary', False)
        )
        
        # Engle-Granger тест
        try:
            # Направление 1: ytm1 ~ ytm2
            score1, pvalue1, crit1 = coint(ytm1_sync, ytm2_sync, trend=trend)
            
            if bidirectional:
                # Направление 2: ytm2 ~ ytm1
                score2, pvalue2, crit2 = coint(ytm2_sync, ytm1_sync, trend=trend)
                
                # Берём лучший результат (минимальный p-value)
                if pvalue2 < pvalue1:
                    score, pvalue, critical_values = score2, pvalue2, crit2
                    direction = 'ytm2_ytm1'
                else:
                    score, pvalue, critical_values = score1, pvalue1, crit1
                    direction = 'ytm1_ytm2'
            else:
                score, pvalue, critical_values = score1, pvalue1, crit1
                direction = 'ytm1_ytm2'
                
        except (ValueError, np.linalg.LinAlgError) as e:
            return {
                'test': 'Engle-Granger',
                'error': str(e),
                'is_cointegrated': False,
                'both_nonstationary': both_nonstationary,
                'n_observations': len(ytm1_sync),
                'interpretation': f'Ошибка теста: {e}'
            }
        
        is_cointegrated = pvalue < self.significance_level
        
        return {
            'test': 'Engle-Granger',
            'coint_statistic': score,
            'pvalue': pvalue,
            'critical_values': {
                '1%': critical_values[0],
                '5%': critical_values[1],
                '10%': critical_values[2]
            },
            'is_cointegrated': is_cointegrated,
            'ytm1_adf_pvalue': adf1.get('pvalue'),
            'ytm2_adf_pvalue': adf2.get('pvalue'),
            'ytm1_stationary': adf1.get('is_stationary'),
            'ytm2_stationary': adf2.get('is_stationary'),
            'both_nonstationary': both_nonstationary,
            'n_observations': len(ytm1_sync),
            'direction': direction,
            'interpretation': self._interpret_coint(pvalue, both_nonstationary)
        }
    
    def calculate_half_life(self, series: pd.Series) -> Optional[float]:
        """
        Расчёт half-life mean reversion.
        
        Half-life показывает, за сколько периодов спред
        вернётся на половину расстояния к среднему.
        """
        if not STATSMODELS_AVAILABLE:
            return None
        
        try:
            series = series.dropna()
            if len(series) < 30:
                return None
            
            spread_lag = series.shift(1)
            spread_diff = series - spread_lag
            
            valid_idx = ~spread_lag.isna() & ~spread_diff.isna()
            spread_lag = spread_lag[valid_idx]
            spread_diff = spread_diff[valid_idx]
            
            if len(spread_lag) < 20:
                return None
            
            spread_lag = sm.add_constant(spread_lag)
            model = OLS(spread_diff, spread_lag).fit()
            
            beta = model.params.iloc[1]
            
            if beta >= 0:
                return float('inf')
            
            return -np.log(2) / np.log(1 + beta)
        except (ValueError, IndexError, np.linalg.LinAlgError):
            return None
    
    def calculate_hedge_ratio(
        self,
        ytm1: pd.Series,
        ytm2: pd.Series
    ) -> Optional[float]:
        """Расчёт коэффициента хеджирования через OLS."""
        if not STATSMODELS_AVAILABLE:
            return None
        
        try:
            ytm1_sync, ytm2_sync = synchronize_series(ytm1, ytm2)
            
            if len(ytm1_sync) < 30:
                return None
            
            ytm2_sync = sm.add_constant(ytm2_sync)
            model = OLS(ytm1_sync, ytm2_sync).fit()
            
            return model.params.iloc[1]
        except (ValueError, IndexError, np.linalg.LinAlgError):
            return None
    
    def analyze_pair(
        self,
        ytm1: pd.Series,
        ytm2: pd.Series
    ) -> Dict:
        """
        Полный анализ пары облигаций.
        
        Workflow:
        1. Синхронизация по датам
        2. ADF на YTM₁ и YTM₂ → должны быть нестационарны
        3. Engle-Granger → коинтеграция?
        4. Half-life → скорость mean reversion
        """
        if not STATSMODELS_AVAILABLE:
            return {'error': 'statsmodels not installed'}
        
        # Синхронизация
        ytm1_sync, ytm2_sync = synchronize_series(ytm1, ytm2)
        
        if len(ytm1_sync) < 30:
            return {
                'error': 'Insufficient data',
                'n_observations': len(ytm1_sync),
                'min_required': 30
            }
        
        # Engle-Granger тест
        eg_result = self.engle_granger_test(ytm1_sync, ytm2_sync)
        
        # ADF тесты отдельно для отчёта
        adf1_result = self.adf_test(ytm1_sync)
        adf2_result = self.adf_test(ytm2_sync)
        
        # Спред
        spread = (ytm1_sync - ytm2_sync) * 100
        
        # ADF на спреде
        adf_spread_result = self.adf_test(spread)
        
        # KPSS на спреде
        kpss_result = self.kpss_test(spread)
        
        # Half-life
        half_life = self.calculate_half_life(spread)
        
        # Hedge ratio
        hedge_ratio = self.calculate_hedge_ratio(ytm1_sync, ytm2_sync)
        
        # Рекомендация
        is_cointegrated = eg_result.get('is_cointegrated', False)
        both_nonstationary = eg_result.get('both_nonstationary', False)
        
        recommendation = self._get_recommendation(
            is_cointegrated, both_nonstationary, half_life
        )
        
        return {
            'n_observations': len(ytm1_sync),
            'engle_granger': eg_result,
            'adf_ytm1': adf1_result,
            'adf_ytm2': adf2_result,
            'adf_spread': adf_spread_result,
            'kpss_spread': kpss_result,
            'half_life': half_life,
            'hedge_ratio': hedge_ratio,
            'is_cointegrated': is_cointegrated,
            'both_nonstationary': both_nonstationary,
            'recommendation': recommendation
        }
    
    def _interpret_adf(self, adf_stat: float, pvalue: float, critical_values: Dict) -> str:
        """Интерпретация ADF теста"""
        if adf_stat < critical_values['1%']:
            return f"Сильная стационарность (p={pvalue:.4f})"
        elif adf_stat < critical_values['5%']:
            return f"Ряд стационарен (p={pvalue:.4f})"
        elif adf_stat < critical_values['10%']:
            return f"Слабая стационарность (p={pvalue:.4f})"
        else:
            return f"Ряд нестационарен (p={pvalue:.4f})"
    
    def _interpret_coint(self, pvalue: float, both_nonstationary: bool) -> str:
        """Интерпретация Engle-Granger теста"""
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
    
    def _get_recommendation(
        self,
        is_cointegrated: bool,
        both_nonstationary: bool,
        half_life: Optional[float]
    ) -> Dict:
        """Рекомендация по торговой стратегии"""
        
        if not both_nonstationary:
            return {
                'strategy': 'Не применимо',
                'reason': 'Один или оба YTM ряда стационарны. Коинтеграция не работает.',
                'risk': 'high'
            }
        
        if not is_cointegrated:
            return {
                'strategy': 'Не рекомендуется',
                'reason': 'Пара не коинтегрирована. Mean reversion не работает.',
                'risk': 'high'
            }
        
        if half_life is None or half_life == float('inf'):
            return {
                'strategy': 'С осторожностью',
                'reason': 'Коинтеграция есть, но mean reversion очень медленная.',
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
            'reason': f'Коинтеграция подтверждена. Mean reversion {speed} (half-life: {half_life:.1f} дней)',
            'risk': risk,
            'half_life_days': half_life
        }


def format_cointegration_report(result: Dict, bond1_name: str = "BOND1", bond2_name: str = "BOND2") -> str:
    """Форматирование отчёта для Streamlit
    
    Args:
        result: Результат анализа от analyze_pair()
        bond1_name: Название первой облигации (например, "ОФЗ 26238")
        bond2_name: Название второй облигации (например, "ОФЗ 26243")
    """
    
    if 'error' in result:
        return f"❌ **Ошибка:** {result['error']}"
    
    lines = []
    lines.append("### 📊 Анализ коинтеграции\n")
    
    eg = result.get('engle_granger', {})
    is_cointegrated = result.get('is_cointegrated', False)
    
    if 'error' not in eg:
        # Проверка стационарности
        lines.append("**Проверка BOND (должны быть нестационарны):**")
        bond1_stat = "❌ стационарен" if eg.get('ytm1_stationary') else "✅ нестационарен"
        bond2_stat = "❌ стационарен" if eg.get('ytm2_stationary') else "✅ нестационарен"
        pval1 = eg.get('ytm1_adf_pvalue')
        pval2 = eg.get('ytm2_adf_pvalue')
        lines.append(f"- {bond1_name}: {bond1_stat}" + (f" (p={pval1:.4f})" if pval1 else ""))
        lines.append(f"- {bond2_name}: {bond2_stat}" + (f" (p={pval2:.4f})" if pval2 else ""))
        lines.append("")
        
        # Engle-Granger
        lines.append("**Engle-Granger тест:**")
        lines.append(f"- Statistic: `{eg['coint_statistic']:.3f}`")
        lines.append(f"- p-value: `{eg['pvalue']:.4f}`")
        lines.append(f"- **{eg['interpretation']}**")
        lines.append("")
    
    # Показываем Half-life и Hedge Ratio ТОЛЬКО если есть коинтеграция
    if is_cointegrated:
        # Half-life
        half_life = result.get('half_life')
        if half_life is not None and half_life != float('inf'):
            lines.append(f"**Half-life:** `{half_life:.1f}` дней")
            lines.append("")
        
        # Hedge ratio с текстовым объяснением
        hedge_ratio = result.get('hedge_ratio')
        if hedge_ratio is not None:
            lines.append(f"**Hedge Ratio:** `{hedge_ratio:.4f}`")
            lines.append(f"> На каждые **{abs(hedge_ratio):.2f} единицы {bond2_name}** нужно взять **1 единицу {bond1_name}**")
            lines.append("")
    
    # Рекомендация
    rec = result.get('recommendation', {})
    if rec:
        emoji = "✅" if rec.get('risk') == 'low' else "⚠️" if rec.get('risk') == 'medium' else "❌"
        lines.append(f"{emoji} **{rec.get('strategy', '')}**")
        lines.append(f"- {rec.get('reason', '')}")
    
    return "\n".join(lines)
