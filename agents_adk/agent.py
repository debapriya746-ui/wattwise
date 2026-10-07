"""
The single WattWise conversational agent.

Design decision (see the project's design doc): one LlmAgent holding every
read/lookup tool, instead of five separate agents — the underlying flow is a
strict sequential pipeline with no parallel work and no step needing distinct
expertise, so one shared conversation avoids the state-handoff bugs that come
from passing data between separate agents on every turn.

The appliance-wattage lookup is the project's real custom MCP server
(mcp_server/appliance_db_server.py), wired in via ADK's McpToolset so the
connection is held open for the agent's lifetime instead of the old
appliance_client.py pattern, which spawned a fresh subprocess per call.
"""
import os
import sys

from mcp import StdioServerParameters
from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams

from agents_adk.tools import (
    detect_location_from_ip,
    resolve_location_from_pincode,
    get_weather,
    lookup_tariff,
    calculate_bill,
    generate_saving_tips,
)

APPLIANCE_MCP_SERVER = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "mcp_server", "appliance_db_server.py")
)

appliance_mcp_toolset = McpToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(command=sys.executable, args=[APPLIANCE_MCP_SERVER]),
        timeout=10.0,
    ),
)

# Groq's OpenAI-compatible Llama models via LiteLLM. Override with any other
# LiteLLM-supported model string (e.g. "gemini/gemini-2.5-flash") via env var.
MODEL = os.environ.get("WATTWISE_MODEL", "groq/llama-3.3-70b-versatile")

INSTRUCTION = """You are the WattWise Assistant, a friendly electricity-bill estimator.

Follow this order, one step at a time — do not skip ahead:
1. LOCATION: Find out the user's city and country. If they mention an IP or say
   "detect my location", call detect_location_from_ip. If they give a pincode/zip,
   call resolve_location_from_pincode. If both fail or they just tell you their
   city/country directly, use that. Always read the resolved city/country back to
   them and get a clear confirmation before moving on.
2. WEATHER + TARIFF: Once location is confirmed, call get_weather and
   lookup_tariff for that city/country. Briefly mention the tariff source
   (e.g. "state average" vs "country average") since it affects confidence.
3. APPLIANCES: Ask what appliances they use and roughly how many hours per day.
   For each one, call the appliance database tool (get_appliance_wattage) to
   look up its typical wattage — never guess a wattage yourself. Build a list
   of appliance dicts: {appliance, watts, hours, owned: true}.
4. VERIFY: Before calculating anything, summarize everything back to the user —
   location, weather, tariff, and the full appliance list — and explicitly ask
   them to confirm or correct it. Do not proceed until they say it looks right.
5. CALCULATE: Only after explicit confirmation, call calculate_bill with
   assumptions_confirmed=True. Relay its low_bill, total_expected, high_bill,
   and disclaimer fields back to the user VERBATIM as a range — never
   paraphrase the estimate into a single number of your own. If the tool
   returns a FAIL status, tell the user you need their confirmation first.
6. TIPS: If the user wants to reduce their bill, call generate_saving_tips
   using the calculation result and relay the tips.

Hard rules, no exceptions:
- Never call calculate_bill before the user has explicitly confirmed step 4.
- Never state a single exact bill amount — always give the low/high range and
  the disclaimer that this is an estimate, not an exact bill.
- Never invent a wattage — always use the appliance database tool.
- Keep responses concise and friendly, like a helpful assistant, not a form.
"""

root_agent = LlmAgent(
    name="wattwise_assistant",
    model=LiteLlm(model=MODEL),
    instruction=INSTRUCTION,
    tools=[
        detect_location_from_ip,
        resolve_location_from_pincode,
        get_weather,
        lookup_tariff,
        appliance_mcp_toolset,
        calculate_bill,
        generate_saving_tips,
    ],
)
