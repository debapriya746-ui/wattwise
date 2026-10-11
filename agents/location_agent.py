import ipaddress
import json
import logging
import urllib.request
import urllib.error
import re

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("location_agent")

# Generous enough for a cold cloud host; IP lookups over the public internet
# can take a couple of seconds on first use.
TIMEOUT_SECONDS = 6.0


def _is_public_ip(ip: str) -> bool:
    """True only for a routable public IP. Private/loopback/reserved addresses
    (what a proxy's x-forwarded-for often contains on cloud hosts) can't be
    geolocated, so we skip them and fall back to server-side detection."""
    try:
        addr = ipaddress.ip_address(ip.strip())
        return not (addr.is_private or addr.is_loopback or addr.is_reserved or addr.is_link_local)
    except ValueError:
        return False

def validate_pincode(pincode: str) -> bool:
    """
    Validates pincode format (e.g. 5-6 digits, standard alphanumeric US/UK zip, etc.).
    Keeps it simple but robust.
    """
    if not pincode:
        return False
    clean_pin = pincode.strip()
    # Matches US 5-digit, Indian 6-digit, UK postal codes, etc.
    pattern = r"^[A-Z0-9]{3,10}$"
    is_valid = bool(re.match(pattern, clean_pin, re.IGNORECASE))
    logger.info(f"Decision: Validated pincode '{clean_pin}'. Valid={is_valid}")
    return is_valid

def _query_geo(url: str) -> dict:
    """Call one geolocation endpoint and normalize its fields. Returns a dict
    with success + city/country/pincode, or success False."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "WattWise/1.0"})
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as response:
            data = json.loads(response.read().decode())
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError) as e:
        logger.warning(f"Decision: Geolocation lookup failed for {url}: {e}")
        return {"success": False}

    # ipwho.is uses success=True/False + postal; ip-api uses status="success"
    # + zip. Treat an explicit failure flag as a miss.
    if data.get("success") is False or data.get("status") == "fail":
        logger.warning(f"Decision: Geolocation API reported failure: {data.get('message')}")
        return {"success": False}

    city = data.get("city")
    country = data.get("country") or data.get("country_name")
    pincode = data.get("postal") or data.get("zip")
    # Privacy: never retain coordinates.
    data.pop("latitude", None); data.pop("longitude", None)
    data.pop("lat", None); data.pop("lon", None)

    if city or country:
        return {"success": True, "city": city, "country": country, "pincode": pincode}
    return {"success": False}


def auto_detect_location(client_ip: str = None) -> dict:
    """
    Auto-detects location via a public IP geolocation API (HTTPS).
    Uses client_ip only when it is a routable public address; otherwise falls
    back to server-side detection. Coordinates are discarded for privacy.
    """
    # Build the ordered list of endpoints to try. ipwho.is is HTTPS and free;
    # ip-api is the HTTP fallback.
    attempts = []
    if client_ip and _is_public_ip(client_ip):
        logger.info(f"Decision: Auto-detecting from public client IP '{client_ip}'.")
        attempts.append(f"https://ipwho.is/{client_ip.strip()}")
        attempts.append(f"http://ip-api.com/json/{client_ip.strip()}")
    else:
        if client_ip:
            logger.info(f"Decision: Client IP '{client_ip}' is not public; using server-side detection.")
        else:
            logger.info("Decision: No client IP; using server-side detection.")
        attempts.append("https://ipwho.is/")
        attempts.append("http://ip-api.com/json/")

    for url in attempts:
        res = _query_geo(url)
        if res.get("success"):
            logger.info(f"Decision: Location detected via {url.split('/')[2]}: {res.get('city')}, {res.get('country')}")
            return res

    logger.warning("Decision: All geolocation attempts failed.")
    return {"success": False, "error": "Auto-detection failed"}

def resolve_pincode_api(pincode: str) -> dict:
    """
    Attempts to resolve pincode using Open-Meteo Geocoding API (global search).
    """
    logger.info(f"Decision: Resolving pincode '{pincode}' via Open-Meteo Geocoding API.")
    import urllib.parse
    encoded_pincode = urllib.parse.quote(pincode.strip())
    url = f"https://geocoding-api.open-meteo.com/v1/search?name={encoded_pincode}&count=1&language=en&format=json"
    try:
        with urllib.request.urlopen(url, timeout=TIMEOUT_SECONDS) as response:
            data = json.loads(response.read().decode())
            results = data.get("results", [])
            if results:
                city = results[0].get("name")
                country = results[0].get("country")
                logger.info(f"Decision: Resolved pincode '{pincode}' to city='{city}', country='{country}'")
                return {"success": True, "city": city, "country": country}
    except Exception as e:
        logger.warning(f"Decision: Open-Meteo Geocoding lookup failed: {str(e)}.")
        
    return {"success": False, "error": "Pincode resolution failed"}


def handle_permission_input(user_input: dict, state: dict) -> dict:
    """Handles location permission user response."""
    granted = user_input.get("permission", False)
    if granted:
        logger.info("Decision: User granted location permission. Auto-detecting location.")
        client_ip = user_input.get("client_ip")
        det = auto_detect_location(client_ip)
        if det["success"]:
            state["city"] = det["city"]
            state["country"] = det["country"]
            state["pincode"] = det["pincode"]
            state["step"] = "confirm_location"
            return {
                "prompt": f"Is this your location: {det['city']}, {det['country']}, {det['pincode']}?",
                "require_input": "confirmation",
                "resolved": True
            }
        else:
            logger.info("Decision: Auto-detect failed. Falling back to pincode request.")
    else:
        logger.info("Decision: User denied location permission. Prompting for pincode.")
        
    state["step"] = "ask_pincode"
    return {
        "prompt": "Please enter your pincode:",
        "require_input": "pincode",
        "resolved": False
    }

def handle_pincode_input(user_input: dict, state: dict) -> dict:
    """Handles user entered pincode."""
    pincode = user_input.get("pincode", "").strip()
    if not validate_pincode(pincode):
        logger.warning(f"Decision: Invalid pincode format entered: '{pincode}'. Prompting user to re-enter.")
        return {
            "prompt": "Invalid pincode format. Please enter a valid pincode:",
            "require_input": "pincode",
            "error": "Invalid format"
        }
        
    res = resolve_pincode_api(pincode)
    if res["success"]:
        state["city"] = res["city"]
        state["country"] = res["country"]
        state["pincode"] = pincode
        state["step"] = "confirm_location"
        return {
            "prompt": f"Is this your location: {res['city']}, {res['country']}?",
            "require_input": "confirmation",
            "resolved": True
        }
    else:
        logger.warning("Decision: Pincode resolution failed. Prompting for manual entry.")
        state["step"] = "ask_manual"
        return {
            "prompt": "Pincode could not be resolved. Please enter your city and country manually (e.g. City, Country):",
            "require_input": "manual_address",
            "resolved": False
        }

def handle_manual_input(user_input: dict, state: dict) -> dict:
    """Handles manual city and country entry."""
    city = user_input.get("city", "").strip()
    country = user_input.get("country", "").strip()
    if not city or not country:
        logger.warning("Decision: Empty manual entry. Prompting user to re-enter.")
        return {
            "prompt": "City and Country cannot be empty. Please enter your city and country manually:",
            "require_input": "manual_address",
            "error": "Empty input"
        }
        
    state["city"] = city
    state["country"] = country
    state["step"] = "confirm_location"
    logger.info(f"Decision: User manually entered city='{city}', country='{country}'. Transitioning to confirmation.")
    return {
        "prompt": f"Is this your location: {city}, {country}?",
        "require_input": "confirmation",
        "resolved": True
    }

def handle_confirmation_input(user_input: dict, state: dict) -> dict:
    """Handles location confirmation step."""
    confirmed = user_input.get("confirmed", False)
    if confirmed:
        logger.info(f"Decision: Location confirmed: {state.get('city')}, {state.get('country')}.")
        state["step"] = "completed"
        return {
            "status": "SUCCESS",
            "city": state.get("city"),
            "country": state.get("country"),
            "pincode": state.get("pincode", ""),
            "resolved": True,
            "completed": True
        }
    else:
        logger.info("Decision: User rejected resolved location. Restarting resolution from pincode.")
        state["city"] = None
        state["country"] = None
        state["pincode"] = None
        state["step"] = "ask_pincode"
        return {
            "prompt": "Let's try again. Please enter your pincode:",
            "require_input": "pincode",
            "resolved": False
        }

def process_step(state: dict, user_input: dict = None) -> str:
    """
    Main state machine function for location resolution.
    Returns structured JSON only.
    """
    if user_input is None:
        user_input = {}
        
    current_step = state.get("step", "ask_permission")
    logger.info(f"Decision: Processing location step. Current state step='{current_step}'")
    
    try:
        if current_step == "ask_permission":
            # If user input contains permission answer, handle it. Else prompt.
            if "permission" in user_input:
                res = handle_permission_input(user_input, state)
            else:
                res = {
                    "prompt": "May we auto-detect your location to calculate weather-adjusted energy costs?",
                    "require_input": "permission",
                    "resolved": False
                }
        elif current_step == "ask_pincode":
            if "pincode" in user_input:
                res = handle_pincode_input(user_input, state)
            else:
                res = {
                    "prompt": "Please enter your pincode:",
                    "require_input": "pincode",
                    "resolved": False
                }
        elif current_step == "ask_manual":
            if "city" in user_input and "country" in user_input:
                res = handle_manual_input(user_input, state)
            else:
                res = {
                    "prompt": "Please enter your city and country manually (e.g. City, Country):",
                    "require_input": "manual_address",
                    "resolved": False
                }
        elif current_step == "confirm_location":
            if "confirmed" in user_input:
                res = handle_confirmation_input(user_input, state)
            else:
                res = {
                    "prompt": f"Is this your location: {state.get('city')}, {state.get('country')}?",
                    "require_input": "confirmation",
                    "resolved": True
                }
        elif current_step == "completed":
            res = {
                "status": "SUCCESS",
                "city": state.get("city"),
                "country": state.get("country"),
                "pincode": state.get("pincode", ""),
                "resolved": True,
                "completed": True
            }
        else:
            logger.error(f"Decision: Unknown step encountered: {current_step}")
            res = {"status": "FAIL", "error": "Invalid state step"}
            
        # Return structured JSON only
        return json.dumps(res, indent=2)
        
    except Exception as e:
        logger.error(f"Decision: Exception in process_step: {str(e)}")
        err_res = {
            "status": "FAIL",
            "error": str(e),
            "prompt": "An error occurred. Please enter your pincode:",
            "require_input": "pincode"
        }
        state["step"] = "ask_pincode"
        return json.dumps(err_res, indent=2)
