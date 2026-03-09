"""
Расчёт G-spread через модель Nelson-Siegel

G-spread = YTM_облигации - YTM_КБД(duration)

Модель Nelson-Siegel:
Y(t) = b0 + b1 * f1(t) + b2 * f2(t)

где:
- t = duration (срок до погашения)
- b0 = долгосрочный уровень ставки (base level)
- b1 = краткосрочный наклон (short-term slope)  
- b2 = кривизна (curvature)
- tau = масштаб времени
- f1(t) = (tau/t) * (1 - exp(-t/tau))
- f2(t) = f1(t) - exp(-t/tau)

Примечание по naming:
- MOEX использует: b1, b2, b3, t1 (где b1=b0, b2=b1, b3=b2, t1=tau)
- Мы используем оба варианта для совместимости
"""
import numpy as np
import pandas as pd
from datetime import date, datetime
from typing import Optional, Dict, Tuple
import logging

logger = logging.getLogger(__name__)


def nelson_siegel(
    t: float,
    b0: float,
    b1: float,
    b2: float,
    tau: float
) -> float:
    """
    Рассчитать YTM по КБД (Nelson-Siegel model)
    
    Y(t) = b0 + b1 * f1(t) + b2 * f2(t)
    
    Args:
        t: Срок до погашения (duration) - автоматически определяется:
           - если t > 30, считается в днях и конвертируется в годы
           - если t <= 30, считается в годах
        b0: Долгосрочный уровень ставки (в %)
        b1: Краткосрочный наклон (в %)
        b2: Кривизна (в %)
        tau: Масштаб времени
        
    Returns:
        YTM по КБД (в %)
        
    Examples:
        >>> nelson_siegel(5.0, 16.0, -2.0, 3.0, 2.0)
        15.12
        >>> # То же самое с duration в днях
        >>> nelson_siegel(1826.25, 16.0, -2.0, 3.0, 2.0)  # 5 лет * 365.25
        15.12
    """
    if t <= 0:
        # Для нулевой дюрации возвращаем b0 + b1 (краткосрочная ставка)
        return b0 + b1
    
    # Автоматическое определение единиц измерения duration
    # Если t > 30, считаем что это дни, иначе годы
    t_years = t / 365.0 if t > 30 else t
    
    if tau <= 0:
        tau = 1e-10
    
    # f1(t) = (tau/t) * (1 - exp(-t/tau))
    # Эквивалентно: (1 - exp(-t/tau)) / (t/tau)
    x = t_years / tau
    
    if x > 100:  # Защита от переполнения
        f1 = 1.0
        f2 = 1.0
    else:
        exp_x = np.exp(-x)
        f1 = (1 - exp_x) / x  # = (tau/t) * (1 - exp(-t/tau))
        f2 = f1 - exp_x
    
    ytm = b0 + b1 * f1 + b2 * f2
    
    return ytm


def nelson_siegel_vectorized(
    durations: np.ndarray,
    b0: float,
    b1: float,
    b2: float,
    tau: float
) -> np.ndarray:
    """
    Векторизованный расчёт YTM по КБД для массива дюраций
    
    Args:
        durations: Массив дюраций (автоматическое определение единиц)
        b0, b1, b2, tau: Параметры Nelson-Siegel
        
    Returns:
        Массив YTM по КБД
    """
    durations = np.asarray(durations, dtype=float)
    
    # Защита от деления на ноль
    durations = np.where(durations <= 0, 1e-10, durations)
    
    # Автоматическое определение единиц измерения
    # Если duration > 30, считаем что это дни
    t_years = np.where(durations > 30, durations / 365.0, durations)
    
    if tau <= 0:
        tau = 1e-10
    
    x = t_years / tau
    x = np.clip(x, 0, 100)  # Защита от переполнения
    
    exp_x = np.exp(-x)
    f1 = (1 - exp_x) / x
    f2 = f1 - exp_x
    
    ytm = b0 + b1 * f1 + b2 * f2
    
    return ytm


def calculate_g_spread(
    ytm_bond: float,
    duration_years: float,
    b1: float,
    b2: float,
    b3: float,
    tau: float
) -> Tuple[float, float]:
    """
    Рассчитать G-spread для одной точки
    
    G-spread = YTM_bond - YTM_KBD(duration)
    
    Args:
        ytm_bond: Реальный YTM облигации (в %)
        duration_years: Дюрация в годах
        b1, b2, b3, tau: Параметры Nelson-Siegel
        
    Returns:
        (ytm_kbd, g_spread_bp):
            ytm_kbd: YTM по КБД (в %)
            g_spread_bp: G-spread (в базисных пунктах)
    """
    ytm_kbd = nelson_siegel(duration_years, b1, b2, b3, tau)
    g_spread_bp = (ytm_bond - ytm_kbd) * 100  # в базисных пунктах
    
    return ytm_kbd, g_spread_bp


def calculate_g_spread_history(
    bond_ytm_df: pd.DataFrame,
    ns_params_df: pd.DataFrame
) -> pd.DataFrame:
    """
    Рассчитать историю G-spread для облигации
    
    Args:
        bond_ytm_df: DataFrame с колонками ['ytm', 'duration_days']
                     индекс = date
        ns_params_df: DataFrame с колонками ['b1', 'b2', 'b3', 't1']
                      индекс = date
                      ВАЖНО: b1, b2, b3 в базисных пунктах от MOEX!
                      
    Returns:
        DataFrame с колонками:
            - ytm_bond: YTM облигации (%)
            - duration_years: Дюрация (годы)
            - ytm_kbd: YTM по КБД (%)
            - g_spread_bp: G-spread (б.п.)
    """
    if bond_ytm_df.empty or ns_params_df.empty:
        return pd.DataFrame()
    
    # Объединяем по дате
    merged = bond_ytm_df.join(ns_params_df, how='inner')
    
    if merged.empty:
        logger.warning("Нет пересекающихся дат между YTM и параметрами NS")
        return pd.DataFrame()
    
    # Проверяем наличие нужных колонок
    required_cols = ['ytm', 'duration_days', 'b1', 'b2', 'b3', 't1']
    missing = [c for c in required_cols if c not in merged.columns]
    if missing:
        logger.error(f"Отсутствуют колонки: {missing}")
        return pd.DataFrame()
    
    # Удаляем строки с None/NaN
    merged = merged.dropna(subset=required_cols)
    
    if merged.empty:
        logger.warning("Все строки содержат None значения")
        return pd.DataFrame()
    
    # Рассчитываем duration в годах
    merged['duration_years'] = merged['duration_days'] / 365.25
    
    # Конвертируем параметры NS из базисных пунктов в проценты
    # MOEX возвращает b1, b2, b3 в базисных пунктах
    b1_pct = merged['b1'] / 100.0
    b2_pct = merged['b2'] / 100.0
    b3_pct = merged['b3'] / 100.0
    
    # Рассчитываем YTM по КБД
    merged['ytm_kbd'] = nelson_siegel_vectorized(
        merged['duration_years'].values,
        b1_pct.values,
        b2_pct.values,
        b3_pct.values,
        merged['t1'].values
    )
    
    # Рассчитываем G-spread
    merged['ytm_bond'] = merged['ytm']
    merged['g_spread_bp'] = (merged['ytm_bond'] - merged['ytm_kbd']) * 100
    
    # Возвращаем только нужные колонки
    result = merged[['ytm_bond', 'duration_years', 'ytm_kbd', 'g_spread_bp']].copy()
    
    logger.info(f"Рассчитано {len(result)} значений G-sread")
    
    return result


def calculate_g_spread_stats(g_spread_series: pd.Series) -> Dict:
    """
    Рассчитать статистику G-spread
    
    Args:
        g_spread_series: Series со значениями G-spread (б.п.)
        
    Returns:
        Словарь со статистикой
    """
    if g_spread_series.empty:
        return {}
    
    clean = g_spread_series.dropna()
    
    if clean.empty:
        return {}
    
    # Используем .item() для гарантии возврата скаляров
    return {
        'mean': float(clean.mean()),
        'median': float(clean.median()),
        'std': float(clean.std()),
        'min': float(clean.min()),
        'max': float(clean.max()),
        'p10': float(clean.quantile(0.10)),
        'p25': float(clean.quantile(0.25)),
        'p75': float(clean.quantile(0.75)),
        'p90': float(clean.quantile(0.90)),
        'current': float(clean.iloc[-1]) if len(clean) > 0 else 0.0,
        'count': int(len(clean))
    }


def generate_g_spread_signal(
    current_spread: float,
    p10: float,
    p25: float,
    p75: float,
    p90: float
) -> Dict:
    """
    Генерировать торговый сигнал на основе G-spread
    
    Интерпретация G-spread:
    - G-spread < 0: Облигация дешевле КБД (покупка)
    - G-spread > 0: Облигация дороже КБД (продажа)
    
    Mean-Reversion стратегия:
    - G-spread < P25: Облигация недооценена → ПОКУПКА
    - G-spread > P75: Облигация переоценена → ПРОДАЖА
    
    Args:
        current_spread: Текущий G-spread (б.п.)
        p10, p25, p75, p90: Перцентили
        
    Returns:
        Словарь с сигналом
    """
    if current_spread < p25:
        # Облигация недооценена относительно КБД
        return {
            'signal': 'BUY',
            'action': 'ПОКУПКА — облигация недооценена относительно КБД',
            'reason': f'G-spread {current_spread:.1f} б.п. ниже P25 ({p25:.1f} б.п.)',
            'color': '#28a745',  # зелёный
            'strength': 'Сильный' if current_spread < p10 else 'Средний'
        }
    elif current_spread > p75:
        # Облигация переоценена относительно КБД
        return {
            'signal': 'SELL',
            'action': 'ПРОДАЖА — облигация переоценена относительно КБД',
            'reason': f'G-spread {current_spread:.1f} б.п. выше P75 ({p75:.1f} б.п.)',
            'color': '#dc3545',  # красный
            'strength': 'Сильный' if current_spread > p90 else 'Средний'
        }
    else:
        return {
            'signal': 'HOLD',
            'action': 'УДЕРЖИВАТЬ — справедливая оценка',
            'reason': f'G-spread {current_spread:.1f} б.п. в нормальном диапазоне [{p25:.1f}, {p75:.1f}]',
            'color': '#ffc107',  # жёлтый
            'strength': 'Нет сигнала'
        }


def enrich_bond_data(
    df_bond: pd.DataFrame,
    df_kbd_params: pd.DataFrame,
    window: int = 30
) -> Tuple[pd.DataFrame, float]:
    """
    Полный расчёт G-spread с Z-Score и проверкой стационарности
    
    Args:
        df_bond: DataFrame с колонками ['date', 'ytm', 'duration']
                 date - datetime или строка YYYY-MM-DD
                 ytm - доходность к погашению (%)
                 duration - дюрация (дни или годы, определяется автоматически)
        df_kbd_params: DataFrame с колонками ['date', 'b0', 'b1', 'b2', 'tau']
                       или MOEX формат ['date', 'b1', 'b2', 'b3', 't1']
        window: Окно для rolling Z-Score (дней)
        
    Returns:
        (df_result, p_value):
            df_result: DataFrame с колонками:
                - date, ytm, duration
                - ytm_theoretical: YTM по КБД (%)
                - g_spread: G-spread (б.п.)
                - z_score: Rolling Z-Score
            p_value: P-value ADF теста на стационарность
                     p < 0.05 означает стационарность (коинтеграция)
    """
    try:
        from statsmodels.tsa.stattools import adfuller
        has_adfuller = True
    except ImportError:
        logger.warning("statsmodels не установлен, ADF тест пропущен")
        has_adfuller = False
    
    # 1. Подготовка данных
    df_bond = df_bond.copy()
    df_kbd_params = df_kbd_params.copy()
    
    # Убеждаемся что date - колонка или индекс
    if 'date' not in df_bond.columns:
        if df_bond.index.name == 'date' or df_bond.index.name is None:
            df_bond = df_bond.reset_index()
            df_bond = df_bond.rename(columns={'index': 'date'})
    
    if 'date' not in df_kbd_params.columns:
        if df_kbd_params.index.name == 'date' or df_kbd_params.index.name is None:
            df_kbd_params = df_kbd_params.reset_index()
            df_kbd_params = df_kbd_params.rename(columns={'index': 'date'})
    
    # Конвертируем date в datetime
    df_bond['date'] = pd.to_datetime(df_bond['date'])
    df_kbd_params['date'] = pd.to_datetime(df_kbd_params['date'])
    
    # 2. Определяем формат колонок KBD (MOEX vs стандартный)
    # MOEX использует: b1, b2, b3, t1
    # Стандартный: b0, b1, b2, tau
    if 'b1' in df_kbd_params.columns and 'b2' in df_kbd_params.columns:
        if 'b3' in df_kbd_params.columns and 't1' in df_kbd_params.columns:
            # MOEX format: b1=b0, b2=b1, b3=b2, t1=tau
            # ВАЖНО: MOEX возвращает параметры в базисных пунктах!
            # Нужно конвертировать в проценты (делим на 100)
            df_kbd_params = df_kbd_params.rename(columns={
                'b1': 'b0',
                'b2': 'b1', 
                'b3': 'b2',
                't1': 'tau'
            })
            # Конвертируем из базисных пунктов в проценты
            for col in ['b0', 'b1', 'b2']:
                if col in df_kbd_params.columns:
                    df_kbd_params[col] = df_kbd_params[col] / 100.0
    
    # 3. Синхронизируем данные по дате
    df = pd.merge(df_bond, df_kbd_params, on='date', how='inner').sort_values('date')
    
    if df.empty:
        logger.warning("Нет пересекающихся дат между облигацией и КБД")
        return pd.DataFrame(), 1.0
    
    # 4. Вычисляем историческую теоретическую доходность (КБД)
    df['ytm_theoretical'] = df.apply(
        lambda r: nelson_siegel(
            r['duration'], 
            r['b0'], 
            r['b1'], 
            r['b2'], 
            r['tau']
        ), 
        axis=1
    )
    
    # 5. Вычисляем G-спред в базисных пунктах (1% = 100 б.п.)
    df['g_spread'] = (df['ytm'] - df['ytm_theoretical']) * 100
    df['g_spread_bp'] = df['g_spread']  # Дублируем для совместимости
    
    # 5.1 Добавляем duration_years для сохранения в БД
    df['duration_years'] = df['duration'] / 365.25
    
    # 6. Считаем скользящий Z-Score для торговых сигналов
    roll = df['g_spread'].rolling(window=window)
    df['z_score'] = (df['g_spread'] - roll.mean()) / roll.std()
    
    # 7. Проверка на стационарность (ADF тест)
    p_value = 1.0
    if has_adfuller:
        try:
            g_spread_clean = df['g_spread'].dropna()
            if len(g_spread_clean) >= 20:  # Минимум данных для ADF
                adf_result = adfuller(g_spread_clean)
                p_value = adf_result[1]
                
                if p_value < 0.05:
                    logger.info(f"G-spread стационарен (p={p_value:.4f} < 0.05) - коинтеграция подтверждена")
                else:
                    logger.warning(f"G-spread НЕ стационарен (p={p_value:.4f} >= 0.05) - коинтеграция не подтверждена")
        except Exception as e:
            logger.warning(f"ADF тест не удался: {e}")
    
    # Возвращаем только нужные колонки
    result_cols = ['date', 'ytm', 'duration', 'ytm_theoretical', 'g_spread', 'g_spread_bp', 'z_score', 'duration_years']
    result = df[[c for c in result_cols if c in df.columns]].copy()
    
    logger.info(f"Рассчитано {len(result)} значений G-spread, p-value ADF: {p_value:.4f}")
    
    return result, p_value


class GSpreadCalculator:
    """
    Калькулятор G-spread для облигаций
    
    Использование:
        calculator = GSpreadCalculator()
        
        # Загрузить данные
        calculator.load_ns_params(ns_df)
        
        # Рассчитать G-spread для облигации
        g_spread_df = calculator.calculate(isin, ytm_df)
    """
    
    def __init__(self):
        self._ns_params: Optional[pd.DataFrame] = None
    
    def load_ns_params(self, ns_params_df: pd.DataFrame):
        """Загрузить параметры Nelson-Siegel"""
        self._ns_params = ns_params_df.copy()
        logger.info(f"Загружено {len(self._ns_params)} параметров NS")
    
    def calculate(
        self,
        bond_ytm_df: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Рассчитать G-spread для облигации
        
        Args:
            bond_ytm_df: DataFrame с YTM и duration облигации
            
        Returns:
            DataFrame с G-spread
        """
        if self._ns_params is None:
            logger.error("Параметры NS не загружены")
            return pd.DataFrame()
        
        return calculate_g_spread_history(bond_ytm_df, self._ns_params)
    
    def calculate_current(
        self,
        ytm: float,
        duration_years: float,
        ns_params: Dict
    ) -> Tuple[float, float]:
        """
        Рассчитать текущий G-spread
        
        Args:
            ytm: Текущий YTM облигации
            duration_years: Дюрация в годах
            ns_params: Параметры NS {'b1', 'b2', 'b3', 't1'}
            
        Returns:
            (ytm_kbd, g_spread_bp)
        """
        return calculate_g_spread(
            ytm,
            duration_years,
            ns_params['b1'],
            ns_params['b2'],
            ns_params['b3'],
            ns_params['t1']
        )
