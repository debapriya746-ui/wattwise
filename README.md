# WattWise ⚡
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

## How to Run
First, install the required dependencies:
```powershell
pip install -r requirements.txt
```

Then, launch the Streamlit application:
```powershell
python -m streamlit run app.py
```

## Disclaimer
> [!IMPORTANT]
> **WattWise provides rough estimates, not exact bill predictions.**

Weather data: Uses Open-Meteo API (free, global, no API key required) for real-time weather fetching.
