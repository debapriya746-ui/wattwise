import streamlit as st
import json
import os
from agents import location_agent
from agents import weather_agent
from agents import tariff_agent
from agents import calculator_agent
from agents import advisor_agent
from agents import orchestrator
from mcp_server import appliance_db_server

# Page settings
st.set_page_config(
    page_title="WattWise",
    page_icon="⚡",
    layout="centered"
)

# Custom styles for clean premium white aesthetic
st.markdown("""
<style>
/* Background and layout */
.stApp {
    background-color: #ffffff;
    color: #333333;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}

/* Card Container */
.card-container {
    background-color: #fcfcfc;
    border: 1px solid #eef0f2;
    border-radius: 16px;
    padding: 24px;
    margin-bottom: 20px;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.015);
}

.card-title {
    font-size: 1.15rem;
    font-weight: 600;
    color: #2c3e50;
    margin-bottom: 8px;
}

/* Estimate result style */
.estimate-box {
    text-align: center;
    background-color: #f7fafc;
    border: 1.5px solid #edf2f7;
    border-radius: 20px;
    padding: 30px;
    margin: 20px 0;
}

.estimate-val {
    font-size: 3.5rem;
    font-weight: 800;
    color: #2b6cb0;
    line-height: 1;
    margin: 10px 0;
}

.estimate-range {
    font-size: 1.25rem;
    color: #4a5568;
    font-weight: 500;
}

/* Badges */
.badge-success {
    background-color: #c6f6d5;
    color: #22543d;
    padding: 4px 12px;
    border-radius: 9999px;
    font-size: 0.85rem;
    font-weight: 600;
    display: inline-block;
    margin-bottom: 8px;
}

.badge-info {
    background-color: #ebf8ff;
    color: #2b6cb0;
    padding: 4px 12px;
    border-radius: 9999px;
    font-size: 0.85rem;
    font-weight: 600;
    display: inline-block;
}

.disclaimer-text {
    font-size: 0.8rem;
    color: #718096;
    font-style: italic;
    margin-top: 15px;
}
</style>
""", unsafe_allow_html=True)

# Currencies
CURRENCY_SYMBOLS = {
    "INR": "₹",
    "USD": "$",
    "GBP": "£",
    "EUR": "€"
}

def get_currency_symbol(curr_code):
    return CURRENCY_SYMBOLS.get(curr_code, "$")

def draw_progress_bar(step):
    steps = ["Location", "Profile", "Usage", "Verify", "Estimate", "Tips"]
    cols = st.columns(6)
    for i, s in enumerate(steps):
        with cols[i]:
            if i + 1 == step:
                st.markdown(f"<div style='text-align:center; border-bottom:3.5px solid #2b6cb0; font-weight:700; color:#2b6cb0; padding-bottom:6px; font-size:0.85rem;'>{s}</div>", unsafe_allow_html=True)
            elif i + 1 < step:
                st.markdown(f"<div style='text-align:center; border-bottom:3.5px solid #319795; color:#319795; padding-bottom:6px; font-size:0.85rem;'>✓ {s}</div>", unsafe_allow_html=True)
            else:
                st.markdown(f"<div style='text-align:center; border-bottom:3.5px solid #edf2f7; color:#a0aec0; padding-bottom:6px; font-size:0.85rem;'>{s}</div>", unsafe_allow_html=True)
    st.write("")

# Initialize session state variables
if "step" not in st.session_state:
    st.session_state.step = 1
if "city" not in st.session_state:
    st.session_state.city = ""
if "country" not in st.session_state:
    st.session_state.country = ""
if "pincode" not in st.session_state:
    st.session_state.pincode = ""
if "location_resolved" not in st.session_state:
    st.session_state.location_resolved = False
if "location_resolved_failed" not in st.session_state:
    st.session_state.location_resolved_failed = False
if "weather" not in st.session_state:
    st.session_state.weather = {}
if "tariff" not in st.session_state:
    st.session_state.tariff = {}
if "home_type" not in st.session_state:
    st.session_state.home_type = "Apartment"
if "members" not in st.session_state:
    st.session_state.members = "2"
if "mode" not in st.session_state:
    st.session_state.mode = "Quick Mode"
if "usage_level" not in st.session_state:
    st.session_state.usage_level = "Medium"
if "appliances" not in st.session_state:
    st.session_state.appliances = []
if "calculation_results" not in st.session_state:
    st.session_state.calculation_results = {}
if "feedback_status" not in st.session_state:
    st.session_state.feedback_status = None

# Header
st.markdown("<h2 style='text-align: center; margin-bottom: 0px;'>⚡ WattWise</h2>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: #718096; margin-bottom: 25px;'>Your personal electricity bill estimator</p>", unsafe_allow_html=True)

# ----------------- STEP 1: Location Access -----------------
if st.session_state.step == 1:
    draw_progress_bar(1)
    st.markdown("<div class='card-container'>", unsafe_allow_html=True)
    st.markdown("<div class='card-title'>Where are you located?</div>", unsafe_allow_html=True)
    st.write("We use your location to estimate weather-adjusted energy usage and find your local electricity tariff rate.")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("📍 Auto-detect my location", use_container_width=True):
            client_ip = st.context.headers.get("x-forwarded-for")
            if client_ip:
                client_ip = client_ip.split(",")[0].strip()
            det = location_agent.auto_detect_location(client_ip)
            if det["success"]:
                st.session_state.city = det["city"]
                st.session_state.country = det["country"]
                st.session_state.pincode = det["pincode"]
                st.session_state.location_resolved = True
                st.session_state.location_resolved_failed = False
                st.rerun()
            else:
                st.error("Auto-detect failed. Please enter pincode below.")
                
    with col2:
        pin = st.text_input("Or enter pincode manually", placeholder="e.g. 94043")
        if st.button("Find Location", use_container_width=True):
            if location_agent.validate_pincode(pin):
                res = location_agent.resolve_pincode_api(pin)
                if res["success"]:
                    st.session_state.city = res["city"]
                    st.session_state.country = res["country"]
                    st.session_state.pincode = pin
                    st.session_state.location_resolved = True
                    st.session_state.location_resolved_failed = False
                    st.rerun()
                else:
                    st.session_state.location_resolved_failed = True
                    st.rerun()
            else:
                st.error("Invalid pincode format.")
                
    if st.session_state.location_resolved_failed:
        st.markdown("<hr style='margin: 15px 0;'>", unsafe_allow_html=True)
        st.markdown("Pincode could not be resolved. Please enter your location details:")
        m_city = st.text_input("City")
        m_country = st.text_input("Country")
        if st.button("Confirm Manual Location", use_container_width=True):
            if m_city and m_country:
                st.session_state.city = m_city
                st.session_state.country = m_country
                st.session_state.pincode = ""
                st.session_state.location_resolved = True
                st.session_state.location_resolved_failed = False
                st.rerun()
                
    if st.session_state.location_resolved:
        st.markdown("<hr style='margin: 15px 0;'>", unsafe_allow_html=True)
        st.write("Please review and correct the resolved location details below if necessary:")
        
        col_c_edit, col_co_edit, col_p_edit = st.columns(3)
        with col_c_edit:
            confirmed_city = st.text_input("City", value=st.session_state.city, key="step1_edit_city")
        with col_co_edit:
            confirmed_country = st.text_input("Country", value=st.session_state.country, key="step1_edit_country")
        with col_p_edit:
            confirmed_pincode = st.text_input("Pincode (Optional)", value=st.session_state.pincode, key="step1_edit_pincode")
            
        c1, c2 = st.columns(2)
        with c1:
            if st.button("Confirm & Continue", use_container_width=True):
                st.session_state.city = confirmed_city
                st.session_state.country = confirmed_country
                st.session_state.pincode = confirmed_pincode
                
                with st.spinner("Fetching weather and tariff rates..."):
                    # Call weather agent
                    w_res_str = weather_agent.get_weather(st.session_state.city, st.session_state.country)
                    w_res = json.loads(w_res_str)
                    if w_res["status"] in ["SUCCESS", "FALLBACK"]:
                        st.session_state.weather = w_res
                    else:
                        st.session_state.weather = {
                            "temp": 72.0, "temp_min": 65.0, "temp_max": 79.0,
                            "humidity": 50, "feels_like": 72.0, "cdd": 5.0, "hdd": 0.0,
                            "condition": "Clear", "source": "fallback", "status": "FALLBACK"
                        }
                    
                    # Call tariff agent
                    t_res = tariff_agent.lookup_tariff_db(st.session_state.city, st.session_state.country)
                    if t_res["found"]:
                        st.session_state.tariff = {
                            "rate": t_res["data"]["rate"],
                            "rate_source": t_res["source"],
                            "fixed_charge": t_res["data"]["fixed_charge"],
                            "slab_based": t_res["data"]["slab_based"],
                            "slabs": t_res["data"]["slabs"],
                            "currency": t_res["currency"],
                            "confidence": "high" if t_res["source"] == "state_average" else "medium"
                        }
                    else:
                        st.session_state.tariff = {
                            "rate": 0.15,
                            "rate_source": "country_average",
                            "fixed_charge": 0.0,
                            "slab_based": False,
                            "slabs": [],
                            "currency": "USD",
                            "confidence": "low"
                        }
                st.session_state.step = 2
                st.rerun()
        with c2:
            if st.button("Cancel / Clear", use_container_width=True):
                st.session_state.location_resolved = False
                st.session_state.location_resolved_failed = False
                st.rerun()
                
    st.markdown("</div>", unsafe_allow_html=True)

# ----------------- STEP 2: Home Profile -----------------
elif st.session_state.step == 2:
    draw_progress_bar(2)
    st.markdown("<div class='card-container'>", unsafe_allow_html=True)
    st.markdown("<div class='card-title'>Tell us about your home</div>", unsafe_allow_html=True)
    
    home_type = st.selectbox(
        "What best describes your home?",
        ["Apartment", "House", "Villa"],
        index=["Apartment", "House", "Villa"].index(st.session_state.home_type)
    )
    members = st.selectbox(
        "Number of family members in your household",
        ["1", "2", "3", "4", "5+"],
        index=["1", "2", "3", "4", "5+"].index(st.session_state.members)
    )
    mode = st.radio(
        "Estimation Mode",
        ["Quick Mode", "Detailed Mode"],
        index=["Quick Mode", "Detailed Mode"].index(st.session_state.mode),
        help="Quick Mode calculates based on home averages. Detailed Mode allows you to add custom appliances."
    )
    
    if st.button("Next Step", use_container_width=True):
        st.session_state.home_type = home_type
        st.session_state.members = members
        st.session_state.mode = mode
        st.session_state.step = 3
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

# ----------------- STEP 3: Appliance / Usage Inputs -----------------
elif st.session_state.step == 3:
    draw_progress_bar(3)
    
    if st.session_state.mode == "Quick Mode":
        st.markdown("<div class='card-container'>", unsafe_allow_html=True)
        st.markdown("<div class='card-title'>Appliance Usage Level</div>", unsafe_allow_html=True)
        usage = st.select_slider(
            "Overall daily appliance usage level",
            options=["Low", "Medium", "High"],
            value=st.session_state.usage_level
        )
        if st.button("Generate Estimate Summary", use_container_width=True):
            st.session_state.usage_level = usage
            m_val = 5 if st.session_state.members == "5+" else int(st.session_state.members)
            # Generate default appliances list
            apps = orchestrator.generate_quick_mode_appliances(
                st.session_state.home_type,
                m_val,
                usage
            )
            st.session_state.appliances = apps
            st.session_state.step = 4
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
        
    else:
        # Detailed Mode - Appliance builder
        st.subheader("Add your appliances")
        
        # Add new appliance form
        with st.expander("➕ Add an Appliance", expanded=len(st.session_state.appliances) == 0):
            app_type = st.selectbox(
                "Appliance Type",
                ["AC", "Fridge", "Washing machine", "TV", "Fan", "Water heater", "Microwave", "Lights", "Laptop", "Desktop", "Iron"]
            )
            
            # Contextual questions based on type
            size_param = None
            star_param = None
            age_param = None
            
            if app_type == "AC":
                size_param = st.selectbox("Tonnage", ["1 ton", "1.5 ton", "2 ton"])
                star_param = st.selectbox("Star Rating", [1, 2, 3, 4, 5], index=2)
                age_param = st.selectbox("Age of AC", ["less than 3 years", "3-5 years", "more than 5 years"])
            elif app_type == "Fridge":
                size_param = st.selectbox("Size", ["small", "medium", "large"])
                star_param = st.selectbox("Star Rating", [1, 2, 3, 4, 5], index=2)
            elif app_type == "Washing machine":
                size_param = st.selectbox("Capacity", ["6 kg", "7 kg", "8 kg"])
                age_param = st.selectbox("Load Type", ["top load", "front load"])
            elif app_type == "TV":
                size_param = st.selectbox("Screen Size", ["32 inch", "43 inch", "55 inch"])
                age_param = st.selectbox("Display Type", ["LED", "OLED", "QLED"])
            elif app_type == "Fan":
                size_param = st.selectbox("Type", ["ceiling", "table", "pedestal", "BLDC ceiling"])
            elif app_type == "Water heater":
                size_param = st.selectbox("Capacity", ["10L", "15L", "25L"])
            elif app_type == "Microwave":
                size_param = st.selectbox("Type", ["solo", "grill", "convection"])
            elif app_type == "Lights":
                size_param = st.selectbox("Bulb Type", ["LED", "CFL", "Incandescent"])
                
            hours = st.slider("Daily Usage (Hours)", min_value=0.5, max_value=24.0, value=4.0, step=0.5)
            
            if st.button("Add to List", use_container_width=True):
                # Call database server directly to fetch wattage
                watts_res_str = appliance_db_server.get_appliance_wattage(
                    app_type, size_param, star_param, age_param
                )
                watts_res = json.loads(watts_res_str)
                watts = watts_res.get("watts_expected", 100)
                
                new_app = {
                    "appliance": app_type,
                    "watts": watts,
                    "hours": hours,
                    "star_rating": star_param if star_param else 3,
                    "age": age_param if age_param else "",
                    "size": size_param if size_param else "",
                    "owned": True,
                    "confirmed": True
                }
                st.session_state.appliances.append(new_app)
                st.success(f"Added {app_type} ({watts}W) for {hours} hours daily.")
                st.rerun()

        # Display added appliances list
        if st.session_state.appliances:
            st.write("### Your Appliances")
            for idx, app in enumerate(st.session_state.appliances):
                col_c, col_d = st.columns([4, 1])
                with col_c:
                    desc = f"{app['appliance']}"
                    if app['size']:
                        desc += f" ({app['size']})"
                    desc += f" — {app['watts']}W | {app['hours']} hrs/day"
                    st.markdown(f"<div class='card-container' style='padding:12px 18px; margin-bottom:8px;'>{desc}</div>", unsafe_allow_html=True)
                with col_d:
                    if st.button("Remove", key=f"del_{idx}", use_container_width=True):
                        st.session_state.appliances.pop(idx)
                        st.rerun()
                        
            if st.button("Verify Details", use_container_width=True):
                st.session_state.step = 4
                st.rerun()
        else:
            st.info("Please add at least one appliance to continue.")

# ----------------- STEP 4: Verification Screen -----------------
elif st.session_state.step == 4:
    draw_progress_bar(4)
    if "is_editing" not in st.session_state:
        st.session_state.is_editing = False
        
    if st.session_state.is_editing:
        st.markdown("<div class='card-container'>", unsafe_allow_html=True)
        st.markdown("<div class='card-title'>🔧 Edit Inputs</div>", unsafe_allow_html=True)
        
        # 1. Location
        st.markdown("### 📍 Location Details")
        col_city, col_country, col_pin = st.columns(3)
        with col_city:
            edit_city = st.text_input("City", value=st.session_state.city)
        with col_country:
            edit_country = st.text_input("Country", value=st.session_state.country)
        with col_pin:
            edit_pincode = st.text_input("Pincode", value=st.session_state.pincode)
            
        # 2. Local Climate
        st.markdown("### 🌡️ Local Climate")
        col_temp, col_hum, col_cdd, col_hdd = st.columns(4)
        with col_temp:
            edit_temp = st.number_input("Average Temperature (°F)", value=float(st.session_state.weather.get("temp", 72.0)), step=1.0)
        with col_hum:
            edit_humidity = st.number_input("Humidity (%)", value=float(st.session_state.weather.get("humidity", 50.0)), min_value=0.0, max_value=100.0, step=5.0)
        with col_cdd:
            edit_cdd = st.number_input("Cooling Degree Days (CDD)", value=float(st.session_state.weather.get("cdd", 0.0)), step=0.5)
        with col_hdd:
            edit_hdd = st.number_input("Heating Degree Days (HDD)", value=float(st.session_state.weather.get("hdd", 0.0)), step=0.5)
            
        # 3. Tariff
        st.markdown("### 💳 Electricity Tariff")
        col_rate, col_fixed = st.columns(2)
        with col_rate:
            edit_rate = st.number_input("Rate per kWh", value=float(st.session_state.tariff.get("rate", 0.15)), min_value=0.01, step=0.01)
        with col_fixed:
            edit_fixed = st.number_input("Fixed Monthly Charge", value=float(st.session_state.tariff.get("fixed_charge", 0.0)), min_value=0.0, step=1.0)
            
        # 4. Mode-specific inputs
        st.markdown("### 🏠 Home & Appliances Profile")
        if st.session_state.mode == "Quick Mode":
            col_ht, col_mem, col_ul = st.columns(3)
            with col_ht:
                edit_home_type = st.selectbox("Home Type", ["Apartment", "House", "Villa"], index=["Apartment", "House", "Villa"].index(st.session_state.home_type))
            with col_mem:
                edit_members = st.selectbox("Members", ["1", "2", "3", "4", "5+"], index=["1", "2", "3", "4", "5+"].index(st.session_state.members))
            with col_ul:
                edit_usage_level = st.select_slider("Usage Level", options=["Low", "Medium", "High"], value=st.session_state.usage_level)
        else:
            st.write("Add or remove appliances below:")
            # Appliance builder form
            with st.expander("➕ Add an Appliance", expanded=False):
                app_type = st.selectbox(
                    "Appliance Type",
                    ["AC", "Fridge", "Washing machine", "TV", "Fan", "Water heater", "Microwave", "Lights", "Laptop", "Desktop", "Iron"],
                    key="edit_builder_type"
                )
                
                size_param = None
                star_param = None
                age_param = None
                
                if app_type == "AC":
                    size_param = st.selectbox("Tonnage", ["1 ton", "1.5 ton", "2 ton"], key="edit_ac_ton")
                    star_param = st.selectbox("Star Rating", [1, 2, 3, 4, 5], index=2, key="edit_ac_star")
                    age_param = st.selectbox("Age of AC", ["less than 3 years", "3-5 years", "more than 5 years"], key="edit_ac_age")
                elif app_type == "Fridge":
                    size_param = st.selectbox("Size", ["small", "medium", "large"], key="edit_fr_sz")
                    star_param = st.selectbox("Star Rating", [1, 2, 3, 4, 5], index=2, key="edit_fr_star")
                elif app_type == "Washing machine":
                    size_param = st.selectbox("Capacity", ["6 kg", "7 kg", "8 kg"], key="edit_wm_cap")
                    age_param = st.selectbox("Load Type", ["top load", "front load"], key="edit_wm_type")
                elif app_type == "TV":
                    size_param = st.selectbox("Screen Size", ["32 inch", "43 inch", "55 inch"], key="edit_tv_sz")
                    age_param = st.selectbox("Display Type", ["LED", "OLED", "QLED"], key="edit_tv_type")
                elif app_type == "Fan":
                    size_param = st.selectbox("Type", ["ceiling", "table", "pedestal", "BLDC ceiling"], key="edit_fan_type")
                elif app_type == "Water heater":
                    size_param = st.selectbox("Capacity", ["10L", "15L", "25L"], key="edit_wh_cap")
                elif app_type == "Microwave":
                    size_param = st.selectbox("Type", ["solo", "grill", "convection"], key="edit_mw_type")
                elif app_type == "Lights":
                    size_param = st.selectbox("Bulb Type", ["LED", "CFL", "Incandescent"], key="edit_light_type")
                    
                hours = st.slider("Daily Usage (Hours)", min_value=0.5, max_value=24.0, value=4.0, step=0.5, key="edit_app_hours")
                
                if st.button("Add to List", key="edit_add_btn", use_container_width=True):
                    watts_res_str = appliance_db_server.get_appliance_wattage(app_type, size_param, star_param, age_param)
                    watts_res = json.loads(watts_res_str)
                    watts = watts_res.get("watts_expected", 100)
                    
                    new_app = {
                        "appliance": app_type,
                        "watts": watts,
                        "hours": hours,
                        "star_rating": star_param if star_param else 3,
                        "age": age_param if age_param else "",
                        "size": size_param if size_param else "",
                        "owned": True,
                        "confirmed": True
                    }
                    st.session_state.appliances.append(new_app)
                    st.success(f"Added {app_type} ({watts}W) for {hours} hours daily.")
                    st.rerun()
            
            if st.session_state.appliances:
                st.write("##### Current Appliance List:")
                for idx, app in enumerate(st.session_state.appliances):
                    col_c, col_d = st.columns([4, 1])
                    with col_c:
                        desc = f"{app['appliance']}"
                        if app['size']:
                            desc += f" ({app['size']})"
                        desc += f" — {app['watts']}W | {app['hours']} hrs/day"
                        st.markdown(f"<div class='card-container' style='padding:8px 15px; margin-bottom:5px; border-radius:8px;'>{desc}</div>", unsafe_allow_html=True)
                    with col_d:
                        if st.button("Remove", key=f"edit_del_{idx}", use_container_width=True):
                            st.session_state.appliances.pop(idx)
                            st.rerun()

        # Save or Cancel Buttons
        col_s, col_c = st.columns(2)
        with col_s:
            if st.button("Save & Estimate", use_container_width=True):
                # 1. Update Location
                st.session_state.city = edit_city
                st.session_state.country = edit_country
                st.session_state.pincode = edit_pincode
                
                # 2. Update Weather
                st.session_state.weather["temp"] = edit_temp
                st.session_state.weather["humidity"] = edit_humidity
                st.session_state.weather["cdd"] = edit_cdd
                st.session_state.weather["hdd"] = edit_hdd
                
                # 3. Update Tariff
                st.session_state.tariff["rate"] = edit_rate
                st.session_state.tariff["fixed_charge"] = edit_fixed
                
                # 4. Update Quick Mode
                if st.session_state.mode == "Quick Mode":
                    st.session_state.home_type = edit_home_type
                    st.session_state.members = edit_members
                    st.session_state.usage_level = edit_usage_level
                    
                    m_val = 5 if edit_members == "5+" else int(edit_members)
                    apps = orchestrator.generate_quick_mode_appliances(
                        edit_home_type,
                        m_val,
                        edit_usage_level
                    )
                    st.session_state.appliances = apps
                
                st.session_state.is_editing = False
                
                # Run calculations
                res_str = calculator_agent.calculate_bill(
                    st.session_state.appliances,
                    st.session_state.weather,
                    st.session_state.tariff,
                    assumptions_confirmed=True
                )
                st.session_state.calculation_results = json.loads(res_str)
                st.session_state.step = 5
                st.rerun()
                
        with col_c:
            if st.button("Cancel Edit", use_container_width=True):
                st.session_state.is_editing = False
                st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
        
    else:
        st.markdown("<div class='card-container'>", unsafe_allow_html=True)
        st.markdown("<div class='card-title'>Review your information</div>", unsafe_allow_html=True)
        st.write("Please confirm the assumptions and inputs resolved before we calculate your estimate:")
        
        # 1. Location
        st.markdown("**Location:**")
        st.write(f"{st.session_state.city}, {st.session_state.country} {st.session_state.pincode}")
        
        # 2. Weather
        st.markdown("**Local Climate:**")
        st.write(f"Temp: {st.session_state.weather.get('temp')}°F ({st.session_state.weather.get('condition')}) | CDD: {st.session_state.weather.get('cdd')} | HDD: {st.session_state.weather.get('hdd')}")
        
        # 3. Tariff
        st.markdown("**Electricity Rate:**")
        curr = get_currency_symbol(st.session_state.tariff.get("currency", "USD"))
        note = " (Fixed charge not included)" if st.session_state.tariff.get("fixed_charge") == 0 else ""
        st.write(f"{curr}{st.session_state.tariff.get('rate')}/kWh (Source: {st.session_state.tariff.get('rate_source').replace('_', ' ')}) | Fixed Charge: {curr}{st.session_state.tariff.get('fixed_charge')}{note}")
        
        # 4. Appliances
        st.markdown("**Appliance Details:**")
        if st.session_state.appliances:
            app_data = []
            for app in st.session_state.appliances:
                app_data.append({
                    "Appliance": app["appliance"],
                    "Watts": f"{app['watts']}W",
                    "Hours/Day": f"{app['hours']} hrs"
                })
            st.table(app_data)
        else:
            st.info("No appliances added.")
            
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Confirm & Estimate", use_container_width=True):
                res_str = calculator_agent.calculate_bill(
                    st.session_state.appliances,
                    st.session_state.weather,
                    st.session_state.tariff,
                    assumptions_confirmed=True
                )
                st.session_state.calculation_results = json.loads(res_str)
                st.session_state.step = 5
                st.rerun()
        with col2:
            if st.button("Edit Details", use_container_width=True):
                st.session_state.is_editing = True
                st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

# ----------------- STEP 5: Results Screen -----------------
elif st.session_state.step == 5:
    draw_progress_bar(5)
    
    res = st.session_state.calculation_results
    curr = get_currency_symbol(res.get("currency", "USD"))
    
    st.markdown("<div class='estimate-box'>", unsafe_allow_html=True)
    st.markdown(f"<div class='badge-success'>{res.get('margin_explanation')}</div>", unsafe_allow_html=True)
    st.markdown("<div style='font-size: 1.1rem; color: #4a5568; font-weight: 500;'>Estimated Monthly Cost</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='estimate-val'>{curr}{int(res.get('total_expected'))}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='estimate-range'>Expected Range: {curr}{int(res.get('low_bill'))} – {curr}{int(res.get('high_bill'))}</div>", unsafe_allow_html=True)
    
    rate_source = res.get("rate_source", "").replace("_", " ")
    st.markdown(f"<div style='font-size: 0.9rem; color: #718096; margin-top: 15px;'>Electricity Tariff Source: **{rate_source}**</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='disclaimer-text'>{res.get('disclaimer')}</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)
    
    if st.button("Show ways to reduce this bill", use_container_width=True):
        st.session_state.step = 6
        st.rerun()

# ----------------- STEP 6: Saving Tips Screen -----------------
elif st.session_state.step == 6:
    draw_progress_bar(6)
    
    calc_res = st.session_state.calculation_results
    curr = get_currency_symbol(calc_res.get("currency", "USD"))
    
    # Generate tips
    tips_res = advisor_agent.generate_tips_list(calc_res, st.session_state.weather)
    
    st.subheader("💡 Personalized Saving Tips")
    
    # Display slab boundary warning if any
    if tips_res.get("slab_boundary_alert"):
        st.warning(tips_res.get("slab_boundary_message"))
        
    for tip in tips_res.get("tips", []):
        st.markdown(f"""
        <div class='card-container'>
            <div style='display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;'>
                <div class='card-title' style='margin:0;'>Tip #{tip['rank']}: {tip['action']}</div>
                <span class='badge-success' style='margin:0;'>Save {curr}{tip['monthly_saving_low']} - {curr}{tip['monthly_saving_high']}</span>
            </div>
            <div style='font-size:0.95rem; color:#4a5568; margin-bottom:10px;'>{tip['why']}</div>
            <div style='display:flex; gap:15px; font-size:0.85rem; color:#718096;'>
                <div>Difficulty: <strong>{tip['difficulty']}</strong></div>
                <div>Impact: <strong>{tip['impact']}</strong></div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
    # Feedback loop section
    st.markdown("<div class='card-container'>", unsafe_allow_html=True)
    st.markdown("<div class='card-title'>Help us improve future estimates</div>", unsafe_allow_html=True)
    st.write("How close was this estimate to your actual monthly bill?")
    
    col1, col2 = st.columns(2)
    with col1:
        act_bill = st.number_input("Enter actual bill amount:", min_value=0.0, step=10.0)
    with col2:
        act_kwh = st.number_input("Enter actual kWh used (Optional):", min_value=0.0, step=10.0)
        
    if st.button("Submit Feedback", use_container_width=True):
        f_input = {}
        if act_kwh > 0:
            f_input = {"feedback": {"actual_kwh": act_kwh}}
        elif act_bill > 0:
            f_input = {"feedback": {"actual_bill": act_bill}}
            
        if f_input:
            adv_state = {"step": "ask_feedback", "calculator_output": calc_res}
            res_str = advisor_agent.process_step(adv_state, f_input)
            res = json.loads(res_str)
            st.session_state.feedback_status = res.get("message")
            st.rerun()
            
    if st.session_state.feedback_status:
        st.success(st.session_state.feedback_status)
    st.markdown("</div>", unsafe_allow_html=True)
    
    if st.button("Start Over", use_container_width=True):
        # Clear all session states
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()
