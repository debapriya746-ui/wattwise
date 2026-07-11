import json
import logging
import urllib.parse
import urllib.request
import urllib.error

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("weather_agent")

TIMEOUT_SECONDS = 3.0

def geocode_city(city: str, country: str) -> dict:
    """Converts a city and country name into latitude and longitude using Open-Meteo."""
    logger.info(f"Decision: Geolocating city='{city}', country='{country}' via Open-Meteo Geocoding API.")
    query = f"{city}, {country}"
    encoded_query = urllib.parse.quote(query)
    url = f"https://geocoding-api.open-meteo.com/v1/search?name={encoded_query}&count=1&language=en&format=json"
    
    try:
        logger.info(f"Decision: Making HTTP GET request to Geocoding API: {url}")
        with urllib.request.urlopen(url, timeout=TIMEOUT_SECONDS) as response:
            data = json.loads(response.read().decode())
            results = data.get("results")
            if not results:
                logger.warning(f"Decision: No geocoding results found for {query}.")
                return {"success": False, "error": "Location not found"}
            
            lat = results[0].get("latitude")
            lon = results[0].get("longitude")
            logger.info(f"Decision: Geocoded successfully. Latitude={lat}, Longitude={lon}")
            return {"success": True, "lat": lat, "lon": lon}
    except urllib.error.URLError as e:
        logger.error(f"Decision: Network error during geocoding: {str(e)}")
        return {"success": False, "error": f"Network error: {str(e)}"}
    except json.JSONDecodeError as e:
        logger.error(f"Decision: JSON decoding error during geocoding: {str(e)}")
        return {"success": False, "error": "Invalid JSON response"}

def fetch_weather_raw(lat: float, lon: float) -> dict:
    """Fetches raw weather data from Open-Meteo API using latitude and longitude."""
    logger.info(f"Decision: Fetching weather for lat={lat}, lon={lon} via Open-Meteo Weather API.")
    url = (
        f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
        "&current=temperature_2m,relative_humidity_2m,apparent_temperature,weather_code"
        "&daily=temperature_2m_max,temperature_2m_min&timezone=auto"
    )
    
    try:
        logger.info(f"Decision: Making HTTP GET request to Weather API: {url}")
        with urllib.request.urlopen(url, timeout=TIMEOUT_SECONDS) as response:
            data = json.loads(response.read().decode())
            current = data.get("current", {})
            daily = data.get("daily", {})
            
            temp_c = current.get("temperature_2m")
            humidity = current.get("relative_humidity_2m")
            feels_like_c = current.get("apparent_temperature")
            
            # Fetch daily min/max
            temp_max_c = daily.get("temperature_2m_max", [temp_c])[0]
            temp_min_c = daily.get("temperature_2m_min", [temp_c])[0]
            weather_code = current.get("weather_code", 0)
            
            if temp_c is None or temp_max_c is None or temp_min_c is None:
                logger.error("Decision: Missing required temperature values from weather API response.")
                return {"success": False, "error": "Incomplete weather data"}
                
            return {
                "success": True,
                "temp_c": temp_c,
                "temp_min_c": temp_min_c,
                "temp_max_c": temp_max_c,
                "humidity": humidity if humidity is not None else 50,
                "feels_like_c": feels_like_c if feels_like_c is not None else temp_c,
                "weather_code": weather_code
            }
    except urllib.error.URLError as e:
        logger.error(f"Decision: Network error during weather fetch: {str(e)}")
        return {"success": False, "error": f"Network error: {str(e)}"}
    except json.JSONDecodeError as e:
        logger.error(f"Decision: JSON decode error during weather fetch: {str(e)}")
        return {"success": False, "error": "Invalid JSON response"}

def map_weather_code(code: int) -> str:
    """Map weather code to condition string."""
    if code in [0]:
        return "Clear"
    elif code in [1, 2, 3]:
        return "Partly Cloudy"
    elif code in [45, 48]:
        return "Foggy"
    elif code in [51, 53, 55, 61, 63, 65, 80, 81, 82]:
        return "Rainy"
    elif code in [71, 73, 75, 77, 85, 86]:
        return "Snowy"
    elif code in [95, 96, 99]:
        return "Thunderstorm"
    return "Cloudy"

def calculate_degree_days(temp_min_c: float, temp_max_c: float) -> dict:
    """Calculates average Fahrenheit temp, CDD, and HDD."""
    temp_min_f = temp_min_c * 9/5 + 32
    temp_max_f = temp_max_c * 9/5 + 32
    avg_temp_f = (temp_max_f + temp_min_f) / 2
    
    cdd = max(0.0, avg_temp_f - 65.0)
    hdd = max(0.0, 65.0 - avg_temp_f)
    
    logger.info(f"Decision: Calculated degree days: avg_temp_f={avg_temp_f:.2f}, CDD={cdd:.2f}, HDD={hdd:.2f}")
    return {
        "temp_min_f": round(temp_min_f, 1),
        "temp_max_f": round(temp_max_f, 1),
        "avg_temp_f": round(avg_temp_f, 1),
        "cdd": round(cdd, 2),
        "hdd": round(hdd, 2)
    }

CAPITALS = {
    "United States": "Washington, D.C.",
    "India": "New Delhi",
    "United Kingdom": "London",
    "Germany": "Berlin",
    "France": "Paris",
    "Canada": "Ottawa",
    "Australia": "Canberra",
    "Japan": "Tokyo",
    "China": "Beijing",
    "Brazil": "Brasilia",
    "South Africa": "Pretoria",
    "Russia": "Moscow",
    "Italy": "Rome",
    "Spain": "Madrid",
    "Mexico": "Mexico City",
    "Singapore": "Singapore",
    "Malaysia": "Kuala Lumpur",
    "Indonesia": "Jakarta",
    "Philippines": "Manila",
    "Thailand": "Bangkok",
    "Vietnam": "Hanoi",
    "South Korea": "Seoul",
    "Netherlands": "Amsterdam",
    "Belgium": "Brussels",
    "Switzerland": "Bern",
    "Sweden": "Stockholm",
    "Norway": "Oslo",
    "Denmark": "Copenhagen",
    "Finland": "Helsinki",
    "Poland": "Warsaw",
    "Austria": "Vienna",
    "New Zealand": "Wellington",
    "Ireland": "Dublin",
    "Portugal": "Lisbon",
    "Greece": "Athens",
    "Turkey": "Ankara",
    "Egypt": "Cairo",
    "Saudi Arabia": "Riyadh",
    "UAE": "Abu Dhabi",
    "United Arab Emirates": "Abu Dhabi",
    "Argentina": "Buenos Aires",
    "Colombia": "Bogota",
    "Chile": "Santiago",
    "Peru": "Lima"
}

def resolve_parent_divisions(city: str, country: str) -> dict:
    """Queries Nominatim to resolve parent administrative divisions (district/county, state/province)."""
    logger.info(f"Decision: Querying Nominatim for address details of '{city}, {country}'")
    query = f"{city}, {country}"
    encoded_query = urllib.parse.quote(query)
    url = f"https://nominatim.openstreetmap.org/search?q={encoded_query}&format=json&addressdetails=1&limit=1"
    
    res = {"district": None, "state": None}
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "WattWise-App/1.0 (contact: admin@wattwise.local)"})
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as response:
            data = json.loads(response.read().decode())
            if data:
                address = data[0].get("address", {})
                res["district"] = address.get("county") or address.get("district") or address.get("state_district")
                res["state"] = address.get("state") or address.get("province") or address.get("region")
                logger.info(f"Decision: Nominatim resolved parent divisions: district={res['district']}, state={res['state']}")
    except Exception as e:
        logger.warning(f"Decision: Nominatim lookup failed: {str(e)}")
        parts = [p.strip() for p in city.split(",")]
        if len(parts) > 1:
            res["district"] = parts[-2]
            res["state"] = parts[-1]
            
    return res

def geocode_with_fallbacks(city: str, country: str) -> tuple:
    """Executes the geocoding fallback chain and returns (geo_res, actual_location, is_fallback)."""
    divisions = resolve_parent_divisions(city, country)
    district = divisions["district"]
    state_prov = divisions["state"]
    capital = CAPITALS.get(country)
    
    fallback_chain = [{"name": city, "query_city": city, "type": "exact"}]
    if district:
        fallback_chain.append({"name": district, "query_city": district, "type": "district"})
    if state_prov:
        fallback_chain.append({"name": state_prov, "query_city": state_prov, "type": "state"})
    if capital:
        fallback_chain.append({"name": capital, "query_city": capital, "type": "capital"})
    fallback_chain.append({"name": country, "query_city": country, "type": "country"})
    
    for attempt in fallback_chain:
        logger.info(f"Decision: Attempting geocoding for {attempt['type']}: '{attempt['name']}, {country}'")
        geo_res = geocode_city(attempt["query_city"], country)
        if geo_res.get("success"):
            logger.info(f"Decision: Weather fetching will use location: '{attempt['name']}' (type: {attempt['type']})")
            return geo_res, attempt["name"], (attempt["type"] != "exact")
            
    return {"success": False, "error": "Location not found"}, None, False

def get_weather(city: str, country: str) -> str:
    """
    Retrieves weather details, converts to Fahrenheit, calculates CDD and HDD.
    Returns a structured JSON string.
    Does NOT store location after the call.
    """
    logger.info(f"Decision: Weather Agent request received for city='{city}', country='{country}'")
    
    geo_res, actual_location, is_fallback = geocode_with_fallbacks(city, country)
    if not geo_res.get("success"):
        fail_res = {
            "status": "FAIL",
            "fallback_required": True,
            "message": f"We could not find weather data for {city}, {country}. Please enter the name of the nearest big city for accurate weather data.",
            "error": geo_res.get("error")
        }
        return json.dumps(fail_res, indent=2)
        
    lat = geo_res["lat"]
    lon = geo_res["lon"]
    
    weather_res = fetch_weather_raw(lat, lon)
    if not weather_res.get("success"):
        fail_res = {
            "status": "FAIL",
            "fallback_required": True,
            "message": f"Weather fetch failed for nearest location {actual_location}: {weather_res.get('error')}. Please enter temperature manually.",
            "error": weather_res.get("error")
        }
        return json.dumps(fail_res, indent=2)
        
    dd_res = calculate_degree_days(weather_res["temp_min_c"], weather_res["temp_max_c"])
    temp_f = weather_res["temp_c"] * 9/5 + 32
    feels_like_f = weather_res["feels_like_c"] * 9/5 + 32
    condition = map_weather_code(weather_res["weather_code"])
    
    output = {
        "status": "SUCCESS",
        "temp": round(temp_f, 1),
        "temp_min": dd_res["temp_min_f"],
        "temp_max": dd_res["temp_max_f"],
        "humidity": weather_res["humidity"],
        "feels_like": round(feels_like_f, 1),
        "cdd": dd_res["cdd"],
        "hdd": dd_res["hdd"],
        "condition": condition,
        "source": "open_meteo"
    }
    
    if is_fallback:
        output["note"] = f"Weather data sourced from nearest available location: {actual_location}"
        
    logger.info(f"Decision: Returned weather successfully using '{actual_location}'. Fallback: {is_fallback}")
    return json.dumps(output, indent=2)

