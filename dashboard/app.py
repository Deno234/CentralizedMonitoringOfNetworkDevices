import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import time
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from datetime import datetime, timedelta
from dashboard.utils import api_get
from anomaly.anomaly_detector import AnomalyDetector, get_all_anomalies

st.set_page_config(page_title="Network Monitoring Dashboard", layout="wide", page_icon="📡")

# Custom CSS for better styling
st.markdown("""
    <style>
    .metric-card {
        background-color: #f0f2f6;
        padding: 20px;
        border-radius: 10px;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.1);
    }
    .anomaly-alert {
        background-color: #ffebee;
        border-left: 5px solid #f44336;
        padding: 10px;
        margin: 10px 0;
        border-radius: 5px;
    }
    .anomaly-warning {
        background-color: #fff3e0;
        border-left: 5px solid #ff9800;
        padding: 10px;
        margin: 10px 0;
        border-radius: 5px;
    }
    </style>
""", unsafe_allow_html=True)

st.title("📡 Network Monitoring Dashboard")

# Sidebar configuration
with st.sidebar:
    st.header("⚙️ Configuration")

    # Auto refresh
    st_autorefresh = st.checkbox("Auto-refresh", value=True)
    refresh_interval = st.slider("Refresh interval (seconds)", 5, 60, 60)

    st.divider()

    # Anomaly detection settings
    st.subheader("🔍 Anomaly Detection")
    enable_anomaly_detection = st.checkbox("Enable Anomaly Detection", value=True)
    detection_method = st.multiselect(
        "Detection Methods",
        ["z_score", "moving_average", "isolation_forest", "lof"],
        default=["z_score", "moving_average"]
    )

    st.divider()

    # Time range for historical data
    st.subheader("📅 Time Range")
    time_range = st.selectbox(
        "Historical data range",
        ["Last Hour", "Last 6 Hours", "Last 24 Hours", "Last 7 Days"],
        index=2
    )

# Session state for refresh timing
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

# REMOVED GLOBAL DETECTOR - This was the bug!
# Each device analysis should create its own detector

# ---------- SUMMARY METRICS ----------
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Total Devices", len(devices))

with col2:
    # Check if device was seen recently (within last 2 minutes)
    online_devices = 0
    for d in devices:
        if d.get('last_seen'):
            try:
                last_seen_time = datetime.fromisoformat(d['last_seen'])
                if datetime.now() - last_seen_time < timedelta(minutes=2):
                    online_devices += 1
            except:
                pass
    st.metric("Online Devices", online_devices)

with col3:
    offline_devices = len(devices) - online_devices
    st.metric("Offline Devices", offline_devices)

with col4:
    if enable_anomaly_detection and devices:
        total_anomalies = 0
        for device in devices:
            anomalies = get_all_anomalies(limit=50, device_id=device['id'])
            # Count anomalies from last hour
            recent_anomalies = [
                a for a in anomalies
                if datetime.fromisoformat(a['timestamp']) > datetime.now() - timedelta(hours=1)
            ]
            total_anomalies += len(recent_anomalies)
        st.metric("Anomalies (1h)", total_anomalies, delta=None if total_anomalies == 0 else "⚠️")
    else:
        st.metric("Anomalies", "N/A")

st.divider()

# ---------- ANOMALY ALERTS (if any recent) ----------
if enable_anomaly_detection:
    st.header("🚨 Recent Anomaly Alerts")

    recent_anomalies_all = []
    for device in devices:
        anomalies = get_all_anomalies(limit=10, device_id=device['id'])
        for anomaly in anomalies:
            try:
                if datetime.fromisoformat(anomaly['timestamp']) > datetime.now() - timedelta(hours=1):
                    anomaly['device_name'] = device['name']
                    recent_anomalies_all.append(anomaly)
            except:
                pass

    if recent_anomalies_all:
        for anomaly in sorted(recent_anomalies_all, key=lambda x: x['timestamp'], reverse=True)[:5]:
            severity_class = "anomaly-alert" if anomaly['severity'] == 'high' else "anomaly-warning"
            st.markdown(f"""
                <div class="{severity_class}">
                    <strong>🔴 {anomaly['device_name']}</strong> - {anomaly['detection_method']} 
                    ({anomaly['severity'].upper()})
                    <br>
                    <small>{anomaly['timestamp']}</small>
                </div>
            """, unsafe_allow_html=True)
    else:
        st.success("✅ No anomalies detected in the last hour")

    st.divider()

# ---------- DEVICES TABLE ----------
st.header("🖥️ Devices Overview")


def status_icon(last_seen):
    """Check device online status"""
    if last_seen is None:
        return "⚪ Unknown"

    try:
        last_seen_time = datetime.fromisoformat(last_seen)
        time_diff = datetime.now() - last_seen_time

        if time_diff < timedelta(minutes=2):
            return "🟢 Online"
        elif time_diff < timedelta(minutes=10):
            return "🟡 Recently Online"
        else:
            return "🔴 Offline"
    except:
        return "⚪ Unknown"


def format_last_seen(last_seen):
    """Format last seen time in a human-readable way"""
    if last_seen is None:
        return "Never"

    try:
        last_seen_time = datetime.fromisoformat(last_seen)
        time_diff = datetime.now() - last_seen_time

        if time_diff < timedelta(minutes=1):
            return "Just now"
        elif time_diff < timedelta(hours=1):
            minutes = int(time_diff.total_seconds() / 60)
            return f"{minutes} min ago"
        elif time_diff < timedelta(days=1):
            hours = int(time_diff.total_seconds() / 3600)
            return f"{hours} hour{'s' if hours > 1 else ''} ago"
        else:
            return last_seen_time.strftime("%Y-%m-%d %H:%M:%S")
    except:
        return last_seen or "Never"


device_rows = []
for d in devices:
    device_rows.append({
        "ID": d["id"],
        "Name": d["name"],
        "MAC": d["mac"],
        "Last IP": d["last_ip"] or "N/A",
        "Last Seen": format_last_seen(d["last_seen"]),
        "Status": status_icon(d["last_seen"])
    })

df_devices = pd.DataFrame(device_rows)
st.dataframe(df_devices, use_container_width=True, hide_index=True)

st.divider()

# ---------- DEVICE SELECTION FOR DETAILED VIEW ----------
if devices:
    st.header("📊 Device Details & Metrics")

    device_names = {d['id']: f"{d['name']} (ID: {d['id']})" for d in devices}
    selected_device_id = st.selectbox(
        "Select device for detailed view:",
        options=list(device_names.keys()),
        format_func=lambda x: device_names[x]
    )

    # Get device data
    selected_device = next(d for d in devices if d['id'] == selected_device_id)

    # Device info
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.write("**Device Name:**", selected_device['name'])
    with col2:
        st.write("**MAC Address:**", selected_device['mac'])
    with col3:
        st.write("**Last IP:**", selected_device['last_ip'] or "N/A")
    with col4:
        st.write("**Status:**", status_icon(selected_device['last_seen']))

    # ---------- ANOMALY DETECTION FOR SELECTED DEVICE ----------
    if enable_anomaly_detection:
        st.subheader("🔍 Anomaly Detection Results")

        with st.spinner("Analyzing device metrics for anomalies..."):
            try:
                # FIXED: Create fresh detector instance for THIS device
                detector = AnomalyDetector(contamination=0.1)
                anomaly_summary = detector.get_anomaly_summary(selected_device_id)

                if anomaly_summary['total_anomalies'] > 0:
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Total Anomalies", anomaly_summary['total_anomalies'])
                    with col2:
                        st.metric("High Severity", anomaly_summary['high_severity_count'])
                    with col3:
                        st.metric("Medium Severity", anomaly_summary['medium_severity_count'])

                    # Show anomalies by method
                    st.write("**Anomalies by Detection Method:**")
                    methods_df = pd.DataFrame([
                        {"Method": method.replace('_', ' ').title(), "Count": count}
                        for method, count in anomaly_summary['by_method'].items()
                        if count > 0
                    ])
                    if not methods_df.empty:
                        st.dataframe(methods_df, hide_index=True)

                    # Detailed anomaly view
                    with st.expander("View Detailed Anomalies"):
                        for method, anomalies in anomaly_summary['detailed_anomalies'].items():
                            if anomalies and method in detection_method:
                                st.write(f"**{method.replace('_', ' ').title()}:**")
                                for anomaly in anomalies[:5]:  # Show first 5
                                    st.json(anomaly)
                else:
                    st.success("✅ No anomalies detected for this device")
            except Exception as e:
                st.warning(f"⚠️ Could not analyze anomalies: {str(e)}")

    st.divider()

    # ---------- METRICS VISUALIZATION ----------
    # Filter metrics by device_id
    device_metrics = [m for m in metrics_logs if m['device_id'] == selected_device_id]

    if device_metrics:
        st.subheader(f"📈 System Metrics ({len(device_metrics)} records)")

        df_metrics = pd.DataFrame(device_metrics)
        df_metrics['timestamp'] = pd.to_datetime(df_metrics['timestamp'])
        df_metrics = df_metrics.sort_values('timestamp')

        # Display data range
        st.caption(f"Data from {df_metrics['timestamp'].min()} to {df_metrics['timestamp'].max()}")

        # CPU and RAM side by side
        col1, col2 = st.columns(2)

        with col1:
            fig_cpu = px.line(df_metrics, x='timestamp', y='cpu',
                              title=f'CPU Usage (%) - {selected_device["name"]}',
                              labels={'cpu': 'CPU %', 'timestamp': 'Time'})
            fig_cpu.add_hline(y=80, line_dash="dash", line_color="orange",
                              annotation_text="Warning (80%)")
            fig_cpu.add_hline(y=95, line_dash="dash", line_color="red",
                              annotation_text="Critical (95%)")
            st.plotly_chart(fig_cpu, use_container_width=True)

        with col2:
            fig_ram = px.line(df_metrics, x='timestamp', y='ram',
                              title=f'RAM Usage (%) - {selected_device["name"]}',
                              labels={'ram': 'RAM %', 'timestamp': 'Time'})
            fig_ram.add_hline(y=80, line_dash="dash", line_color="orange",
                              annotation_text="Warning (80%)")
            fig_ram.add_hline(y=95, line_dash="dash", line_color="red",
                              annotation_text="Critical (95%)")
            st.plotly_chart(fig_ram, use_container_width=True)

        # Disk usage
        fig_disk = px.line(df_metrics, x='timestamp', y='disk',
                           title=f'Disk Usage (%) - {selected_device["name"]}',
                           labels={'disk': 'Disk %', 'timestamp': 'Time'})
        fig_disk.add_hline(y=80, line_dash="dash", line_color="orange",
                           annotation_text="Warning (80%)")
        fig_disk.add_hline(y=95, line_dash="dash", line_color="red",
                           annotation_text="Critical (95%)")
        st.plotly_chart(fig_disk, use_container_width=True)

        # Network traffic (now showing bytes/sec rate)
        fig_network = go.Figure()
        fig_network.add_trace(go.Scatter(
            x=df_metrics['timestamp'],
            y=df_metrics['net_sent'],
            mode='lines',
            name='Upload',
            line=dict(color='blue')
        ))
        fig_network.add_trace(go.Scatter(
            x=df_metrics['timestamp'],
            y=df_metrics['net_recv'],
            mode='lines',
            name='Download',
            line=dict(color='green')
        ))
        fig_network.update_layout(
            title=f'Network Traffic Rate (bytes/sec) - {selected_device["name"]}',
            xaxis_title='Time',
            yaxis_title='Bytes/Second'
        )
        st.plotly_chart(fig_network, use_container_width=True)

    else:
        st.info(
            f"ℹ️ No metrics data available for {selected_device['name']} yet. "
            f"Make sure the agent is running on this device."
        )
        st.write("**Debugging Info:**")
        st.write(f"- Selected Device ID: {selected_device_id}")
        st.write(f"- Selected Device MAC: {selected_device['mac']}")

        # Show all device IDs that have metrics
        if metrics_logs:
            unique_device_ids = set(m['device_id'] for m in metrics_logs)
            st.write(f"- Device IDs with metrics: {unique_device_ids}")

            # Show device MAC addresses for comparison
            st.write("**All devices in database:**")
            for dev in devices:
                has_metrics = dev['id'] in unique_device_ids
                status_emoji = "✅" if has_metrics else "❌"
                st.write(f"  {status_emoji} ID {dev['id']}: {dev['name']} ({dev['mac']})")
        else:
            st.write("- No metrics in database at all")

st.divider()

# ---------- PING LOGS ----------
st.header("📶 Connection Logs")

if ping_logs:
    df_ping = pd.DataFrame(ping_logs)
    df_ping['timestamp'] = pd.to_datetime(df_ping['timestamp'])

    # Add device names
    device_id_to_name = {d['id']: d['name'] for d in devices}
    df_ping['device_name'] = df_ping['device_id'].map(device_id_to_name)

    # Status mapping
    df_ping['status_text'] = df_ping['status'].map({1: '🟢 Online', 0: '🔴 Offline'})

    # Show recent logs
    st.dataframe(
        df_ping[['timestamp', 'device_name', 'ip', 'status_text', 'latency_ms']]
        .head(50)
        .rename(columns={
            'timestamp': 'Time',
            'device_name': 'Device',
            'ip': 'IP Address',
            'status_text': 'Status',
            'latency_ms': 'Latency (ms)'
        }),
        use_container_width=True,
        hide_index=True
    )

    # Connection timeline
    st.subheader("Connection Timeline")
    fig_timeline = px.scatter(df_ping.head(100), x='timestamp', y='device_name',
                              color='status_text',
                              color_discrete_map={'🟢 Online': 'green', '🔴 Offline': 'red'},
                              title='Device Connection Status Over Time')
    st.plotly_chart(fig_timeline, use_container_width=True)
else:
    st.info("No ping logs available yet")

# Footer with refresh info
st.divider()
if st_autorefresh:
    time_until_refresh = refresh_interval - (time.time() - st.session_state.last_refresh)
    st.caption(f"🔄 Auto-refresh enabled | Next refresh in: {int(time_until_refresh)}s")
else:
    st.caption("🔄 Auto-refresh disabled")

# Debug info
with st.expander("🔧 Debug Information"):
    st.write("**Database Contents:**")
    st.write(f"- Total devices: {len(devices)}")
    st.write(f"- Total ping logs: {len(ping_logs)}")
    st.write(f"- Total metrics logs: {len(metrics_logs)}")

    if devices:
        st.write("\n**Device Details:**")
        for d in devices:
            metric_count = len([m for m in metrics_logs if m['device_id'] == d['id']])
            st.write(f"- ID {d['id']}: {d['name']} | MAC: {d['mac']} | Metrics: {metric_count}")