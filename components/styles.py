"""
CSS стили для приложения

Централизованные стили для OFZ Spread Analytics.
"""

CSS_STYLES = """
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        margin-bottom: 1rem;
    }
    .metric-card {
        background: #f8f9fa;
        padding: 15px;
        border-radius: 10px;
        border-left: 4px solid #1f77b4;
    }
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
    .mode-badge {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 15px;
        font-size: 0.85em;
        font-weight: bold;
        margin-left: 10px;
    }
    .mode-daily {
        background: #3498db;
        color: white;
    }
    .mode-intraday {
        background: #e74c3c;
        color: white;
    }
</style>
"""


def apply_styles():
    """Применяет CSS стили к приложению"""
    import streamlit as st
    st.markdown(CSS_STYLES, unsafe_allow_html=True)
