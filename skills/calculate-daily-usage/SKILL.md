---
name: calculate-daily-usage
description: |
  Calculates daily electricity consumption in kWh
  for a single appliance.
  User never enters wattage directly.
  Agent collects simple user-friendly inputs and
  looks up wattage from appliance database.
  Do NOT use for monthly calculations.
---

## User Friendly Inputs
AC: tonnage + star rating + age
Fridge: size + star rating
Washing Machine: capacity + load type
TV: screen size + display type
Fan: fan type
Water Heater: tank capacity
Lights: bulb type + count
Microwave: type

## Hours Collection
Do NOT ask "how many hours".
Ask lifestyle questions:
- "When do you use this appliance?"
- Agent suggests hours based on answer + weather
- User confirms or corrects via Human-in-the-Loop

## Formula
daily_kWh = (wattage_watts x hours_per_day) / 1000
Wattage always fetched from appliance database.
Never ask user for wattage directly.

## Weather Adjustment
CDD = max(0, avg_temp_F - 65)
HDD = max(0, 65 - avg_temp_F)
Adjust only appliances user confirms they own:
AC, heater, fan, heat pump, dehumidifier

## Output format
{
  "appliance": "AC",
  "size": "1.5 ton",
  "star_rating": 3,
  "age": "less than 3 years",
  "watts": 1500,
  "hours": 9,
  "daily_kwh": 13.5,
  "weather_adjusted": true,
  "confidence": "medium"
}
