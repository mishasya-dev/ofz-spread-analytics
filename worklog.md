# OFZ Spread Analytics - Журнал работы

## v0.2.1-patch1 — Исправление тестов (27.02.2026)

### Найденные и исправленные проблемы

| # | Проблема | Решение |
|---|----------|---------|
| 1 | `ImportError` в `__init__.py` при запуске pytest | try/except с fallback на абсолютные импорты |
| 2 | Отсутствует `tests/conftest.py` | Создан файл с настройкой путей |
| 3 | 6 тестов падали в `test_moex_bonds.py` | Обновлены тестовые данные (`has_trades`, `num_trades`) |

### Изменённые файлы

- `streamlit-app/__init__.py` — fallback импорты
- `streamlit-app/tests/conftest.py` — новый файл для pytest
- `streamlit-app/tests/test_moex_bonds.py` — обновлены тестовые данные

### Результаты тестирования

```
pytest streamlit-app/tests/ -v
================================
79 passed in 12.34s
```

### Git

- Ветка: `fix/v0.2.1-tests-and-imports`
- Репозиторий: `mishasya-dev/ofz-spread-analytics`

---

## v0.2.2 — Оптимизация (27.02.2026)

### Найденные и исправленные проблемы

| # | Проблема | Решение |
|---|----------|---------|
| 1 | `FutureWarning: 'H' is deprecated` | `freq='H'` → `freq='h'` |
| 2 | Пустой `except:` без логирования | `(ValueError, TypeError)` с логированием |
| 3 | **Медленный MOEX API (30+ сек)** | Пакетный запрос `fetch_all_market_data()` |
| 4 | `LASTTRADEDATE` недоступна | Используем `NUMTRADES` / `VALTODAY` |
| 5 | Дубли облигаций | `seen_isins` для удаления |
| 6 | O(n²) расчёт спредов | Убран — спреды на лету |

### Оптимизация MOEX API

**До:**
```
fetch_ofz_only() - много запросов
fetch_market_data(isin) - N запросов
LASTTRADEDATE - не работает
```

**После:**
```
fetch_ofz_only() - 1 запрос
fetch_all_market_data() - 1 запрос для всех
NUMTRADES, VALTODAY - работают
```

**Результат:** ~1.7 сек для 33 ОФЗ (было 30+ сек)

### Intraday улучшения

| Интервал | Было | Стало |
|----------|------|-------|
| 1 минута | 3 дня | 3 дня |
| 10 минут | 30 дней | 30 дней |
| **1 час** | **30 дней** | **365 дней** |

Пагинация работает: ~6 сек для 4000+ часовых свечей.

### Удаление лишнего

- **Расчёт спредов при обновлении БД** — убран
- Спреды рассчитываются на лету: `spread = (YTM1 - YTM2) × 100`
- Для 64 облигаций: 2016 расчётов → 0

### Тесты

```
tests/run_tests.py:    38/38 ✅
tests/test_database.py: 38/38 ✅
tests/test_sidebar.py:  14/14 ✅
────────────────────────────────
Итого:                  90/90 ✅
```

---

## v0.2.0 — Динамическое управление (27.02.2026)

### Реализовано

- Таблица `bonds` в SQLite
- Модальное окно `@st.dialog` для управления
- Фильтрация: ОФЗ-ПД, > 0.5 года, торги за 10 дней
- `is_favorite` для избранного
- Миграция 16 облигаций из config.py

### Файлы

- `components/bond_manager.py` — модальное окно
- `api/moex_bonds.py` — получение облигаций с MOEX
- `tests/test_sidebar.py` — 14 новых тестов

---

## v0.1.0 — Базовая версия (26.02.2026)

### Реализовано

- SQLite БД (daily_ytm, intraday_ytm, spreads)
- Два режима: daily и intraday
- Расчёт YTM из цен свечей
- Торговые сигналы
- 76 тестов

---

## v0.2.3 — Git Flow & CI/CD Setup (27.02.2026)

### Выполненная работа

#### 1. UI тесты (Playwright)
- Создан `tests/test_ui.py` — 12 UI тестов
- Тесты: загрузка приложения, sidebar, метрики, графики, отсутствие ошибок
- Responsive тесты: mobile (375x667), tablet (768x1024)
- Результат: **12/12 PASSED**

#### 2. Git Flow настройка

| Файл | Описание |
|------|----------|
| `.commitlintrc.json` | Conventional Commits конфигурация |
| `.pre-commit-config.yaml` | Pre-commit hooks (black, isort, flake8, pytest) |
| `pyproject.toml` | Конфигурация инструментов (black, isort, pytest, commitizen) |
| `requirements-dev.txt` | Dev-зависимости |
| `CONTRIBUTING.md` | Руководство по разработке |

#### 3. GitHub Actions CI/CD

`.github/workflows/ci.yml`:
- **lint** — black, isort, flake8 проверки
- **test** — pytest с coverage
- **build** — создание архива
- **release** — автоматический релиз при теге

#### 4. Шаблоны

- `.github/PULL_REQUEST_TEMPLATE.md`
- `.github/ISSUE_TEMPLATE/bug_report.md`
- `.github/ISSUE_TEMPLATE/feature_request.md`

#### 5. Документация

- `README.md` — добавлен раздел "Разработка"
- `CONTRIBUTING.md` — Git Flow, коммиты, тестирование, code style

### Структура коммитов

```
<type>(<scope>): <subject>

Типы: feat, fix, refactor, test, docs, style, chore, perf, ci
Scope: api, db, ui, ytm, charts, test
```

### Тесты (итого)

```
Юнит-тесты:  97/97 ✅
UI-тесты:    12/12 ✅
────────────────────
Итого:       109/109 ✅
```

### Git

- Ветка: `fix/v0.2.1-tests-and-imports` → merged to `main`
- Коммит merge: `4f3b623`
- Тег: `v0.2.3`
- Push: https://github.com/mishasya-dev/ofz-spread-analytics

### Архив

- `/home/z/my-project/download/ofz-spread-analytics-refactored-v0.2.2.zip` (157 KB)

---

*Последнее обновление: 27.02.2026*
