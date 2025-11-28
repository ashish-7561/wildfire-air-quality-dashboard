import requests
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
import folium
from streamlit_folium import st_folium

# -------------------------
# Config
# -------------------------
WAQI_TOKEN = "3cd76abad0501e79bb285944bee4c559a17d69ba"

# -------------------------
# Data Fetching
# -------------------------
@st.cache_data
def load_historical_fires():
    """Loads a curated list of major historical wildfires."""
    try:
        df = pd.read_csv("app/data/major_wildfires.csv")
        return df
    except FileNotFoundError:
        return pd.DataFrame()

@st.cache_data(ttl=600)
def fetch_waqi_data(city="Delhi"):
    """Fetches REAL LIVE AQI + PM2.5 + Forecast from WAQI."""
    url = f"https://api.waqi.info/feed/{city}/?token={WAQI_TOKEN}"
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    data = r.json()

    api_status = data.get("status")
    if api_status != "ok":
        return pd.DataFrame(), pd.DataFrame(), api_status

    # 🌍 REAL LIVE AQI VALUE
    aqi_live = data["data"].get("aqi")

    # PM2.5 concentration (not AQI)
    pm25 = data["data"].get("iaqi", {}).get("pm25", {}).get("v")

    # Location + Geo
    location = data["data"]["city"].get("name", city)
    lat = data["data"]["city"]["geo"][0]
    lon = data["data"]["city"]["geo"][1]

    current_df = pd.DataFrame([{
        "location": location,
        "aqi": aqi_live,
        "pm25": pm25,
        "lat": lat,
        "lon": lon
    }])

    # Forecast Data
    forecast_data = data["data"].get("forecast", {}).get("daily", {}).get("pm25", [])
    forecast_df = pd.DataFrame(forecast_data) if forecast_data else pd.DataFrame()
    if not forecast_df.empty:
        forecast_df['day'] = pd.to_datetime(forecast_df['day'])

    return current_df, forecast_df, api_status


# -------------------------
# Visualization Functions
# -------------------------
def create_aqi_gauge(aqi_value):
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=aqi_value,
        title={'text': "🌫️ REAL LIVE AQI"},
        gauge={
            'axis': {'range': [0, 500]},
            'bar': {'color': "black"},
            'steps': [
                {'range': [0, 50], 'color': "green"},
                {'range': [51, 100], 'color': "yellow"},
                {'range': [101, 150], 'color': "orange"},
                {'range': [151, 200], 'color': "red"},
                {'range': [201, 300], 'color': "purple"},
                {'range': [301, 500], 'color': "maroon"},
            ]
        }
    ))
    fig.update_layout(height=250, margin=dict(l=10, r=10, t=40, b=10))
    return fig


def create_forecast_plot(df, city):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df['day'], y=df['avg'], mode='lines+markers', name='Average'))
    fig.add_trace(go.Scatter(x=df['day'], y=df['max'], mode='lines', name='Max'))
    fig.add_trace(go.Scatter(x=df['day'], y=df['min'], mode='lines', fill='tonexty', name='Min'))
    fig.update_layout(title=f"🔮 7-Day PM2.5 Forecast – {city}",
                      xaxis_title="Date", yaxis_title="PM2.5",
                      legend_title="Forecast")
    return fig


def create_interactive_fire_map(df_fires):
    fire_map = folium.Map(location=[20, 0], zoom_start=2, tiles="CartoDB dark_matter")
    for _, row in df_fires.iterrows():
        html = f"""
        <h4>{row['name']}</h4>
        <b>Country:</b> {row['country']}<br>
        <b>Date:</b> {row['start_date']}<br>
        <b>Intensity (FRP):</b> {row['intensity_frp']}
        """
        popup = folium.Popup(html, max_width=300)
        folium.CircleMarker(
            location=[row['latitude'], row['longitude']],
            radius=5, color='orangered',
            fill=True, fill_color='red',
            popup=popup
        ).add_to(fire_map)
    return fire_map


# -------------------------
# Streamlit Layout
# -------------------------
st.set_page_config(page_title="🌍 Fires & Air Quality Dashboard", layout="wide")
st.title("🌍 Wildfire & Air Quality Monitoring Dashboard")

# Loading Fire Data
df_fires = load_historical_fires()

# Sidebar
st.sidebar.header("Configuration")
city = st.sidebar.text_input("Enter City", "Delhi")


# Fetch AQI Data
show_fallback_message = False
try:
    df_aq, df_forecast, api_status = fetch_waqi_data(city)
    if api_status != "ok":
        show_fallback_message = True
        df_aq, df_forecast, api_status = fetch_waqi_data("Delhi")
except Exception:
    show_fallback_message = True
    df_aq, df_forecast, api_status = fetch_waqi_data("Delhi")
    st.sidebar.error("❌ Could not fetch live AQI data.")

if show_fallback_message:
    st.info(f"ℹ️ Could not find live data for '{city}'. Showing Delhi instead.")


# -------------------------
# Main Layout
# -------------------------
col1, col2 = st.columns([2, 1])

# Fire Map
with col1:
    st.subheader("🔥 Major Historical Wildfires")
    if not df_fires.empty:
        fire_map = create_interactive_fire_map(df_fires)
        st_folium(fire_map, use_container_width=True, height=450)
    else:
        st.warning("No fire data available.")

# AQI Panel
with col2:
    st.subheader("🌫️ Live Air Quality")
    if not df_aq.empty:
        aqi_value = df_aq['aqi'].iloc[0]
        st.plotly_chart(create_aqi_gauge(aqi_value), use_container_width=True)

        # Show coordinates on a map
        st.map(df_aq[['lat', 'lon']])

        st.markdown(f"### 📍 Location: **{df_aq['location'].iloc[0]}**")
        st.markdown(f"### 🟦 PM2.5 (μg/m³): **{df_aq['pm25'].iloc[0]}**")
        st.markdown(f"### 🟥 AQI: **{aqi_value}**")
    else:
        st.warning("AQI data not available.")


# Forecast Section
st.markdown("---")
st.header("🔮 Live 7-Day Air Quality Forecast")

if not df_forecast.empty:
    display_city = df_aq['location'].iloc[0] if not df_aq.empty else city
    st.plotly_chart(create_forecast_plot(df_forecast, display_city), use_container_width=True)
else:
    st.warning("Forecast not available for this city.")

