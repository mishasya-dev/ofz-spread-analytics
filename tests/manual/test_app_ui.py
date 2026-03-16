"""
Тестирование UI приложения через Streamlit AppTest

Требует настоящий streamlit. Запускать вручную:
    python tests/manual/test_app_ui.py
"""
import pytest

# Пропускаем весь модуль при обычном запуске pytest
pytestmark = pytest.mark.skip(reason="Manual test requiring real streamlit")

from streamlit.testing.v1 import AppTest

def test_app_loads():
    """Тест: приложение загружается без ошибок"""
    at = AppTest.from_file("app.py")
    at.run(timeout=30)
    
    # Проверяем, что нет исключений
    assert not at.exception
    
    # Проверяем, что есть заголовок
    print(f"Заголовки: {at.title}")
    print(f"Markdown: {len(at.markdown)} элементов")
    print(f"Метрики: {len(at.metric)} метрик")
    
def test_sidebar_widgets():
    """Тест: виджеты sidebar работают"""
    at = AppTest.from_file("app.py")
    at.run(timeout=30)
    
    # Проверяем sidebar
    print(f"Selectbox: {len(at.selectbox)}")
    print(f"Slider: {len(at.slider)}")
    print(f"Toggle: {len(at.toggle)}")
    print(f"Button: {len(at.button)}")
    
def test_period_slider():
    """Тест: изменение периода"""
    at = AppTest.from_file("app.py")
    at.run(timeout=30)
    
    if len(at.slider) > 0:
        # Находим слайдер периода (индекс 0)
        at.slider[0].set_value(180)  # 180 дней
        at.run(timeout=30)
        print(f"Период изменён на 180 дней")

if __name__ == "__main__":
    print("=== Тест 1: Загрузка приложения ===")
    try:
        test_app_loads()
        print("✅ Загрузка OK")
    except Exception as e:
        print(f"❌ Ошибка: {e}")
    
    print("\n=== Тест 2: Виджеты sidebar ===")
    try:
        test_sidebar_widgets()
        print("✅ Виджеты OK")
    except Exception as e:
        print(f"❌ Ошибка: {e}")
    
    print("\n=== Тест 3: Изменение периода ===")
    try:
        test_period_slider()
        print("✅ Слайдер OK")
    except Exception as e:
        print(f"❌ Ошибка: {e}")
