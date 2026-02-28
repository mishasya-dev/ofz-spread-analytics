"""
Mock для streamlit при тестировании

Используется когда streamlit не установлен в окружении.
"""
from unittest.mock import MagicMock, Mock
import sys

# Создаём mock модуль для streamlit
class StreamlitMock:
    """Mock для модуля streamlit"""
    
    def __init__(self):
        self.session_state = {}
        self.cache_data = self._cache_decorator
        self.cache_resource = self._cache_decorator
        self.sidebar = MagicMock()
        self.columns = self._columns_mock
        self.metric = Mock()
        self.markdown = Mock()
        self.write = Mock()
    
    def _cache_decorator(self, ttl=None):
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
        return kwargs.get('value', False)
    
    def selectbox(self, label, options, **kwargs):
        return options[0] if options else None
    
    def radio(self, label, options, **kwargs):
        return options[0] if options else None
    
    def slider(self, label, **kwargs):
        return kwargs.get('value', 0)
    
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


# Регистрируем mock
st_mock = StreamlitMock()
sys.modules['streamlit'] = st_mock
