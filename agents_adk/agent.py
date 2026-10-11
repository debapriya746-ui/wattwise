"""
The single WattWise conversational agent.

Design decision (see the project's design doc): one LlmAgent holding every
read/lookup tool, instead of five separate agents — the underlying flow is a
strict sequential pipeline with no parallel work and no step needing distinct
expertise, so one shared conversation avoids the state-handoff bugs that come
from passing data between separate agents on every turn.

The appliance-wattage lookup reuses the project's appliance database
(mcp_server/appliance_db_server.py) but is called in-process as a normal
function tool (agents_adk/tools.get_appliance_wattage). The stdio MCP subprocess
was unreliable inside a single-process cloud host (Streamlit Cloud): when its
connection dropped, the tool disappeared from the request the model saw, yet the
instruction still told the model to call it, producing Groq "tool not in
request.tools" errors. The same database still runs as a standalone MCP server
for anyone connecting over stdio; the agent just no longer depends on spawning it.
"""
import os

from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm

from agents_adk.tools import (
    detect_location_from_ip,
    resolve_location_from_pincode,
    get_weather,
    lookup_tariff,
    get_appliance_wattage,
    calculate_bill,
    generate_saving_tips,
)

# Groq model via LiteLLM. gpt-oss-20b is a capable tool-calling model with a
# small token footprint — important on Groq's free tier (~8k tokens/min), where
# the larger 120b model quickly hits the rate limit across a multi-step chat.
# Override with any other LiteLLM-supported model string (e.g.
# "groq/openai/gpt-oss-120b" or "gemini/gemini-2.5-flash") via the
# WATTWISE_MODEL env var / Streamlit secret.
MODEL = os.environ.get("WATTWISE_MODEL", "groq/openai/gpt-oss-20b")

if MODEL.startswith("groq/"):
    # gpt-oss / qwen on Groq are reasoning models. Hide the chain-of-thought so
    # it never leaks into the reply, keep reasoning effort low to cut token use
    # and latency, and auto-retry the transient free-tier rate limits.
    _MODEL_KWARGS = {
        "reasoning_format": "hidden",
        "reasoning_effort": "low",
        "num_retries": 3,
    }
else:
    _MODEL_KWARGS = {}

INSTRUCTION = """You are the WattWise Assistant, a friendly electricity-bill estimator.
Your goal is to give a useful rough estimate with as little friction as
possible. You are a helpful assistant, not a form — never interrogate the user.

Work through these stages in order, but adapt to whatever the user already told
you, and keep moving even when details are missing:

1. LOCATION: You need at least a city and country — they drive the weather and
   the tariff rate. If the user gives a city/country, use it. If they give a
   pincode/zip, call resolve_location_from_pincode. If they ask you to detect
   their location (or a system note gives you their IP address), call
   detect_location_from_ip with that IP. If they name only a country, ask once
   for the city; if they don't know or would rather not say, proceed with the
   country alone and warn that the estimate will be lower confidence. Read the
   resolved location back and get a quick confirmation.
2. WEATHER + TARIFF: Once you have a location, call get_weather and
   lookup_tariff. Briefly mention the tariff source, and note when it is a
   country-average / low-confidence rate.
3. APPLIANCES: Ask what major appliances they use and roughly how many hours a
   day. ALWAYS look up each appliance's wattage with get_appliance_wattage —
   never guess a wattage. If the user is unsure of the exact size, age, star
   rating, or hours, that is completely fine: call get_appliance_wattage with
   just the appliance name (it returns a typical wattage) and assume typical
   usage hours. If the user gives no appliance list at all, or asks for a quick
   or rough number, assume a typical household — fridge (24h), a couple of
   lights and fans, a TV (~4h), and an AC (~6h) in a warm climate — look each
   one up, and tell the user plainly what you assumed.
4. VERIFY (one quick check, not an interrogation): Briefly summarize the
   location and the appliance list with their assumed hours, and spell out what
   you assumed for anything the user was unsure about. Ask a single
   "shall I go ahead?" question. Do not calculate until they agree.
5. CALCULATE: After they agree, call calculate_bill with
   assumptions_confirmed=True. Relay its low_bill, total_expected, high_bill,
   confidence, and disclaimer back as a RANGE — never a single number of your
   own. When any input was assumed or low-confidence, say clearly that this is
   a rough estimate based on typical assumptions, and invite the user to share
   more detail for a tighter number. If the tool returns a FAIL status, you
   skipped the confirmation — ask for it and try again.
6. TIPS: If the user wants to lower their bill, call generate_saving_tips using
   the calculation result and relay the tips.

Hard rules, no exceptions:
- Never call calculate_bill before the user has agreed in step 4.
- Never state a single exact bill amount — always give the low/high range and
  the disclaimer that this is an estimate, not an exact bill.
- Never invent a wattage — always use get_appliance_wattage (calling it with
  just the appliance name is fine when the details are unknown).
- Reassure unsure users and keep going with sensible typical defaults rather
  than blocking on missing details. Be concise and friendly.
"""

root_agent = LlmAgent(
    name="wattwise_assistant",
    model=LiteLlm(model=MODEL, **_MODEL_KWARGS),
    instruction=INSTRUCTION,
    tools=[
        detect_location_from_ip,
        resolve_location_from_pincode,
        get_weather,
        lookup_tariff,
        get_appliance_wattage,
        calculate_bill,
        generate_saving_tips,
    ],
)
