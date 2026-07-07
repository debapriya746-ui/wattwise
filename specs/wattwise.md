Scenario: Location permission granted
  Given the user opens WattWise
  When the user grants location permission
  Then the agent auto-detects city, country 
  and pincode automatically
  And confirms "Is this your location: 
  [city, country, pincode]?" before continuing

Scenario: Location permission denied
  Given the user opens WattWise
  When the user denies location permission
  Then the agent asks user to enter pincode only
  When the user enters pincode
  Then the agent resolves city and country 
  automatically from the pincode
  And confirms "Is this your location: 
  [city, country]?" before continuing

Scenario: Invalid or ambiguous pincode
  Given the user enters a pincode manually
  When the pincode cannot be resolved
  Then the agent asks user to enter 
  city and country manually as fallback


Scenario: Weather fetch success
  Given the location is known
  When the Weather Agent calls Google Weather API
  Then it returns temp, humidity, feels_like, 
  condition, source, status as structured JSON

Scenario: Weather fetch failure
  Given the Google Weather API is unavailable
  When the Weather Agent tries to fetch weather
  Then the agent asks user to enter temperature manually

Scenario: Appliance ownership check
  Given the location and weather are known
  When the agent asks about appliances
  Then it only applies weather adjustment to 
  appliances the user confirms they own

Scenario: Verification before calculation
  Given all inputs are collected
  When the agent shows the assumption summary
  Then the user must confirm or edit before 
  any calculation runs

Scenario: Monthly bill estimate with ranges
  Given the user confirms all assumptions
  When the Calculator Agent runs
  Then it shows low, expected, and high estimate
  And never shows a single exact number
  And shows usage confidence and cost confidence

Scenario: Feedback loop
  Given the monthly estimate is shown
  When the user enters their actual bill
  Then if actual kWh given, update usage calibration
  And if actual bill only given, update cautiously
  with a note about unknown fees
