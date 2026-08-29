# src/dashboard/dashboard_simple.py
"""
1981 DAEMON Ω V3 — Dashboard Simple (Consola)
Monitor básico con actualización manual.
"""

import streamlit as st
import json
import os
from datetime import datetime

st.set_page_config(page_title="1981 DAEMON Ω", layout="wide", page_icon="⚙️")

# CSS oscuro minimalista
st.markdown("""
<style>
    .stApp { background-color: #0a0a0a; }
    .metric-card { background: #1a1a1a; padding: 15px; border-radius: 8px; border-left: 3px solid #00ff66; }
    .critical { border-left-color: #ff0044; }
    .warning { border-left-color: #ffaa00; }
    h1, h2, h3 { color: #00ff66; font-family: 'Courier New', monospace; }
    .stDataFrame { background-color: #1a1a1a; }
</style>
""", unsafe_allow_html=True)

st.title("⚙️ 1981 DAEMON Ω V3")
st.caption(f"📟 Estado del sistema — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# Cargar estado
def load_state():
    try:
        with open('./data/state/daemon_state.json', 'r') as f:
            return json.load(f)
    except:
        return {}

state = load_state()

# Métricas principales
col1, col2, col3, col4 = st.columns(4)
col1.metric("💓 Heartbeat", state.get('last_heartbeat', '⏳ Sin datos'))
col2.metric("📊 Posiciones", len(state.get('positions', [])))
col3.metric("🔄 Órdenes", len(state.get('orders', [])))
col4.metric("📟 Estado", state.get('state', 'BOOT'))

# Posiciones
st.subheader("📊 Posiciones Activas")
if state.get('positions'):
    st.dataframe(state['positions'], use_container_width=True)
else:
    st.info("No hay posiciones abiertas")

# Logs recientes
st.subheader("📋 Últimos Logs")
try:
    with open('./data/logs/daemon.log', 'r') as f:
        lines = f.readlines()[-15:]
    st.code(''.join(lines), language='log')
except:
    st.warning("Logs no disponibles")

# Controles
st.divider()
col1, col2, col3 = st.columns(3)
if col1.button("🔄 Refrescar"):
    st.rerun()
if col2.button("⏹️ Emergency Stop"):
    st.error("⚠️ EMERGENCY STOP ACTIVADO")
if col3.button("▶️ Reanudar"):
    st.success("✅ Sistema reanudado")

st.caption("🔄 Auto-refresh cada 10 segundos")
st.rerun()
