import streamlit as st
import smtplib
import requests
import folium
from email.message import EmailMessage
from geopy.geocoders import Nominatim
from streamlit_folium import st_folium
from datetime import datetime
from zoneinfo import ZoneInfo
import time
from geopy.exc import GeocoderTimedOut, GeocoderServiceError

# --- 1. Configuration & Secrets ---
try:
    USER_EMAIL = st.secrets["USER_EMAIL"]
    APP_PASSWORD = st.secrets["APP_PASSWORD"]
except KeyError:
    st.error("Missing Secrets: Please configure USER_EMAIL and APP_PASSWORD in Streamlit Cloud.")
    st.stop()

# --- 2. Initialize Session State for Date/Time ---
local_tz = ZoneInfo("America/Vancouver")

if "initialized" not in st.session_state:
    now_local = datetime.now(local_tz)
    st.session_state.default_date = now_local.date()
    st.session_state.default_time = now_local.time()
    st.session_state.initialized = True

# --- 3. Logic: Routing & Geocoding ---
@st.cache_data(show_spinner="Calculating route...")
def get_route_data(start_loc, end_loc):
    # Modified User-Agent to bypass the 429 rate limit
    geolocator = Nominatim(user_agent="uberdad_v3_delivery_app", timeout=10)
    
    def safe_geocode(query, retries=3):
        for i in range(retries):
            try:
                time.sleep(1.1)  # Rate limit courtesy delay
                return geolocator.geocode(query)
            except (GeocoderTimedOut, GeocoderServiceError):
                if i == retries - 1:
                    return None
                time.sleep(2)
        return None

    loc1 = safe_geocode(f"{start_loc}, BC, Canada")
    loc2 = safe_geocode(f"{end_loc}, BC, Canada")
    
    if not loc1:
        return {"error": f"Could not find start location: '{start_loc}'"}
    if not loc2:
        return {"error": f"Could not find destination: '{end_loc}'"}

    try:
        url = f"http://router.project-osrm.org/route/v1/driving/{loc1.longitude},{loc1.latitude};{loc2.longitude},{loc2.latitude}?overview=full&geometries=geojson"
        r = requests.get(url).json()
        
        if 'routes' not in r or not r['routes']:
            return {"error": "No driving route found between these locations."}

        distance_km = r['routes'][0]['distance'] / 1000
        geometry = r['routes'][0]['geometry']['coordinates']
        route_points = [[p[1], p[0]] for p in geometry]
        
        return {
            "dist": distance_km,
            "route": route_points,
            "start": [loc1.latitude, loc1.longitude],
            "end": [loc2.latitude, loc2.longitude]
        }
    except Exception:
        return {"error": "Routing service (OSRM) is currently unavailable."}

# --- 4. Logic: Email Notification ---
def send_ride_request(details):
    try:
        msg = EmailMessage()
        msg.set_content(f"UberDad Ride Request Received:\n\n{details}")
        msg['Subject'] = "🚗 New UberDad Request!"
        msg['From'] = USER_EMAIL
        msg['To'] = USER_EMAIL

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(USER_EMAIL, APP_PASSWORD)
            server.send_message(msg)
        return True, None
    except Exception as e:
        return False, str(e)

# --- 5. UI Layout ---
st.set_page_config(page_title="UberDad", page_icon="🚗")
st.title("🚗 UberDad")
st.markdown("Request a ride from the best driver in North Delta.")

# Input Fields using state values
col1, col2 = st.columns(2)
with col1:
    date_req = st.date_input("Requested Date", value=st.session_state.default_date)
with col2:
    time_req = st.time_input("Requested Time", value=st.session_state.default_time)

start_address = st.text_input("From (Address or Landmark)")
end_address = st.text_input("To (Address or Landmark)")

# --- 6. Execution ---
if start_address and end_address:
    data = get_route_data(start_address, end_address)
    
    if "error" in data:
        st.error(data["error"])
    else:
        cost = round(data['dist'], 1)
        st.metric("Estimated Cost", f"{cost} Brownie Points")
        
        m = folium.Map(location=data['start'], zoom_start=12)
        folium.PolyLine(data['route'], color="#2e7d32", weight=6, opacity=0.8).add_to(m)
        folium.Marker(data['start'], popup="Pickup", icon=folium.Icon(color='green')).add_to(m)
        folium.Marker(data['end'], popup="Dropoff", icon=folium.Icon(color='red')).add_to(m)
        st_folium(m, width=700, height=400, key="ride_map")
        
        if st.button("Confirm & Request Ride", use_container_width=True):
            summary = (
                f"Date: {date_req}\n"
                f"Time: {time_req.strftime('%I:%M %p')}\n"
                f"From: {start_address}\n"
                f"To: {end_address}\n"
                f"Distance: {cost} km\n"
                f"Cost: {cost} Brownie Points"
            )
            
            success, err = send_ride_request(summary)
            if success:
                st.success("Request sent! Check your email for confirmation.")
                st.balloons()
            else:
                st.error(f"Failed to send request: {err}")
                
