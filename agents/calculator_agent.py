import json
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("calculator_agent")

WEATHER_SENSITIVE_COOLING = ["ac", "fan", "dehumidifier"]
WEATHER_SENSITIVE_HEATING = ["heater", "heat pump"]

DAYS_IN_MONTH = 30

def calculate_appliance_usage(appliance: dict, weather: dict) -> dict:
    """
    Calculates daily kWh usage for a single appliance, adjusting for CDD/HDD if owned and sensitive.
    """
    name = appliance.get("appliance", "").lower().strip()
    watts = float(appliance.get("watts", 0.0))
    hours = float(appliance.get("hours", 0.0))
    owned = appliance.get("owned", True)
    
    adjusted_hours = hours
    weather_adjusted = False
    
    if owned:
        cdd = float(weather.get("cdd", 0.0))
        hdd = float(weather.get("hdd", 0.0))
        
        # Applies CDD/HDD adjustment only for sensitive appliances
        is_cooling = any(k in name for k in WEATHER_SENSITIVE_COOLING) or (appliance.get("weather_type") == "cooling")
        is_heating = any(k in name for k in WEATHER_SENSITIVE_HEATING) or (appliance.get("weather_type") == "heating")
        
        if is_cooling:
            if cdd > 0:
                adjusted_hours = hours * (1.0 + 0.03 * cdd)
                weather_adjusted = True
                logger.info(f"Decision: Applied CDD adjustment of {cdd} to {appliance.get('appliance')}. Hours: {hours} -> {adjusted_hours:.2f}")
        elif is_heating:
            if hdd > 0:
                adjusted_hours = hours * (1.0 + 0.03 * hdd)
                weather_adjusted = True
                logger.info(f"Decision: Applied HDD adjustment of {hdd} to {appliance.get('appliance')}. Hours: {hours} -> {adjusted_hours:.2f}")
                
        # Cap hours at 24
        adjusted_hours = min(24.0, max(0.0, adjusted_hours))

    daily_kwh = (watts * adjusted_hours) / 1000.0 if owned else 0.0
    
    return {
        "appliance": appliance.get("appliance"),
        "watts": watts,
        "hours": hours,
        "adjusted_hours": round(adjusted_hours, 2),
        "daily_kwh": round(daily_kwh, 2),
        "weather_adjusted": weather_adjusted,
        "owned": owned
    }

def calculate_slab_cost(monthly_kwh: float, slabs: list, default_rate: float) -> float:
    """
    Calculates the energy cost based on slab rates. If slabs are empty, uses the flat rate.
    """
    if not slabs:
        cost = monthly_kwh * default_rate
        logger.info(f"Decision: Calculating cost using flat rate {default_rate}. Cost = {cost:.2f}")
        return cost
        
    cost = 0.0
    remaining_kwh = monthly_kwh
    prev_limit = 0.0
    
    logger.info(f"Decision: Calculating slab-based tariff cost for {monthly_kwh} kWh.")
    for slab in slabs:
        limit = slab.get("limit")
        rate = float(slab.get("rate", default_rate))
        
        if limit is None:
            # Last open slab
            cost += remaining_kwh * rate
            logger.info(f"Decision: Final open slab charged {remaining_kwh:.2f} kWh at rate {rate}.")
            break
            
        slab_size = float(limit) - prev_limit
        kwh_in_slab = min(remaining_kwh, slab_size)
        cost += kwh_in_slab * rate
        remaining_kwh -= kwh_in_slab
        prev_limit = float(limit)
        
        logger.info(f"Decision: Charged {kwh_in_slab:.2f} kWh in slab up to {limit} at rate {rate}.")
        if remaining_kwh <= 0:
            break
            
    return cost

def check_slab_alert(monthly_kwh: float, slabs: list) -> dict:
    """
    Checks if the monthly kWh is within 50 units of the next slab boundary.
    """
    if not slabs:
        return {"alert": False, "message": ""}
        
    for slab in slabs:
        limit = slab.get("limit")
        if limit is not None:
            limit_val = float(limit)
            if monthly_kwh < limit_val:
                diff = limit_val - monthly_kwh
                if diff <= 50.0:
                    msg = f"Alert: You are within {diff:.1f} kWh of the next slab boundary ({limit_val} kWh)."
                    logger.info(f"Decision: Slab boundary alert triggered. Next boundary: {limit_val}, Diff: {diff:.2f}")
                    return {"alert": True, "message": msg, "next_limit": limit_val, "diff": round(diff, 1)}
                break
                
    return {"alert": False, "message": ""}

def determine_margin(confidence: str) -> float:
    """Helper to return uncertainty margin based on confidence level."""
    if confidence == "high":
        return 0.10
    elif confidence == "medium":
        return 0.18
    return 0.25

def get_overall_confidence(usage_conf: str, cost_conf: str) -> str:
    """Resolves overall confidence based on usage and cost confidence levels."""
    levels = {"high": 3, "medium": 2, "low": 1}
    u_val = levels.get(usage_conf.lower(), 1)
    c_val = levels.get(cost_conf.lower(), 1)
    
    min_val = min(u_val, c_val)
    if min_val == 3:
        return "high"
    elif min_val == 2:
        return "medium"
    return "low"

def calculate_bill(
    appliances: list,
    weather: dict,
    tariff: dict,
    assumptions_confirmed: bool
) -> str:
    """
    Executes the monthly bill estimation.
    Enforces that verification must be complete before running.
    Returns structured JSON only.
    """
    logger.info("Decision: Calculator Agent received calculation request.")
    
    if not assumptions_confirmed:
        logger.error("Decision: Calculation blocked because user has not confirmed assumptions.")
        return json.dumps({
            "status": "FAIL",
            "error": "Verification incomplete. Calculations cannot run before user confirms all assumptions.",
            "message": "Please verify and confirm your assumptions before running the calculator."
        }, indent=2)
        
    try:
        # 1. Calculate each appliance
        computed_appliances = []
        total_daily_kwh = 0.0
        
        for app in appliances:
            res = calculate_appliance_usage(app, weather)
            computed_appliances.append(res)
            total_daily_kwh += res["daily_kwh"]
            
        # 2. Monthly totals
        total_monthly_kwh = total_daily_kwh * DAYS_IN_MONTH
        logger.info(f"Decision: Total daily kWh = {total_daily_kwh:.2f}. Total monthly kWh = {total_monthly_kwh:.2f}")
        
        # 3. Energy cost and total bill
        default_rate = float(tariff.get("rate", 0.15))
        slabs = tariff.get("slabs", [])
        fixed_charge = float(tariff.get("fixed_charge", 0.0))
        
        expected_bill = calculate_slab_cost(total_monthly_kwh, slabs, default_rate)
        
        # 4. Confidence and margin calculations
        cost_confidence = tariff.get("confidence", "low")
        # Usage confidence is high if all hours were user-confirmed
        unconfirmed_exists = any(not app.get("confirmed", True) for app in appliances)
        usage_confidence = "medium" if unconfirmed_exists else "high"
        
        overall_conf = get_overall_confidence(usage_confidence, cost_confidence)
        margin = determine_margin(overall_conf)
        
        low_bill = expected_bill * (1.0 - margin)
        high_bill = expected_bill * (1.0 + margin)
        total_expected = expected_bill + fixed_charge
        
        # 5. Slab alerts
        alert_res = check_slab_alert(total_monthly_kwh, slabs)
        
        output = {
            "appliances": computed_appliances,
            "total_daily_kwh": round(total_daily_kwh, 2),
            "total_monthly_kwh": round(total_monthly_kwh, 2),
            "expected_bill": round(expected_bill, 2),
            "low_bill": round(low_bill, 2),
            "high_bill": round(high_bill, 2),
            "margin": margin,
            "confidence": overall_conf,
            "margin_explanation": f"±{int(margin*100)}% {overall_conf} confidence",
            "fixed_charge": round(fixed_charge, 2),
            "total_expected": round(total_expected, 2),
            "usage_confidence": usage_confidence,
            "cost_confidence": cost_confidence,
            "slab_boundary_alert": alert_res["alert"],
            "currency": tariff.get("currency", "USD"),
            "rate_source": tariff.get("rate_source", "unknown"),
            "disclaimer": "This is a rough estimate, not your exact electricity bill"
        }
        
        if alert_res["alert"]:
            output["slab_boundary_message"] = alert_res["message"]
            
        logger.info(f"Decision: Calculation complete. Expected monthly bill = {total_expected:.2f} {output['currency']}")
        return json.dumps(output, indent=2)
        
    except Exception as e:
        logger.error(f"Decision: Exception in calculator: {str(e)}")
        err_res = {
            "status": "FAIL",
            "error": str(e),
            "message": "Error occurred during calculation."
        }
        return json.dumps(err_res, indent=2)
