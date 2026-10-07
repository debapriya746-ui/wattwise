"""
Guardrail tests: assert the safety rules WattWise claims in policies.yaml
actually hold in the calculator's behavior. No network, no LLM -- these
exercise the pure pipeline logic in agents/calculator_agent.py directly.
"""
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agents import calculator_agent

# A simple, weather-neutral setup (cdd/hdd = 0 so no climate scaling kicks in).
APPLIANCES = [{"appliance": "Fridge", "watts": 250, "hours": 24, "owned": True, "confirmed": True}]
WEATHER = {"cdd": 0.0, "hdd": 0.0}
TARIFF = {
    "rate": 8.0,
    "fixed_charge": 50.0,
    "slab_based": False,
    "slabs": [],
    "confidence": "high",
    "currency": "INR",
    "rate_source": "state_average",
}


def _run(confirmed: bool) -> dict:
    return json.loads(calculator_agent.calculate_bill(APPLIANCES, WEATHER, TARIFF, confirmed))


def test_calculation_is_blocked_before_confirmation():
    """Guardrail: no calculation can run until the user confirms the inputs."""
    result = _run(confirmed=False)
    assert result["status"] == "FAIL"
    # A blocked run must not leak any estimate numbers.
    assert "total_expected" not in result
    assert "low_bill" not in result


def test_confirmed_estimate_is_always_a_range():
    """Guardrail: the estimate is a low/high range, never a single number."""
    result = _run(confirmed=True)
    for key in ("low_bill", "expected_bill", "high_bill", "total_expected"):
        assert key in result
    assert result["low_bill"] < result["expected_bill"] < result["high_bill"]


def test_estimate_always_carries_a_disclaimer():
    """Guardrail: every estimate is labeled a rough estimate, not an exact bill."""
    result = _run(confirmed=True)
    assert "disclaimer" in result
    assert "estimate" in result["disclaimer"].lower()


def test_rate_source_is_always_reported():
    """Guardrail: the tariff source is always shown so confidence is transparent."""
    result = _run(confirmed=True)
    assert result["rate_source"] == "state_average"
    assert "confidence" in result


def test_lower_confidence_widens_the_margin():
    """Guardrail: less certainty must mean a wider range, never a false-precise one."""
    assert calculator_agent.determine_margin("high") < calculator_agent.determine_margin("medium")
    assert calculator_agent.determine_margin("medium") < calculator_agent.determine_margin("low")
