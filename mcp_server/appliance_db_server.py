import json
import logging
import sys
from mcp.server.fastmcp import FastMCP

# Setup logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)]
)
logger = logging.getLogger("appliance_db_server")

mcp = FastMCP("appliance_db_server")

# Reference database of appliance options and wattages
APPLIANCE_DB = {
    "AC": {
        "tonnage": ["1 ton", "1.5 ton", "2 ton"],
        "star_rating": [1, 2, 3, 4, 5],
        "age": ["less than 3 years", "3-5 years", "more than 5 years"],
        "base_wattage": {
            "1 ton": 1000,
            "1.5 ton": 1500,
            "2 ton": 2000
        },
        "star_modifier": {
            1: 1.10,
            2: 1.05,
            3: 1.00,
            4: 0.90,
            5: 0.80
        },
        "age_modifier": {
            "less than 3 years": 1.00,
            "3-5 years": 1.08,
            "more than 5 years": 1.15
        }
    },
    "Fridge": {
        "size": ["small", "medium", "large"],
        "star_rating": [1, 2, 3, 4, 5],
        "base_wattage": {
            "small": 150,
            "medium": 250,
            "large": 400
        },
        "star_modifier": {
            1: 1.15,
            2: 1.05,
            3: 1.00,
            4: 0.90,
            5: 0.80
        }
    },
    "Washing machine": {
        "capacity": ["6 kg", "7 kg", "8 kg"],
        "load_type": ["top load", "front load"],
        "base_wattage": {
            "6 kg": 400,
            "7 kg": 500,
            "8 kg": 600
        },
        "load_modifier": {
            "top load": 1.00,
            "front load": 0.85
        }
    },
    "TV": {
        "screen_size": ["32 inch", "43 inch", "55 inch"],
        "display_type": ["LED", "OLED", "QLED"],
        "base_wattage": {
            "32 inch": 40,
            "43 inch": 80,
            "55 inch": 120
        },
        "display_modifier": {
            "LED": 1.00,
            "OLED": 1.20,
            "QLED": 1.30
        }
    },
    "Fan": {
        "type": ["ceiling", "table", "pedestal", "BLDC ceiling"],
        "base_wattage": {
            "ceiling": 75,
            "table": 55,
            "pedestal": 65,
            "BLDC ceiling": 28
        }
    },
    "Water heater": {
        "capacity": ["10L", "15L", "25L"],
        "base_wattage": {
            "10L": 2000,
            "15L": 2500,
            "25L": 3000
        }
    },
    "Microwave": {
        "type": ["solo", "grill", "convection"],
        "base_wattage": {
            "solo": 800,
            "grill": 1000,
            "convection": 1200
        }
    },
    "Lights": {
        "bulb_type": ["LED", "CFL", "Incandescent"],
        "base_wattage": {
            "LED": 9,
            "CFL": 15,
            "Incandescent": 60
        }
    },
    "Laptop": {
        "base_wattage": {
            "standard": 65
        }
    },
    "Desktop": {
        "base_wattage": {
            "standard": 250
        }
    },
    "Iron": {
        "base_wattage": {
            "standard": 1200
        }
    }
}

# Normalization maps for helper lookup
APPLIANCE_KEYS_MAP = {
    "ac": "AC",
    "air conditioner": "AC",
    "fridge": "Fridge",
    "refrigerator": "Fridge",
    "washing machine": "Washing machine",
    "washer": "Washing machine",
    "tv": "TV",
    "television": "TV",
    "fan": "Fan",
    "water heater": "Water heater",
    "geyser": "Water heater",
    "microwave": "Microwave",
    "oven": "Microwave",
    "lights": "Lights",
    "bulb": "Lights",
    "light": "Lights",
    "laptop": "Laptop",
    "desktop": "Desktop",
    "iron": "Iron"
}

@mcp.tool()
def get_appliance_wattage(
    appliance: str,
    size: str = None,
    star_rating: int = None,
    age: str = None
) -> str:
    """
    Get the estimated wattage for a given appliance based on parameters like size/tonnage/capacity,
    star rating, and age.

    Parameters:
    - appliance (str): Name of the appliance (e.g. AC, Fridge, TV, etc.)
    - size (str, optional): Size, tonnage, capacity, display type, fan type, or bulb type.
    - star_rating (int, optional): Star energy rating (1 to 5).
    - age (str, optional): Age group (e.g. "less than 3 years", "3-5 years", "more than 5 years") or load type.
    
    Returns:
    - A structured JSON string with the expected wattage and low/high range limits.
    """
    logger.info(f"Decision: Querying wattage for appliance='{appliance}', size='{size}', star_rating={star_rating}, age='{age}'")
    try:
        norm_appliance = APPLIANCE_KEYS_MAP.get(appliance.lower().strip(), None)
        
        if not norm_appliance or norm_appliance not in APPLIANCE_DB:
            logger.warning(f"Decision: Appliance '{appliance}' not found in DB. Falling back to default options.")
            result = {
                "appliance": appliance,
                "found": False,
                "watts_expected": 100,
                "watts_low": 50,
                "watts_high": 150,
                "source": "fallback_default",
                "message": f"Appliance '{appliance}' not found in DB. Used fallback values."
            }
            return json.dumps(result, indent=2)

        db_entry = APPLIANCE_DB[norm_appliance]
        
        # Determine base wattage
        watts = 0
        
        if norm_appliance == "AC":
            ton = size if size in db_entry["base_wattage"] else "1.5 ton"
            base = db_entry["base_wattage"][ton]
            star = int(star_rating) if star_rating in db_entry["star_modifier"] else 3
            star_mod = db_entry["star_modifier"][star]
            age_val = age if age in db_entry["age_modifier"] else "less than 3 years"
            age_mod = db_entry["age_modifier"][age_val]
            
            watts = base * star_mod * age_mod
            result = {
                "appliance": norm_appliance,
                "found": True,
                "size": ton,
                "star_rating": star,
                "age": age_val,
                "watts_expected": round(watts),
                "watts_low": round(watts * 0.9),
                "watts_high": round(watts * 1.1),
                "source": "db_lookup"
            }
            
        elif norm_appliance == "Fridge":
            sz = size if size in db_entry["base_wattage"] else "medium"
            base = db_entry["base_wattage"][sz]
            star = int(star_rating) if star_rating in db_entry["star_modifier"] else 3
            star_mod = db_entry["star_modifier"][star]
            
            watts = base * star_mod
            result = {
                "appliance": norm_appliance,
                "found": True,
                "size": sz,
                "star_rating": star,
                "watts_expected": round(watts),
                "watts_low": round(watts * 0.9),
                "watts_high": round(watts * 1.1),
                "source": "db_lookup"
            }
            
        elif norm_appliance == "Washing machine":
            # For washing machine, age might contain the load type, or size capacity
            cap = size if size in db_entry["base_wattage"] else "7 kg"
            base = db_entry["base_wattage"][cap]
            load = age if age in db_entry["load_modifier"] else "top load"
            load_mod = db_entry["load_modifier"][load]
            
            watts = base * load_mod
            result = {
                "appliance": norm_appliance,
                "found": True,
                "capacity": cap,
                "load_type": load,
                "watts_expected": round(watts),
                "watts_low": round(watts * 0.95),
                "watts_high": round(watts * 1.05),
                "source": "db_lookup"
            }
            
        elif norm_appliance == "TV":
            scr = size if size in db_entry["base_wattage"] else "43 inch"
            base = db_entry["base_wattage"][scr]
            # age could contain the display type, check both
            disp = age if age in db_entry["display_modifier"] else "LED"
            disp_mod = db_entry["display_modifier"][disp]
            
            watts = base * disp_mod
            result = {
                "appliance": norm_appliance,
                "found": True,
                "screen_size": scr,
                "display_type": disp,
                "watts_expected": round(watts),
                "watts_low": round(watts * 0.9),
                "watts_high": round(watts * 1.1),
                "source": "db_lookup"
            }
            
        elif norm_appliance == "Fan":
            ftype = size if size in db_entry["base_wattage"] else "ceiling"
            watts = db_entry["base_wattage"][ftype]
            result = {
                "appliance": norm_appliance,
                "found": True,
                "type": ftype,
                "watts_expected": round(watts),
                "watts_low": round(max(1, watts - 10)),
                "watts_high": round(watts + 10),
                "source": "db_lookup"
            }
            
        elif norm_appliance == "Water heater":
            cap = size if size in db_entry["base_wattage"] else "15L"
            watts = db_entry["base_wattage"][cap]
            result = {
                "appliance": norm_appliance,
                "found": True,
                "capacity": cap,
                "watts_expected": round(watts),
                "watts_low": round(watts * 0.95),
                "watts_high": round(watts * 1.05),
                "source": "db_lookup"
            }
            
        elif norm_appliance == "Microwave":
            mtype = size if size in db_entry["base_wattage"] else "solo"
            watts = db_entry["base_wattage"][mtype]
            result = {
                "appliance": norm_appliance,
                "found": True,
                "type": mtype,
                "watts_expected": round(watts),
                "watts_low": round(watts * 0.9),
                "watts_high": round(watts * 1.1),
                "source": "db_lookup"
            }
            
        elif norm_appliance == "Lights":
            ltype = size if size in db_entry["base_wattage"] else "LED"
            watts = db_entry["base_wattage"][ltype]
            result = {
                "appliance": norm_appliance,
                "found": True,
                "bulb_type": ltype,
                "watts_expected": round(watts),
                "watts_low": round(watts * 0.9),
                "watts_high": round(watts * 1.1),
                "source": "db_lookup"
            }
            
        else:
            # Laptop, Desktop, Iron (Standard single options)
            watts = db_entry["base_wattage"]["standard"]
            low_mod, high_mod = 0.9, 1.1
            if norm_appliance == "Laptop":
                low_mod, high_mod = 0.7, 1.3
            elif norm_appliance == "Desktop":
                low_mod, high_mod = 0.6, 1.6
            elif norm_appliance == "Iron":
                low_mod, high_mod = 0.83, 1.25
                
            result = {
                "appliance": norm_appliance,
                "found": True,
                "watts_expected": round(watts),
                "watts_low": round(watts * low_mod),
                "watts_high": round(watts * high_mod),
                "source": "db_lookup"
            }
            
        logger.info(f"Decision: Returned wattage = {result['watts_expected']}W for {norm_appliance}")
        return json.dumps(result, indent=2)

    except Exception as e:
        logger.error(f"Decision: Error in get_appliance_wattage: {str(e)}")
        fallback_res = {
            "appliance": appliance,
            "found": False,
            "watts_expected": 100,
            "watts_low": 50,
            "watts_high": 150,
            "source": "error_fallback",
            "error": str(e)
        }
        return json.dumps(fallback_res, indent=2)

@mcp.tool()
def list_appliance_options(appliance: str) -> str:
    """
    List the available configuration options (e.g. sizes, ratings, types) for a given appliance.

    Parameters:
    - appliance (str): Name of the appliance.

    Returns:
    - A structured JSON string describing the options.
    """
    logger.info(f"Decision: Listing options for appliance='{appliance}'")
    try:
        norm_appliance = APPLIANCE_KEYS_MAP.get(appliance.lower().strip(), None)
        
        if not norm_appliance or norm_appliance not in APPLIANCE_DB:
            logger.warning(f"Decision: Appliance '{appliance}' not found for options lookup.")
            result = {
                "appliance": appliance,
                "found": False,
                "options": {},
                "message": f"Appliance '{appliance}' not found in database."
            }
            return json.dumps(result, indent=2)
            
        db_entry = APPLIANCE_DB[norm_appliance]
        options = {}
        
        if norm_appliance == "AC":
            options = {
                "tonnage": db_entry["tonnage"],
                "star_rating": db_entry["star_rating"],
                "age": db_entry["age"]
            }
        elif norm_appliance == "Fridge":
            options = {
                "size": db_entry["size"],
                "star_rating": db_entry["star_rating"]
            }
        elif norm_appliance == "Washing machine":
            options = {
                "capacity": db_entry["capacity"],
                "load_type": db_entry["load_type"]
            }
        elif norm_appliance == "TV":
            options = {
                "screen_size": db_entry["screen_size"],
                "display_type": db_entry["display_type"]
            }
        elif norm_appliance == "Fan":
            options = {
                "type": db_entry["type"]
            }
        elif norm_appliance == "Water heater":
            options = {
                "capacity": db_entry["capacity"]
            }
        elif norm_appliance == "Microwave":
            options = {
                "type": db_entry["type"]
            }
        elif norm_appliance == "Lights":
            options = {
                "bulb_type": db_entry["bulb_type"]
            }
        else:
            # Laptop, Desktop, Iron
            options = {
                "standard": ["default"]
            }
            
        result = {
            "appliance": norm_appliance,
            "found": True,
            "options": options
        }
        return json.dumps(result, indent=2)
        
    except Exception as e:
        logger.error(f"Decision: Error in list_appliance_options: {str(e)}")
        fallback_res = {
            "appliance": appliance,
            "found": False,
            "options": {},
            "error": str(e)
        }
        return json.dumps(fallback_res, indent=2)

if __name__ == "__main__":
    mcp.run(transport="stdio")
