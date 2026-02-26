"""
Сохранение и загрузка данных intraday режима
"""
import os
import json
import pandas as pd
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)

# Директория для сохранения данных
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "intraday")


def ensure_data_dir():
    """Создать директорию для данных если не существует"""
    os.makedirs(DATA_DIR, exist_ok=True)


def save_intraday_snapshot(
    bond1_data: Dict[str, Any],
    bond2_data: Dict[str, Any],
    spread_data: Dict[str, Any],
    interval: str
) -> str:
    """
    Сохранить снимок intraday данных
    
    Args:
        bond1_data: Данные облигации 1 {ytm, price, datetime}
        bond2_data: Данные облигации 2
        spread_data: Данные спреда {spread_bp, signal}
        interval: Интервал свечей
        
    Returns:
        Путь к сохранённому файлу
    """
    ensure_data_dir()
    
    timestamp = datetime.now()
    filename = f"snapshot_{timestamp.strftime('%Y%m%d')}.json"
    filepath = os.path.join(DATA_DIR, filename)
    
    # Загружаем существующие данные или создаём новые
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
    else:
        data = {
            "date": timestamp.strftime('%Y-%m-%d'),
            "interval": interval,
            "snapshots": []
        }
    
    # Добавляем новый снимок
    snapshot = {
        "timestamp": timestamp.isoformat(),
        "bond1": {
            "isin": bond1_data.get("isin"),
            "ytm": bond1_data.get("ytm"),
            "price": bond1_data.get("price"),
            "name": bond1_data.get("name")
        },
        "bond2": {
            "isin": bond2_data.get("isin"),
            "ytm": bond2_data.get("ytm"),
            "price": bond2_data.get("price"),
            "name": bond2_data.get("name")
        },
        "spread_bp": spread_data.get("spread_bp"),
        "signal": spread_data.get("signal"),
        "p25": spread_data.get("p25"),
        "p75": spread_data.get("p75")
    }
    
    data["snapshots"].append(snapshot)
    
    # Сохраняем
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    logger.info(f"Сохранён снимок: {filepath}")
    return filepath


def load_intraday_history(
    target_date: Optional[date] = None,
    days: int = 7
) -> pd.DataFrame:
    """
    Загрузить историю intraday данных
    
    Args:
        target_date: Целевая дата (по умолчанию сегодня)
        days: Количество дней для загрузки
        
    Returns:
        DataFrame с историей
    """
    ensure_data_dir()
    
    if target_date is None:
        target_date = date.today()
    
    all_snapshots = []
    
    for i in range(days):
        check_date = target_date - timedelta(days=i)
        filename = f"snapshot_{check_date.strftime('%Y%m%d')}.json"
        filepath = os.path.join(DATA_DIR, filename)
        
        if os.path.exists(filepath):
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                for snap in data.get("snapshots", []):
                    snap["date"] = check_date
                    all_snapshots.append(snap)
            except Exception as e:
                logger.warning(f"Ошибка загрузки {filepath}: {e}")
    
    if not all_snapshots:
        return pd.DataFrame()
    
    df = pd.DataFrame(all_snapshots)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values("timestamp")
    df = df.set_index("timestamp")
    
    return df


def save_candle_data(
    isin: str,
    df: pd.DataFrame,
    interval: str
) -> str:
    """
    Сохранить данные свечей в CSV
    
    Args:
        isin: ISIN облигации
        df: DataFrame со свечами
        interval: Интервал
        
    Returns:
        Путь к файлу
    """
    ensure_data_dir()
    
    today = date.today().strftime('%Y%m%d')
    filename = f"candles_{isin}_{interval}_{today}.csv"
    filepath = os.path.join(DATA_DIR, filename)
    
    df.to_csv(filepath, encoding='utf-8')
    logger.info(f"Сохранены свечи: {filepath}")
    
    return filepath


def load_candle_data(
    isin: str,
    interval: str,
    target_date: Optional[date] = None
) -> Optional[pd.DataFrame]:
    """
    Загрузить сохранённые данные свечей
    
    Args:
        isin: ISIN облигации
        interval: Интервал
        target_date: Дата данных
        
    Returns:
        DataFrame или None
    """
    if target_date is None:
        target_date = date.today()
    
    filename = f"candles_{isin}_{interval}_{target_date.strftime('%Y%m%d')}.csv"
    filepath = os.path.join(DATA_DIR, filename)
    
    if os.path.exists(filepath):
        try:
            df = pd.read_csv(filepath, index_col=0, parse_dates=True)
            return df
        except Exception as e:
            logger.warning(f"Ошибка загрузки {filepath}: {e}")
    
    return None


def get_saved_data_info() -> Dict[str, Any]:
    """
    Получить информацию о сохранённых данных
    
    Returns:
        Словарь с информацией о файлах
    """
    ensure_data_dir()
    
    files = os.listdir(DATA_DIR)
    
    info = {
        "total_files": len(files),
        "snapshots": [],
        "candles": [],
        "oldest": None,
        "newest": None
    }
    
    dates = []
    
    for f in files:
        filepath = os.path.join(DATA_DIR, f)
        mtime = datetime.fromtimestamp(os.path.getmtime(filepath))
        
        if f.startswith("snapshot_"):
            info["snapshots"].append({
                "file": f,
                "modified": mtime.isoformat()
            })
            # Извлекаем дату из имени
            try:
                date_str = f.replace("snapshot_", "").replace(".json", "")
                file_date = datetime.strptime(date_str, "%Y%m%d").date()
                dates.append(file_date)
            except:
                pass
                
        elif f.startswith("candles_"):
            info["candles"].append({
                "file": f,
                "modified": mtime.isoformat()
            })
    
    if dates:
        info["oldest"] = min(dates).isoformat()
        info["newest"] = max(dates).isoformat()
    
    return info


def cleanup_old_data(days_to_keep: int = 30):
    """
    Удалить старые данные
    
    Args:
        days_to_keep: Количество дней для хранения
    """
    ensure_data_dir()
    
    cutoff_date = date.today() - timedelta(days=days_to_keep)
    
    for f in os.listdir(DATA_DIR):
        filepath = os.path.join(DATA_DIR, f)
        
        try:
            # Извлекаем дату из имени файла
            parts = f.split("_")
            if len(parts) >= 2:
                date_str = parts[-1].replace(".json", "").replace(".csv", "")
                file_date = datetime.strptime(date_str, "%Y%m%d").date()
                
                if file_date < cutoff_date:
                    os.remove(filepath)
                    logger.info(f"Удалён старый файл: {f}")
        except Exception as e:
            logger.warning(f"Не удалось обработать файл {f}: {e}")


# Удобные функции для Streamlit session state
def init_session_storage(st_session_state):
    """Инициализировать хранилище в session state"""
    if 'saved_snapshots' not in st_session_state:
        st_session_state.saved_snapshots = []
    
    if 'last_save_time' not in st_session_state:
        st_session_state.last_save_time = None


def should_save(st_session_state, interval_seconds: int = 60) -> bool:
    """
    Проверить нужно ли сохранять данные
    
    Args:
        st_session_state: Streamlit session state
        interval_seconds: Минимальный интервал между сохранениями
        
    Returns:
        True если нужно сохранить
    """
    if st_session_state.last_save_time is None:
        return True
    
    elapsed = (datetime.now() - st_session_state.last_save_time).total_seconds()
    return elapsed >= interval_seconds
