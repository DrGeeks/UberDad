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

def get_route(start_coords, end_coords):
    url = f"http://router.project-osrm.org/route/v1/driving/{start_coords[1]},{start_coords[0]};{end_coords[1]},{end_coords[0]}?overview=full&geometries=geojson"
    r = requests.get(url).json()
    distance = r['routes'][0]['distance'] / 1000 # convert to km
    geometry = r['routes'][0]['geometry']['coordinates']
    # OSRM returns [lon, lat], Folium needs [lat, lon]
    route_points = [[p[1], p[0]] for p in geometry]
    return distance, route_points

def send_email(details):
    msg = EmailMessage()
    msg.set_content(f"New Ride Request:\n\n{details}")
    msg['Subject'] = "UberDad: New Ride Requested!"
    msg['From'] = USER_EMAIL
    msg['To'] = USER_EMAIL

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(USER_EMAIL, APP_PASSWORD)
        server.send_message(msg)

st.title("🚗 UberDad")

# Input Fields
# Use now_local for defaults
date = st.date_input("Requested Date", value=now_local.date())
time = st.time_input("Requested Time", value=now_local.time())
start_loc = st.text_input("From Location (e.g., 123 Main St)")
end_loc = st.text_input("To Location")

if start_loc and end_loc:
    try:
        geolocator = Nominatim(user_agent="uberdad_mock")
        loc1 = geolocator.geocode(start_loc)
        loc2 = geolocator.geocode(end_loc)
        
        if loc1 and loc2:
            dist_km, route = get_route((loc1.latitude, loc1.longitude), (loc2.latitude, loc2.longitude))
            cost = round(dist_km, 1)
            
            st.metric("Estimated Cost", f"{cost} Brownie Points")
            
            # Display Map
            m = folium.Map(location=[loc1.latitude, loc1.longitude], zoom_start=13)
            folium.PolyLine(route, color="blue", weight=5, opacity=0.8).add_to(m)
            folium.Marker([loc1.latitude, loc1.longitude], tooltip="Start").add_to(m)
            folium.Marker([loc2.latitude, loc2.longitude], tooltip="End").add_to(m)
            st_folium(m, width=700, height=400)
            
            if st.button("Request Ride"):
                details = f"Date: {date}\nTime: {time}\nFrom: {start_loc}\nTo: {end_loc}\nDistance: {cost} km\nCost: {cost} Brownie Points"
                send_email(details)
                st.success("Request sent to Dad!")
    except Exception as e:
        st.error("Error calculating route. Please check the addresses.")
