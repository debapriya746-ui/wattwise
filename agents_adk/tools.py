"""
Tool functions for the WattWise ADK agent.

These wrap the existing deterministic business logic in agents/*.py as plain
Python functions the LLM can call directly. They deliberately do NOT reuse the
*_agent.process_step() state machines — those were built to drive a fixed
Streamlit wizard through named internal steps (ask_permission, ask_pincode, ...),
which is the wrong shape for a conversational agent. Here, the agent itself
decides when to call which atomic function based on the conversation; the
step order lives in the agent's instruction, not in code.

calculate_bill and generate_saving_tips call straight into the same
agents/*.py functions used by the API's v1 path — the safety rules
(never calculate before confirmation, never return a single number) are
enforced there, in code, not by trusting the LLM to behave.
"""
import json

from agents import location_agent, weather_agent, tariff_agent, calculator_agent, advisor_agent


def detect_location_from_ip(client_ip: str) -> dict:
    """Auto-detects the user's city, country, and postal code from their IP address.

    Args:
        client_ip: The user's public IP address, if known. Pass an empty string
            if unavailable.

    Returns:
        A dict with success (bool), and if successful: city, country, pincode.
    """
    return location_agent.auto_detect_location(client_ip or None)


def resolve_location_from_pincode(pincode: str) -> dict:
    """Resolves a city and country from a postal/zip/pincode the user typed.

    Args:
        pincode: The postal code as entered by the user.

    Returns:
        A dict with success (bool), and if successful: city, country. If
        success is False, ask the user for their city and country directly
        instead of retrying this tool.
    """
    if not location_agent.validate_pincode(pincode):
        return {"success": False, "error": "invalid_format"}
    return location_agent.resolve_pincode_api(pincode)


def get_weather(city: str, country: str) -> dict:
    """Fetches current weather and computes cooling/heating degree days (CDD/HDD)
    for a city. CDD/HDD drive weather-based adjustments to appliance usage
    estimates (e.g. more AC hours on hot days).

    Args:
        city: City name.
        country: Country name.

    Returns:
        A dict with temp, humidity, cdd, hdd, condition, source, status.
        Always returns usable values, even on failure (falls back to
        reasonable defaults), so this never blocks the conversation.
    """
    result = json.loads(weather_agent.get_weather(city, country))
    if result.get("status") in ("SUCCESS", "FALLBACK"):
        return result
    return {
        "temp": 72.0, "temp_min": 65.0, "temp_max": 79.0, "humidity": 50,
        "feels_like": 72.0, "cdd": 5.0, "hdd": 0.0, "condition": "Clear",
        "source": "fallback", "status": "FALLBACK",
    }


def lookup_tariff(city: str, country: str) -> dict:
    """Looks up the local electricity tariff for a city/country, ready to pass
    straight into calculate_bill's `tariff` argument.

    Args:
        city: City name.
        country: Country name.

    Returns:
        A dict with rate, rate_source, fixed_charge, slab_based, slabs,
        currency, confidence. Falls back to a low-confidence generic rate
        if the city/country isn't in the tariff database.
    """
    result = tariff_agent.lookup_tariff_db(city, country)
    if result.get("found"):
        return {
            "rate": result["data"]["rate"],
            "rate_source": result["source"],
            "fixed_charge": result["data"]["fixed_charge"],
            "slab_based": result["data"]["slab_based"],
            "slabs": result["data"]["slabs"],
            "currency": result["currency"],
            "confidence": "high" if result["source"] == "state_average" else "medium",
        }
    return {
        "rate": 0.15, "rate_source": "country_average", "fixed_charge": 0.0,
        "slab_based": False, "slabs": [], "currency": "USD", "confidence": "low",
    }


def calculate_bill(appliances: list[dict], weather: dict, tariff: dict, assumptions_confirmed: bool) -> dict:
    """Calculates the estimated monthly electricity bill as a low/expected/high
    range. This NEVER returns a single exact number, by design.

    IMPORTANT: only call this with assumptions_confirmed=True after the user
    has explicitly confirmed their location, weather, tariff, and appliance
    list are correct — read back a summary and get a clear yes first. If they
    have not confirmed yet, do not call this tool. Calling it with
    assumptions_confirmed=False is rejected on purpose and returns a FAIL
    status; this is enforced in code, not something you need to remember to
    check yourself.

    Args:
        appliances: List of appliance dicts, each with appliance, watts,
            hours, owned (bool).
        weather: The weather dict from get_weather (needs cdd and hdd).
        tariff: The tariff dict from lookup_tariff.
        assumptions_confirmed: True only if the user has explicitly confirmed
            everything above in this conversation.

    Returns:
        A dict with low_bill, total_expected, high_bill, currency,
        disclaimer, confidence, margin_explanation — or status "FAIL" with
        an error message if assumptions_confirmed was False.
    """
    return json.loads(calculator_agent.calculate_bill(appliances, weather, tariff, assumptions_confirmed))


def generate_saving_tips(calculation_result: dict, weather: dict) -> dict:
    """Generates up to 3 personalized electricity-saving tips based on a
    completed bill calculation. Only call this after calculate_bill has
    succeeded.

    Args:
        calculation_result: The dict returned by calculate_bill.
        weather: The same weather dict used in that calculation.

    Returns:
        A dict with tips (list of action/why/savings/difficulty/impact),
        biggest_consumer, and slab_boundary_alert if the user is close to a
        cheaper tariff bracket.
    """
    return advisor_agent.generate_tips_list(calculation_result, weather)
