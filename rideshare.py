import streamlit as st
import smtplib
from email.message import EmailMessage
from geopy.geocoders import Nominatim
import requests
import folium
import streamlit as st
from streamlit_folium import st_folium
from datetime import datetime
from zoneinfo import ZoneInfo

# Define the timezone
local_tz = ZoneInfo("America/Vancouver")
now_local = datetime.now(local_tz)

# Configuration
# Access secrets via the st.secrets dictionary
try:
    USER_EMAIL = st.secrets["USER_EMAIL"]
    APP_PASSWORD = st.secrets["APP_PASSWORD"]
except KeyError:
    st.error("Secrets not configured. Please check your Streamlit Cloud settings or secrets.toml.")
    st.stop()

@st.cache_data(show_spinner="Searching addresses...")
def get_route_data(start_loc, end_loc):
    geolocator = Nominatim(user_agent="uberdad_mock")
    
    # Geocode Start
    loc1 = geolocator.geocode(start_loc)
    if not loc1:
        return {"error": f"Could not find start location: '{start_loc}'"}
        
    # Geocode End
    loc2 = geolocator.geocode(end_loc)
    if not loc2:
        return {"error": f"Could not find destination: '{end_loc}'"}

    # Calculate Route
    try:
        url = f"http://router.project-osrm.org/route/v1/driving/{loc1.longitude},{loc1.latitude};{loc2.longitude},{loc2.latitude}?overview=full&geometries=geojson"
        r = requests.get(url).json()
        
        if 'routes' not in r or not r['routes']:
            return {"error": "No driving route found between these locations."}

        distance = r['routes'][0]['distance'] / 1000
        geometry = r['routes'][0]['geometry']['coordinates']
        route_points = [[p[1], p[0]] for p in geometry]
        
        return {
            "dist": distance,
            "route": route_points,
            "start": [loc1.latitude, loc1.longitude],
            "end": [loc2.latitude, loc2.longitude]
        }
    except Exception:
        return {"error": "Routing service is currently unavailable."}
        
def send_email(details):
    try:
        msg = EmailMessage()
        msg.set_content(f"New Ride Request:\n\n{details}")
        msg['Subject'] = "UberDad: New Ride Requested!"
        msg['From'] = USER_EMAIL
        msg['To'] = USER_EMAIL

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(USER_EMAIL, APP_PASSWORD)
            server.send_message(msg)
        return True, "Success"
    except Exception as e:
        return False, str(e)

st.title("🚗 UberDad")

# Input Fields
# Use now_local for defaults
date = st.date_input("Requested Date", value=now_local.date())
time = st.time_input("Requested Time", value=now_local.time())
start_loc = st.text_input("From Location (e.g., 123 Main St)")
end_loc = st.text_input("To Location")

if start_loc and end_loc:
    data = get_route_data(start_loc, end_loc)

if "error" in data:
        st.error(data["error"])
    else:
    if data:
        cost = round(data['dist'], 1)
        st.metric("Estimated Cost", f"{cost} Brownie Points")
        
        m = folium.Map(location=data['start'], zoom_start=13)
        folium.PolyLine(data['route'], color="blue", weight=5).add_to(m)
        folium.Marker(data['start'], tooltip="Start").add_to(m)
        folium.Marker(data['end'], tooltip="End").add_to(m)
        st_folium(m, width=700, height=400, key="map")
        
        if st.button("Request Ride"):
            details = f"Date: {date}\nTime: {time}\nFrom: {start_loc}\nTo: {end_loc}\nDistance: {cost} km"
            success, error_msg = send_email(details)
            if success:
                st.success("Request sent to Dad!")
            else:
                st.error(f"Email Failed: {error_msg}")
    else:
        st.error("Could not find addresses or calculate route.")
