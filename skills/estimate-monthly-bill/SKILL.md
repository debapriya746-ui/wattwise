---
name: estimate-monthly-bill
description: |
  Estimates monthly electricity bill from 
  daily kWh totals of all appliances.
  Use only AFTER calculate-daily-usage has run 
  for every appliance.
  Use only AFTER user confirms all assumptions.
  Do NOT use before verification is complete.
  Do NOT show a single exact number ever.
---

## Formula
total_daily_kwh = sum of all appliance daily_kwh
total_monthly_kwh = total_daily_kwh x 30
energy_cost = apply slab rates if available
              OR total_monthly_kwh x rate
total_bill = energy_cost + fixed_monthly_charge

## Confidence Rules
high:   user confirmed all inputs AND
        user entered rate directly
medium: some inputs assumed from database OR
        weather adjusted hours used
low:    rate from country average AND
        hours not confirmed by user

## Uncertainty Margin
high confidence:   margin = 0.10
medium confidence: margin = 0.18
low confidence:    margin = 0.25

low_bill      = expected_bill x (1 - margin)
high_bill     = expected_bill x (1 + margin)

Always show margin source in output:
"Range based on medium confidence: ±18%"

## Rate Priority
1. user_entered
2. utility_state_average
3. country_average
4. ask_user

## Output Format
{
  "total_daily_kwh": 33.5,
  "total_monthly_kwh": 1005,
  "rate": 7.0,
  "rate_source": "user_entered",
  "expected_bill": 7035,
  "low_bill": 6369,
  "high_bill": 7700,
  "margin": 0.10,
  "confidence": "high",
  "margin_explanation": "Range based on 
    high confidence: ±10%",
  "fixed_charge": 20,
  "total_expected": 7055,
  "usage_confidence": "high",
  "cost_confidence": "high",
  "disclaimer": "This is a rough estimate,
    not your exact electricity bill"
}

## Fallbacks
If slab rates unavailable:
  → use flat rate x total_monthly_kwh

If rate completely unavailable after all 
priority steps exhausted:
  → set cost_confidence to "low"
  → show message: "Rate not found. Please 
    enter your electricity rate manually"
  → do not calculate bill until rate provided

If total_daily_kwh is zero:
  → do not calculate
  → show message: "No appliance data found.
    Please add at least one appliance first"

If fixed_charge not provided by user:
  → set fixed_charge to 0
  → note in output: "Fixed charge not included"

If calculation produces unrealistic result:
  high > 3x expected:
    → flag result as suspicious
    → show message: "This estimate seems 
      unusually high. Please verify your 
      appliance inputs"

