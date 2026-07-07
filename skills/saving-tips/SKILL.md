---
name: saving-tips
description: |
  Analyzes appliance usage and gives top 3 
  personalized saving tips with estimated savings.
  Use only AFTER monthly bill is calculated.
  Use only AFTER verification is complete.
  Do NOT give generic tips.
  Every tip must show specific estimated saving 
  in user's local currency.
  Run ONLY if user explicitly requests tips.
  Never run automatically.
---

## Trigger Rule
Always ask user first:
"Would you like to see ways to reduce 
this bill?"
Run this skill ONLY if user says YES.
If user says NO, end session cleanly.

## How to Generate Tips
Step 1: Sort all appliances by daily_kwh 
        highest to lowest
Step 2: Focus on top 2 energy consumers
Step 3: For each calculate saving if usage 
        reduced by 1 hour per day
Step 4: Check if star rating upgrade saves money
Step 5: Check if user is near a slab boundary
        If yes flag as highest priority tip

## Slab Boundary Check
If total_monthly_kwh is within 50 units of 
next slab boundary:
  → Always make this Tip 1
  → Show exact units to reduce
  → Show exact bill saving from dropping slab

## Tip Format
Each tip must include:
- What to do (specific action)
- Why it helps (one line)
- Estimated monthly saving in local currency
- Difficulty: Easy / Medium / Hard
- Impact: Low / Medium / High

## Fallbacks
If only one appliance added:
  → Still give 3 tips but note limited data
If all appliances already 5-star:
  → Focus tips on usage hours reduction
If rate not user confirmed:
  → Show saving as range not exact number
If user in cold climate (HDD > CDD):
  → Focus tips on heater not AC

## Output Format
Internal use only. Never show raw JSON to user.
Show tips in clean readable format in UI.

{
  "tips": [
    {
      "rank": 1,
      "action": "Reduce AC by 1 hour daily",
      "why": "AC is your biggest energy user",
      "monthly_saving_expected": 450,
      "monthly_saving_low": 380,
      "monthly_saving_high": 520,
      "difficulty": "Easy",
      "impact": "High"
    }
  ],
  "biggest_consumer": "AC",
  "slab_boundary_alert": true,
  "slab_boundary_message": "You are 45 units 
    from the next slab. Reducing usage saves 
    an extra ₹300/month",
  "confidence": "medium"
}

## Saving Estimate Margin
Apply same confidence margin as bill estimate:
high confidence:   margin = 0.10
medium confidence: margin = 0.18
low confidence:    margin = 0.25

monthly_saving_low = expected x (1 - margin)
monthly_saving_high = expected x (1 + margin)

