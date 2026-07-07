- Never assume, always confirm with user
- Never store GPS or exact address
- Always return structured JSON not free text
- Always show ranges not single numbers
- Every API call must have a fallback
- Always log every agent decision
- Stack: Python, Google ADK, Streamlit, MCP
- Disclaimer in UI and README:
  "WattWise provides rough estimates, not exact bill predictions."
- Never add code not asked for in instructions
- Location resolution priority:
  1. Auto-detect city + country + pincode 
     if permission granted
  2. If denied, ask for pincode only and 
     resolve city + country from it
  3. If pincode fails, ask for city + 
     country manually

