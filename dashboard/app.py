import streamlit as st
import pandas as pd
import time
from utils import api_get

st.set_page_config(page_title="Network Monitoring Dashboard", layout="wide")

st.title("📡 Network Monitoring Dashboard")

# Auto refresh every 5s
st_autorefresh = st.sidebar.checkbox("Auto-refresh", value=True)
refresh_interval = 5 # seconds

# Use session state to track last refresh time
if 'last_refresh' not in st.session_state:
    st.session_state.last_refresh = time.time()

# Check if it's time to refresh
if st_autorefresh:
    current_time = time.time()
    if current_time - st.session_state.last_refresh >= refresh_interval:
        st.session_state.last_refresh = current_time
        st.rerun()


# ---------- LOAD DATA FROM API ----------

devices = api_get("/api/devices") or []
ping_logs = api_get("/api/ping_logs") or []
metrics_logs = api_get("/api/metrics_logs") or []


# ---------- DEVICES TABLE ----------
st.header("🖥️ Devices Overview")

def status_icon(last_seen):
    if last_seen is None:
        return "⚪ Unknown"
    return "🟢 Online"

device_rows = []
for d in devices:
    device_rows.append({
        "Name": d["name"],
        "MAC": d["mac"],
        "Last IP": d["last_ip"],
        "Last Seen": d["last_seen"],
        "Status": status_icon(d["last_seen"])
    })

df_devices = pd.DataFrame(device_rows)
st.dataframe(df_devices, use_container_width=True)


# ---------- METRICS SECTION ----------
st.header("📊 System Metrics Logs")

if metrics_logs:
    df_metrics = pd.DataFrame(metrics_logs)
    device_mac_list = df_metrics["device_id"].unique()

    selected_device = st.selectbox("Select device ID:", device_mac_list)

    df_sel = df_metrics[df_metrics["device_id"] == selected_device]

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("CPU Usage (%)")
        st.line_chart(df_sel[["timestamp", "cpu"]], x="timestamp", y="cpu")

    with col2:
        st.subheader("RAM Usage (%)")
        st.line_chart(df_sel[["timestamp", "ram"]], x="timestamp", y="ram")

    st.subheader("Disk Usage (%)")
    st.line_chart(df_sel[["timestamp", "disk"]], x="timestamp", y="disk")

    st.subheader("Network Usage (bytes)")
    st.line_chart(df_sel[["timestamp", "net_sent", "net_recv"]], x="timestamp")


# ---------- PING LOGS ----------
st.header("📶 Ping Logs")

if ping_logs:
    df_ping = pd.DataFrame(ping_logs)
    st.dataframe(df_ping, use_container_width=True)

# Display next refresh countdown if auto-refresh is enabled
if st_autorefresh:
    time_until_refresh = refresh_interval - (time.time() - st.session_state.last_refresh)
    st.sidebar.text(f"Next refresh in: {int(time_until_refresh)}s")