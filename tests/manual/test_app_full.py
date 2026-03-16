"""
Полное тестирование UI приложения

Требует настоящий streamlit. Запускать вручную:
    python tests/manual/test_app_full.py
"""
import pytest

# Пропускаем весь модуль при обычном запуске pytest
pytestmark = pytest.mark.skip(reason="Manual test requiring real streamlit")

from streamlit.testing.v1 import AppTest
import time

def run_test(name, test_func, timeout=120):
    print(f"\n{'='*60}")
    print(f"=== {name} ===")
    print(f"{'='*60}")
    try:
        test_func(timeout)
        print(f"✅ {name}: OK")
        return True
    except Exception as e:
        print(f"❌ {name}: {e}")
        return False

def test_app_initial_load(timeout):
    """Тест: начальная загрузка"""
    at = AppTest.from_file("app.py")
    at.run(timeout=timeout)
    
    assert not at.exception, f"Исключение: {at.exception}"
    
    # Проверяем элементы UI
    print(f"  📊 Метрик: {len(at.metric)}")
    print(f"  📝 Markdown: {len(at.markdown)}")
    print(f"  📈 Графиков: {len(at.main.element)}")
    
def test_sidebar_selectbox(timeout):
    """Тест: выбор облигаций"""
    at = AppTest.from_file("app.py")
    at.run(timeout=timeout)
    
    print(f"  📋 Selectbox: {len(at.selectbox)}")
    
    if len(at.selectbox) >= 2:
        # Меняем выбор облигации 2 (индекс 1)
        at.selectbox[1].set_value(2)  # Выбираем 3-ю облигацию
        at.run(timeout=timeout)
        print(f"  ✅ Облигация 2 изменена на индекс 2")
    
def test_period_slider(timeout):
    """Тест: изменение периода"""
    at = AppTest.from_file("app.py")
    at.run(timeout=timeout)
    
    print(f"  📊 Slider: {len(at.slider)}")
    
    # Слайдер периода - первый по порядку
    at.slider[0].set_value(180)
    at.run(timeout=timeout)
    print(f"  ✅ Период изменён на 180 дней")
    
def test_spread_window_slider(timeout):
    """Тест: изменение окна спреда"""
    at = AppTest.from_file("app.py")
    at.run(timeout=timeout)
    
    # Слайдер окна spread analytics (обычно 2-й)
    if len(at.slider) >= 2:
        at.slider[1].set_value(45)
        at.run(timeout=timeout)
        print(f"  ✅ Окно spread изменено на 45 дней")
    
def test_z_threshold_slider(timeout):
    """Тест: изменение Z-Score порога"""
    at = AppTest.from_file("app.py")
    at.run(timeout=timeout)
    
    # Слайдер Z-Score порога
    if len(at.slider) >= 3:
        at.slider[2].set_value(2.5)
        at.run(timeout=timeout)
        print(f"  ✅ Z-Score порог изменён на 2.5σ")
    
def test_candle_interval_radio(timeout):
    """Тест: переключение интервала свечей"""
    at = AppTest.from_file("app.py")
    at.run(timeout=timeout)
    
    print(f"  📻 Radio: {len(at.radio)}")
    
    # Переключаем на 10 минут
    if len(at.radio) >= 1:
        at.radio[0].set_value("10")
        at.run(timeout=timeout)
        print(f"  ✅ Интервал свечей изменён на 10 мин")
    
def test_auto_refresh_toggle(timeout):
    """Тест: включение автообновления"""
    at = AppTest.from_file("app.py")
    at.run(timeout=timeout)
    
    print(f"  🔘 Toggle: {len(at.toggle)}")
    
    if len(at.toggle) >= 1:
        at.toggle[0].set_value(True)
        at.run(timeout=timeout)
        print(f"  ✅ Автообновление включено")
    
def test_clear_cache_button(timeout):
    """Тест: кнопка очистки кэша"""
    at = AppTest.from_file("app.py")
    at.run(timeout=timeout)
    
    print(f"  🔘 Button: {len(at.button)}")
    
    # Ищем кнопку очистки кэша (обычно последняя)
    if len(at.button) >= 1:
        at.button[-1].click()
        at.run(timeout=timeout)
        print(f"  ✅ Кнопка очистки кэша нажата")

if __name__ == "__main__":
    print("\n" + "="*60)
    print("🧪 ПОЛНОЕ ТЕСТИРОВАНИЕ UI OFZ SPREAD ANALYTICS")
    print("="*60)
    
    results = []
    
    # Запускаем тесты
    results.append(run_test("1. Начальная загрузка", test_app_initial_load, 120))
    results.append(run_test("2. Выбор облигаций (selectbox)", test_sidebar_selectbox, 60))
    results.append(run_test("3. Слайдер периода", test_period_slider, 60))
    results.append(run_test("4. Слайдер окна спреда", test_spread_window_slider, 60))
    results.append(run_test("5. Слайдер Z-Score порога", test_z_threshold_slider, 60))
    results.append(run_test("6. Интервал свечей (radio)", test_candle_interval_radio, 60))
    results.append(run_test("7. Автообновление (toggle)", test_auto_refresh_toggle, 60))
    results.append(run_test("8. Кнопка очистки кэша", test_clear_cache_button, 60))
    
    print("\n" + "="*60)
    print("📊 РЕЗУЛЬТАТЫ:")
    print("="*60)
    passed = sum(results)
    total = len(results)
    print(f"  ✅ Пройдено: {passed}/{total}")
    print(f"  ❌ Провалено: {total - passed}/{total}")
    
    if passed == total:
        print("\n🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ!")
    else:
        print("\n⚠️ Некоторые тесты провалены")
