import sqlite3 # To work with the database.
import pandas as pd # Used to handle and analyze data.
import streamlit as st # Framework for creating web dashboards and visualizations.

DB_NAME = "monitor.db"

# The configuration of the Streamlit page is set: the title and the wider layout.
st.set_page_config(page_title="Network Device Monitor", layout="wide")

# Sets the main title on the web page.
st.title("Centralized Network Device Monitor")

#This function does the following:
#    - Opens a database connection
#    - Loads the last 200 records from the ping_status table into a Pandas DataFrame sorted by descending ID
#    - Closes the connection and returns the DataFrame
def load_data():
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query("SELECT * FROM ping_status ORDER BY id DESC LIMIT 200", conn)
    conn.close()
    return df

df = load_data()

#Shows the subtitle.
#Displays a data table in the Streamlit dashboard with the ability to sort and filter.
st.subheader("Last 200 ping entries")
st.dataframe(df)

#Shows a subtitle for the device's current status.
#From the dataframe, df sorts records by timestamp and groups by device_name, taking the first (latest) record for each device.
st.subheader("Current device status")
latest = df.sort_values("timestamp", ascending=False).groupby("device_name").first()

# Changes numeric status values to readable text
latest["status"] = latest["status"].map({1: "ONLINE", 0: "OFFLINE"})

# Displays a table with only the MAC, IP and device status fields, representing hte latest status of each device on the network.
st.table(latest[["mac", "ip", "status"]])
