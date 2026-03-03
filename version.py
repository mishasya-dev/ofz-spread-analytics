"""
Метаданные версии приложения

Обновляется автоматически при сборке.
"""
import subprocess
from datetime import datetime
from pathlib import Path

# Основные данные версии
VERSION = "0.5.5"
RELEASE_NAME = "Chart Update Fix"

def get_git_info():
    """Получить информацию из git"""
    try:
        # Ветка
        branch = subprocess.check_output(
            ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
            stderr=subprocess.DEVNULL,
            cwd=Path(__file__).parent
        ).decode().strip()
        
        # Хеш коммита (короткий)
        commit = subprocess.check_output(
            ['git', 'rev-parse', '--short', 'HEAD'],
            stderr=subprocess.DEVNULL,
            cwd=Path(__file__).parent
        ).decode().strip()
        
        # Дата коммита
        commit_date = subprocess.check_output(
            ['git', 'log', '-1', '--format=%ci'],
            stderr=subprocess.DEVNULL,
            cwd=Path(__file__).parent
        ).decode().strip()
        
        # Количество коммитов
        commit_count = subprocess.check_output(
            ['git', 'rev-list', '--count', 'HEAD'],
            stderr=subprocess.DEVNULL,
            cwd=Path(__file__).parent
        ).decode().strip()
        
        return {
            'branch': branch,
            'commit': commit,
            'commit_date': commit_date[:10],  # YYYY-MM-DD
            'build': commit_count
        }
    except Exception:
        return {
            'branch': 'unknown',
            'commit': 'local',
            'commit_date': datetime.now().strftime('%Y-%m-%d'),
            'build': 'dev'
        }

# Кэшируем git info
GIT_INFO = get_git_info()

def get_version_info():
    """Получить полную информацию о версии"""
    return {
        'version': VERSION,
        'release_name': RELEASE_NAME,
        'branch': GIT_INFO['branch'],
        'commit': GIT_INFO['commit'],
        'date': GIT_INFO['commit_date'],
        'build': GIT_INFO['build']
    }

def format_version_badge():
    """Форматировать HTML для badge версии"""
    info = get_version_info()
    
    # Сокращаем название ветки для отображения
    branch_display = info['branch']
    if branch_display.startswith('feature/'):
        branch_display = branch_display.replace('feature/', 'feat/')
    elif branch_display.startswith('fix/'):
        branch_display = branch_display.replace('fix/', '')
    elif branch_display.startswith('release/'):
        branch_display = branch_display.replace('release/', 'rel/')
    
    return f"""
<div class="version-badge-full">
    <div class="version-main">v{info['version']}</div>
    <div class="version-details">
        <span class="version-branch">📁 {branch_display}</span>
        <span class="version-date">📅 {info['date']}</span>
        <span class="version-build">#{info['build']}</span>
    </div>
    <div class="version-commit">commit: {info['commit']}</div>
</div>
"""

def format_version_compact():
    """Компактный формат для sidebar"""
    info = get_version_info()
    
    branch_display = info['branch']
    if branch_display.startswith('feature/'):
        branch_display = branch_display.replace('feature/', '')
    elif branch_display.startswith('fix/'):
        branch_display = branch_display.replace('fix/', '')
    
    return f"v{info['version']} | {branch_display} | #{info['build']}"


if __name__ == '__main__':
    # Тестовый вывод
    info = get_version_info()
    print(f"Version: {info['version']}")
    print(f"Release: {info['release_name']}")
    print(f"Branch:  {info['branch']}")
    print(f"Commit:  {info['commit']}")
    print(f"Date:    {info['date']}")
    print(f"Build:   {info['build']}")
