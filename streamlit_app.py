import os
import sys
import time
import threading
import streamlit as st
import streamlit.components.v1 as components

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app as flask_app

# Start Flask server in background thread if not already running
def start_flask():
    try:
        flask_app.run(host="127.0.0.1", port=5001, debug=False, use_reloader=False)
    except Exception as e:
        pass

if "flask_thread_started" not in st.session_state:
    thread = threading.Thread(target=start_flask, daemon=True)
    thread.start()
    st.session_state["flask_thread_started"] = True
    time.sleep(1.2)

# Page Setup: Full Width, No Margins
st.set_page_config(
    page_title="GeoPulse AI — Brand Visibility & GEO Intelligence",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom CSS to hide Streamlit header/footer and expand iframe full screen
st.markdown("""
<style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    [data-testid="stHeader"] {display: none;}
    [data-testid="stSidebar"] {display: none;}
    .block-container {
        padding: 0rem !important;
        margin: 0rem !important;
        max-width: 100% !important;
    }
    iframe {
        width: 100vw !important;
        height: 100vh !important;
        border: none !important;
        overflow: auto;
    }
</style>
""", unsafe_allow_html=True)

# Embed the exact Flask Web App UI from port 5001
components.iframe("http://127.0.0.1:5001", height=950, scrolling=True)
