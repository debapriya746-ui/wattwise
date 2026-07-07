import sys
import os
import json
import traceback

# Add parent directory to path to import agents
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from agents import location_agent
from agents import weather_agent
from agents import tariff_agent
from agents import calculator_agent
from agents import advisor_agent
from agents import orchestrator

def run_tc001(case):
    """TC001: location_denied"""
    state = case["state"].copy()
    res = json.loads(location_agent.process_step(state, case["user_input"]))
    assert state["step"] == case["expected_next_step"]
    assert res.get("require_input") == case["expected_input_requirement"]

def run_tc002(case):
    """TC002: pincode_fails"""
    state = case["state"].copy()
    res = json.loads(location_agent.process_step(state, case["user_input"]))
    assert state["step"] == case["expected_next_step"]
    assert res.get("require_input") == case["expected_input_requirement"]

def run_tc003(case):
    """TC003: weather_api_fails"""
    state = case["state"].copy()
    user_input = case["user_input"].copy()
    # To simulate API failure, we pass an unknown city and check manual prompt
    res = orchestrator.run_weather_step(state, user_input)
    assert res.get("require_input") == case["expected_input_requirement"]
    assert case["expected_prompt_keyword"] in res.get("prompt", "")

def run_tc004(case):
    """TC004: rate_not_found"""
    state = case["state"].copy()
    res = json.loads(tariff_agent.process_step(state, case["user_input"]))
    assert state["step"] == case["expected_next_step"]
    assert res.get("require_input") == case["expected_input_requirement"]

def run_tc005(case):
    """TC005: unrealistic_rate"""
    state = case["state"].copy()
    res = json.loads(tariff_agent.process_step(state, case["user_input"]))
    assert res.get("error") == case["expected_error"]
    assert res.get("require_input") == case["expected_input_requirement"]

def run_tc006(case):
    """TC006: hot_day_cdd"""
    res = json.loads(calculator_agent.calculate_bill(
        case["appliances"],
        case["weather_data"],
        {"rate": 0.15},
        assumptions_confirmed=True
    ))
    ac = res["appliances"][0]
    assert ac["weather_adjusted"] == case["expected_weather_adjusted"]
    assert ac["daily_kwh"] >= case["expected_daily_kwh_min"]

def run_tc007(case):
    """TC007: cold_day_hdd"""
    res = json.loads(calculator_agent.calculate_bill(
        case["appliances"],
        case["weather_data"],
        {"rate": 0.15},
        assumptions_confirmed=True
    ))
    heater = res["appliances"][0]
    assert heater["weather_adjusted"] == case["expected_weather_adjusted"]
    assert heater["daily_kwh"] >= case["expected_daily_kwh_min"]

def run_tc008(case):
    """TC008: over_budget"""
    res = json.loads(calculator_agent.calculate_bill(
        case["appliances"],
        case["weather_data"],
        case["tariff_data"],
        assumptions_confirmed=True
    ))
    assert res["total_monthly_kwh"] == case["expected_monthly_kwh"]
    assert res["slab_boundary_alert"] == case["expected_slab_boundary_alert"]

def run_tc009(case):
    """TC009: actual_kwh_feedback"""
    state = case["state"].copy()
    res = json.loads(advisor_agent.process_step(state, case["user_input"]))
    assert res.get("calibration_status") == case["expected_calibration_status"]
    assert res.get("calibration_factor") == case["expected_calibration_factor"]

def run_tc010(case):
    """TC010: actual_bill_only_feedback"""
    state = case["state"].copy()
    res = json.loads(advisor_agent.process_step(state, case["user_input"]))
    assert res.get("calibration_status") == case["expected_calibration_status"]
    assert res.get("note") == case["expected_note"]

RUNNERS = {
    "TC001": run_tc001,
    "TC002": run_tc002,
    "TC003": run_tc003,
    "TC004": run_tc004,
    "TC005": run_tc005,
    "TC006": run_tc006,
    "TC007": run_tc007,
    "TC008": run_tc008,
    "TC009": run_tc009,
    "TC010": run_tc010
}

def run_test_case(case) -> bool:
    """Executes a single test case using its registered runner."""
    case_id = case["id"]
    name = case["name"]
    runner = RUNNERS.get(case_id)
    
    if not runner:
        print(f"[-] {case_id} ({name}): FAIL - No runner found")
        return False
        
    try:
        runner(case)
        print(f"[+] {case_id} ({name}): PASS")
        return True
    except Exception as e:
        print(f"[-] {case_id} ({name}): FAIL - {str(e)}")
        # Print traceback for debugging
        traceback.print_exc()
        return False

def main():
    cases_file = os.path.join(os.path.dirname(__file__), 'eval_cases.json')
    with open(cases_file, 'r') as f:
        cases = json.load(f)
        
    print(f"Running {len(cases)} evaluation test cases...\n" + "="*50)
    
    passed_count = 0
    for case in cases:
        if run_test_case(case):
            passed_count += 1
            
    print("="*50)
    print(f"EVALUATION SUMMARY: {passed_count}/{len(cases)} cases PASSED.")
    
    if passed_count == len(cases):
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()
