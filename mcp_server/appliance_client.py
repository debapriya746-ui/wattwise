import asyncio
import json
import os
import sys
import logging
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Setup client-level logging
logger = logging.getLogger("appliance_client")

# Path to the actual MCP server script
SERVER_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "appliance_db_server.py"))

async def _call_mcp_tool_async(tool_name: str, arguments: dict) -> str:
    """
    Connects to the appliance MCP server via stdio transport, 
    initializes session, calls a tool, and returns the result.
    """
    server_params = StdioServerParameters(
        command=sys.executable,
        args=[SERVER_PATH],
        env=os.environ.copy()
    )
    
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, arguments=arguments)
            if result.content and len(result.content) > 0:
                return result.content[0].text
            raise ValueError(f"No content returned from tool '{tool_name}'")

def call_mcp_tool_sync(tool_name: str, arguments: dict) -> str:
    """Synchronous wrapper around the async MCP client call."""
    try:
        return asyncio.run(_call_mcp_tool_async(tool_name, arguments))
    except Exception as e:
        logger.error(f"Error calling MCP tool '{tool_name}' with args {arguments}: {str(e)}")
        # Construct a fallback JSON error message compatible with the server's contract
        fallback = {
            "appliance": arguments.get("appliance", "unknown"),
            "found": False,
            "error": str(e),
            "watts_expected": 150,  # safe fallback average
            "watts_range": [100, 200]
        }
        return json.dumps(fallback)

def get_appliance_wattage(appliance: str, size: str = None, star_rating: int = None, age: str = None) -> str:
    """Calls get_appliance_wattage through the stdio MCP client."""
    args = {
        "appliance": appliance,
        "size": size,
        "star_rating": star_rating,
        "age": age
    }
    return call_mcp_tool_sync("get_appliance_wattage", args)

def list_appliance_options(appliance: str) -> str:
    """Calls list_appliance_options through the stdio MCP client."""
    return call_mcp_tool_sync("list_appliance_options", {"appliance": appliance})
