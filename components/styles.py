"""
CSS стили для приложения OFZ Spread Analytics

Централизованное управление всеми стилями.
"""
import streamlit as st


# ============================================================================
# ОСНОВНЫЕ CSS СТИЛИ
# ============================================================================

MAIN_STYLES = """
<style>
    /* Main header */
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        margin-bottom: 1rem;
    }
    
    /* Metric cards */
    .metric-card {
        background: #f8f9fa;
        padding: 15px;
        border-radius: 10px;
        border-left: 4px solid #1f77b4;
    }
    
    /* Signal styles */
    .signal-buy {
        background: linear-gradient(135deg, #d4edda, #c3e6cb);
        border-left: 4px solid #28a745;
    }
    .signal-sell {
        background: linear-gradient(135deg, #f8d7da, #f5c6cb);
        border-left: 4px solid #dc3545;
    }
    .signal-neutral {
        background: linear-gradient(135deg, #fff3cd, #ffeeba);
        border-left: 4px solid #ffc107;
    }
    
    /* Streamlit metrics */
    .stMetric > div {
        background: #f8f9fa;
        padding: 10px;
        border-radius: 8px;
        color: #333;
    }
    .stMetric label {
        color: #555 !important;
    }
    .stMetric [data-testid="stMetricValue"] {
        color: #333 !important;
    }
    
    /* Version badge in sidebar */
    .version-badge-full {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 12px 16px;
        border-radius: 12px;
        margin-bottom: 12px;
        box-shadow: 0 3px 12px rgba(102, 126, 234, 0.35);
        text-align: center;
    }
    .version-badge-full .version-main {
        font-size: 1.3rem;
        font-weight: 700;
        margin-bottom: 8px;
        letter-spacing: 0.5px;
    }
    .version-badge-full .version-details {
        display: flex;
        justify-content: space-around;
        font-size: 0.75rem;
        opacity: 0.95;
        margin-bottom: 6px;
        gap: 8px;
    }
    .version-badge-full .version-details span {
        background: rgba(255,255,255,0.15);
        padding: 2px 8px;
        border-radius: 10px;
    }
    .version-badge-full .version-commit {
        font-size: 0.7rem;
        opacity: 0.7;
        font-family: monospace;
    }
</style>
"""

# Стили для кнопки валидации YTM (зелёная)
VALIDATION_BUTTON_GREEN = """
<style>
    div.stButton > button[kind="primary"] {
        background-color: #28a745 !important;
        border-color: #28a745 !important;
    }
    div.stButton > button[kind="primary"]:hover {
        background-color: #218838 !important;
        border-color: #1e7e34 !important;
    }
</style>
"""

# Стили для кнопки валидации YTM (красная)
VALIDATION_BUTTON_RED = """
<style>
    div.stButton > button[kind="secondary"] {
        background-color: #dc3545 !important;
        border-color: #dc3545 !important;
        color: white !important;
    }
    div.stButton > button[kind="secondary"]:hover {
        background-color: #c82333 !important;
        border-color: #bd2130 !important;
    }
</style>
"""


# ============================================================================
# ФУНКЦИИ ПРИМЕНЕНИЯ СТИЛЕЙ
# ============================================================================

def apply_main_styles():
    """Применить основные стили приложения"""
    st.markdown(MAIN_STYLES, unsafe_allow_html=True)


def apply_validation_button_style(color: str):
    """
    Применить стиль кнопки валидации YTM
    
    Args:
        color: 'green', 'red', или 'normal'
    """
    if color == "green":
        st.markdown(VALIDATION_BUTTON_GREEN, unsafe_allow_html=True)
    elif color == "red":
        st.markdown(VALIDATION_BUTTON_RED, unsafe_allow_html=True)
    # normal — не применяем дополнительные стили


__all__ = [
    'apply_main_styles',
    'apply_validation_button_style',
    'MAIN_STYLES',
    'VALIDATION_BUTTON_GREEN',
    'VALIDATION_BUTTON_RED',
]
