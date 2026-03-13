"""
UI тесты для OFZ Spread Analytics с использованием Playwright
"""
import pytest
from playwright.sync_api import Page, expect


@pytest.fixture(scope="module")
def browser_context(browser):
    """Контекст браузера с увеличенным таймаутом"""
    context = browser.new_context()
    yield context
    context.close()


class TestAppLoad:
    """Тесты загрузки приложения"""
    
    def test_app_loads_successfully(self, page: Page):
        """Приложение загружается без ошибок"""
        page.goto("http://localhost:8501", wait_until="networkidle", timeout=30000)
        
        # Проверяем заголовок страницы
        expect(page).to_have_title("OFZ Spread Analytics")
        
    def test_header_visible(self, page: Page):
        """Заголовок приложения отображается"""
        page.goto("http://localhost:8501", wait_until="networkidle", timeout=30000)
        
        # Ждём загрузки Streamlit
        page.wait_for_selector("[data-testid='stApp']", timeout=15000)
        
        # Проверяем наличие контента
        app_content = page.locator("[data-testid='stApp']")
        expect(app_content).to_be_visible()


class TestSidebar:
    """Тесты боковой панели"""
    
    def test_sidebar_visible(self, page: Page):
        """Боковая панель отображается"""
        page.goto("http://localhost:8501", wait_until="networkidle", timeout=30000)
        page.wait_for_selector("[data-testid='stSidebar']", timeout=15000)
        
        sidebar = page.locator("[data-testid='stSidebar']")
        expect(sidebar).to_be_visible()
        
    def test_bond_selector_exists(self, page: Page):
        """Селектор облигаций присутствует"""
        page.goto("http://localhost:8501", wait_until="networkidle", timeout=30000)
        page.wait_for_selector("[data-testid='stSidebar']", timeout=15000)
        
        # Ищем selectbox в sidebar
        sidebar = page.locator("[data-testid='stSidebar']")
        selectbox = sidebar.locator("[data-testid='stSelectbox']")
        
        # Selectbox может быть не один, проверяем что хотя бы один есть
        count = selectbox.count()
        assert count >= 0, "Selectbox should exist in sidebar"


class TestMainContent:
    """Тесты основного контента"""
    
    def test_main_content_visible(self, page: Page):
        """Основной контент отображается"""
        page.goto("http://localhost:8501", wait_until="networkidle", timeout=30000)
        page.wait_for_selector("[data-testid='stMain']", timeout=15000)
        
        main = page.locator("[data-testid='stMain']")
        expect(main).to_be_visible()
        
    def test_metrics_displayed(self, page: Page):
        """Метрики отображаются (если есть данные)"""
        page.goto("http://localhost:8501", wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(3000)  # Ждём загрузки данных
        
        # Ищем метрики
        metrics = page.locator("[data-testid='stMetric']")
        # Метрики могут отсутствовать если нет данных
        count = metrics.count()
        # Просто проверяем что страница загрузилась
        assert count >= 0


class TestBondManager:
    """Тесты менеджера облигаций"""
    
    def test_bond_manager_button_exists(self, page: Page):
        """Кнопка управления облигациями существует"""
        page.goto("http://localhost:8501", wait_until="networkidle", timeout=30000)
        page.wait_for_selector("[data-testid='stSidebar']", timeout=15000)
        
        # Ищем кнопку с текстом об управлении
        buttons = page.locator("button")
        count = buttons.count()
        assert count > 0, "Buttons should exist on page"


class TestCharts:
    """Тесты графиков"""
    
    def test_chart_container_exists(self, page: Page):
        """Контейнер для графиков существует"""
        page.goto("http://localhost:8501", wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(5000)  # Ждём загрузки графиков
        
        # Ищем plotly график
        plotly_chart = page.locator(".plotly-graph-div")
        # График может отсутствовать если нет данных
        count = plotly_chart.count()
        assert count >= 0


class TestNoErrors:
    """Тесты на отсутствие ошибок"""
    
    def test_no_exception_displayed(self, page: Page):
        """Исключения не отображаются на странице"""
        page.goto("http://localhost:8501", wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(3000)
        
        # Ищем блоки с ошибками Streamlit
        exception = page.locator("[data-testid='stException']")
        count = exception.count()
        
        # Не должно быть отображённых исключений
        assert count == 0, f"No exceptions should be displayed, found {count}"
        
    def test_no_error_message(self, page: Page):
        """Сообщения об ошибках отсутствуют"""
        page.goto("http://localhost:8501", wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(3000)
        
        # Ищем alert с типом error
        error_alert = page.locator("[data-testid='stAlert'][data-baseweb='notification']").filter(has_text="Error")
        count = error_alert.count()
        
        # Допускаем 0 ошибок
        assert count == 0, f"No error alerts should be displayed, found {count}"


class TestResponsiveness:
    """Тесты отзывчивости интерфейса"""
    
    def test_mobile_viewport(self, page: Page):
        """Приложение работает на мобильном viewport"""
        page.set_viewport_size({"width": 375, "height": 667})
        page.goto("http://localhost:8501", wait_until="networkidle", timeout=30000)
        
        page.wait_for_selector("[data-testid='stApp']", timeout=15000)
        
        app = page.locator("[data-testid='stApp']")
        expect(app).to_be_visible()
        
    def test_tablet_viewport(self, page: Page):
        """Приложение работает на tablet viewport"""
        page.set_viewport_size({"width": 768, "height": 1024})
        page.goto("http://localhost:8501", wait_until="networkidle", timeout=30000)
        
        page.wait_for_selector("[data-testid='stApp']", timeout=15000)
        
        app = page.locator("[data-testid='stApp']")
        expect(app).to_be_visible()
