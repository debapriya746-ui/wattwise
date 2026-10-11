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

INSTRUCTION = """You are WattWise, a concise, friendly electricity-bill estimator.
Reply in 1-3 short sentences. Respond to what the user actually said. Call tools
silently — only speak to ask for something you need or to give a result. Ask for
any missing essentials in ONE short question, not step by step. Do not narrate
your plan or pre-list assumptions.

To estimate a bill, gather in this order: location (city + country) -> weather +
tariff -> appliances -> one confirmation -> calculation.

- Location: use the city/country the user gives, a pincode
  (resolve_location_from_pincode), or detect_location_from_ip if they ask or an
  IP note is present. Confirm the resolved location in one short line.
- Weather + tariff: call get_weather and lookup_tariff; just use the results,
  don't narrate them.
- Appliances: ask what major appliances they use and rough daily hours. Look up
  each wattage with get_appliance_wattage (never guess; calling it with just the
  name is fine). If the user is unsure or wants a quick number, quietly assume a
  typical household and note in ONE line that you used typical values.
- Confirm: give a one-line summary and ask "shall I go ahead?" once. Do not
  calculate before they agree.
- Calculate: call calculate_bill with assumptions_confirmed=True. Give the
  low-expected-high range and the disclaimer; if anything was assumed, add one
  short line that it's a rough estimate.
- Tips: only if the user asks, call generate_saving_tips and give the top tips
  briefly.

Hard rules: never calculate before the user agrees; never give a single exact
number (always a range + the estimate disclaimer); never invent a wattage. Keep
every reply short.
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
