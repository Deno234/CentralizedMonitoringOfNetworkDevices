"""
Network Monitoring Dashboard
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import time
import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from datetime import datetime, timedelta
from dashboard.utils import api_get
from anomaly.anomaly_detector import AnomalyDetector, get_all_anomalies

# ==================== PAGE CONFIGURATION ====================
st.set_page_config(
    page_title="Network Monitoring Dashboard",
    layout="wide",
    page_icon="📡",
    initial_sidebar_state="expanded"
)

# ==================== CUSTOM CSS ====================

st.markdown("""
    <style>
    /* Better metric cards */
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 20px;
        border-radius: 10px;
        color: white;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }

    /* Anomaly alerts */
    .anomaly-alert {
        background-color: #ffebee;
        border-left: 5px solid #f44336;
        padding: 15px;
        margin: 10px 0;
        border-radius: 5px;
        animation: pulse 2s infinite;
    }

    .anomaly-warning {
        background-color: #fff3e0;
        border-left: 5px solid #ff9800;
        padding: 15px;
        margin: 10px 0;
        border-radius: 5px;
    }

    @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.8; }
    }

    /* Better table styling */
    .dataframe {
        font-size: 14px;
    }

    /* Status badges */
    .status-online {
        background-color: #4caf50;
        color: white;
        padding: 4px 12px;
        border-radius: 12px;
        font-weight: bold;
    }

    .status-offline {
        background-color: #f44336;
        color: white;
        padding: 4px 12px;
        border-radius: 12px;
        font-weight: bold;
    }
    </style>
""", unsafe_allow_html=True)


# ==================== HELPER FUNCTIONS ====================

def safe_api_call(endpoint, default=None):
    """Safely call API with error handling"""
    try:
        result = api_get(endpoint)
        return result if result is not None else (default or [])
    except Exception as e:
        st.error(f"API Error: {endpoint} - {str(e)}")
        return default or []


def status_icon(last_seen):
    """Get device online status with icon"""
    if last_seen is None:
        return "⚪ Unknown", "unknown"

    try:
        last_seen_time = datetime.fromisoformat(last_seen)
        time_diff = datetime.now() - last_seen_time

        if time_diff < timedelta(minutes=2):
            return "🟢 Online", "online"
        elif time_diff < timedelta(minutes=10):
            return "🟡 Recently Online", "recent"
        else:
            return "🔴 Offline", "offline"
    except:
        return "⚪ Unknown", "unknown"


def format_last_seen(last_seen):
    """Format last seen time in human-readable format"""
    if last_seen is None:
        return "Never"

    try:
        last_seen_time = datetime.fromisoformat(last_seen)
        time_diff = datetime.now() - last_seen_time

        if time_diff < timedelta(seconds=30):
            return "Just now"
        elif time_diff < timedelta(minutes=1):
            return f"{int(time_diff.total_seconds())}s ago"
        elif time_diff < timedelta(hours=1):
            minutes = int(time_diff.total_seconds() / 60)
            return f"{minutes}m ago"
        elif time_diff < timedelta(days=1):
            hours = int(time_diff.total_seconds() / 3600)
            return f"{hours}h ago"
        else:
            days = int(time_diff.days)
            return f"{days}d ago"
    except:
        return last_seen or "Never"


def format_bytes(bytes_val):
    """Format bytes to human-readable format"""
    if bytes_val < 1024:
        return f"{bytes_val:.1f} B/s"
    elif bytes_val < 1024 * 1024:
        return f"{bytes_val / 1024:.1f} KB/s"
    elif bytes_val < 1024 * 1024 * 1024:
        return f"{bytes_val / (1024 * 1024):.1f} MB/s"
    else:
        return f"{bytes_val / (1024 * 1024 * 1024):.2f} GB/s"


def create_percentage_chart(df, column, title, device_name):
    """Create a percentage chart with proper 0-100% Y-axis"""
    fig = px.line(
        df,
        x='timestamp',
        y=column,
        title=title,
        labels={column: f'{column.upper()} %', 'timestamp': 'Time'}
    )

    # Set Y-axis range to 0-100%
    fig.update_yaxes(range=[0, 100])

    # Add threshold lines
    fig.add_hline(
        y=80,
        line_dash="dash",
        line_color="orange",
        annotation_text="Warning (80%)",
        annotation_position="right"
    )
    fig.add_hline(
        y=95,
        line_dash="dash",
        line_color="red",
        annotation_text="Critical (95%)",
        annotation_position="right"
    )

    # Better styling
    fig.update_layout(
        hovermode='x unified',
        showlegend=False,
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
    )

    return fig


# ==================== HEADER ====================
st.title("📡 Network Monitoring Dashboard")
st.caption("Real-time monitoring of network devices and system metrics")

# ==================== SIDEBAR CONFIGURATION ====================
with st.sidebar:
    st.header("⚙️ Settings")

    # Auto refresh
    st.subheader("🔄 Auto-Refresh")
    st_autorefresh = st.checkbox("Enable auto-refresh", value=True)

    if st_autorefresh:
        refresh_interval = st.slider(
            "Refresh interval (seconds)",
            min_value=5,
            max_value=300,
            value=30,
            step=5
        )
    else:
        refresh_interval = 60

    # Manual refresh button
    if st.button("🔄 Refresh Now", use_container_width=True):
        st.rerun()

    st.divider()

    # Anomaly detection settings
    st.subheader("🔍 Anomaly Detection")
    enable_anomaly_detection = st.checkbox("Enable anomaly detection", value=True)

    if enable_anomaly_detection:
        detection_method = st.multiselect(
            "Detection methods",
            ["z_score", "moving_average", "isolation_forest", "lof"],
            default=["z_score", "moving_average"],
            help="Select which anomaly detection algorithms to use"
        )
    else:
        detection_method = []

    st.divider()

    # Time range filter
    st.subheader("📅 Data Range")
    time_range_hours = st.select_slider(
        "Show data from last:",
        options=[1, 6, 12, 24, 48, 72, 168],  # hours
        value=24,
        format_func=lambda x: f"{x}h" if x < 24 else f"{x // 24}d"
    )

    st.divider()

    # API Status
    st.subheader("🔌 API Status")
    try:
        health = api_get("/api/health")
        if health:
            st.success("✅ Connected")
        else:
            st.error("❌ Disconnected")
    except:
        st.error("❌ API Unavailable")

# ==================== SESSION STATE ====================
if 'last_refresh' not in st.session_state:
    st.session_state.last_refresh = time.time()

# Auto-refresh logic
if st_autorefresh:
    current_time = time.time()
    if current_time - st.session_state.last_refresh >= refresh_interval:
        st.session_state.last_refresh = current_time
        st.rerun()

# ==================== LOAD DATA ====================
with st.spinner("Loading data..."):
    devices = safe_api_call("/api/devices", [])
    ping_logs = safe_api_call("/api/ping_logs?limit=500", [])
    metrics_logs = safe_api_call("/api/metrics_logs?limit=1000", [])

# ==================== SUMMARY METRICS ====================
st.header("📊 Overview")

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        "Total Devices",
        len(devices),
        help="Total number of devices registered in the system"
    )

with col2:
    online_count = sum(
        1 for d in devices
        if d.get('last_seen') and
        datetime.now() - datetime.fromisoformat(d['last_seen']) < timedelta(minutes=2)
    )
    st.metric(
        "Online Now",
        online_count,
        delta=f"{online_count}/{len(devices)}",
        delta_color="normal" if online_count > 0 else "off"
    )

with col3:
    offline_count = len(devices) - online_count
    st.metric(
        "Offline",
        offline_count,
        delta=f"-{offline_count}" if offline_count > 0 else "0",
        delta_color="inverse"
    )

with col4:
    if enable_anomaly_detection and devices:
        try:
            total_anomalies = 0
            for device in devices:
                anomalies = get_all_anomalies(limit=100, device_id=device['id'])
                recent = [
                    a for a in anomalies
                    if datetime.fromisoformat(a['timestamp']) > datetime.now() - timedelta(hours=1)
                ]
                total_anomalies += len(recent)

            st.metric(
                "Anomalies (1h)",
                total_anomalies,
                delta="⚠️" if total_anomalies > 0 else "✅",
                delta_color="inverse" if total_anomalies > 0 else "normal"
            )
        except Exception as e:
            st.metric("Anomalies", "Error", delta="⚠️")
    else:
        st.metric("Anomalies", "Disabled")

st.divider()

# ==================== ANOMALY ALERTS ====================
if enable_anomaly_detection and devices:
    st.header("🚨 Recent Anomaly Alerts")

    try:
        all_recent_anomalies = []
        for device in devices:
            anomalies = get_all_anomalies(limit=20, device_id=device['id'])
            for anomaly in anomalies:
                try:
                    anomaly_time = datetime.fromisoformat(anomaly['timestamp'])
                    if anomaly_time > datetime.now() - timedelta(hours=1):
                        anomaly['device_name'] = device['name']
                        all_recent_anomalies.append(anomaly)
                except:
                    pass

        # ==================== POBOLJŠANI ANOMALY ALERTS ====================
        if all_recent_anomalies:
            all_recent_anomalies.sort(key=lambda x: x['timestamp'], reverse=True)

            for anomaly in all_recent_anomalies[:5]:

                severity_class = "anomaly-alert" if anomaly['severity'] == 'high' else "anomaly-warning"
                emoji = "🔴" if anomaly['severity'] == 'high' else "🟡"

                # LOGIKA ZA IZVLAČENJE NAZIVA RESURSA (CPU, RAM, itd.)
                resource_display = "UNKNOWN"

                details_raw = anomaly.get("details")
                data = None

                if isinstance(details_raw, str):
                    try:
                        data = json.loads(details_raw)
                    except Exception:
                        data = None

                if not isinstance(data, dict):
                    data = anomaly


                # 1. Provjera liste 'anomalous_metrics' (Z-score i Moving Average)
                if "anomalous_metrics" in data and data["anomalous_metrics"]:
                    # Uzimamo naziv prve anomalije u listi i njenu vrijednost
                    first_metric = data["anomalous_metrics"][0]
                    m_name = first_metric.get("metric", "Unknown").upper()
                    m_val = first_metric.get("value", 0)
                    resource_display = f"{m_name} ({m_val:.1f}%)"

                # 2. Provjera 'metrics_snapshot' (za Isolation Forest i LOF)
                elif "metrics_snapshot" in data:
                    resource_display = "ML ANALYSIS"

                # 3. Fallback na stare ključeve
                else:
                    resource_display = (
                        data.get("metric") or
                        data.get("resource") or
                        "UNKNOWN"
                    ).upper()

                st.markdown(f"""
                    <div class="{severity_class}">
                        <strong>{emoji} {anomaly['device_name']}</strong> - 
                        <span style="color: #d32f2f; font-weight: bold;">{resource_display}</span> 
                        via {anomaly['detection_method'].replace('_', ' ').title()}
                        <span style="float: right; font-weight: bold; border: 1px solid; padding: 0 5px; border-radius: 3px;">
                            {anomaly['severity'].upper()}
                        </span>
                        <br>
                        <small>🕐 {format_last_seen(anomaly['timestamp'])}</small>
                    </div>
                """, unsafe_allow_html=True)

        else:
            st.success("✅ No anomalies detected in the last hour")

    except Exception as e:
        st.warning(f"⚠️ Could not load anomaly alerts: {str(e)}")

    st.divider()

# ==================== DEVICES TABLE ====================
st.header("🖥️ Devices")

if not devices:
    st.warning("⚠️ No devices found. Make sure devices are configured and agents are running.")
else:
    # Create enhanced device table
    device_data = []
    for d in devices:
        status_text, status_type = status_icon(d.get('last_seen'))
        last_seen_text = format_last_seen(d.get('last_seen'))

        # Count metrics for this device
        metric_count = len([m for m in metrics_logs if m['device_id'] == d['id']])

        device_data.append({
            'Status': status_text,
            'Name': d['name'],
            'MAC Address': d['mac'],
            'Last IP': d.get('last_ip', 'N/A'),
            'Last Seen': last_seen_text,
            'Metrics': metric_count,
            '_status_type': status_type,  # Hidden column for filtering
            '_device_id': d['id']  # Hidden column for selection
        })

    df_devices = pd.DataFrame(device_data)

    # Display table
    st.dataframe(
        df_devices[['Status', 'Name', 'MAC Address', 'Last IP', 'Last Seen', 'Metrics']],
        use_container_width=True,
        hide_index=True,
        column_config={
            "Status": st.column_config.TextColumn("Status", width="small"),
            "Name": st.column_config.TextColumn("Device Name", width="medium"),
            "Metrics": st.column_config.NumberColumn("Data Points", width="small"),
        }
    )

    st.divider()

    # ==================== DEVICE DETAILS ====================
    st.header("📈 Device Details")

    # Device selector
    device_names = [d['name'] for d in devices]
    selected_device_name = st.selectbox(
        "Select a device to view details:",
        options=device_names,
        help="Choose a device to see detailed metrics and graphs"
    )

    selected_device = next(d for d in devices if d['name'] == selected_device_name)
    selected_device_id = selected_device['id']

    # Device header
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Device Name", selected_device['name'])

    with col2:
        st.metric("MAC Address", selected_device['mac'])

    with col3:
        st.metric("Last IP", selected_device['last_ip'] or "N/A")

    with col4:
        status_text, _ = status_icon(selected_device['last_seen'])
        st.metric("Status", status_text)

    # ==================== ANOMALY DETECTION ====================
    if enable_anomaly_detection:
        st.subheader("🔍 Anomaly Detection")

        with st.spinner("Analyzing metrics for anomalies..."):
            try:
                # Create fresh detector for this device
                detector = AnomalyDetector(contamination=0.1)
                anomaly_summary = detector.get_anomaly_summary(selected_device_id)

                if anomaly_summary['total_anomalies'] > 0:
                    # Summary metrics
                    col1, col2, col3 = st.columns(3)

                    with col1:
                        st.metric("Total Anomalies", anomaly_summary['total_anomalies'])
                    with col2:
                        st.metric("High Severity", anomaly_summary['high_severity_count'])
                    with col3:
                        st.metric("Medium Severity", anomaly_summary['medium_severity_count'])

                    # Anomalies by method
                    if any(anomaly_summary['by_method'].values()):
                        st.write("**Detection Methods:**")
                        methods_df = pd.DataFrame([
                            {
                                "Method": method.replace('_', ' ').title(),
                                "Anomalies Found": count
                            }
                            for method, count in anomaly_summary['by_method'].items()
                            if count > 0
                        ])
                        st.dataframe(methods_df, hide_index=True, use_container_width=True)

                    # Detailed view
                    with st.expander("📋 View All Anomalies"):
                        # Tabs for different views
                        tab1, tab2 = st.tabs(["Real-time Analysis", "Historical Database"])

                        with tab1:
                            st.caption("Anomalies detected by analyzing recent metrics")
                            for method, anomalies in anomaly_summary['detailed_anomalies'].items():
                                if anomalies and method in detection_method:
                                    st.markdown(f"**{method.replace('_', ' ').title()}** ({len(anomalies)} anomalies)")
                                    for i, anomaly in enumerate(anomalies[:10], 1):
                                        with st.expander(f"Anomaly #{i} - {anomaly.get('timestamp', 'N/A')}"):
                                            st.json(anomaly)

                        with tab2:
                            st.caption("Historical anomalies stored in the database")
                            limit = st.slider("Number to show", 10, 500, 100, 10, key="hist_anomaly_slider")

                            db_anomalies = get_all_anomalies(limit=limit, device_id=selected_device_id)

                            if db_anomalies:
                                st.write(f"Showing {len(db_anomalies)} most recent anomalies")

                                # Table view
                                anomaly_table = pd.DataFrame([
                                    {
                                        'Time': format_last_seen(a['timestamp']),
                                        'Method': a['detection_method'].replace('_', ' ').title(),
                                        'Severity': a['severity'].upper(),
                                        'Acknowledged': '✅' if a.get('acknowledged', 0) else '❌'
                                    }
                                    for a in db_anomalies
                                ])

                                st.dataframe(anomaly_table, use_container_width=True, hide_index=True)

                                # Detailed JSON
                                st.write("**Detailed Data:**")
                                for i, anomaly in enumerate(db_anomalies, 1):
                                    with st.expander(f"#{i} - {anomaly['timestamp']} ({anomaly['severity']})"):
                                        st.json(anomaly)
                            else:
                                st.info("No historical anomalies found for this device")

                else:
                    st.success("✅ No anomalies detected for this device")

            except Exception as e:
                st.warning(f"⚠️ Anomaly detection failed: {str(e)}")

    st.divider()

    # ==================== METRICS VISUALIZATION ====================
    st.subheader("📊 System Metrics")

    device_metrics = [m for m in metrics_logs if m['device_id'] == selected_device_id]

    if device_metrics:
        df_metrics = pd.DataFrame(device_metrics)

        # FIXED: Check if timestamp column exists and has data
        if 'timestamp' in df_metrics.columns and not df_metrics.empty:
            df_metrics['timestamp'] = pd.to_datetime(df_metrics['timestamp'])
            df_metrics = df_metrics.sort_values('timestamp')

            # Filter by time range
            cutoff_time = datetime.now() - timedelta(hours=time_range_hours)
            df_metrics = df_metrics[df_metrics['timestamp'] > cutoff_time]

            if df_metrics.empty:
                st.warning(f"⚠️ No metrics found in the last {time_range_hours} hours")
            else:
                # Show data info
                st.caption(
                    f"📅 {len(df_metrics)} data points | "
                    f"From {df_metrics['timestamp'].min().strftime('%Y-%m-%d %H:%M')} to "
                    f"{df_metrics['timestamp'].max().strftime('%Y-%m-%d %H:%M')}"
                )

                # CPU and RAM
                col1, col2 = st.columns(2)

                with col1:
                    if 'cpu' in df_metrics.columns:
                        fig_cpu = create_percentage_chart(
                            df_metrics, 'cpu',
                            f'CPU Usage - {selected_device["name"]}',
                            selected_device["name"]
                        )
                        st.plotly_chart(fig_cpu, use_container_width=True)

                with col2:
                    if 'ram' in df_metrics.columns:
                        fig_ram = create_percentage_chart(
                            df_metrics, 'ram',
                            f'RAM Usage - {selected_device["name"]}',
                            selected_device["name"]
                        )
                        st.plotly_chart(fig_ram, use_container_width=True)

                # Disk
                if 'disk' in df_metrics.columns:
                    fig_disk = create_percentage_chart(
                        df_metrics, 'disk',
                        f'Disk Usage - {selected_device["name"]}',
                        selected_device["name"]
                    )
                    st.plotly_chart(fig_disk, use_container_width=True)

                # Network traffic
                if 'net_sent' in df_metrics.columns and 'net_recv' in df_metrics.columns:
                    fig_network = go.Figure()

                    fig_network.add_trace(go.Scatter(
                        x=df_metrics['timestamp'],
                        y=df_metrics['net_sent'],
                        mode='lines',
                        name='Upload',
                        line=dict(color='#2196F3', width=2),
                        hovertemplate='<b>Upload</b><br>%{y}<br>%{x}<extra></extra>'
                    ))

                    fig_network.add_trace(go.Scatter(
                        x=df_metrics['timestamp'],
                        y=df_metrics['net_recv'],
                        mode='lines',
                        name='Download',
                        line=dict(color='#4CAF50', width=2),
                        hovertemplate='<b>Download</b><br>%{y}<br>%{x}<extra></extra>'
                    ))

                    fig_network.update_layout(
                        title=f'Network Traffic - {selected_device["name"]}',
                        xaxis_title='Time',
                        yaxis_title='Bytes/Second',
                        hovermode='x unified',
                        plot_bgcolor='rgba(0,0,0,0)',
                        paper_bgcolor='rgba(0,0,0,0)',
                        legend=dict(
                            orientation="h",
                            yanchor="bottom",
                            y=1.02,
                            xanchor="right",
                            x=1
                        )
                    )

                    st.plotly_chart(fig_network, use_container_width=True)

                # Current values
                if not df_metrics.empty:
                    latest = df_metrics.iloc[-1]
                    st.subheader("📌 Current Values")

                    col1, col2, col3, col4, col5 = st.columns(5)

                    with col1:
                        st.metric("CPU", f"{latest.get('cpu', 0):.1f}%")
                    with col2:
                        st.metric("RAM", f"{latest.get('ram', 0):.1f}%")
                    with col3:
                        st.metric("Disk", f"{latest.get('disk', 0):.1f}%")
                    with col4:
                        st.metric("Upload", format_bytes(latest.get('net_sent', 0)))
                    with col5:
                        st.metric("Download", format_bytes(latest.get('net_recv', 0)))
        else:
            st.warning("⚠️ Metrics data is corrupted or empty")
    else:
        st.info(
            f"ℹ️ No metrics available for **{selected_device['name']}**\n\n"
            "**Possible reasons:**\n"
            "- Agent is not running on this device\n"
            "- Network connectivity issues\n"
            "- Firewall blocking port 5000\n"
            "- Incorrect server IP in agent configuration"
        )

        # Debugging help
        with st.expander("🔧 Troubleshooting"):
            st.write(f"**Device ID:** {selected_device_id}")
            st.write(f"**MAC Address:** {selected_device['mac']}")

            if metrics_logs:
                unique_ids = set(m['device_id'] for m in metrics_logs)
                st.write(f"**Devices with metrics:** {unique_ids}")

                st.write("**All devices:**")
                for dev in devices:
                    has_data = dev['id'] in unique_ids
                    emoji = "✅" if has_data else "❌"
                    st.write(f"{emoji} ID {dev['id']}: {dev['name']} ({dev['mac']})")
            else:
                st.write("**No metrics in database at all**")

st.divider()

# ==================== CONNECTION LOGS ====================
st.header("📶 Connection Logs")

if ping_logs:
    df_ping = pd.DataFrame(ping_logs)

    # Check if dataframe is not empty before processing
    if not df_ping.empty and 'timestamp' in df_ping.columns:
        df_ping['timestamp'] = pd.to_datetime(df_ping['timestamp'])

        # Add device names
        device_map = {d['id']: d['name'] for d in devices}
        df_ping['device_name'] = df_ping['device_id'].map(device_map)

        # Status mapping
        df_ping['status_text'] = df_ping['status'].map({1: '🟢 Online', 0: '🔴 Offline'})

        # Recent logs table
        recent_logs = df_ping.head(50)[
            ['timestamp', 'device_name', 'ip', 'status_text', 'latency_ms']
        ].rename(columns={
            'timestamp': 'Time',
            'device_name': 'Device',
            'ip': 'IP Address',
            'status_text': 'Status',
            'latency_ms': 'Latency (ms)'
        })

        st.dataframe(recent_logs, use_container_width=True, hide_index=True)

        # Connection timeline
        st.subheader("📊 Connection Timeline")

        timeline_data = df_ping.head(200)
        if not timeline_data.empty:
            fig_timeline = px.scatter(
                timeline_data,
                x='timestamp',
                y='device_name',
                color='status_text',
                color_discrete_map={'🟢 Online': '#4CAF50', '🔴 Offline': '#F44336'},
                title='Device Connection Status Over Time',
                labels={'device_name': 'Device', 'timestamp': 'Time'}
            )

            fig_timeline.update_layout(
                hovermode='closest',
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
            )

            st.plotly_chart(fig_timeline, use_container_width=True)
    else:
        st.warning("⚠️ Ping log data is empty or corrupted")
else:
    st.info("ℹ️ No ping logs available yet. Start the ping monitor to collect connection data.")

# ==================== FOOTER ====================
st.divider()

col1, col2, col3 = st.columns(3)

with col1:
    if st_autorefresh:
        time_left = max(0, refresh_interval - (time.time() - st.session_state.last_refresh))
        st.caption(f"🔄 Auto-refresh: {int(time_left)}s")
    else:
        st.caption("🔄 Auto-refresh: OFF")

with col2:
    st.caption(f"📅 Last updated: {datetime.now().strftime('%H:%M:%S')}")

with col3:
    st.caption(f"📊 Total records: {len(metrics_logs):,}")

# Debug info (collapsible)
with st.expander("🔧 System Information"):
    col1, col2 = st.columns(2)

    with col1:
        st.write("**Database Summary:**")
        st.write(f"- Devices: {len(devices)}")
        st.write(f"- Ping logs: {len(ping_logs):,}")
        st.write(f"- Metrics logs: {len(metrics_logs):,}")

    with col2:
        st.write("**Configuration:**")
        st.write(f"- Anomaly detection: {enable_anomaly_detection}")
        st.write(f"- Detection methods: {', '.join(detection_method) if detection_method else 'None'}")
        st.write(f"- Time range: {time_range_hours}h")

    if devices:
        st.write("**Device Metrics Count:**")
        for d in devices:
            count = len([m for m in metrics_logs if m['device_id'] == d['id']])
            st.write(f"- {d['name']}: {count:,} records")