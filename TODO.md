# TODO: OFZ Spread Analytics

## Приоритет: Средний

### Автоматизация UI тестов (Playwright)

**Текущий статус:** Ручное тестирование через Playwright в интерактивном режиме

**Что проверено вручную:**
- ✅ Страница загружается (title: "OFZ Spread Analytics")
- ✅ 2 selectbox для выбора облигаций (10+ options каждый)
- ✅ 4 метрики с данными (YTM, spread, signal)
- ✅ 3 plotly графика рендерятся
- ✅ 32 кнопки на странице
- ✅ Выбор bonds из dropdown работает
- ✅ Кэширование в БД работает

---

## Варианты автоматизации

### Вариант 1: pytest + Playwright (Рекомендуется)

**Файл:** `tests/test_ui_e2e.py`

```python
import pytest
from playwright.sync_api import sync_playwright

class TestOFZAnalyticsUI:
    
    @pytest.fixture(scope="class")
    def page(self):
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto('http://localhost:8501', timeout=60000)
            page.wait_for_load_state('networkidle', timeout=30000)
            yield page
            browser.close()
    
    def test_page_loads(self, page):
        """Страница загружается с правильным title"""
        assert page.title() == "OFZ Spread Analytics"
    
    def test_bonds_loaded(self, page):
        """Selectbox-ы с облигациями заполнены"""
        selects = page.locator('[data-baseweb="select"]').all()
        assert len(selects) >= 2, "Должно быть минимум 2 selectbox"
    
    def test_charts_rendered(self, page):
        """Plotly графики рендерятся"""
        charts = page.locator('.js-plotly-plot').all()
        assert len(charts) >= 1, "Должен быть минимум 1 график"
    
    def test_metrics_not_empty(self, page):
        """Метрики не пустые"""
        metrics = page.locator('[data-testid="stMetric"]')
        assert metrics.count() >= 4, "Должно быть минимум 4 метрики"
    
    def test_bond_selection_works(self, page):
        """Выбор облигации работает"""
        selects = page.locator('[data-baseweb="select"]').all()
        if selects:
            selects[0].click()
            options = page.locator('li[role="option"]').all()
            assert len(options) > 0, "Должны быть опции для выбора"
```

**Зависимости:**
```bash
pip install pytest-playwright
playwright install chromium
```

---

### Вариант 2: GitHub Actions CI/CD

**Файл:** `.github/workflows/ui-tests.yml`

```yaml
name: UI Tests
on: [push, pull_request]

jobs:
  ui-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest-playwright
          playwright install chromium
      
      - name: Start Streamlit
        run: |
          streamlit run app.py --server.headless true --server.port 8501 &
          sleep 10
      
      - name: Run UI tests
        run: pytest tests/test_ui_e2e.py -v
```

---

### Вариант 3: Playwright Test (Node.js)

**Альтернатива для сложных сценариев, требует Node.js**

---

## Чек-лист проверок для автоматизации

| Проверка | Приоритет | Сложность | Статус |
|----------|-----------|-----------|--------|
| Страница загружается | 🔴 Высокий | Низкая | ✅ Протестировано вручную |
| Selectbox с bonds заполнен | 🔴 Высокий | Низкая | ✅ Протестировано вручную |
| Графики рендерятся | 🔴 Высокий | Низкая | ✅ Протестировано вручную |
| Метрики не пустые | 🔴 Высокий | Низкая | ✅ Протестировано вручную |
| Выбор bonds меняет график | 🟡 Средний | Средняя | Не протестировано |
| Кнопка "Обновить БД" работает | 🟡 Средний | Средняя | Не протестировано |
| Кнопка "Очистить кэш" работает | 🟡 Средний | Средняя | Не протестировано |
| Слайдеры меняют период | 🟡 Средний | Средняя | Не протестировано |
| Скриншот diff (регрессия) | 🟢 Низкий | Высокая | Не требуется |

---

## Следующие шаги

1. [ ] Создать `tests/test_ui_e2e.py` с базовыми тестами
2. [ ] Добавить `pytest-playwright` в `requirements.txt`
3. [ ] Протестировать локально
4. [ ] Добавить GitHub Actions workflow (опционально)
5. [ ] Интегрировать в CI/CD пайплайн

---

## Заметки

- Streamlit требует время на загрузку (~10-20 секунд)
- Использовать `wait_for_load_state('networkidle')` для ожидания
- Playwright лучше Selenium для современных JS-фреймворков
- Headless режим работает корректно

---

# Другие задачи

## Приоритет: Низкий

- [ ] Починить упавшие тесты в `test_app_v030.py` (Streamlit mock issue)
- [ ] Починить `test_candle_service.py` (TypeError)
- [ ] Починить `test_zcyc_optimization.py` (sqlite3 error)
- [ ] Удалить неиспользуемый код `modes/base.py` (DailyMode)
- [ ] Убрать излишнее логирование watchdog (DEBUG level spam)
