import json
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("tariff_agent")

TARIFF_DB = {
    "united states": {
        "currency": "USD",
        "default": {"rate": 0.18, "fixed_charge": 12.0, "slab_based": False, "slabs": []},
        "regions": {
            "california": {"rate": 0.32, "fixed_charge": 15.0, "slab_based": False, "slabs": []},
            "new york": {"rate": 0.23, "fixed_charge": 17.0, "slab_based": False, "slabs": []},
            "texas": {"rate": 0.14, "fixed_charge": 10.0, "slab_based": False, "slabs": []}
        }
    },
    "india": {
        "currency": "INR",
        "default": {
            "rate": 6.0,
            "fixed_charge": 50.0,
            "slab_based": True,
            "slabs": [
                {"limit": 150, "rate": 5.0},
                {"limit": None, "rate": 7.0}
            ]
        },
        "regions": {
            "maharashtra": {
                "rate": 8.0,
                "fixed_charge": 100.0,
                "slab_based": True,
                "slabs": [
                    {"limit": 100, "rate": 5.0},
                    {"limit": 300, "rate": 8.0},
                    {"limit": 500, "rate": 11.0},
                    {"limit": None, "rate": 13.0}
                ]
            },
            "delhi": {
                "rate": 4.5,
                "fixed_charge": 50.0,
                "slab_based": True,
                "slabs": [
                    {"limit": 200, "rate": 3.0},
                    {"limit": 400, "rate": 4.5},
                    {"limit": None, "rate": 7.0}
                ]
            },
            "karnataka": {
                "rate": 7.0,
                "fixed_charge": 75.0,
                "slab_based": True,
                "slabs": [
                    {"limit": 50, "rate": 4.0},
                    {"limit": 100, "rate": 5.5},
                    {"limit": 200, "rate": 7.0},
                    {"limit": None, "rate": 8.5}
                ]
            }
        }
    },
    "united kingdom": {
        "currency": "GBP",
        "default": {"rate": 0.28, "fixed_charge": 15.0, "slab_based": False, "slabs": []}
    },
    "germany": {
        "currency": "EUR",
        "default": {"rate": 0.35, "fixed_charge": 12.0, "slab_based": False, "slabs": []}
    }
}

CITY_TO_REGION = {
    "mumbai": "maharashtra",
    "pune": "maharashtra",
    "nagpur": "maharashtra",
    "bangalore": "karnataka",
    "bengaluru": "karnataka",
    "mysore": "karnataka",
    "new delhi": "delhi",
    "delhi": "delhi",
    "los angeles": "california",
    "san francisco": "california",
    "new york city": "new york",
    "new york": "new york",
    "houston": "texas",
    "dallas": "texas",
    "austin": "texas"
}

def get_currency_for_country(country: str) -> str:
    """Helper to detect currency based on normalized country name."""
    norm = country.lower().strip()
    if norm in TARIFF_DB:
        return TARIFF_DB[norm]["currency"]
    return "USD"

def lookup_tariff_db(city: str, country: str) -> dict:
    """
    Looks up state average or country average rate from database.
    """
    norm_country = country.lower().strip()
    norm_city = city.lower().strip()
    
    logger.info(f"Decision: Searching tariff database for city='{norm_city}', country='{norm_country}'")
    
    if norm_country not in TARIFF_DB:
        logger.warning(f"Decision: Country '{country}' not in DB. No averages resolved.")
        return {"found": False}
        
    db_country = TARIFF_DB[norm_country]
    region_name = CITY_TO_REGION.get(norm_city, None)
    
    if region_name and region_name in db_country.get("regions", {}):
        region_data = db_country["regions"][region_name]
        logger.info(f"Decision: Resolved state average tariff for region='{region_name}'.")
        return {
            "found": True,
            "source": "state_average",
            "data": region_data,
            "currency": db_country["currency"]
        }
        
    # Fallback to country average
    default_data = db_country["default"]
    logger.info(f"Decision: Resolved country average tariff for country='{norm_country}'.")
    return {
        "found": True,
        "source": "country_average",
        "data": default_data,
        "currency": db_country["currency"]
    }

def handle_ask_user_rate(user_input: dict, state: dict) -> dict:
    """Handles first step where user inputs rate choice."""
    choice = user_input.get("manual", False)
    
    if choice:
        rate = user_input.get("rate")
        fixed = user_input.get("fixed_charge", 0.0)
        
        # Validate inputs are positive numbers
        if rate is None or float(rate) <= 0:
            logger.warning("Decision: User attempted manual rate entry but entered invalid value.")
            return {
                "prompt": "Please enter a valid positive electricity rate per kWh:",
                "require_input": "manual_rate",
                "error": "Invalid rate value"
            }
            
        fixed = float(fixed) if fixed is not None else 0.0
        state["rate"] = float(rate)
        state["rate_source"] = "user_entered"
        state["fixed_charge"] = fixed
        state["slab_based"] = False
        state["slabs"] = []
        state["currency"] = get_currency_for_country(state["country"])
        state["confidence"] = "high"
        state["step"] = "confirm_resolved_rate"
        
        logger.info(f"Decision: User entered manual rate={rate}, fixed={fixed}. Proceeding to confirmation.")
    else:
        logger.info("Decision: User requested estimation. Resolving from database averages.")
        res = lookup_tariff_db(state["city"], state["country"])
        
        if res["found"]:
            state["rate"] = res["data"]["rate"]
            state["rate_source"] = res["source"]
            state["fixed_charge"] = res["data"]["fixed_charge"]
            state["slab_based"] = res["data"]["slab_based"]
            state["slabs"] = res["data"]["slabs"]
            state["currency"] = res["currency"]
            state["confidence"] = "medium" if res["source"] == "state_average" else "low"
            state["step"] = "confirm_resolved_rate"
        else:
            logger.warning("Decision: No average tariff rates found. Forcing manual rate entry.")
            state["step"] = "force_manual"
            return {
                "prompt": "No regional average rates found. Please enter your rate per kWh manually:",
                "require_input": "manual_rate"
            }
            
    # Show confirmation prompt to satisfy requirement 3 and 4
    note = ""
    if state["fixed_charge"] == 0:
        note = " (Fixed charge not included)"
        
    return {
        "prompt": f"Resolved rate: {state['rate']} per kWh. Rate source: {state['rate_source']}. Fixed charge: {state['fixed_charge']}{note}. Do you confirm this rate?",
        "require_input": "confirmation",
        "resolved": True
    }

def handle_confirm_resolved_rate(user_input: dict, state: dict) -> dict:
    """Handles rate confirmation response from user."""
    confirmed = user_input.get("confirmed", False)
    
    if confirmed:
        logger.info(f"Decision: Tariff rate confirmed: {state['rate']} per kWh. Source: {state['rate_source']}.")
        state["step"] = "completed"
        
        note = "Fixed charge not included" if state["fixed_charge"] == 0 else None
        res = {
            "status": "SUCCESS",
            "rate": state["rate"],
            "rate_source": state["rate_source"],
            "fixed_charge": state["fixed_charge"],
            "slab_based": state["slab_based"],
            "slabs": state["slabs"],
            "currency": state["currency"],
            "confidence": state["confidence"],
            "completed": True
        }
        if note:
            res["note"] = note
        return res
    else:
        logger.info("Decision: User rejected resolved rate. Requesting manual entry.")
        state["step"] = "force_manual"
        return {
            "prompt": "Please enter your electricity rate per kWh manually:",
            "require_input": "manual_rate"
        }

def process_step(state: dict, user_input: dict = None) -> str:
    """
    Main entrypoint state machine for tariff agent.
    Returns structured JSON only.
    """
    if user_input is None:
        user_input = {}
        
    current_step = state.get("step", "ask_user_rate")
    logger.info(f"Decision: Processing tariff step. Current step='{current_step}'")
    
    try:
        if current_step == "ask_user_rate":
            # If user input contains choices, handle. Else prompt.
            if "manual" in user_input:
                res = handle_ask_user_rate(user_input, state)
            else:
                res = {
                    "prompt": "Would you like to enter your electricity rate manually, or should we estimate it based on location?",
                    "require_input": "rate_choice",
                    "resolved": False
                }
        elif current_step == "force_manual":
            if "rate" in user_input:
                user_input["manual"] = True
                res = handle_ask_user_rate(user_input, state)
            else:
                res = {
                    "prompt": "Please enter your electricity rate per kWh manually:",
                    "require_input": "manual_rate",
                    "resolved": False
                }
        elif current_step == "confirm_resolved_rate":
            if "confirmed" in user_input:
                res = handle_confirm_resolved_rate(user_input, state)
            else:
                note = " (Fixed charge not included)" if state.get("fixed_charge") == 0 else ""
                res = {
                    "prompt": f"Resolved rate: {state.get('rate')} per kWh. Rate source: {state.get('rate_source')}. Fixed charge: {state.get('fixed_charge')}{note}. Do you confirm this rate?",
                    "require_input": "confirmation",
                    "resolved": True
                }
        elif current_step == "completed":
            note = "Fixed charge not included" if state.get("fixed_charge") == 0 else None
            res = {
                "status": "SUCCESS",
                "rate": state.get("rate"),
                "rate_source": state.get("rate_source"),
                "fixed_charge": state.get("fixed_charge"),
                "slab_based": state.get("slab_based"),
                "slabs": state.get("slabs"),
                "currency": state.get("currency"),
                "confidence": state.get("confidence"),
                "completed": True
            }
            if note:
                res["note"] = note
        else:
            logger.error(f"Decision: Invalid tariff state step: {current_step}")
            res = {"status": "FAIL", "error": "Invalid state step"}
            
        return json.dumps(res, indent=2)
        
    except Exception as e:
        logger.error(f"Decision: Exception in process_step: {str(e)}")
        err_res = {
            "status": "FAIL",
            "error": str(e),
            "prompt": "An error occurred. Please enter your rate per kWh manually:",
            "require_input": "manual_rate"
        }
        state["step"] = "force_manual"
        return json.dumps(err_res, indent=2)
