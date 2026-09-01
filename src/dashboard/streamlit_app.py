"""
Streamlit Dashboard — Panel de control para el daemon
"""
import streamlit as st
import yaml
import requests
import json
from pathlib import Path
from datetime import datetime

st.set_page_config(page_title="1981 DAEMON Ω V4", layout="wide")

TIERS_CONFIG = "./config/tiers.yaml"
LOGS_FILE = "./data/logs/daemon.log"
API_BASE = "http://localhost:8000/api/daemon"

def load_tiers():
    try:
        with open(TIERS_CONFIG, 'r') as f:
            data = yaml.safe_load(f) or {}
        return data.get('signals', {}).get('allowed_tiers', ['S-TIER', 'A-TIER'])
    except:
        return ['S-TIER', 'A-TIER']

def save_tiers(tiers):
    data = {'signals': {'allowed_tiers': tiers, 'updated_at': datetime.now().isoformat()}}
    Path(TIERS_CONFIG).parent.mkdir(parents=True, exist_ok=True)
    with open(TIERS_CONFIG, 'w') as f:
        yaml.dump(data, f, default_flow_style=False)
    try:
        requests.post(f"{API_BASE}/config/tiers", json={"tiers": tiers}, timeout=1)
    except:
        pass

def get_daemon_status():
    try:
        r = requests.get(f"{API_BASE}/status", timeout=2)
        return r.json() if r.status_code == 200 else {}
    except:
        return {}

def get_logs(n=20):
    if Path(LOGS_FILE).exists():
        with open(LOGS_FILE, 'r') as f:
            lines = f.readlines()
            return ''.join(lines[-n:])
    return "No hay logs."

with st.sidebar:
    st.title("🎮 Control Center")
    status = get_daemon_status()
    if status:
        st.success(f"🟢 Estado: {status.get('state', 'N/A')}")
        st.metric("Exchange", status.get('exchange', 'N/A'))
        st.metric("Heartbeat", status.get('last_heartbeat', 'N/A')[:19] if status.get('last_heartbeat') else 'N/A')
        st.metric("Posiciones", status.get('open_positions', 0))
    else:
        st.warning("⚠️ Daemon no disponible")

    st.markdown("---")
    st.subheader("🎯 Filtrar Señales")
    current = load_tiers()
    selected = st.multiselect("Tiers permitidos", ["S-TIER", "A-TIER", "B-TIER"], default=current)
    if selected != current:
        save_tiers(selected)
        st.success("✅ Guardado")

    st.markdown("---")
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("🚀 START", type="primary", use_container_width=True):
            try:
                requests.post(f"{API_BASE}/start", timeout=2)
                st.success("Iniciado")
            except:
                st.error("Error")
    with col2:
        if st.button("⛔ STOP", use_container_width=True):
            try:
                requests.post(f"{API_BASE}/stop", timeout=2)
                st.warning("Detenido")
            except:
                st.error("Error")
    with col3:
        if st.button("🔄 RESTART", use_container_width=True):
            try:
                requests.post(f"{API_BASE}/restart", timeout=2)
                st.info("Reiniciando...")
            except:
                st.error("Error")

st.title("⚙️ 1981 DAEMON Ω V4 — Dashboard")
col1, col2, col3 = st.columns(3)
col1.metric("Estado", status.get('state', 'SLEEPING') if status else 'N/A')
col2.metric("Tiers activos", ", ".join(selected))
col3.metric("Último heartbeat", status.get('last_heartbeat', 'N/A')[:19] if status and status.get('last_heartbeat') else 'N/A')

st.markdown("---")
st.subheader("📜 Logs (últimas 20 líneas)")
st.code(get_logs(), language='log')
st.caption("1981 DAEMON Ω V4 — Event-Driven Execution Engine")
