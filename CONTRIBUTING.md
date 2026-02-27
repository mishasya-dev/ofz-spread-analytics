# Руководство по разработке OFZ Spread Analytics

## Содержание

- [Git Flow](#git-flow)
- [Коммиты](#коммиты)
- [Ветвление](#ветвление)
- [Тестирование](#тестирование)
- [Code Style](#code-style)
- [Релизы](#релизы)

---

## Git Flow

### Структура веток

```
main (стабильный релиз)
  │
  └── develop (интеграция фич)
        │
        ├── feature/xxx (новые фичи)
        ├── fix/xxx (багфиксы)
        └── refactor/xxx (рефакторинг)
```

### Правила работы с ветками

| Тип | Префикс | Пример | Base | Merge в |
|-----|---------|--------|------|---------|
| Feature | `feature/` | `feature/ytm-chart` | develop | develop |
| Fix | `fix/` | `fix/checkbox-state` | develop | develop + main |
| Refactor | `refactor/` | `refactor/database` | develop | develop |
| Release | `release/` | `release/v0.3.0` | develop | main + tag |

### Workflow

1. **Создать ветку** от `develop`
   ```bash
   git checkout develop
   git pull
   git checkout -b feature/my-feature
   ```

2. **Разрабатывать** с атомарными коммитами

3. **Запустить тесты**
   ```bash
   pytest tests/ -v
   ```

4. **Создать Pull Request** в `develop`

5. **После Code Review** — merge

---

## Коммиты

### Формат (Conventional Commits)

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Типы коммитов

| Тип | Описание | Пример |
|-----|----------|--------|
| `feat` | Новая функциональность | `feat(ui): add bond selector` |
| `fix` | Исправление бага | `fix(ytm): correct settlement date` |
| `refactor` | Рефакторинг | `refactor(db): split into repositories` |
| `test` | Тесты | `test(api): add moex_bonds tests` |
| `docs` | Документация | `docs: update README` |
| `style` | Форматирование | `style: fix indentation` |
| `chore` | Обслуживание | `chore: update dependencies` |
| `perf` | Производительность | `perf(api): cache moex responses` |
| `ci` | CI/CD | `ci: add github actions` |

### Области (Scope)

| Scope | Модуль |
|-------|--------|
| `api` | MOEX API интеграция |
| `db` | База данных, репозитории |
| `ui` | Streamlit компоненты |
| `ytm` | Расчёт YTM |
| `charts` | Графики Plotly |
| `test` | Тестирование |

### Примеры

```bash
# Хорошо
feat(ui): add bond manager modal dialog
fix(ytm): pass settlement_date to calculate_ytm
refactor(db): extract bonds_repo from database.py
test(api): add tests for fetch_ofz_for_trading

# Плохо
fixed bug
updates
WIP
```

---

## Тестирование

### Структура тестов

```
tests/
├── conftest.py          # Фикстуры pytest
├── mock_streamlit.py    # Моки для Streamlit
├── test_database.py     # Тесты БД
├── test_ytm_calculation.py
├── test_moex_bonds.py
├── test_bond_manager.py
└── test_ui.py           # UI тесты (Playwright)
```

### Запуск тестов

```bash
# Все тесты
pytest tests/ -v

# Только юнит-тесты
pytest tests/ -v -m "not ui"

# Конкретный файл
pytest tests/test_ytm_calculation.py -v

# С покрытием
pytest tests/ -v --cov=. --cov-report=html
```

### Требования к тестам

- Каждый новый модуль должен иметь тесты
- Минимальное покрытие: 80%
- Тесты должны быть независимыми
- Использовать фикстуры из `conftest.py`

---

## Code Style

### Форматирование

```bash
# Black — форматирование кода
black . --line-length=100

# isort — сортировка импортов
isort . --profile=black --line-length=100
```

### Линтеры

```bash
# flake8 — проверка кода
flake8 . --max-line-length=100 --ignore=E501,W503,E203
```

### Структура файла

```python
"""
Модуль: описание
"""
# 1. Стандартная библиотека
import os
from datetime import datetime

# 2. Сторонние пакеты
import pandas as pd
import streamlit as st

# 3. Локальные модули
from api.moex_bonds import fetch_ofz_list
from core.database import get_bonds_repo

# 4. Константы
CACHE_TTL = 300

# 5. Функции/классы
def my_function():
    """Описание функции."""
    pass
```

---

## Релизы

### Семантическое версионирование

```
MAJOR.MINOR.PATCH

MAIOR — несовместимые изменения API
MINOR — новая функциональность (обратная совместимость)
PATCH — багфиксы
```

### Процесс релиза

1. Создать ветку `release/vX.Y.Z` от `develop`
2. Обновить версию в `pyproject.toml`
3. Обновить `CHANGELOG.md`
4. Создать PR в `main`
5. После merge — создать tag:
   ```bash
   git tag -a vX.Y.Z -m "Release vX.Y.Z"
   git push origin vX.Y.Z
   ```
6. GitHub создаст Release автоматически

### Changelog

```markdown
## [0.3.0] - 2025-02-27

### Added
- New bond manager modal dialog
- UI tests with Playwright

### Fixed
- YTM calculation with correct settlement date
- Checkbox state preservation in data_editor

### Changed
- Refactored database into repositories
```

---

## Pre-commit Hooks

### Установка

```bash
pip install pre-commit
pre-commit install
pre-commit install --hook-type commit-msg
```

### Запуск вручную

```bash
pre-commit run --all-files
```

### Что проверяется

- Форматирование (black, isort)
- Линтеры (flake8)
- Тесты (pytest)
- Сообщения коммитов (commitizen)

---

## Контакты

Вопросы по разработке: создайте Issue с меткой `question`
