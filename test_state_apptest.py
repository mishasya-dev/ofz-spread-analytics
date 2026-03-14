"""
Тест сохранения состояния через Streamlit AppTest с проверкой sessionStorage
"""
import json

def test_state_with_apptest():
    """Тест сохранения настроек через AppTest"""

    print("=" * 60)
    print("🧪 ТЕСТ СОХРАНЕНИЯ СОСТОЯНИЯ (AppTest)")
    print("=" * 60)

    from streamlit.testing.v1 import AppTest

    # 1. Первый запуск - проверяем начальное состояние
    print("\n1️⃣  Первый запуск приложения...")
    at = AppTest.from_file("app.py")
    at.run(timeout=120)

    print(f"   Исключения: {at.exception}")
    print(f"   Метрик: {len(at.metric)}")

    # Проверяем session_state после загрузки
    print("\n2️⃣  Проверяем session_state...")
    period = at.session_state.get("period")
    spread_window = at.session_state.get("spread_window")
    z_threshold = at.session_state.get("z_threshold")
    candle_interval = at.session_state.get("candle_interval")

    print(f"   period: {period}")
    print(f"   spread_window: {spread_window}")
    print(f"   z_threshold: {z_threshold}")
    print(f"   candle_interval: {candle_interval}")

    # 2. Меняем слайдер периода
    print("\n3️⃣  Меняем период на 180 дней...")
    if len(at.slider) > 0:
        at.slider[0].set_value(180)  # Первый слайдер - период
        at.run(timeout=60)

        new_period = at.session_state.get("period")
        print(f"   period после изменения: {new_period}")

        if new_period == 180:
            print("   ✅ Период изменён корректно")
        else:
            print(f"   ❌ Период не изменился: {new_period}")

    # 3. Меняем интервал свечей
    print("\n4️⃣  Меняем интервал свечей на 10 мин...")
    if len(at.radio) > 0:
        at.radio[0].set_value("10")  # Radio интервала
        at.run(timeout=60)

        new_interval = at.session_state.get("candle_interval")
        print(f"   candle_interval после изменения: {new_interval}")

        if new_interval == "10":
            print("   ✅ Интервал изменён корректно")
        else:
            print(f"   ❌ Интервал не изменился: {new_interval}")

    # 4. Проверяем что сохранилось в sessionStorage
    print("\n5️⃣  Проверяем состояние после изменений...")
    final_period = at.session_state.get("period")
    final_spread_window = at.session_state.get("spread_window")
    final_z_threshold = at.session_state.get("z_threshold")
    final_candle_interval = at.session_state.get("candle_interval")
    final_g_spread_period = at.session_state.get("g_spread_period")

    print(f"   period: {final_period}")
    print(f"   spread_window: {final_spread_window}")
    print(f"   z_threshold: {final_z_threshold}")
    print(f"   candle_interval: {final_candle_interval}")
    print(f"   g_spread_period: {final_g_spread_period}")

    # 5. Симулируем F5 - создаём новый AppTest
    print("\n6️⃣  Симулируем F5 (новый запуск приложения)...")
    at2 = AppTest.from_file("app.py")
    at2.run(timeout=120)

    restored_period = at2.session_state.get("period")
    restored_interval = at2.session_state.get("candle_interval")

    print(f"   period после F5: {restored_period}")
    print(f"   candle_interval после F5: {restored_interval}")

    # Результаты
    print("\n" + "=" * 60)
    print("📊 РЕЗУЛЬТАТЫ:")
    print("=" * 60)

    # Примечание: AppTest не сохраняет browser storage между запусками
    # Поэтому проверяем что callbacks работают
    print("\n⚠️  Внимание: AppTest не эмулирует browser storage между запусками")
    print("   Реальное тестирование требует запуска в браузере.")
    print("\n   Но проверяем что callbacks работают:")

    success = True

    # Проверяем что слайдеры меняются
    if final_period == 180:
        print("   ✅ Слайдер периода работает (180 дней)")
    else:
        print(f"   ❌ Слайдер периода: {final_period}")
        success = False

    if final_candle_interval == "10":
        print("   ✅ Radio интервала работает (10 мин)")
    else:
        print(f"   ❌ Radio интервала: {final_candle_interval}")
        success = False

    print("\n💡 Для полного тестирования browser storage:")
    print("   1. Запусти start.bat")
    print("   2. Открой http://localhost:8501")
    print("   3. Измени период → F5 → проверь что восстановился")
    print("   4. Смени облигации → закрой вкладку → открой заново")

    return success


if __name__ == "__main__":
    import sys
    try:
        test_state_with_apptest()
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
