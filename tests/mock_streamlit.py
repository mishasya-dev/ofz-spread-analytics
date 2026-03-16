"""
Mock для streamlit при тестировании

Используется когда streamlit не установлен в окружении.
"""
from unittest.mock import MagicMock, Mock
import sys


class SessionStateDict(dict):
    """
    Dict с поддержкой доступа через атрибуты.
    st.session_state.period работает как st.session_state['period']
    """
    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(f"'{type(self).__name__}' object has no attribute '{key}'")

    def __setattr__(self, key, value):
        self[key] = value

    def __delattr__(self, key):
        try:
            del self[key]
        except KeyError:
            raise AttributeError(f"'{type(self).__name__}' object has no attribute '{key}'")


# Создаём mock модуль для streamlit
class StreamlitMock:
    """Mock для модуля streamlit"""

    def __init__(self):
        self.session_state = SessionStateDict()
        self.cache_data = self._cache_decorator
        self.cache_resource = self._cache_decorator
        self.sidebar = MagicMock()
        self.columns = self._columns_mock
        self.metric = Mock()
        self.markdown = Mock()
        self.write = Mock()
    
    def _cache_decorator(self, ttl=None, show_spinner=True, **kwargs):
        def decorator(func):
            return func
        return decorator
    
    def _columns_mock(self, *args, **kwargs):
        return [MagicMock() for _ in range(args[0] if args else 2)]
    
    def __getattr__(self, name):
        return Mock()
    
    def set_page_config(self, **kwargs):
        pass
    
    def title(self, text):
        pass
    
    def header(self, text):
        pass
    
    def subheader(self, text):
        pass
    
    def info(self, text):
        pass
    
    def warning(self, text):
        pass
    
    def error(self, text):
        pass
    
    def success(self, text):
        pass
    
    def spinner(self, text):
        class SpinnerContext:
            def __enter__(self):
                return self
            def __exit__(self, *args):
                pass
        return SpinnerContext()
    
    def progress(self, value):
        return MagicMock()
    
    def empty(self):
        return MagicMock()
    
    def text(self, txt=""):
        pass
    
    def caption(self, txt):
        pass
    
    def divider(self):
        pass
    
    def button(self, label, **kwargs):
        return False
    
    def toggle(self, label, **kwargs):
        key = kwargs.get('key')
        value = kwargs.get('value', False)
        # Если есть key, синхронизируем с session_state
        if key is not None:
            if key not in self.session_state:
                self.session_state[key] = value
            return self.session_state[key]
        return value
    
    def selectbox(self, label, options, **kwargs):
        key = kwargs.get('key')
        index = kwargs.get('index', 0)
        value = options[index] if options and index < len(options) else None
        # Если есть key, синхронизируем с session_state
        if key is not None:
            if key not in self.session_state:
                self.session_state[key] = index
            # Возвращаем индекс для совместимости с тестами
            return self.session_state[key]
        return value
    
    def radio(self, label, options, **kwargs):
        key = kwargs.get('key')
        index = kwargs.get('index', 0)
        # Если есть key, синхронизируем с session_state
        if key is not None:
            if key not in self.session_state:
                self.session_state[key] = options[index] if options else None
            return self.session_state[key]
        return options[index] if options else None
    
    def slider(self, label, **kwargs):
        key = kwargs.get('key')
        value = kwargs.get('value')
        min_val = kwargs.get('min_value', 0)
        max_val = kwargs.get('max_value', 100)
        
        # Если есть key, синхронизируем с session_state
        if key is not None:
            if key not in self.session_state:
                # Если value не указан, используем середину диапазона
                default = value if value is not None else (min_val + max_val) // 2
                self.session_state[key] = default
            return self.session_state[key]
        
        # Без key возвращаем value или середину
        return value if value is not None else (min_val + max_val) // 2
    
    def select_slider(self, label, options, **kwargs):
        return kwargs.get('value', options[0] if options else None)
    
    def data_editor(self, df, **kwargs):
        return df
    
    def expander(self, label, **kwargs):
        class ExpanderContext:
            def __enter__(self):
                return self
            def __exit__(self, *args):
                pass
        return ExpanderContext()
    
    def dialog(self, title, **kwargs):
        def decorator(func):
            return func
        return decorator
    
    def toast(self, message):
        pass
    
    def rerun(self):
        pass
    
    def stop(self):
        pass
    
    def reset(self):
        """Сбросить mock в исходное состояние (восстановить методы)"""
        # Восстанавливаем оригинальные методы через __dict__ для корректной привязки
        # Удаляем переопределённые методы из экземпляра, чтобы использовались методы класса
        for method_name in ['slider', 'toggle', 'radio', 'selectbox', 'button']:
            if method_name in self.__dict__:
                del self.__dict__[method_name]
        self.session_state = SessionStateDict()


# Регистрируем mock
st_mock = StreamlitMock()
sys.modules['streamlit'] = st_mock
