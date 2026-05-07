import streamlit as st
import smtplib
import requests
import folium
import time
from geopy.exc import GeocoderTimedOut, GeocoderServiceError, GeocoderUnavailable
from email.message import EmailMessage
from geopy.geocoders import Nominatim
from streamlit_folium import st_folium
from datetime import datetime
from zoneinfo import ZoneInfo

# --- 1. Configuration & Secrets ---
try:
    USER_EMAIL = st.secrets["USER_EMAIL"]
    APP_PASSWORD = st.secrets["APP_PASSWORD"]
except KeyError:
    st.error("Missing Secrets: Please configure USER_EMAIL and APP_PASSWORD in Streamlit Cloud.")
    st.stop()

# --- 2. Timezone Setup (PDT/PST) ---
local_tz = ZoneInfo("America/Vancouver")
now_local = datetime.now(local_tz)

# --- 3. Logic: Routing & Geocoding ---
@st.cache_data(show_spinner="Contacting geocoder...")
def get_route_data(start_loc, end_loc):
    # Unique agent is critical
    geolocator = Nominatim(user_agent="uberdad_sholefield_v1", timeout=10)
    
    def safe_geocode(query, retries=3):
        for i in range(retries):
            try:
                # Adding a small sleep to respect the 1 req/sec policy
                time.sleep(1.1) 
                return geolocator.geocode(query)
            except (GeocoderTimedOut, GeocoderServiceError) as e:
                if i == retries - 1:
                    raise e
                time.sleep(2) # Wait longer before retrying
        return None

    try:
        loc1 = safe_geocode(f"{start_loc}, BC, Canada")
        loc2 = safe_geocode(f"{end_loc}, BC, Canada")
        
        if not loc1:
            return {"error": f"Could not find start location: '{start_loc}'"}
        if not loc2:
            return {"error": f"Could not find destination: '{end_loc}'"}

        # OSRM API for driving route
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
    
    except GeocoderUnavailable:
        return {"error": "The geocoding service is currently busy or unavailable. Please wait a few seconds and try again."}
    except Exception as e:
        return {"error": f"An unexpected error occurred: {str(e)}"}

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

# Input Fields
col1, col2 = st.columns(2)
with col1:
    date_req = st.date_input("Requested Date", value=now_local.date())
with col2:
    time_req = st.time_input("Requested Time", value=now_local.time())

start_address = st.text_input("From (Address or Landmark)")
end_address = st.text_input("To (Address or Landmark)")

# --- 6. Execution ---
if start_address and end_address:
    data = get_route_data(start_address, end_address)
    
    if "error" in data:
        st.error(data["error"])
    else:
        # Calculation logic: 1 brownie point per km
        # $C = d \times 1$
        cost = round(data['dist'], 1)
        st.metric("Estimated Cost", f"{cost} Brownie Points")
        
        # Render Map
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
