import json
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("advisor_agent")

DAYS_IN_MONTH = 30

def calculate_hourly_saving(appliance: dict, avg_rate: float) -> float:
    """Calculates monthly savings in currency if usage is reduced by 1 hour per day."""
    watts = float(appliance.get("watts", 0.0))
    hours = float(appliance.get("hours", 0.0))
    
    if hours <= 0:
        return 0.0
        
    kwh_saved_daily = watts / 1000.0
    kwh_saved_monthly = kwh_saved_daily * DAYS_IN_MONTH
    saving = kwh_saved_monthly * avg_rate
    logger.info(f"Decision: Calculated 1h reduction saving for {appliance.get('appliance')}: {saving:.2f} currency.")
    return saving

def calculate_upgrade_saving(appliance: dict, avg_rate: float) -> float:
    """Calculates monthly savings if upgrading a non-5-star appliance to 5-star (saves 20%)."""
    name = appliance.get("appliance", "").lower()
    daily_kwh = float(appliance.get("daily_kwh", 0.0))
    star = appliance.get("star_rating", 3)
    
    if star >= 5 or not any(k in name for k in ["ac", "fridge", "refrigerator"]):
        return 0.0
        
    # Standard upgrade saving is 20%
    kwh_saved_monthly = (daily_kwh * DAYS_IN_MONTH) * 0.20
    saving = kwh_saved_monthly * avg_rate
    logger.info(f"Decision: Calculated star upgrade saving for {appliance.get('appliance')}: {saving:.2f} currency.")
    return saving

def get_climate_priority_appliances(appliances: list, weather: dict) -> list:
    """
    Sorts appliances taking into account climate awareness.
    If HDD > CDD, prioritize heater. If CDD > HDD, prioritize AC.
    """
    cdd = float(weather.get("cdd", 0.0))
    hdd = float(weather.get("hdd", 0.0))
    
    # Sort primarily by daily kWh consumption
    sorted_apps = sorted(appliances, key=lambda x: x.get("daily_kwh", 0.0), reverse=True)
    
    # Apply climate awareness shifts
    if hdd > cdd:
        # Prioritize heater
        logger.info("Decision: Cold climate detected (HDD > CDD). Prioritizing heating appliances.")
        heaters = [a for a in sorted_apps if any(k in a.get("appliance", "").lower() for k in ["heater", "heat pump"])]
        others = [a for a in sorted_apps if a not in heaters]
        return heaters + others
    elif cdd > hdd:
        # Prioritize AC
        logger.info("Decision: Hot climate detected (CDD > HDD). Prioritizing cooling appliances.")
        coolers = [a for a in sorted_apps if any(k in a.get("appliance", "").lower() for k in ["ac", "fan"])]
        others = [a for a in sorted_apps if a not in coolers]
        return coolers + others
        
    return sorted_apps

def compile_tip_details(action: str, why: str, expected_saving: float, margin: float, diff: str, imp: str) -> dict:
    """Helper to assemble a single tip object with confidence margins applied."""
    return {
        "action": action,
        "why": why,
        "monthly_saving_expected": round(expected_saving),
        "monthly_saving_low": round(expected_saving * (1.0 - margin)),
        "monthly_saving_high": round(expected_saving * (1.0 + margin)),
        "difficulty": diff,
        "impact": imp
    }

def generate_tips_list(calc_data: dict, weather: dict) -> dict:
    """
    Generates the top 3 saving tips based on Sorted appliances, slab boundaries,
    and upgrades.
    """
    appliances = [a for a in calc_data.get("appliances", []) if a.get("owned", True) and a.get("daily_kwh", 0.0) > 0]
    total_monthly_kwh = float(calc_data.get("total_monthly_kwh", 1.0))
    expected_bill = float(calc_data.get("expected_bill", 0.0))
    avg_rate = expected_bill / total_monthly_kwh if total_monthly_kwh > 0 else float(calc_data.get("rate", 0.15))
    
    confidence = calc_data.get("confidence", "medium")
    margin = float(calc_data.get("margin", 0.18))
    
    # 1. Climate awareness sorting
    sorted_apps = get_climate_priority_appliances(appliances, weather)
    
    tips = []
    biggest = sorted_apps[0].get("appliance") if sorted_apps else "None"
    
    # 2. Step 5: Check slab boundary alert
    slab_alert = calc_data.get("slab_boundary_alert", False)
    if slab_alert:
        msg = calc_data.get("slab_boundary_message", "You are close to next slab boundary.")
        # Extrapolate extra savings from dropping slab
        slab_saving = avg_rate * 30 + 100.0  # Assumed drop benefit
        tips.append(compile_tip_details(
            "Drop to lower slab rate",
            msg,
            slab_saving,
            margin,
            "Medium",
            "High"
        ))
        logger.info("Decision: Slab boundary alert is active. Inserted as Tip 1.")
        
    # 3. Add appliance usage tips
    if len(sorted_apps) == 1:
        app = sorted_apps[0]
        # Tip 1/2: Reduce usage hours
        h_saving = calculate_hourly_saving(app, avg_rate)
        if h_saving > 0:
            tips.append(compile_tip_details(f"Reduce {app['appliance']} by 1 hour daily", f"{app['appliance']} is your only appliance.", h_saving, margin, "Easy", "Medium"))
        # Tip 3: Upgrade if AC/Fridge
        up_saving = calculate_upgrade_saving(app, avg_rate)
        if up_saving > 0:
            tips.append(compile_tip_details(f"Upgrade {app['appliance']} to 5-star", "Upgrading older appliances saves up to 20%.", up_saving, margin, "Hard", "High"))
    elif len(sorted_apps) >= 2:
        # Focus on top 2 consumers
        for app in sorted_apps[:2]:
            h_saving = calculate_hourly_saving(app, avg_rate)
            if h_saving > 0 and len(tips) < 3:
                tips.append(compile_tip_details(f"Reduce {app['appliance']} by 1 hour daily", f"{app['appliance']} is a top energy consumer.", h_saving, margin, "Easy", "Medium"))
                
        # Upgrades check
        for app in sorted_apps[:2]:
            up_saving = calculate_upgrade_saving(app, avg_rate)
            if up_saving > 0 and len(tips) < 3:
                tips.append(compile_tip_details(f"Upgrade {app['appliance']} to 5-star", f"Upgraded {app['appliance']} increases efficiency.", up_saving, margin, "Hard", "High"))
                
    # 4. Standard fallback tip if we still need 3
    if len(tips) < 3:
        tips.append(compile_tip_details("Switch off standby devices", "Unplugging idle electronics prevents phantom loads.", 10.0 * avg_rate, margin, "Easy", "Low"))
        
    # Slice to top 3
    tips = tips[:3]
    for idx, t in enumerate(tips):
        t["rank"] = idx + 1
        
    # Format slab boundary details
    slab_msg = calc_data.get("slab_boundary_message", "") if slab_alert else ""
    
    return {
        "tips": tips,
        "biggest_consumer": biggest,
        "slab_boundary_alert": slab_alert,
        "slab_boundary_message": slab_msg,
        "confidence": confidence
    }

def handle_feedback(user_input: dict, state: dict) -> dict:
    """Processes calibration feedback loop from user."""
    feedback = user_input.get("feedback", {})
    actual_kwh = feedback.get("actual_kwh")
    actual_bill = feedback.get("actual_bill")
    
    res = {"feedback_received": True}
    
    if actual_kwh is not None:
        logger.info(f"Decision: Calibrating model using actual consumption = {actual_kwh} kWh.")
        res["calibration_status"] = "CALIBRATED_KWH"
        res["calibration_factor"] = round(float(actual_kwh) / float(state["calculator_output"].get("total_monthly_kwh", 1.0)), 2)
        res["message"] = f"Usage calibration updated directly based on your actual consumption of {actual_kwh} kWh."
    elif actual_bill is not None:
        logger.info(f"Decision: Calibrating model using actual bill = {actual_bill}.")
        res["calibration_status"] = "CALIBRATED_COST_CAUTIOUS"
        res["note"] = "Difference may include unknown fees"
        res["message"] = "Estimate calibrated cautiously. Note: Differences in final bill amount may include unknown utility taxes or fixed fees."
    else:
        logger.info("Decision: Completed session cleanly without specific calibration inputs.")
        res["feedback_received"] = False
        res["message"] = "Session completed cleanly."
        
    state["step"] = "completed"
    return res

def process_step(state: dict, user_input: dict = None) -> str:
    """
    Main entrypoint state machine for Advisor Agent.
    Returns structured JSON only.
    """
    if user_input is None:
        user_input = {}
        
    current_step = state.get("step", "ask_show_tips")
    logger.info(f"Decision: Processing advisor step. Current step='{current_step}'")
    
    try:
        if current_step == "ask_show_tips":
            show_tips = user_input.get("show_tips", False)
            if "show_tips" in user_input:
                if show_tips:
                    logger.info("Decision: User consented to receive saving tips.")
                    tips_res = generate_tips_list(state["calculator_output"], state.get("weather_data", {}))
                    state["tips"] = tips_res["tips"]
                    state["biggest_consumer"] = tips_res["biggest_consumer"]
                    state["slab_boundary_alert"] = tips_res["slab_boundary_alert"]
                    state["slab_boundary_message"] = tips_res["slab_boundary_message"]
                    state["step"] = "ask_feedback"
                    
                    return json.dumps({
                        "tips": state["tips"],
                        "biggest_consumer": state["biggest_consumer"],
                        "slab_boundary_alert": state["slab_boundary_alert"],
                        "slab_boundary_message": state["slab_boundary_message"],
                        "feedback_received": False,
                        "confidence": tips_res["confidence"],
                        "prompt": "How close was this to your actual bill?",
                        "require_input": "feedback"
                    }, indent=2)
                else:
                    logger.info("Decision: User declined saving tips. Ending session cleanly.")
                    state["step"] = "completed"
                    return json.dumps({
                        "status": "COMPLETED",
                        "message": "Session ended cleanly. Thank you for using WattWise!"
                    }, indent=2)
            else:
                return json.dumps({
                    "prompt": "Would you like to see ways to reduce this bill?",
                    "require_input": "show_tips_consent",
                    "resolved": False
                }, indent=2)
                
        elif current_step == "ask_feedback":
            if "feedback" in user_input:
                feedback_res = handle_feedback(user_input, state)
                output = {
                    "tips": state.get("tips", []),
                    "biggest_consumer": state.get("biggest_consumer", ""),
                    "slab_boundary_alert": state.get("slab_boundary_alert", False),
                    "slab_boundary_message": state.get("slab_boundary_message", ""),
                    "feedback_received": True,
                    "confidence": state["calculator_output"].get("confidence", "medium")
                }
                output.update(feedback_res)
                return json.dumps(output, indent=2)
            else:
                return json.dumps({
                    "prompt": "How close was this to your actual bill?",
                    "require_input": "feedback",
                    "resolved": False
                }, indent=2)
        elif current_step == "completed":
            return json.dumps({
                "status": "COMPLETED",
                "message": "Session completed."
            }, indent=2)
        else:
            logger.error(f"Decision: Unknown advisor step: {current_step}")
            return json.dumps({"status": "FAIL", "error": "Invalid state step"}, indent=2)
            
    except Exception as e:
        logger.error(f"Decision: Exception in advisor step processor: {str(e)}")
        return json.dumps({
            "status": "FAIL",
            "error": str(e),
            "message": "Error occurred while generating tips or processing feedback."
        }, indent=2)
