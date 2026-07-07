import json
import logging
from agents import location_agent
from agents import weather_agent
from agents import tariff_agent
from agents import calculator_agent
from agents import advisor_agent

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("orchestrator")

def init_session_state(mode: str = "detailed") -> dict:
    """Initializes the session state dictionary."""
    return {
        "step": "location",
        "mode": mode,
        "location_state": {"step": "ask_permission"},
        "tariff_state": {"step": "ask_user_rate"},
        "advisor_state": {"step": "ask_show_tips"},
        "collected_data": {
            "city": None,
            "country": None,
            "pincode": None,
            "weather": {},
            "tariff": {},
            "appliances": []
        },
        "verification_confirmed": False,
        "calculator_output": {},
        "advisor_output": {},
        "errors": []
    }

def generate_quick_mode_appliances(home_type: str, members: int, usage_level: str) -> list:
    """Generates default appliance list based on Quick Mode inputs."""
    logger.info(f"Decision: Generating Quick Mode appliances for home_type='{home_type}', members={members}, usage='{usage_level}'")
    
    # Scale hours based on usage level
    usage_mult = 0.7 if usage_level.lower() == "low" else (1.3 if usage_level.lower() == "high" else 1.0)
    
    apps = [
        {"appliance": "Fridge", "watts": 250, "hours": 24, "star_rating": 3, "age": "3-5 years", "size": "medium", "owned": True, "confirmed": True},
        {"appliance": "AC", "watts": 1500, "hours": round(6 * usage_mult, 1), "star_rating": 3, "age": "less than 3 years", "size": "1.5 ton", "owned": members > 1, "confirmed": True},
        {"appliance": "Lights", "watts": 9, "hours": round(5 * usage_mult, 1), "star_rating": 5, "age": "less than 3 years", "size": "LED", "owned": True, "confirmed": True},
        {"appliance": "Fan", "watts": 75, "hours": round(10 * usage_mult, 1), "star_rating": 3, "age": "3-5 years", "size": "ceiling", "owned": True, "confirmed": True},
        {"appliance": "TV", "watts": 80, "hours": round(4 * usage_mult, 1), "star_rating": 4, "age": "3-5 years", "size": "43 inch", "owned": True, "confirmed": True}
    ]
    return apps

def run_location_step(state: dict, user_input: dict) -> dict:
    """Runs Location Agent step in the orchestrator pipeline."""
    loc_input = user_input.get("location", user_input)
    res_str = location_agent.process_step(state["location_state"], loc_input)
    res = json.loads(res_str)
    
    if res.get("status") == "SUCCESS":
        logger.info("Decision: Location Agent completed successfully. Transitioning to Weather Agent.")
        state["collected_data"]["city"] = res.get("city")
        state["collected_data"]["country"] = res.get("country")
        state["collected_data"]["pincode"] = res.get("pincode")
        state["step"] = "weather"
        return {"next_immediate": True}
        
    return res

def run_weather_step(state: dict, user_input: dict) -> dict:
    """Runs Weather Agent step in the orchestrator pipeline."""
    city = state["collected_data"]["city"]
    country = state["collected_data"]["country"]
    
    logger.info(f"Decision: Invoking Weather Agent for city='{city}', country='{country}'")
    try:
        # Check if we need to handle manual temperature fallback input
        if user_input.get("action") == "enter_manual_weather":
            logger.info("Decision: Processing manual weather temperature input.")
            temp = float(user_input.get("temp", 72.0))
            avg_temp_f = temp
            cdd = max(0.0, avg_temp_f - 65.0)
            hdd = max(0.0, 65.0 - avg_temp_f)
            state["collected_data"]["weather"] = {
                "temp": temp, "temp_min": temp - 10, "temp_max": temp + 10,
                "humidity": 50, "feels_like": temp, "cdd": cdd, "hdd": hdd,
                "condition": "Manual Entry", "source": "user_entered", "status": "SUCCESS"
            }
            state["step"] = "tariff"
            return {"next_immediate": True}
            
        weather_res_str = weather_agent.get_weather(city, country)
        res = json.loads(weather_res_str)
        
        if res.get("status") in ["SUCCESS", "FALLBACK"]:
            state["collected_data"]["weather"] = res
            state["step"] = "tariff"
            return {"next_immediate": True}
        else:
            logger.warning("Decision: Weather Agent failed. Offering manual temperature fallback prompt.")
            return {
                "prompt": "Weather service is currently unavailable. Please enter your local average temperature manually (Fahrenheit):",
                "require_input": "manual_weather_temp",
                "action": "enter_manual_weather"
            }
    except Exception as e:
        logger.error(f"Decision: Weather Agent execution exception: {str(e)}")
        return {
            "prompt": "Weather service encountered an error. Please enter your local average temperature manually (Fahrenheit):",
            "require_input": "manual_weather_temp",
            "action": "enter_manual_weather",
            "error": str(e)
        }

def run_tariff_step(state: dict, user_input: dict) -> dict:
    """Runs Tariff Agent step in the orchestrator pipeline."""
    tariff_input = user_input.get("tariff", user_input)
    # Pass location data to tariff state for lookup context
    state["tariff_state"]["city"] = state["collected_data"]["city"]
    state["tariff_state"]["country"] = state["collected_data"]["country"]
    
    res_str = tariff_agent.process_step(state["tariff_state"], tariff_input)
    res = json.loads(res_str)
    
    if res.get("status") == "SUCCESS":
        logger.info("Decision: Tariff Agent completed successfully. Transitioning to Verification step.")
        state["collected_data"]["tariff"] = res
        state["step"] = "verification"
        return {"next_immediate": True}
        
    return res

def run_verification_step(state: dict, user_input: dict) -> dict:
    """Runs Verification step showing all data to user before any calculations."""
    # Populate Quick Mode appliances if detailed list is empty and mode is quick
    if state["mode"] == "quick" and not state["collected_data"]["appliances"]:
        quick_in = user_input.get("quick_mode_inputs", {})
        apps = generate_quick_mode_appliances(
            quick_in.get("home_type", "Apartment"),
            int(quick_in.get("members", 2)),
            quick_in.get("usage_level", "Medium")
        )
        state["collected_data"]["appliances"] = apps
    elif state["mode"] == "detailed" and "appliances" in user_input:
        state["collected_data"]["appliances"] = user_input.get("appliances", [])
        
    # Check confirmation
    if user_input.get("confirmed", False) or user_input.get("verification_confirmed", False):
        logger.info("Decision: User confirmed verification step. Transitioning to Calculator Agent.")
        state["verification_confirmed"] = True
        state["step"] = "calculator"
        return {"next_immediate": True}
        
    logger.info("Decision: Displaying collected data details to user for verification.")
    return {
        "step": "verification",
        "prompt": "Does everything look correct? Please confirm or edit before I calculate.",
        "require_input": "verification_confirmation",
        "summary": {
            "location": {
                "city": state["collected_data"]["city"],
                "country": state["collected_data"]["country"],
                "pincode": state["collected_data"]["pincode"]
            },
            "weather": state["collected_data"]["weather"],
            "tariff": state["collected_data"]["tariff"],
            "appliances": state["collected_data"]["appliances"]
        }
    }

def run_calculator_step(state: dict) -> dict:
    """Runs Calculator Agent calculation logic."""
    logger.info("Decision: Executing Calculator Agent calculation.")
    res_str = calculator_agent.calculate_bill(
        state["collected_data"]["appliances"],
        state["collected_data"]["weather"],
        state["collected_data"]["tariff"],
        state["verification_confirmed"]
    )
    res = json.loads(res_str)
    
    if res.get("status") != "FAIL":
        state["calculator_output"] = res
        state["step"] = "advisor"
        return {"next_immediate": True}
    else:
        logger.error(f"Decision: Calculator Agent execution failed: {res.get('error')}")
        state["step"] = "verification"
        return {
            "prompt": f"Calculation failed: {res.get('message')}. Returning to verification.",
            "require_input": "verification_confirmation",
            "error": res.get("error")
        }

def run_advisor_step(state: dict, user_input: dict) -> dict:
    """Runs Advisor Agent step in the orchestrator pipeline."""
    advisor_input = user_input.get("advisor", user_input)
    state["advisor_state"]["calculator_output"] = state["calculator_output"]
    state["advisor_state"]["weather_data"] = state["collected_data"]["weather"]
    
    res_str = advisor_agent.process_step(state["advisor_state"], advisor_input)
    res = json.loads(res_str)
    
    if res.get("status") == "COMPLETED" or state["advisor_state"].get("step") == "completed":
        logger.info("Decision: Advisor Agent completed. Finalizing session and clearing memory.")
        state["advisor_output"] = res
        state["step"] = "completed"
        
        # Enforce Session Privacy: Clear all user data from memory
        state["collected_data"] = {}
        state["calculator_output"] = {}
        state["location_state"] = {}
        state["tariff_state"] = {}
        state["advisor_state"] = {}
        logger.info("Decision: Session completed. Memory cleared of all user personal data.")
        
        return {
            "status": "COMPLETED",
            "message": "Session complete. All personal data cleared from active memory."
        }
        
    return res

def process_session(state: dict, user_input: dict = None) -> str:
    """
    Core state router controlling the orchestrator execution flow.
    Returns structured JSON only.
    """
    if user_input is None:
        user_input = {}
        
    # Check for global mode toggle
    if "mode" in user_input:
        state["mode"] = user_input["mode"]
        
    logger.info(f"Decision: Routing session step. Current step='{state.get('step')}'")
    
    try:
        # Loop to immediately execute steps that do not require user-wait (like weather call)
        max_loops = 5
        for _ in range(max_loops):
            current_step = state.get("step")
            
            if current_step == "location":
                res = run_location_step(state, user_input)
            elif current_step == "weather":
                res = run_weather_step(state, user_input)
            elif current_step == "tariff":
                res = run_tariff_step(state, user_input)
            elif current_step == "verification":
                res = run_verification_step(state, user_input)
            elif current_step == "calculator":
                res = run_calculator_step(state)
            elif current_step == "advisor":
                res = run_advisor_step(state, user_input)
            elif current_step == "completed":
                return json.dumps({
                    "status": "COMPLETED",
                    "message": "Session completed. All data cleared."
                }, indent=2)
            else:
                return json.dumps({"status": "FAIL", "error": "Invalid state step"}, indent=2)
                
            # If the step completed internally and flagged a transition, loop immediately
            if isinstance(res, dict) and res.get("next_immediate"):
                user_input = {} # Clear inputs for immediate transition steps
                continue
            else:
                return json.dumps(res, indent=2)
                
        return json.dumps({"status": "FAIL", "error": "Max step transitions reached"}, indent=2)
        
    except Exception as e:
        logger.error(f"Decision: Orchestrator failed to process session: {str(e)}")
        # Safe fallback response
        state["step"] = "location"
        return json.dumps({
            "status": "FAIL",
            "message": "The system encountered an unexpected error. We have restarted the location resolution.",
            "error": str(e)
        }, indent=2)
