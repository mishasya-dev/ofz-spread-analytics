"""
Унифицированный модуль логирования действий

Содержит:
- Декоратор @log_call для автоматического логирования функций
- Функции для логирования пользовательских действий (кнопки, слайдеры и т.д.)
"""
import logging
from functools import wraps
from typing import Callable, Any, Optional
import time


# =============================================================================
# ДЕКОРАТОР ДЛЯ ЛОГИРОВАНИЯ ФУНКЦИЙ
# =============================================================================

def log_call(level: int = logging.DEBUG, log_args: bool = False, log_result: bool = False):
    """
    Декоратор для автоматического логирования входа/выхода из функции.
    
    Args:
        level: Уровень логирования (по умолчанию DEBUG)
        log_args: Логировать аргументы функции
        log_result: Логировать тип результата
    
    Usage:
        @log_call()
        def my_function():
            pass
        
        @log_call(level=logging.INFO, log_args=True)
        def fetch_data(isin: str, days: int):
            return df
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            logger = logging.getLogger(func.__module__)
            
            # Формируем сообщение о входе
            entry_msg = f"→ {func.__name__}()"
            if log_args and (args or kwargs):
                args_str = ", ".join(
                    [repr(a) for a in args[:3]] +  # Первые 3 позиционных
                    [f"{k}={repr(v)}" for k, v in list(kwargs.items())[:3]]  # Первые 3 именованных
                )
                if len(args) > 3 or len(kwargs) > 3:
                    args_str += ", ..."
                entry_msg = f"→ {func.__name__}({args_str})"
            
            logger.log(level, entry_msg)
            
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                elapsed = time.time() - start_time
                
                # Формируем сообщение о выходе
                if log_result and result is not None:
                    result_type = type(result).__name__
                    if hasattr(result, '__len__'):
                        result_type = f"{result_type}({len(result)})"
                    logger.log(level, f"← {func.__name__}() → {result_type} [{elapsed:.3f}s]")
                else:
                    logger.log(level, f"← {func.__name__}() [{elapsed:.3f}s]")
                
                return result
                
            except Exception as e:
                elapsed = time.time() - start_time
                logger.error(f"✗ {func.__name__}() → {type(e).__name__}: {e} [{elapsed:.3f}s]")
                raise
        
        return wrapper
    return decorator


def log_call_simple(func: Callable) -> Callable:
    """Простой декоратор без параметров для быстрого использования"""
    return log_call()(func)


# =============================================================================
# ЛОГИРОВАНИЕ ПОЛЬЗОВАТЕЛЬСКИХ ДЕЙСТВИЙ
# =============================================================================

# Эмодзи для разных типов виджетов
WIDGET_EMOJI = {
    'selected_bond': '📌',
    'period': '📏',
    'spread_window': '📐',
    'z_threshold': '🎯',
    'g_spread': '📊',
    'candle': '🕯️',
    'refresh': '🔄',
    'log_level': '📜',
    'validation': '🔍',
    'auto_refresh': '⚡',
}

DEFAULT_WIDGET_EMOJI = '🎛️'


def log_widget_change(widget_name: str, details: Optional[str] = None, session_state: dict = None):
    """
    Логирует изменение виджета в DEBUG режиме.
    
    Args:
        widget_name: Имя виджета (ключ в session_state)
        details: Дополнительная информация
        session_state: Streamlit session_state (передаётся явно для избежания импорта)
    
    Usage:
        def on_bond_change():
            log_widget_change("selected_bond1", bonds[st.session_state.selected_bond1].isin, st.session_state)
        
        st.selectbox("Облигация", ..., on_change=on_bond_change)
    """
    logger = logging.getLogger('__main__')
    
    # Получаем значение
    value = None
    if session_state is not None:
        value = session_state.get(widget_name)
    
    # Выбираем эмодзи
    emoji = DEFAULT_WIDGET_EMOJI
    for key, e in WIDGET_EMOJI.items():
        if key in widget_name:
            emoji = e
            break
    
    # Формируем сообщение
    msg = f"{emoji} {widget_name} = {value}"
    if details:
        msg += f" ({details})"
    
    logger.debug(msg)


def log_button_press(button_name: str, details: Optional[str] = None):
    """
    Логирует нажатие кнопки в DEBUG режиме.
    
    Args:
        button_name: Название кнопки
        details: Дополнительная информация
    
    Usage:
        if st.button("Обновить", on_click=lambda: log_button_press("Обновить")):
            ...
    """
    logger = logging.getLogger('__main__')
    
    msg = f"🔘 Нажата кнопка: '{button_name}'"
    if details:
        msg += f" ({details})"
    
    logger.debug(msg)


def log_action(action_type: str, description: str, details: Optional[str] = None):
    """
    Универсальная функция для логирования действий.
    
    Args:
        action_type: Тип действия (button, widget, data, api, calc)
        description: Описание действия
        details: Дополнительная информация
    
    Usage:
        log_action("api", "Загрузка данных с MOEX", f"isin={isin}")
        log_action("calc", "Расчёт G-spread", f"window={window}")
    """
    logger = logging.getLogger('__main__')
    
    emoji_map = {
        'button': '🔘',
        'widget': '🎛️',
        'data': '📦',
        'api': '🌐',
        'calc': '🧮',
        'cache': '💾',
        'db': '🗄️',
    }
    
    emoji = emoji_map.get(action_type, '▶️')
    
    msg = f"{emoji} {description}"
    if details:
        msg += f" ({details})"
    
    logger.debug(msg)


# =============================================================================
# КОНТЕКСТНЫЙ МЕНЕДЖЕР ДЛЯ ЛОГИРОВАНИЯ БЛОКОВ КОДА
# =============================================================================

class LogBlock:
    """
    Контекстный менеджер для логирования блоков кода.
    
    Usage:
        with LogBlock("Загрузка данных с MOEX"):
            data = fetch_data()
    """
    def __init__(self, name: str, level: int = logging.DEBUG, logger_name: str = '__main__'):
        self.name = name
        self.level = level
        self.logger = logging.getLogger(logger_name)
        self.start_time = None
    
    def __enter__(self):
        self.start_time = time.time()
        self.logger.log(self.level, f"▶️ Начало: {self.name}")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        elapsed = time.time() - self.start_time
        if exc_type is None:
            self.logger.log(self.level, f"✅ Завершено: {self.name} [{elapsed:.3f}s]")
        else:
            self.logger.error(f"❌ Ошибка в {self.name}: {exc_val} [{elapsed:.3f}s]")
        return False
