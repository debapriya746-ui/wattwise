---
title: WattWise
emoji: ⚡
colorFrom: yellow
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
---

# WattWise ⚡

[![CI/CD Pipeline](https://github.com/debapriya746-ui/wattwise/actions/workflows/ci.yml/badge.svg)](https://github.com/debapriya746-ui/wattwise/actions/workflows/ci.yml)

An agentic electricity bill estimator that helps you understand, review, and reduce your household energy costs.

## Track
**Concierge Agents**

## Course Concepts Demonstrated
1. **Multi-Agent Coordination (GCP ADK / Python)**: Powered by an orchestrator coordinating 6 distinct, single-purpose agents (Location, Weather, Tariff, Verification, Calculator, and Advisor).
2. **Custom Model Context Protocol (MCP) Server**: Integrates a custom Python-based MCP server (`appliance-db-server`) executing wattage lookups with calculated low/high margins.
3. **Human-in-the-Loop Verification**: A strict verification gate prevents calculator execution until the user manually confirms or edits location, weather parameters, appliances, and rates.
4. **Agent Skills**: Guided by custom Markdown skill specifications (`calculate-daily-usage`, `estimate-monthly-bill`, `saving-tips`, `code-reviewer`) with distinct trigger, margin, and validation rules.
5. **CI/CD Integration**: Employs GitHub Actions pipeline (`ci.yml`) validating the project on every push using a 10-test-case validation suite (`run_evals.py`).

## Architecture Flow Diagram
```mermaid
graph TD
    User([User Input]) --> LocationAgent[1. Location Agent]
    LocationAgent -->|City/Country/Pincode| WeatherAgent[2. Weather Agent]
    WeatherAgent -->|CDD/HDD Metrics| TariffAgent[3. Tariff Agent]
    TariffAgent -->|Regional Rates & Slabs| Verification{4. Verification Screen}
    
    Verification -->|Edit Inputs| User
    Verification -->|Confirm & Verify| CalculatorAgent[5. Calculator Agent]
    
    CalculatorAgent -->|Usage & Cost Ranges| AdvisorAgent[6. Advisor Agent]
    AdvisorAgent -->|Personalized Savings Tips| User
    
    subgraph Custom Skills
        Skill1[calculate-daily-usage]
        Skill2[estimate-monthly-bill]
        Skill3[saving-tips]
    end
    
    subgraph Database Server
        MCPServer[(appliance_db_server MCP)]
    end
    
    CalculatorAgent -.-> Skill1
    CalculatorAgent -.-> Skill2
    AdvisorAgent -.-> Skill3
    User -.->|Add Appliances| MCPServer
    MCPServer -.->|Wattage Lookup| User
```

## Two ways to use it
WattWise offers two modes, chosen from the sidebar:
- **🧭 Guided Wizard** — the deterministic step-by-step flow (location → profile → usage → verify → estimate → tips). No API key needed.
- **💬 AI Assistant** — a single conversational **LLM agent** (`agents_adk/agent.py`) that holds every lookup/calculation tool (location, weather, tariff, the appliance-wattage MCP server, calculator, saving-tips) and decides which to call based on the conversation. The safety rules (never calculate before you confirm; always a low/high range, never one exact number; never invent a wattage) are enforced in the tool code, not left to the model. Requires a Groq API key.

## How to Run
First, install the required dependencies:
```powershell
pip install -r requirements.txt
```

Then, launch the Streamlit application:
```powershell
python -m streamlit run app.py
```

To enable the AI Assistant locally, copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` and add your free [Groq](https://console.groq.com) key.

## Deploy (Streamlit Community Cloud — free, no Docker)
The app runs as a single process: `app.py` boots the FastAPI backend in a background thread (`embedded_backend.py`), so there is nothing else to host.
1. Push this repo to GitHub.
2. At [share.streamlit.io](https://share.streamlit.io), create an app pointing at `app.py` on this branch.
3. In the app's **Settings → Secrets**, add:
   ```toml
   GROQ_API_KEY = "your-groq-api-key-here"
   ```
   (Omit the key to ship the Guided Wizard only.)
4. Deploy. The AI Assistant tab is live once the key is set.

> The combined Docker image (`Dockerfile`) and Render blueprint (`render.yaml`) still work for a two-process deploy; set `WATTWISE_ENABLE_ADK=1` and provide `GROQ_API_KEY` there to enable the agent.

## Disclaimer
> [!IMPORTANT]
> **WattWise provides rough estimates, not exact bill predictions.**

Weather data: Uses Open-Meteo API (free, global, no API key required) for real-time weather fetching.
