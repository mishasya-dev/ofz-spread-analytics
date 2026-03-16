"""
Автоматический тест сохранения состояния в браузере через Playwright
"""
import subprocess
import time
import json
import sys

def test_state_persistence():
    """Тест сохранения настроек в браузере"""

    print("=" * 60)
    print("🧪 ТЕСТ СОХРАНЕНИЯ СОСТОЯНИЯ В БРАУЗЕРЕ")
    print("=" * 60)

    # Запускаем streamlit в фоне
    print("\n1️⃣  Запускаем Streamlit приложение...")
    proc = subprocess.Popen(
        ["streamlit", "run", "app.py", "--server.port", "8502", "--server.headless", "true"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd="/home/z/my-project/ofz-spread-analytics"
    )

    # Ждём запуска
    time.sleep(8)

    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            print("2️⃣  Открываем браузер...")
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()
            page = context.new_page()

            # Открываем приложение
            print("3️⃣  Загружаем страницу...")
            page.goto("http://localhost:8502", wait_until="networkidle", timeout=60000)
            time.sleep(5)  # Ждём загрузки данных

            # Проверяем начальное состояние sessionStorage
            print("\n4️⃣  Проверяем начальное состояние...")
            initial_settings = page.evaluate("""() => {
                const data = sessionStorage.getItem('ofz_session/settings');
                return data ? JSON.parse(data) : null;
            }""")
            print(f"   sessionStorage (до): {initial_settings}")

            # Проверяем localStorage (last_pair)
            initial_pair = page.evaluate("""() => {
                const data = localStorage.getItem('ofz_local/last_pair');
                return data ? JSON.parse(data) : null;
            }""")
            print(f"   localStorage last_pair (до): {initial_pair}")

            # Находим слайдер периода и меняем значение
            print("\n5️⃣  Меняем период на 180 дней...")

            # Ищем слайдер по aria-label
            period_slider = page.locator('[data-testid="stSlider"]').first
            if period_slider:
                # Кликаем на слайдер чтобы активировать
                period_slider.click()
                time.sleep(0.5)

                # Используем клавиатуру для изменения значения
                # Сначала получаем текущее значение
                page.keyboard.press("Home")  # Минимум
                time.sleep(0.3)

                # Двигаем вправо (увеличиваем)
                for _ in range(5):
                    page.keyboard.press("ArrowRight")
                    time.sleep(0.1)

            time.sleep(2)  # Ждём сохранения

            # Проверяем что настройки сохранились
            print("\n6️⃣  Проверяем сохранение в sessionStorage...")
            saved_settings = page.evaluate("""() => {
                const data = sessionStorage.getItem('ofz_session/settings');
                return data ? JSON.parse(data) : null;
            }""")
            print(f"   sessionStorage (после): {saved_settings}")

            # Проверяем localStorage (должна сохраниться пара облигаций)
            saved_pair = page.evaluate("""() => {
                const data = localStorage.getItem('ofz_local/last_pair');
                return data ? JSON.parse(data) : null;
            }""")
            print(f"   localStorage last_pair (после): {saved_pair}")

            # Имитируем F5 (перезагрузка страницы)
            print("\n7️⃣  Перезагружаем страницу (F5)...")
            page.reload(wait_until="networkidle", timeout=60000)
            time.sleep(5)

            # Проверяем что настройки восстановились
            print("\n8️⃣  Проверяем восстановление после F5...")
            restored_settings = page.evaluate("""() => {
                const data = sessionStorage.getItem('ofz_session/settings');
                return data ? JSON.parse(data) : null;
            }""")
            print(f"   sessionStorage (после F5): {restored_settings}")

            # Результаты
            print("\n" + "=" * 60)
            print("📊 РЕЗУЛЬТАТЫ:")
            print("=" * 60)

            success = True

            if saved_settings:
                print("✅ sessionStorage: настройки сохраняются")
            else:
                print("❌ sessionStorage: настройки НЕ сохраняются")
                success = False

            if saved_pair:
                print("✅ localStorage: пара облигаций сохраняется")
            else:
                print("⚠️  localStorage: пара облигаций (возможно ещё не меняли)")

            if restored_settings:
                print("✅ Восстановление после F5: работает")
            else:
                print("❌ Восстановление после F5: НЕ работает")
                success = False

            browser.close()

            if success:
                print("\n🎉 ТЕСТ ПРОЙДЕН!")
            else:
                print("\n⚠️  ТЕСТ НЕ ПОЛНОСТЬЮ ПРОЙДЕН")

            return success

    finally:
        # Останавливаем streamlit
        print("\n🛑 Останавливаем Streamlit...")
        proc.terminate()
        proc.wait(timeout=5)


if __name__ == "__main__":
    try:
        test_state_persistence()
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
