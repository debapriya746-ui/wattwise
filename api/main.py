import json
import logging
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from agents import location_agent, weather_agent, tariff_agent, calculator_agent, advisor_agent, orchestrator
from mcp_server import appliance_client
from api.session_store import store

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("api")

app = FastAPI(title="WattWise API")


def _get_session(session_id: str) -> dict:
    session = store.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


# ---------- Sessions ----------

@app.post("/sessions")
def create_session():
    session_id = store.create()
    return {"session_id": session_id}


@app.get("/sessions/{session_id}")
def get_session(session_id: str):
    return _get_session(session_id)


# ---------- Location ----------

class AutoDetectRequest(BaseModel):
    client_ip: Optional[str] = None


@app.post("/sessions/{session_id}/location/auto-detect")
def location_auto_detect(session_id: str, body: AutoDetectRequest):
    session = _get_session(session_id)
    result = location_agent.auto_detect_location(body.client_ip)
    if result.get("success"):
        session["city"] = result["city"]
        session["country"] = result["country"]
        session["pincode"] = result["pincode"]
        session["location_resolved"] = True
    return result


class PincodeRequest(BaseModel):
    pincode: str


@app.post("/sessions/{session_id}/location/pincode")
def location_pincode(session_id: str, body: PincodeRequest):
    session = _get_session(session_id)
    if not location_agent.validate_pincode(body.pincode):
        return {"success": False, "error": "invalid_format"}
    result = location_agent.resolve_pincode_api(body.pincode)
    if result.get("success"):
        session["city"] = result["city"]
        session["country"] = result["country"]
        session["pincode"] = body.pincode
        session["location_resolved"] = True
    return result


class ManualLocationRequest(BaseModel):
    city: str
    country: str


@app.post("/sessions/{session_id}/location/manual")
def location_manual(session_id: str, body: ManualLocationRequest):
    session = _get_session(session_id)
    if not body.city or not body.country:
        raise HTTPException(status_code=400, detail="city and country are required")
    session["city"] = body.city
    session["country"] = body.country
    session["pincode"] = ""
    session["location_resolved"] = True
    return {"success": True, "city": body.city, "country": body.country}


class ConfirmLocationRequest(BaseModel):
    city: str
    country: str
    pincode: str = ""


@app.post("/sessions/{session_id}/location/confirm")
def location_confirm(session_id: str, body: ConfirmLocationRequest):
    """Confirms location and immediately fetches weather + tariff, mirroring app.py's
    'Confirm & Continue' button on the location screen."""
    session = _get_session(session_id)
    session["city"] = body.city
    session["country"] = body.country
    session["pincode"] = body.pincode

    weather_res_str = weather_agent.get_weather(body.city, body.country)
    weather_res = json.loads(weather_res_str)
    if weather_res.get("status") in ["SUCCESS", "FALLBACK"]:
        session["weather"] = weather_res
    else:
        session["weather"] = {
            "temp": 72.0, "temp_min": 65.0, "temp_max": 79.0,
            "humidity": 50, "feels_like": 72.0, "cdd": 5.0, "hdd": 0.0,
            "condition": "Clear", "source": "fallback", "status": "FALLBACK",
        }

    tariff_res = tariff_agent.lookup_tariff_db(body.city, body.country)
    if tariff_res.get("found"):
        session["tariff"] = {
            "rate": tariff_res["data"]["rate"],
            "rate_source": tariff_res["source"],
            "fixed_charge": tariff_res["data"]["fixed_charge"],
            "slab_based": tariff_res["data"]["slab_based"],
            "slabs": tariff_res["data"]["slabs"],
            "currency": tariff_res["currency"],
            "confidence": "high" if tariff_res["source"] == "state_average" else "medium",
        }
    else:
        session["tariff"] = {
            "rate": 0.15,
            "rate_source": "country_average",
            "fixed_charge": 0.0,
            "slab_based": False,
            "slabs": [],
            "currency": "USD",
            "confidence": "low",
        }

    return {"weather": session["weather"], "tariff": session["tariff"]}


# ---------- Home profile ----------

class ProfileRequest(BaseModel):
    home_type: str
    members: str
    mode: str


@app.post("/sessions/{session_id}/profile")
def set_profile(session_id: str, body: ProfileRequest):
    session = _get_session(session_id)
    session["home_type"] = body.home_type
    session["members"] = body.members
    session["mode"] = body.mode
    return {"success": True}


# ---------- Appliances ----------

class QuickApplianceRequest(BaseModel):
    usage_level: str


@app.post("/sessions/{session_id}/appliances/quick")
def generate_quick_appliances(session_id: str, body: QuickApplianceRequest):
    session = _get_session(session_id)
    session["usage_level"] = body.usage_level
    m_val = 5 if session["members"] == "5+" else int(session["members"])
    apps = orchestrator.generate_quick_mode_appliances(session["home_type"], m_val, body.usage_level)
    session["appliances"] = apps
    return {"appliances": apps}


class AddApplianceRequest(BaseModel):
    appliance: str
    size: Optional[str] = None
    star_rating: Optional[int] = None
    age: Optional[str] = None
    hours: float


@app.post("/sessions/{session_id}/appliances")
def add_appliance(session_id: str, body: AddApplianceRequest):
    session = _get_session(session_id)
    watts_res = json.loads(appliance_client.get_appliance_wattage(body.appliance, body.size, body.star_rating, body.age))
    watts = watts_res.get("watts_expected", 100)
    new_app = {
        "appliance": body.appliance,
        "watts": watts,
        "hours": body.hours,
        "star_rating": body.star_rating if body.star_rating else 3,
        "age": body.age if body.age else "",
        "size": body.size if body.size else "",
        "owned": True,
        "confirmed": True,
    }
    session["appliances"].append(new_app)
    return {"appliance": new_app, "appliances": session["appliances"]}


class AddCustomApplianceRequest(BaseModel):
    name: str
    watts: float
    hours: float
    weather_type: str = "none"


@app.post("/sessions/{session_id}/appliances/custom")
def add_custom_appliance(session_id: str, body: AddCustomApplianceRequest):
    session = _get_session(session_id)
    if not body.name.strip():
        raise HTTPException(status_code=400, detail="name is required")
    new_app = {
        "appliance": body.name.strip(),
        "watts": body.watts,
        "hours": body.hours,
        "star_rating": 3,
        "age": "",
        "size": "",
        "is_custom": True,
        "weather_type": body.weather_type.lower(),
        "owned": True,
        "confirmed": True,
    }
    session["appliances"].append(new_app)
    return {"appliance": new_app, "appliances": session["appliances"]}


@app.delete("/sessions/{session_id}/appliances/{index}")
def remove_appliance(session_id: str, index: int):
    session = _get_session(session_id)
    if index < 0 or index >= len(session["appliances"]):
        raise HTTPException(status_code=404, detail="Appliance index out of range")
    session["appliances"].pop(index)
    return {"appliances": session["appliances"]}


# ---------- Verify / edit ----------

class VerifyUpdateRequest(BaseModel):
    city: Optional[str] = None
    country: Optional[str] = None
    pincode: Optional[str] = None
    temp: Optional[float] = None
    humidity: Optional[float] = None
    cdd: Optional[float] = None
    hdd: Optional[float] = None
    rate: Optional[float] = None
    fixed_charge: Optional[float] = None
    home_type: Optional[str] = None
    members: Optional[str] = None
    usage_level: Optional[str] = None


@app.patch("/sessions/{session_id}")
def update_session(session_id: str, body: VerifyUpdateRequest):
    session = _get_session(session_id)
    if body.city is not None:
        session["city"] = body.city
    if body.country is not None:
        session["country"] = body.country
    if body.pincode is not None:
        session["pincode"] = body.pincode
    if body.temp is not None:
        session["weather"]["temp"] = body.temp
    if body.humidity is not None:
        session["weather"]["humidity"] = body.humidity
    if body.cdd is not None:
        session["weather"]["cdd"] = body.cdd
    if body.hdd is not None:
        session["weather"]["hdd"] = body.hdd
    if body.rate is not None:
        session["tariff"]["rate"] = body.rate
    if body.fixed_charge is not None:
        session["tariff"]["fixed_charge"] = body.fixed_charge

    regenerate_quick = session["mode"] == "Quick Mode" and (
        body.home_type is not None or body.members is not None or body.usage_level is not None
    )
    if body.home_type is not None:
        session["home_type"] = body.home_type
    if body.members is not None:
        session["members"] = body.members
    if body.usage_level is not None:
        session["usage_level"] = body.usage_level

    if regenerate_quick:
        m_val = 5 if session["members"] == "5+" else int(session["members"])
        session["appliances"] = orchestrator.generate_quick_mode_appliances(
            session["home_type"], m_val, session["usage_level"]
        )

    return session


# ---------- Calculate / tips / feedback ----------

@app.post("/sessions/{session_id}/calculate")
def calculate(session_id: str):
    session = _get_session(session_id)
    result_str = calculator_agent.calculate_bill(
        session["appliances"], session["weather"], session["tariff"], assumptions_confirmed=True
    )
    result = json.loads(result_str)
    session["calculation_results"] = result
    return result


@app.get("/sessions/{session_id}/tips")
def tips(session_id: str):
    session = _get_session(session_id)
    if not session["calculation_results"]:
        raise HTTPException(status_code=400, detail="Run /calculate first")
    return advisor_agent.generate_tips_list(session["calculation_results"], session["weather"])


class FeedbackRequest(BaseModel):
    actual_bill: Optional[float] = None
    actual_kwh: Optional[float] = None


@app.post("/sessions/{session_id}/feedback")
def feedback(session_id: str, body: FeedbackRequest):
    session = _get_session(session_id)
    feedback_input = {}
    if body.actual_kwh:
        feedback_input = {"feedback": {"actual_kwh": body.actual_kwh}}
    elif body.actual_bill:
        feedback_input = {"feedback": {"actual_bill": body.actual_bill}}
    else:
        raise HTTPException(status_code=400, detail="actual_bill or actual_kwh is required")

    advisor_state = {"step": "ask_feedback", "calculator_output": session["calculation_results"]}
    result = json.loads(advisor_agent.process_step(advisor_state, feedback_input))
    session["feedback_status"] = result.get("message")
    return result
