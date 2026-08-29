# src/dashboard/dashboard_advanced.py
"""
1981 DAEMON Ω V3 — Dashboard Avanzado
Monitor completo con gráficos, métricas DAPS, y control en tiempo real.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import json
import os
import time
from datetime import datetime, timedelta
import numpy as np

# ============================================================================
# CONFIGURACIÓN
# ============================================================================
st.set_page_config(
    page_title="1981 DAEMON Ω V3 — Advanced Dashboard",
    layout="wide",
    page_icon="⚙️",
    initial_sidebar_state="expanded"
)

# CSS personalizado
st.markdown("""
<style>
    .stApp { background-color: #0a0a0a; }
    .main-header { color: #00ff66; font-size: 2.5rem; font-weight: bold; font-family: 'Courier New', monospace; }
    .sub-header { color: #888; font-size: 0.9rem; }
    .metric-card { background: #1a1a1a; padding: 20px; border-radius: 10px; border-left: 4px solid #00ff66; margin: 5px 0; }
    .metric-card.critical { border-left-color: #ff0044; }
    .metric-card.warning { border-left-color: #ffaa00; }
    .metric-value { font-size: 2rem; font-weight: bold; color: #fff; }
    .metric-label { color: #888; font-size: 0.8rem; text-transform: uppercase; }
    .stDataFrame { background-color: #1a1a1a; }
    .stTabs [data-baseweb="tab-list"] { gap: 2px; }
    .stTabs [data-baseweb="tab"] { background-color: #1a1a1a; border-radius: 4px; padding: 8px 16px; }
    .stTabs [aria-selected="true"] { background-color: #00ff66; color: #000; }
    .sidebar .sidebar-content { background-color: #111; }
</style>
""", unsafe_allow_html=True)

# ============================================================================
# FUNCIONES DE CARGA DE DATOS
# ============================================================================

@st.cache_data(ttl=5)
def load_state():
    """Carga el estado del sistema desde archivos."""
    state = {}
    try:
        with open('./data/state/daemon_state.json', 'r') as f:
            state = json.load(f)
    except:
        pass
    return state

@st.cache_data(ttl=10)
def load_metrics():
    """Carga métricas históricas."""
    try:
        with open('./data/metrics/metrics_history.json', 'r') as f:
            return json.load(f)
    except:
        return []

@st.cache_data(ttl=10)
def load_logs(n=100):
    """Carga los últimos N logs."""
    try:
        with open('./data/logs/daemon.log', 'r') as f:
            lines = f.readlines()
            return lines[-n:]
    except:
        return []

@st.cache_data(ttl=5)
def load_certification():
    """Carga el reporte de certificación."""
    try:
        with open('./certification_report.log', 'r') as f:
            return f.read()
    except:
        return "No hay reporte de certificación disponible"

# ============================================================================
# SIDEBAR — PANEL DE CONTROL
# ============================================================================

with st.sidebar:
    st.markdown("### ⚙️ 1981 DAEMON Ω V3")
    st.markdown("---")
    
    state = load_state()
    
    # Estado del sistema
    system_state = state.get('state', 'UNKNOWN')
    state_colors = {
        'LIVE': '🟢',
        'STANDALONE': '🟡',
        'ERROR': '🔴',
        'SHUTDOWN': '⚫',
        'BOOT': '🔵'
    }
    st.markdown(f"**Estado:** {state_colors.get(system_state, '⚪')} {system_state}")
    
    # Emergency Stop
    emergency = state.get('emergency_stop', False)
    if emergency:
        st.error("⛔ EMERGENCY STOP ACTIVO")
    else:
        st.success("✅ Sistema operativo")
    
    # Heartbeat
    last_heartbeat = state.get('last_heartbeat', 'Sin datos')
    st.metric("💓 Último heartbeat", last_heartbeat)
    
    # Versión
    st.caption(f"v3.0.0 — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    
    st.markdown("---")
    
    # Controles
    st.markdown("### 🎮 Controles")
    col1, col2 = st.columns(2)
    if col1.button("🔄 Refresh", use_container_width=True):
        st.rerun()
    if col2.button("⏹️ Stop", use_container_width=True, type="primary"):
        st.warning("Comando STOP enviado")
    
    if st.button("🔴 Emergency Stop", use_container_width=True, type="secondary"):
        st.error("⚠️ EMERGENCY STOP ACTIVADO")
    
    st.markdown("---")
    st.caption("🔒 Modo: DEMO")

# ============================================================================
# MAIN CONTENT — PESTAÑAS
# ============================================================================

st.markdown('<div class="main-header">⚙️ 1981 DAEMON Ω V3</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">Sistema operativo autónomo de ejecución certificable</div>', unsafe_allow_html=True)

# Cargar datos
metrics_history = load_metrics()
logs = load_logs()

# ============================================================================
# TAB 1 — RESUMEN
# ============================================================================

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "📊 Resumen", "📈 Posiciones", "🔄 Órdenes", 
    "📉 Riesgo", "🧠 DAPS", "📋 Logs"
])

with tab1:
    # Métricas principales
    col1, col2, col3, col4 = st.columns(4)
    
    positions = state.get('positions', [])
    orders = state.get('orders', [])
    
    col1.metric("📊 Posiciones abiertas", len(positions))
    col2.metric("🔄 Órdenes activas", len([o for o in orders if o.get('status') in ['PENDING', 'OPEN']]))
    col3.metric("💰 PnL total", f"${state.get('total_pnl', 0):.2f}")
    col4.metric("📈 Win Rate", f"{state.get('win_rate', 0)*100:.1f}%")
    
    # Gráfico de equity (simulado)
    st.subheader("📈 Evolución del Equity")
    
    if metrics_history:
        df = pd.DataFrame(metrics_history)
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df.get('timestamp', []),
            y=df.get('equity', []),
            mode='lines',
            name='Equity',
            line=dict(color='#00ff66', width=2)
        ))
        fig.update_layout(
            plot_bgcolor='#0a0a0a',
            paper_bgcolor='#0a0a0a',
            font_color='#888',
            xaxis=dict(gridcolor='#1a1a1a'),
            yaxis=dict(gridcolor='#1a1a1a'),
            height=300
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No hay datos históricos de equity disponibles")
    
    # Posiciones rápidas
    if positions:
        st.subheader("📊 Resumen de Posiciones")
        pos_df = pd.DataFrame(positions)
        st.dataframe(pos_df[['symbol', 'direction', 'amount', 'entry_price', 'mark_price', 'unrealized_pnl']], 
                     use_container_width=True)

# ============================================================================
# TAB 2 — POSICIONES
# ============================================================================

with tab2:
    st.subheader("📊 Posiciones Activas")
    
    if positions:
        pos_df = pd.DataFrame(positions)
        # Formatear
        if 'unrealized_pnl' in pos_df.columns:
            pos_df['unrealized_pnl'] = pos_df['unrealized_pnl'].apply(lambda x: f"${x:.2f}")
        st.dataframe(pos_df, use_container_width=True)
        
        # KPIs de posiciones
        col1, col2, col3 = st.columns(3)
        col1.metric("Total LONG", len([p for p in positions if p.get('direction') == 'LONG']))
        col2.metric("Total SHORT", len([p for p in positions if p.get('direction') == 'SHORT']))
        total_pnl = sum(p.get('unrealized_pnl', 0) for p in positions)
        col3.metric("PnL no realizado", f"${total_pnl:.2f}", 
                   delta=f"{total_pnl:.2f}" if total_pnl != 0 else None)
    else:
        st.info("📭 No hay posiciones abiertas")

# ============================================================================
# TAB 3 — ÓRDENES
# ============================================================================

with tab3:
    st.subheader("🔄 Órdenes Recientes")
    
    if orders:
        ord_df = pd.DataFrame(orders)
        st.dataframe(ord_df, use_container_width=True)
    else:
        st.info("📭 No hay órdenes registradas")

# ============================================================================
# TAB 4 — RIESGO
# ============================================================================

with tab4:
    st.subheader("📉 Panel de Riesgo")
    
    risk_config = {
        'max_positions': 3,
        'max_exposure': 0.20,
        'max_daily_loss': 0.05,
        'max_drawdown': 0.10
    }
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### 📊 Exposición Actual")
        current_exposure = len(positions) / risk_config['max_positions']
        st.progress(min(current_exposure, 1.0), text=f"{current_exposure*100:.1f}% de {risk_config['max_positions']} posiciones")
        
        st.markdown("#### 📉 Drawdown")
        current_drawdown = state.get('drawdown', 0)
        st.progress(min(current_drawdown / risk_config['max_drawdown'], 1.0), 
                   text=f"{current_drawdown*100:.1f}% / {risk_config['max_drawdown']*100:.1f}%")
    
    with col2:
        st.markdown("#### 💰 Pérdida Diaria")
        daily_loss = state.get('daily_loss', 0)
        st.progress(min(abs(daily_loss) / risk_config['max_daily_loss'], 1.0),
                   text=f"${daily_loss:.2f} / ${risk_config['max_daily_loss']:.2f}")
        
        st.markdown("#### 🛡️ Emergency Stop")
        if emergency:
            st.error("🔴 ACTIVADO")
        else:
            st.success("🟢 DESACTIVADO")

# ============================================================================
# TAB 5 — DAPS
# ============================================================================

with tab5:
    st.subheader("🧠 DAPS — Detección de Anomalías")
    
    daps_score = state.get('daps_score', 0)
    
    # Medidor de score
    col1, col2 = st.columns([1, 2])
    with col1:
        if daps_score >= 80:
            st.success(f"### {daps_score:.1f}%")
            st.caption("🟢 EXCELENTE")
        elif daps_score >= 60:
            st.warning(f"### {daps_score:.1f}%")
            st.caption("🟡 NORMAL")
        elif daps_score >= 40:
            st.error(f"### {daps_score:.1f}%")
            st.caption("🟠 WARNING")
        else:
            st.error(f"### {daps_score:.1f}%")
            st.caption("🔴 CRÍTICO")
    
    with col2:
        # Componentes DAPS
        components = state.get('daps_components', {})
        if components:
            st.markdown("#### Dimensiones")
            for name, value in components.items():
                st.progress(value/100, text=f"{name}: {value:.1f}%")
        else:
            st.info("No hay datos DAPS disponibles")

# ============================================================================
# TAB 6 — LOGS
# ============================================================================

with tab6:
    st.subheader("📋 Consola de Logs")
    
    # Filtros
    col1, col2 = st.columns(2)
    with col1:
        log_level = st.selectbox("Nivel", ["ALL", "INFO", "WARNING", "ERROR", "DEBUG"])
    with col2:
        log_lines = st.slider("Líneas", 10, 200, 50)
    
    # Mostrar logs
    if logs:
        filtered = logs
        if log_level != "ALL":
            filtered = [l for l in logs if log_level in l]
        st.code(''.join(filtered[-log_lines:]), language='log')
    else:
        st.info("No hay logs disponibles")

# ============================================================================
# AUTO-REFRESH
# ============================================================================

st.divider()
st.caption(f"🔄 Última actualización: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} — Auto-refresh cada 10s")

# Auto-refresh con JavaScript
st.markdown("""
<script>
    setTimeout(function() {
        window.location.reload();
    }, 10000);
</script>
""", unsafe_allow_html=True)
