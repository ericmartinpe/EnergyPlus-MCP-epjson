"""
EnergyPlus MCP Server with FastMCP
"""

import os
import logging
import json
from typing import Optional, Dict, Any, List
from pathlib import Path
from datetime import datetime

# Import FastMCP instead of the low-level Server
from mcp.server.fastmcp import FastMCP

# Import our EnergyPlus utilities and configuration
from energyplus_mcp_server.energyplus_tools import EnergyPlusManager
from energyplus_mcp_server.config import get_config

logger = logging.getLogger(__name__)

# Initialize configuration and set up logging
config = get_config()

# Initialize the FastMCP server with configuration
mcp = FastMCP(config.server.name)

# Initialize EnergyPlus manager with configuration
ep_manager = EnergyPlusManager(config)

logger.info(
    f"EnergyPlus MCP Server '{config.server.name}' v{config.server.version} initialized"
)


# Add this tool function to server.py


@mcp.tool()
async def copy_file(
    source_path: str,
    target_path: str,
    overwrite: bool = False,
    file_types: Optional[List[str]] = None,
) -> str:
    """
    Copy a file from source to target location with intelligent path resolution

    Args:
        source_path: Source file path. Can be:
                    - Absolute path: "/full/path/to/file.epJSON"
                    - Relative path: "models/mymodel.epJSON"
                    - Filename only: "1ZoneUncontrolled.epJSON" (searches in sample_files)
                    - Fuzzy name: Will search in sample_files, example_files, weather_data, etc.
        target_path: Target path for the copy. Can be:
                    - Absolute path: "/full/path/to/copy.epJSON"
                    - Relative path: "outputs/modified_file.epJSON"
                    - Filename only: "my_copy.epJSON" (saves to outputs directory)
        overwrite: Whether to overwrite existing target file (default: False)
        file_types: List of acceptable file extensions (e.g., [".epJSON", ".epw"]). If None, accepts any file type.

    Returns:
        JSON string with copy operation results including resolved paths, file sizes, and validation status

    Examples:
        # Copy epJSON file with validation
        copy_file("1ZoneUncontrolled.epJSON", "my_model.epJSON", file_types=[".epJSON"])

        # Copy weather file
        copy_file("USA_CA_San.Francisco.epw", "sf_weather.epw", file_types=[".epw"])

        # Copy any file type
        copy_file("sample.epJSON", "outputs/test.epJSON", overwrite=True)

        # Copy with fuzzy matching (e.g., city name for weather files)
        copy_file("san francisco", "my_weather.epw", file_types=[".epw"])
    """
    try:
        logger.info(
            f"Copying file: '{source_path}' -> '{target_path}' (overwrite={overwrite}, file_types={file_types})"
        )
        result = ep_manager.copy_file(source_path, target_path, overwrite, file_types)
        return f"File copy operation completed:\n{result}"
    except ValueError as e:
        logger.warning(f"Invalid arguments for copy_file: {str(e)}")
        return f"Invalid arguments: {str(e)}"
    except Exception as e:
        logger.error(f"Unexpected error copying file: {str(e)}")
        return f"Error copying file: {str(e)}"


@mcp.tool()
async def convert_idf_to_epjson(
    idf_path: str, output_path: Optional[str] = None
) -> str:
    """
    Convert an IDF file to epJSON format using EnergyPlus --convert-only
    
    NOTE: This tool is typically NOT needed for normal workflows!
    All MCP tools automatically convert IDF files to epJSON when you pass an .idf path.
    Use this tool ONLY when you need explicit control over the output location.

    Args:
        idf_path: Path to the IDF file (can be absolute, relative, or filename for sample files)
        output_path: Optional path for the output epJSON file. If None, creates one in outputs/ with same name but .epJSON extension

    Returns:
        JSON string with conversion results including the path to the converted epJSON file

    Examples:
        # Direct workflow (RECOMMENDED - no explicit conversion needed):
        # Just pass the .idf file to any tool - it auto-converts!
        find_exterior_walls("5ZoneAirCooled.idf")  # Automatically converts behind the scenes
        
        # Explicit conversion (only needed for custom output paths):
        convert_idf_to_epjson("models/mymodel.idf", "custom_location/mymodel.epJSON")

    When to use this tool:
        - Copying IDF files to a specific directory with custom naming
        - Pre-converting files for inspection before running other operations
        - Batch conversion workflows with specific output requirements
        
    When NOT to use this tool:
        - Normal workflows - just pass .idf paths directly to other tools!
        - The automatic conversion in _resolve_epjson_path handles this for you
    """
    try:
        logger.info(f"Converting IDF to epJSON: {idf_path}")
        result = ep_manager.convert_idf_to_epjson(idf_path, output_path)
        result_dict = json.loads(result)

        if result_dict["success"]:
            return f"Successfully converted IDF to epJSON:\n{result}"
        else:
            return f"Conversion failed:\n{result}"

    except FileNotFoundError as e:
        logger.warning(f"IDF file not found: {idf_path}")
        return f"File not found: {str(e)}"
    except Exception as e:
        logger.error(f"Unexpected error converting IDF {idf_path}: {str(e)}")
        return f"Error converting IDF {idf_path}: {str(e)}"


@mcp.tool()
async def load_epjson_model(epjson_path: str) -> str:
    """
    Load and validate an EnergyPlus epJSON file

    Args:
        epjson_path: Path to the epJSON file (can be absolute, relative, or just filename for sample files)

    Returns:
        JSON string with model information and loading status
    """
    try:
        logger.info(f"Loading epJSON model: {epjson_path}")
        result = ep_manager.load_epjson(epjson_path)
        return f"Successfully loaded epJSON: {result['original_path']}\nModel info: {result}"
    except FileNotFoundError as e:
        logger.warning(f"epJSON file not found: {epjson_path}")
        return f"File not found: {str(e)}"
    except ValueError as e:
        logger.warning(f"Invalid input for load_epjson_model: {str(e)}")
        return f"Invalid input: {str(e)}"
    except Exception as e:
        logger.error(f"Unexpected error loading epJSON {epjson_path}: {str(e)}")
        return f"Error loading epJSON {epjson_path}: {str(e)}"


@mcp.tool()
async def get_model_summary(epjson_path: str) -> str:
    """
    Get basic model information (Building, Site, SimulationControl, Version)

    Args:
        epjson_path: Path to the epJSON file

    Returns:
        JSON string with model summary information
    """
    try:
        logger.info(f"Getting model summary: {epjson_path}")
        resolved_path = ep_manager._resolve_epjson_path(epjson_path)
        ep_data = ep_manager.load_json(resolved_path)
        summary = ep_manager.get_model_basics(ep_data)
        return f"Model Summary for {epjson_path}:\n{summary}"
    except FileNotFoundError as e:
        logger.warning(f"epJSON file not found: {epjson_path}")
        return f"File not found: {str(e)}"
    except Exception as e:
        logger.error(f"Error getting model summary for {epjson_path}: {str(e)}")
        return f"Error getting model summary for {epjson_path}: {str(e)}"


@mcp.tool()
async def check_simulation_settings(epjson_path: str) -> str:
    """
    Check SimulationControl and RunPeriod settings with information about modifiable fields

    Args:
        epjson_path: Path to the epJSON file

    Returns:
        JSON string with current settings and descriptions of modifiable fields
    """
    try:
        logger.info(f"Checking simulation settings: {epjson_path}")
        resolved_path = ep_manager._resolve_epjson_path(epjson_path)
        ep_data = ep_manager.load_json(resolved_path)
        settings = ep_manager.check_simulation_settings(ep_data)
        return f"Simulation settings for {epjson_path}:\n{settings}"
    except FileNotFoundError as e:
        logger.warning(f"epJSON file not found: {epjson_path}")
        return f"File not found: {str(e)}"
    except Exception as e:
        logger.error(f"Error checking simulation settings for {epjson_path}: {str(e)}")
        return f"Error checking simulation settings for {epjson_path}: {str(e)}"


@mcp.tool()
async def inspect_schedules(epjson_path: str, include_values: bool = False) -> str:
    """
    Inspect and inventory all schedule objects in the EnergyPlus model

    Args:
        epjson_path: Path to the epJSON file
        include_values: Whether to extract actual schedule values (default: False)

    Returns:
        JSON string with detailed schedule inventory and analysis
    """
    try:
        logger.info(
            f"Inspecting schedules: {epjson_path} (include_values={include_values})"
        )
        resolved_path = ep_manager._resolve_epjson_path(epjson_path)
        ep_data = ep_manager.load_json(resolved_path)
        schedules_info = ep_manager.inspect_schedules(ep_data, include_values)
        return f"Schedule inspection for {epjson_path}:\n{schedules_info}"
    except FileNotFoundError as e:
        logger.warning(f"epJSON file not found: {epjson_path}")
        return f"File not found: {str(e)}"
    except Exception as e:
        logger.error(f"Error inspecting schedules for {epjson_path}: {str(e)}")
        return f"Error inspecting schedules for {epjson_path}: {str(e)}"


@mcp.tool()
async def inspect_people(epjson_path: str) -> str:
    """
    Inspect and list all People objects in the EnergyPlus model

    Args:
        epjson_path: Path to the epJSON file

    Returns:
        JSON string with detailed People objects information including:
        - Name, zone, and schedule associations
        - Calculation method (People, People/Area, Area/Person)
        - Occupancy values and thermal comfort settings
        - Summary statistics by zone and calculation method
    """
    try:
        logger.info(f"Inspecting People objects: {epjson_path}")
        resolved_path = ep_manager._resolve_epjson_path(epjson_path)
        ep_data = ep_manager.load_json(resolved_path)
        result = ep_manager.inspect_people(ep_data)
        return f"People objects inspection for {epjson_path}:\n{result}"
    except FileNotFoundError as e:
        logger.warning(f"epJSON file not found: {epjson_path}")
        return f"File not found: {str(e)}"
    except Exception as e:
        logger.error(f"Error inspecting People objects for {epjson_path}: {str(e)}")
        return f"Error inspecting People objects for {epjson_path}: {str(e)}"


@mcp.tool()
async def modify_people(
    epjson_path: str,
    modifications: List[Dict[str, Any]],
    output_path: Optional[str] = None,
) -> str:
    """
    Modify People objects in the EnergyPlus model

    Args:
        epjson_path: Path to the input epJSON file
        modifications: List of modification specifications. Each item should contain:
                      - "target": Specifies which People objects to modify
                        - "all": Apply to all People objects
                        - "zone:ZoneName": Apply to People objects in specific zone
                        - "name:PeopleName": Apply to specific People object by name
                      - "field_updates": Dictionary of field names and new values
                        Valid fields include:
                        - Number_of_People_Schedule_Name
                        - Number_of_People_Calculation_Method (People, People/Area, Area/Person)
                        - Number_of_People
                        - People_per_Floor_Area
                        - Floor_Area_per_Person
                        - Fraction_Radiant
                        - Sensible_Heat_Fraction
                        - Activity_Level_Schedule_Name
                        - Carbon_Dioxide_Generation_Rate
                        - Clothing_Insulation_Schedule_Name
                        - Air_Velocity_Schedule_Name
                        - Thermal_Comfort_Model_1_Type
                        - Thermal_Comfort_Model_2_Type
        output_path: Optional path for output file (if None, creates one with _modified suffix)

    Returns:
        JSON string with modification results

    Examples:
        # Modify all People objects to use 0.1 people/m2
        modify_people("model.epJSON", [
            {
                "target": "all",
                "field_updates": {
                    "Number_of_People_Calculation_Method": "People/Area",
                    "People_per_Floor_Area": 0.1
                }
            }
        ])

        # Modify People objects in specific zone
        modify_people("model.epJSON", [
            {
                "target": "zone:Office Zone",
                "field_updates": {
                    "Number_of_People": 10,
                    "Activity_Level_Schedule_Name": "Office Activity"
                }
            }
        ])

        # Modify specific People object by name
        modify_people("model.epJSON", [
            {
                "target": "name:Office People",
                "field_updates": {
                    "Fraction_Radiant": 0.3,
                    "Sensible_Heat_Fraction": 0.6
                }
            }
        ])
    """
    try:
        logger.info(f"Modifying People objects: {epjson_path}")
        resolved_path = ep_manager._resolve_epjson_path(epjson_path)
        ep_data = ep_manager.load_json(resolved_path)
        
        # Get modified data from the method (no output_path parameter)
        modified_ep_data = ep_manager.modify_people(ep_data, modifications)
        
        # Determine output path
        if output_path is None:
            path_obj = Path(resolved_path)
            output_path = str(path_obj.parent / f"{path_obj.stem}_modified{path_obj.suffix}")
        
        # Save the modified data
        ep_manager.save_json(modified_ep_data, output_path)
        
        result = {
            "success": True,
            "input_file": resolved_path,
            "output_file": output_path,
            "modifications_count": len(modifications)
        }
        
        return f"People modification results:\n{json.dumps(result, indent=2)}"
    except FileNotFoundError as e:
        logger.warning(f"epJSON file not found: {epjson_path}")
        return f"File not found: {str(e)}"
    except ValueError as e:
        logger.warning(f"Invalid input for modify_people: {str(e)}")
        return f"Invalid input: {str(e)}"
    except Exception as e:
        logger.error(f"Error modifying People objects for {epjson_path}: {str(e)}")
        return f"Error modifying People objects for {epjson_path}: {str(e)}"


@mcp.tool()
async def inspect_lights(epjson_path: str) -> str:
    """
    Inspect and list all Lights objects in the EnergyPlus model

    Args:
        epjson_path: Path to the epJSON file

    Returns:
        JSON string with detailed Lights objects information including:
        - Name, zone, and schedule associations
        - Calculation method (LightingLevel, Watts/Area, Watts/Person)
        - Lighting power values and heat fraction settings
        - Summary statistics by zone and calculation method
    """
    try:
        logger.info(f"Inspecting Lights objects: {epjson_path}")
        resolved_path = ep_manager._resolve_epjson_path(epjson_path)
        ep_data = ep_manager.load_json(resolved_path)
        result = ep_manager.inspect_lights(ep_data)
        return f"Lights objects inspection for {epjson_path}:\n{result}"
    except FileNotFoundError as e:
        logger.warning(f"epJSON file not found: {epjson_path}")
        return f"File not found: {str(e)}"
    except Exception as e:
        logger.error(f"Error inspecting Lights objects for {epjson_path}: {str(e)}")
        return f"Error inspecting Lights objects for {epjson_path}: {str(e)}"


@mcp.tool()
async def modify_lights(
    epjson_path: str,
    modifications: List[Dict[str, Any]],
    output_path: Optional[str] = None,
) -> str:
    """
    Modify Lights objects in the EnergyPlus model

    Args:
        epjson_path: Path to the input epJSON file
        modifications: List of modification specifications. Each item should contain:
                      - "target": Specifies which Lights objects to modify
                        - "all": Apply to all Lights objects
                        - "zone:ZoneName": Apply to Lights objects in specific zone
                        - "name:LightsName": Apply to specific Lights object by name
                      - "field_updates": Dictionary of field names and new values
                        Valid fields include:
                        - Schedule_Name
                        - Design_Level_Calculation_Method (LightingLevel, Watts/Area, Watts/Person)
                        - Lighting_Level
                        - Watts_per_Floor_Area
                        - Watts_per_Person
                        - Return_Air_Fraction
                        - Fraction_Radiant
                        - Fraction_Visible
                        - Fraction_Replaceable
                        - EndUse_Subcategory
                        - Return_Air_Fraction_Calculated_from_Plenum_Temperature
                        - Return_Air_Fraction_Function_of_Plenum_Temperature_Coefficient_1
                        - Return_Air_Fraction_Function_of_Plenum_Temperature_Coefficient_2
                        - Return_Air_Heat_Gain_Node_Name
                        - Exhaust_Air_Heat_Gain_Node_Name
        output_path: Optional path for output file (if None, creates one with _modified suffix)

    Returns:
        JSON string with modification results

    Examples:
        # Modify all Lights objects to use 10 W/m2
        modify_lights("model.epJSON", [
            {
                "target": "all",
                "field_updates": {
                    "Design_Level_Calculation_Method": "Watts/Area",
                    "Watts_per_Floor_Area": 10.0
                }
            }
        ])

        # Modify Lights objects in specific zone
        modify_lights("model.epJSON", [
            {
                "target": "zone:Office Zone",
                "field_updates": {
                    "Lighting_Level": 2000,
                    "Schedule_Name": "Office Lighting Schedule"
                }
            }
        ])

        # Modify specific Lights object by name
        modify_lights("model.epJSON", [
            {
                "target": "name:Office Lights",
                "field_updates": {
                    "Fraction_Radiant": 0.42,
                    "Fraction_Visible": 0.18
                }
            }
        ])
    """
    try:
        logger.info(f"Modifying Lights objects: {epjson_path}")
        resolved_path = ep_manager._resolve_epjson_path(epjson_path)
        ep_data = ep_manager.load_json(resolved_path)
        
        # Get modified data from the method (no output_path parameter)
        modified_ep_data = ep_manager.modify_lights(ep_data, modifications)
        
        # Determine output path
        if output_path is None:
            path_obj = Path(resolved_path)
            output_path = str(path_obj.parent / f"{path_obj.stem}_modified{path_obj.suffix}")
        
        # Save the modified data
        ep_manager.save_json(modified_ep_data, output_path)
        
        result = {
            "success": True,
            "input_file": resolved_path,
            "output_file": output_path,
            "modifications_count": len(modifications)
        }
        
        return f"Lights modification results:\n{json.dumps(result, indent=2)}"
    except FileNotFoundError as e:
        logger.warning(f"epJSON file not found: {epjson_path}")
        return f"File not found: {str(e)}"
    except ValueError as e:
        logger.warning(f"Invalid input for modify_lights: {str(e)}")
        return f"Invalid input: {str(e)}"
    except Exception as e:
        logger.error(f"Error modifying Lights objects for {epjson_path}: {str(e)}")
        return f"Error modifying Lights objects for {epjson_path}: {str(e)}"


@mcp.tool()
async def inspect_electric_equipment(epjson_path: str) -> str:
    """
    Inspect and list all ElectricEquipment objects in the EnergyPlus model

    Args:
        epjson_path: Path to the epJSON file

    Returns:
        JSON string with detailed ElectricEquipment objects information including:
        - Name, zone, and schedule associations
        - Calculation method (EquipmentLevel, Watts/Area, Watts/Person)
        - Equipment power values and heat fraction settings
        - Summary statistics by zone and calculation method
    """
    try:
        logger.info(f"Inspecting ElectricEquipment objects: {epjson_path}")
        resolved_path = ep_manager._resolve_epjson_path(epjson_path)
        ep_data = ep_manager.load_json(resolved_path)
        result = ep_manager.inspect_electric_equipment(ep_data)
        return f"ElectricEquipment objects inspection for {epjson_path}:\n{result}"
    except FileNotFoundError as e:
        logger.warning(f"epJSON file not found: {epjson_path}")
        return f"File not found: {str(e)}"
    except Exception as e:
        logger.error(
            f"Error inspecting ElectricEquipment objects for {epjson_path}: {str(e)}"
        )
        return f"Error inspecting ElectricEquipment objects for {epjson_path}: {str(e)}"


@mcp.tool()
async def modify_electric_equipment(
    epjson_path: str,
    modifications: List[Dict[str, Any]],
    output_path: Optional[str] = None,
) -> str:
    """
    Modify ElectricEquipment objects in the EnergyPlus model

    Args:
        epjson_path: Path to the input epJSON file
        modifications: List of modification specifications. Each item should contain:
                      - "target": Specifies which ElectricEquipment objects to modify
                        - "all": Apply to all ElectricEquipment objects
                        - "zone:ZoneName": Apply to ElectricEquipment objects in specific zone
                        - "name:ElectricEquipmentName": Apply to specific ElectricEquipment object by name
                      - "field_updates": Dictionary of field names and new values
                        Valid fields include:
                        - Schedule_Name
                        - Design_Level_Calculation_Method (EquipmentLevel, Watts/Area, Watts/Person)
                        - Design_Level
                        - Watts_per_Floor_Area
                        - Watts_per_Person
                        - Fraction_Latent
                        - Fraction_Radiant
                        - Fraction_Lost
                        - EndUse_Subcategory
        output_path: Optional path for output file (if None, creates one with _modified suffix)

    Returns:
        JSON string with modification results

    Examples:
        # Modify all ElectricEquipment objects to use 15 W/m2
        modify_electric_equipment("model.epJSON", [
            {
                "target": "all",
                "field_updates": {
                    "Design_Level_Calculation_Method": "Watts/Area",
                    "Watts_per_Floor_Area": 15.0
                }
            }
        ])

        # Modify ElectricEquipment objects in specific zone
        modify_electric_equipment("model.epJSON", [
            {
                "target": "zone:Office Zone",
                "field_updates": {
                    "Design_Level": 3000,
                    "Schedule_Name": "Office Equipment Schedule"
                }
            }
        ])

        # Modify specific ElectricEquipment object by name
        modify_electric_equipment("model.epJSON", [
            {
                "target": "name:Office Equipment",
                "field_updates": {
                    "Fraction_Radiant": 0.3,
                    "Fraction_Latent": 0.1
                }
            }
        ])
    """
    try:
        logger.info(f"Modifying ElectricEquipment objects: {epjson_path}")
        resolved_path = ep_manager._resolve_epjson_path(epjson_path)
        ep_data = ep_manager.load_json(resolved_path)
        
        # Get modified data from the method (no output_path parameter)
        modified_ep_data = ep_manager.modify_electric_equipment(ep_data, modifications)
        
        # Determine output path
        if output_path is None:
            path_obj = Path(resolved_path)
            output_path = str(path_obj.parent / f"{path_obj.stem}_modified{path_obj.suffix}")
        
        # Save the modified data
        ep_manager.save_json(modified_ep_data, output_path)
        
        result = {
            "success": True,
            "input_file": resolved_path,
            "output_file": output_path,
            "modifications_count": len(modifications)
        }
        
        return f"ElectricEquipment modification results:\n{json.dumps(result, indent=2)}"
    except FileNotFoundError as e:
        logger.warning(f"epJSON file not found: {epjson_path}")
        return f"File not found: {str(e)}"
    except ValueError as e:
        logger.warning(f"Invalid input for modify_electric_equipment: {str(e)}")
        return f"Invalid input: {str(e)}"
    except Exception as e:
        logger.error(
            f"Error modifying ElectricEquipment objects for {epjson_path}: {str(e)}"
        )
        return f"Error modifying ElectricEquipment objects for {epjson_path}: {str(e)}"


@mcp.tool()
async def modify_simulation_control(
    epjson_path: str,
    field_updates: Dict[str, Any],  # Changed from str to Dict[str, Any]
    output_path: Optional[str] = None,
) -> str:
    """
    Modify SimulationControl settings and save to a new file

    Args:
        epjson_path: Path to the input epJSON file
        field_updates: Dictionary with field names and new values (e.g., {"Run_Simulation_for_Weather_File_Run_Periods": "Yes"})
        output_path: Optional path for output file (if None, creates one with _modified suffix)

    Returns:
        JSON string with modification results
    """
    try:
        logger.info(f"Modifying SimulationControl: {epjson_path}")
        resolved_path = ep_manager._resolve_epjson_path(epjson_path)
        ep_data = ep_manager.load_json(resolved_path)
        
        # Get modified data from the method (no output_path parameter)
        modified_ep_data = ep_manager.modify_simulation_settings(
            epjson_data=ep_data,
            object_type="SimulationControl",
            field_updates=field_updates
        )
        
        # Determine output path
        if output_path is None:
            path_obj = Path(resolved_path)
            output_path = str(path_obj.parent / f"{path_obj.stem}_modified{path_obj.suffix}")
        
        # Save the modified data
        ep_manager.save_json(modified_ep_data, output_path)
        
        result = {
            "success": True,
            "input_file": resolved_path,
            "output_file": output_path,
            "fields_modified": list(field_updates.keys())
        }
        
        return f"SimulationControl modification results:\n{json.dumps(result, indent=2)}"
    except FileNotFoundError as e:
        logger.warning(f"epJSON file not found: {epjson_path}")
        return f"File not found: {str(e)}"
    except Exception as e:
        logger.error(f"Error modifying SimulationControl for {epjson_path}: {str(e)}")
        return f"Error modifying SimulationControl for {epjson_path}: {str(e)}"


@mcp.tool()
async def modify_run_period(
    epjson_path: str,
    field_updates: Dict[str, Any],  # Changed from str to Dict[str, Any]
    run_period_index: int = 0,
    output_path: Optional[str] = None,
) -> str:
    """
    Modify RunPeriod settings and save to a new file

    Args:
        epjson_path: Path to the input epJSON file
        field_updates: Dictionary with field names and new values (e.g., {"Begin_Month": 1, "End_Month": 3})
        run_period_index: Index of RunPeriod to modify (default 0 for first RunPeriod)
        output_path: Optional path for output file (if None, creates one with _modified suffix)

    Returns:
        JSON string with modification results
    """
    try:
        logger.info(f"Modifying RunPeriod: {epjson_path}")
        resolved_path = ep_manager._resolve_epjson_path(epjson_path)
        ep_data = ep_manager.load_json(resolved_path)
        
        # Get modified data from the method (no output_path parameter)
        modified_ep_data = ep_manager.modify_simulation_settings(
            epjson_data=ep_data,
            object_type="RunPeriod",
            field_updates=field_updates,
            run_period_index=run_period_index
        )
        
        # Determine output path
        if output_path is None:
            path_obj = Path(resolved_path)
            output_path = str(path_obj.parent / f"{path_obj.stem}_modified{path_obj.suffix}")
        
        # Save the modified data
        ep_manager.save_json(modified_ep_data, output_path)
        
        result = {
            "success": True,
            "input_file": resolved_path,
            "output_file": output_path,
            "run_period_index": run_period_index,
            "fields_modified": list(field_updates.keys())
        }
        
        return f"RunPeriod modification results:\n{json.dumps(result, indent=2)}"
    except FileNotFoundError as e:
        logger.warning(f"epJSON file not found: {epjson_path}")
        return f"File not found: {str(e)}"
    except Exception as e:
        logger.error(f"Error modifying RunPeriod for {epjson_path}: {str(e)}")
        return f"Error modifying RunPeriod for {epjson_path}: {str(e)}"


@mcp.tool()
async def change_infiltration_by_mult(
    epjson_path: str, mult: float, output_path: Optional[str] = None
) -> str:
    """
    Modify infiltration in ZoneInfiltration:DesignFlowRate and save to a new file

    Args:
        epjson_path: Path to the input epJSON file
        mult: Multiplicative factor to apply to all ZoneInfiltration:DesignFlowRate objects
        output_path: Optional path for output file (if None, creates one with _modified suffix)

    Returns:
        JSON string with modification results
    """
    try:
        logger.info(f"Modifying Infiltration: {epjson_path}")
        resolved_path = ep_manager._resolve_epjson_path(epjson_path)
        ep_data = ep_manager.load_json(resolved_path)
        
        # Get modified data from the method (no output_path parameter)
        modified_ep_data = ep_manager.change_infiltration_by_mult(
            epjson_data=ep_data,
            mult=mult
        )
        
        # Determine output path
        if output_path is None:
            path_obj = Path(resolved_path)
            output_path = str(path_obj.parent / f"{path_obj.stem}_modified{path_obj.suffix}")
        
        # Save the modified data
        ep_manager.save_json(modified_ep_data, output_path)
        
        result = {
            "success": True,
            "input_file": resolved_path,
            "output_file": output_path,
            "multiplier": mult
        }
        
        return f"Infiltration modification results:\n{json.dumps(result, indent=2)}"
    except FileNotFoundError as e:
        logger.warning(f"epJSON file not found: {epjson_path}")
        return f"File not found: {str(e)}"
    except Exception as e:
        logger.error(f"Error Infiltration modification for {epjson_path}: {str(e)}")
        return f"Error Infiltration modification for {epjson_path}: {str(e)}"


@mcp.tool()
async def add_window_film_outside(
    epjson_path: str,
    u_value: float = 4.94,
    shgc: float = 0.45,
    visible_transmittance: float = 0.66,
    output_path: Optional[str] = None,
) -> str:
    """
    Add exterior window film to all exterior windows using WindowMaterial:SimpleGlazingSystem

    Args:
        epjson_path: Path to the input epJSON file
        u_value: U-value of the window film (default: 4.94 W/m²·K from CBES)
        shgc: Solar Heat Gain Coefficient of the window film (default: 0.45)
        visible_transmittance: Visible transmittance of the window film (default: 0.66)
        output_path: Optional path for output file (if None, creates one with _modified suffix)

    Returns:
        JSON string with modification results
    """
    try:
        logger.info(f"Adding window film to exterior windows: {epjson_path}")
        resolved_path = ep_manager._resolve_epjson_path(epjson_path)
        ep_data = ep_manager.load_json(resolved_path)
        
        # Get modified data from the method (no output_path parameter)
        modified_ep_data = ep_manager.add_window_film_outside(
            epjson_data=ep_data,
            u_value=u_value,
            shgc=shgc,
            visible_transmittance=visible_transmittance
        )
        
        # Determine output path
        if output_path is None:
            path_obj = Path(resolved_path)
            output_path = str(path_obj.parent / f"{path_obj.stem}_modified{path_obj.suffix}")
        
        # Save the modified data
        ep_manager.save_json(modified_ep_data, output_path)
        
        result = {
            "success": True,
            "input_file": resolved_path,
            "output_file": output_path,
            "u_value": u_value,
            "shgc": shgc,
            "visible_transmittance": visible_transmittance
        }
        
        return f"Window film modification results:\n{json.dumps(result, indent=2)}"
    except FileNotFoundError as e:
        logger.warning(f"epJSON file not found: {epjson_path}")
        return f"File not found: {str(e)}"
    except Exception as e:
        logger.error(f"Error adding window film for {epjson_path}: {str(e)}")
        return f"Error adding window film for {epjson_path}: {str(e)}"


@mcp.tool()
async def adjust_windows_for_target_wwr(
    epjson_path: str,
    target_wwr: float,
    by_orientation: bool = False,
    orientation_targets: Optional[Dict[str, float]] = None,
    output_path: Optional[str] = None,
) -> str:
    """
    Adjust window sizes to achieve a target window-to-wall ratio (WWR)
    
    This tool modifies window dimensions by scaling them uniformly to meet a specified WWR target.
    Windows can be adjusted globally for the entire building, by orientation, or with custom targets
    for each orientation. Glass doors are included in WWR calculations but not scaled.

    Args:
        epjson_path: Path to the input epJSON file
        target_wwr: Target window-to-wall ratio as a percentage (e.g., 30 for 30%) or fraction (0.30 for 30%)
        by_orientation: If True, apply target_wwr to each orientation independently (default: False)
        orientation_targets: Optional dict mapping orientation to target WWR 
                           (e.g., {"North": 30, "South": 40, "East": 25, "West": 25})
                           Overrides target_wwr and by_orientation if provided
        output_path: Optional path for output file (if None, creates one with _WWR{target} suffix)

    Returns:
        JSON string with modification results including initial and final WWR values

    Examples:
        # Set building-wide WWR to 30%
        adjust_windows_for_target_wwr("5ZoneAirCooled.epJSON", 30.0)
        
        # Set WWR to 30% independently for each orientation
        adjust_windows_for_target_wwr("5ZoneAirCooled.epJSON", 30.0, by_orientation=True)
        
        # Set different WWR targets per orientation
        adjust_windows_for_target_wwr(
            "5ZoneAirCooled.epJSON", 
            30.0,
            orientation_targets={"North": 25, "South": 40, "East": 30, "West": 30}
        )
    """
    try:
        logger.info(f"Adjusting windows for target WWR {target_wwr}%: {epjson_path}")
        resolved_path = ep_manager._resolve_epjson_path(epjson_path)
        ep_data = ep_manager.load_json(resolved_path)
        
        # Calculate initial WWR
        initial_wwr_json = ep_manager.calculate_window_to_wall_ratio(ep_data)
        initial_wwr_data = json.loads(initial_wwr_json)
        initial_wwr = initial_wwr_data["total_building_wwr"]["wwr_percent"]
        
        # Get modified data from the method
        modified_ep_data = ep_manager.adjust_windows_for_target_wwr(
            epjson_data=ep_data,
            target_wwr=target_wwr,
            by_orientation=by_orientation,
            orientation_targets=orientation_targets
        )
        
        # Calculate final WWR
        final_wwr_json = ep_manager.calculate_window_to_wall_ratio(modified_ep_data)
        final_wwr_data = json.loads(final_wwr_json)
        final_wwr = final_wwr_data["total_building_wwr"]["wwr_percent"]
        
        # Determine output path
        if output_path is None:
            path_obj = Path(resolved_path)
            # Normalize target_wwr for filename (convert to percentage if needed)
            wwr_display = int(target_wwr) if target_wwr > 1.0 else int(target_wwr * 100)
            output_path = str(path_obj.parent / f"{path_obj.stem}_WWR{wwr_display}{path_obj.suffix}")
        
        # Save the modified data
        ep_manager.save_json(modified_ep_data, output_path)
        
        result = {
            "success": True,
            "input_file": resolved_path,
            "output_file": output_path,
            "target_wwr_percent": target_wwr if target_wwr > 1.0 else target_wwr * 100,
            "initial_wwr_percent": initial_wwr,
            "final_wwr_percent": final_wwr,
            "by_orientation": by_orientation,
            "orientation_targets": orientation_targets,
            "wwr_by_orientation": final_wwr_data["wwr_by_orientation"]
        }
        
        return f"Window WWR adjustment results:\n{json.dumps(result, indent=2)}"
    except FileNotFoundError as e:
        logger.warning(f"epJSON file not found: {epjson_path}")
        return f"File not found: {str(e)}"
    except Exception as e:
        logger.error(f"Error adjusting windows for target WWR in {epjson_path}: {str(e)}")
        return f"Error adjusting windows for target WWR in {epjson_path}: {str(e)}"


@mcp.tool()
async def add_coating_outside(
    epjson_path: str,
    location: str,
    solar_abs: float = 0.4,
    thermal_abs: float = 0.9,
    output_path: Optional[str] = None,
) -> str:
    """
    Add exterior coating to all exterior surfaces of the specified location (wall or roof)

    Args:
        epjson_path: Path to the input epJSON file
        location: Surface type - either "wall" or "roof"
        solar_abs: Solar Absorptance of the exterior coating (default: 0.4)
        thermal_abs: Thermal Absorptance of the exterior coating (default: 0.9)
        output_path: Optional path for output file (if None, creates one with _modified suffix)

    Returns:
        JSON string with modification results
    """
    try:
        logger.info(f"Adding exterior coating to {location} surfaces: {epjson_path}")
        resolved_path = ep_manager._resolve_epjson_path(epjson_path)
        ep_data = ep_manager.load_json(resolved_path)
        
        # Get modified data from the method (no output_path parameter)
        modified_ep_data = ep_manager.add_coating_outside(
            epjson_data=ep_data,
            location=location,
            solar_abs=solar_abs,
            thermal_abs=thermal_abs
        )
        
        # Determine output path
        if output_path is None:
            path_obj = Path(resolved_path)
            output_path = str(path_obj.parent / f"{path_obj.stem}_modified{path_obj.suffix}")
        
        # Save the modified data
        ep_manager.save_json(modified_ep_data, output_path)
        
        result = {
            "success": True,
            "input_file": resolved_path,
            "output_file": output_path,
            "location": location,
            "solar_absorptance": solar_abs,
            "thermal_absorptance": thermal_abs
        }
        
        return f"Exterior coating modification results:\n{json.dumps(result, indent=2)}"
    except FileNotFoundError as e:
        logger.warning(f"epJSON file not found: {epjson_path}")
        return f"File not found: {str(e)}"
    except ValueError as e:
        logger.warning(f"Invalid location parameter: {location}")
        return f"Invalid location (must be 'wall' or 'roof'): {str(e)}"
    except Exception as e:
        logger.error(f"Error adding exterior coating for {epjson_path}: {str(e)}")
        return f"Error adding exterior coating for {epjson_path}: {str(e)}"


@mcp.tool()
async def find_exterior_walls(epjson_path: str) -> str:
    """
    Find all exterior walls in the EnergyPlus model
    
    Identifies all BuildingSurface:Detailed objects that are walls with outdoor boundary
    conditions. Useful for inventory before applying construction modifications.
    
    NOTE: IDF files are AUTOMATICALLY converted to epJSON - do NOT manually call 
    convert_idf_to_epjson before using this tool.

    Args:
        epjson_path: Path to the input epJSON or IDF file (IDF files are auto-converted)

    Returns:
        JSON string with dictionary of exterior wall names and their current constructions

    Examples:
        # Find all exterior walls (works with both epJSON and IDF)
        find_exterior_walls("model.epJSON")
        find_exterior_walls("model.idf")  # Auto-converts to epJSON
        
        # Use results to identify walls for construction assignment
        walls = find_exterior_walls("5ZoneAirCooled.idf")
    """
    try:
        logger.info(f"Finding exterior walls: {epjson_path}")
        
        resolved_path = ep_manager._resolve_epjson_path(epjson_path)
        ep_data = ep_manager.load_json(resolved_path)
        ext_walls = ep_manager.find_exterior_walls(ep_data)
        
        result = {
            "success": True,
            "epjson_file": epjson_path,
            "exterior_walls": ext_walls,
            "total_exterior_walls": len(ext_walls)
        }
        
        logger.info(f"Found {len(ext_walls)} exterior walls in {epjson_path}")
        return f"Exterior walls found:\n{json.dumps(result, indent=2)}"
        
    except FileNotFoundError as e:
        logger.warning(f"epJSON file not found: {epjson_path}")
        return f"File not found: {str(e)}"
    except Exception as e:
        logger.error(f"Error finding exterior walls for {epjson_path}: {str(e)}")
        return f"Error finding exterior walls: {str(e)}"


@mcp.tool()
async def set_exterior_wall_construction(
    epjson_path: str,
    wall_type: str,
    code_version: str,
    climate_zone: str,
    wall_list: Optional[List[str]] = None,
    use_type: str = "non_residential",
    output_path: Optional[str] = None,
) -> str:
    """
    Set exterior wall construction with code-compliant materials and U-factor
    
    Creates or updates exterior wall constructions using ASHRAE-compliant materials
    and adjusts insulation to meet specified code requirements. Automatically adds
    all required materials to the model and assigns construction to specified walls.
    
    NOTE: IDF files are AUTOMATICALLY converted to epJSON - do NOT manually call 
    convert_idf_to_epjson before using this tool.
    
    This tool:
    1. Loads construction definitions from the data library
    2. Adds all required materials (except insulation placeholder)
    3. Creates construction with proper layer sequence
    4. Calculates and sets insulation R-value to meet code U-factor
    5. Optionally assigns construction to specified walls

    Args:
        epjson_path: Path to the input epJSON or IDF file (IDF files are auto-converted)
        wall_type: Type of wall construction. Options:
                  - "MassWall" (concrete, brick, stone)
                  - "MetalBuildingWall" (metal panel systems)
                  - "SteelFramedWall" (steel studs with insulation)
                  - "WoodFramedWall" (wood studs with insulation)
                  - "BelowGradeWall" (basement/foundation walls)
        code_version: Energy code version (e.g., "90.1-2019", "90.1-2016", "90.1-2013")
        climate_zone: ASHRAE climate zone (e.g., "5A", "3B", "2A", "7")
        wall_list: Optional list of wall names to assign this construction.
                  If None, construction is created but not assigned to any walls.
                  Use find_exterior_walls() to get available wall names.
        use_type: Space use type. Options:
                 - "non_residential" (default - commercial, office, retail)
                 - "residential" (apartments, condos, dormitories)
                 - "semiheated" (warehouses, garages, unconditioned spaces)
        output_path: Optional path for output file (if None, creates one with _modified suffix)

    Returns:
        JSON string with construction creation results including:
        - Materials added to the model
        - Construction name and composition
        - Target and achieved U-factor
        - Number of walls modified

    Examples:
        # Create steel-framed wall construction for climate zone 5A
        set_exterior_wall_construction(
            "model.epJSON",
            wall_type="SteelFramedWall",
            code_version="90.1-2019",
            climate_zone="5A"
        )
        
        # Find walls first, then apply construction
        walls_info = find_exterior_walls("model.epJSON")
        set_exterior_wall_construction(
            "model.epJSON",
            wall_type="MassWall",
            code_version="90.1-2019",
            climate_zone="3B",
            wall_list=["North_Wall", "South_Wall", "East_Wall", "West_Wall"]
        )
        
        # Residential wood-framed walls for cold climate
        set_exterior_wall_construction(
            "model.epJSON",
            wall_type="WoodFramedWall",
            code_version="90.1-2019",
            climate_zone="7",
            use_type="residential"
        )
        
        # Below-grade walls for basement
        set_exterior_wall_construction(
            "model.epJSON",
            wall_type="BelowGradeWall",
            code_version="90.1-2019",
            climate_zone="5A",
            wall_list=["Basement_Wall_North", "Basement_Wall_South"]
        )
    """
    try:
        logger.info(f"Setting exterior wall construction: {epjson_path}")
        logger.info(f"Parameters: {wall_type}, {code_version}, {climate_zone}, {use_type}")
        
        # Load the epJSON model
        resolved_path = ep_manager._resolve_epjson_path(epjson_path)
        ep = ep_manager.load_json(resolved_path)
        
        # Apply the construction
        ep = ep_manager.set_exterior_wall_construction(
            ep=ep,
            wall_type=wall_type,
            code_version=code_version,
            climate_zone=climate_zone,
            wall_list=wall_list,
            use_type=use_type
        )
        
        # Determine output path
        if output_path is None:
            from pathlib import Path
            path_obj = Path(resolved_path)
            output_path = str(path_obj.parent / f"{path_obj.stem}_modified{path_obj.suffix}")
        
        # Save the modified model
        ep_manager.save_json(ep, output_path)
        
        result = {
            "success": True,
            "input_file": resolved_path,
            "output_file": output_path,
            "wall_type": wall_type,
            "code_version": code_version,
            "climate_zone": climate_zone,
            "use_type": use_type,
            "walls_modified": len(wall_list) if wall_list else 0,
            "wall_names": wall_list if wall_list else [],
            "message": f"Successfully created {wall_type} construction for {use_type} use complying with {code_version} for climate zone {climate_zone}"
        }
        
        logger.info(f"Successfully set exterior wall construction: {output_path}")
        return f"Exterior wall construction set:\n{json.dumps(result, indent=2)}"
        
    except FileNotFoundError as e:
        logger.warning(f"epJSON file not found: {epjson_path}")
        return f"File not found: {str(e)}"
    except ValueError as e:
        logger.warning(f"Invalid parameter for set_exterior_wall_construction: {str(e)}")
        return f"Invalid parameter: {str(e)}"
    except KeyError as e:
        logger.error(f"Configuration not found in data files: {str(e)}")
        return f"Configuration not found: {str(e)}. Please verify that wall_type ('{wall_type}'), code_version ('{code_version}'), climate_zone ('{climate_zone}'), and use_type ('{use_type}') are valid."
    except RuntimeError as e:
        logger.error(f"Runtime error: {str(e)}")
        return f"Runtime error: {str(e)}"
    except Exception as e:
        logger.error(f"Error setting exterior wall construction for {epjson_path}: {str(e)}")
        return f"Error setting exterior wall construction: {str(e)}"


@mcp.tool()
async def list_zones(epjson_path: str) -> str:
    """
    List all zones in the EnergyPlus model

    Args:
        epjson_path: Path to the epJSON file

    Returns:
        JSON string with detailed zone information
    """
    try:
        logger.info(f"Listing zones: {epjson_path}")
        resolved_path = ep_manager._resolve_epjson_path(epjson_path)
        ep_data = ep_manager.load_json(resolved_path)
        zones = ep_manager.list_zones(ep_data)
        return f"Zones in {epjson_path}:\n{zones}"
    except FileNotFoundError as e:
        logger.warning(f"epJSON file not found: {epjson_path}")
        return f"File not found: {str(e)}"
    except Exception as e:
        logger.error(f"Error listing zones for {epjson_path}: {str(e)}")
        return f"Error listing zones for {epjson_path}: {str(e)}"


@mcp.tool()
async def get_surfaces(epjson_path: str) -> str:
    """
    Get detailed surface information from the EnergyPlus model

    Args:
        epjson_path: Path to the epJSON file

    Returns:
        JSON string with surface details
    """
    try:
        logger.info(f"Getting surfaces: {epjson_path}")
        resolved_path = ep_manager._resolve_epjson_path(epjson_path)
        ep_data = ep_manager.load_json(resolved_path)
        surfaces = ep_manager.get_surfaces(ep_data)
        return f"Surfaces in {epjson_path}:\n{surfaces}"
    except FileNotFoundError as e:
        logger.warning(f"epJSON file not found: {epjson_path}")
        return f"File not found: {str(e)}"
    except Exception as e:
        logger.error(f"Error getting surfaces for {epjson_path}: {str(e)}")
        return f"Error getting surfaces for {epjson_path}: {str(e)}"


@mcp.tool()
async def get_materials(epjson_path: str) -> str:
    """
    Get material information from the EnergyPlus model

    Args:
        epjson_path: Path to the epJSON file

    Returns:
        JSON string with material details
    """
    try:
        logger.info(f"Getting materials: {epjson_path}")
        resolved_path = ep_manager._resolve_epjson_path(epjson_path)
        ep_data = ep_manager.load_json(resolved_path)
        materials = ep_manager.get_materials(ep_data)
        return f"Materials in {epjson_path}:\n{materials}"
    except FileNotFoundError as e:
        logger.warning(f"epJSON file not found: {epjson_path}")
        return f"File not found: {str(e)}"
    except Exception as e:
        logger.error(f"Error getting materials for {epjson_path}: {str(e)}")
        return f"Error getting materials for {epjson_path}: {str(e)}"


@mcp.tool()
async def validate_epjson(epjson_path: str) -> str:
    """
    Validate an EnergyPlus epJSON file and return validation results

    Args:
        epjson_path: Path to the epJSON file

    Returns:
        JSON string with validation results, warnings, and errors
    """
    try:
        logger.info(f"Validating epJSON: {epjson_path}")
        validation_result = ep_manager.validate_epjson(epjson_path)
        return f"Validation results for {epjson_path}:\n{validation_result}"
    except FileNotFoundError as e:
        logger.warning(f"epJSON file not found: {epjson_path}")
        return f"File not found: {str(e)}"
    except Exception as e:
        logger.error(f"Error validating epJSON {epjson_path}: {str(e)}")
        return f"Error validating epJSON {epjson_path}: {str(e)}"


@mcp.tool()
async def get_output_variables(
    epjson_path: str, discover_available: bool = False, run_days: int = 1
) -> str:
    """
    Get output variables from the model - either configured variables or discover all available ones

    Args:
        epjson_path: Path to the epJSON file (can be absolute, relative, or just filename for sample files)
        discover_available: If True, runs a short simulation to discover all available variables.
                          If False, returns currently configured variables in the epJSON file (default: False)
        run_days: Number of days to run for discovery simulation (default: 1, only used if discover_available=True)

    Returns:
        JSON string with output variables information. When discover_available=True, includes
        all possible variables with units, frequencies, and ready-to-use Output:Variable lines.
        When discover_available=False, shows only currently configured Output:Variable and Output:Meter objects.
    """
    try:
        logger.info(
            f"Getting output variables: {epjson_path} (discover_available={discover_available})"
        )
        resolved_path = ep_manager._resolve_epjson_path(epjson_path)
        ep_data = ep_manager.load_json(resolved_path)
        result = ep_manager.get_output_variables(ep_data, discover_available, run_days)

        mode = (
            "available variables discovery"
            if discover_available
            else "configured variables"
        )
        return f"Output variables ({mode}) for {epjson_path}:\n{result}"

    except FileNotFoundError as e:
        logger.warning(f"epJSON file not found: {epjson_path}")
        return f"File not found: {str(e)}"
    except Exception as e:
        logger.error(f"Error getting output variables for {epjson_path}: {str(e)}")
        return f"Error getting output variables for {epjson_path}: {str(e)}"


@mcp.tool()
async def get_output_meters(
    epjson_path: str, discover_available: bool = False, run_days: int = 1
) -> str:
    """
    Get output meters from the model - either configured meters or discover all available ones

    Args:
        epjson_path: Path to the epJSON file (can be absolute, relative, or just filename for sample files)
        discover_available: If True, runs a short simulation to discover all available meters.
                          If False, returns currently configured meters in the epJSON file (default: False)
        run_days: Number of days to run for discovery simulation (default: 1, only used if discover_available=True)

    Returns:
        JSON string with meter information. When discover_available=True, includes
        all possible meters with units, frequencies, and ready-to-use Output:Meter lines.
        When discover_available=False, shows only currently configured Output:Meter objects.
    """
    try:
        logger.info(
            f"Getting output meters: {epjson_path} (discover_available={discover_available})"
        )
        resolved_path = ep_manager._resolve_epjson_path(epjson_path)
        ep_data = ep_manager.load_json(resolved_path)
        result = ep_manager.get_output_meters(ep_data, discover_available, run_days)

        mode = (
            "available meters discovery" if discover_available else "configured meters"
        )
        return f"Output meters ({mode}) for {epjson_path}:\n{result}"

    except FileNotFoundError as e:
        logger.warning(f"epJSON file not found: {epjson_path}")
        return f"File not found: {str(e)}"
    except Exception as e:
        logger.error(f"Error getting output meters for {epjson_path}: {str(e)}")
        return f"Error getting output meters for {epjson_path}: {str(e)}"


@mcp.tool()
async def add_output_variables(
    epjson_path: str,
    variables: List,  # Can be List[Dict], List[str], or mixed
    validation_level: str = "moderate",
    allow_duplicates: bool = False,
    output_path: Optional[str] = None,
) -> str:
    """
    Add output variables to an EnergyPlus epJSON file with intelligent validation

    Args:
        epjson_path: Path to the input epJSON file (can be absolute, relative, or filename for sample files)
        variables: List of variable specifications. Can be:
                  - Simple strings: ["Zone Air Temperature", "Surface Inside Face Temperature"]
                  - [name, frequency] pairs: [["Zone Air Temperature", "hourly"], ["Surface Temperature", "daily"]]
                  - Full specifications: [{"key_value": "*", "variable_name": "Zone Air Temperature", "frequency": "hourly"}]
                  - Mixed formats in the same list
        validation_level: Validation strictness level:
                         - "strict": Full validation with model checking (recommended for beginners)
                         - "moderate": Basic validation with helpful warnings (default)
                         - "lenient": Minimal validation (for advanced users)
        allow_duplicates: Whether to allow duplicate output variable specifications (default: False)
        output_path: Optional path for output file (if None, creates one with _with_outputs suffix)

    Returns:
        JSON string with detailed results including validation report, added variables, and performance metrics

    Examples:
        # Simple usage
        add_output_variables("model.epJSON", ["Zone Air Temperature", "Zone Air Relative Humidity"])

        # With custom frequencies
        add_output_variables("model.epJSON", [["Zone Air Temperature", "daily"], ["Surface Temperature", "hourly"]])

        # Full control
        add_output_variables("model.epJSON", [
            {"key_value": "Zone1", "variable_name": "Zone Air Temperature", "frequency": "hourly"},
            {"key_value": "*", "variable_name": "Surface Inside Face Temperature", "frequency": "daily"}
        ], validation_level="strict")
    """
    try:
        logger.info(
            f"Adding output variables: {epjson_path} ({len(variables)} variables, {validation_level} validation)"
        )
        resolved_path = ep_manager._resolve_epjson_path(epjson_path)
        ep_data = ep_manager.load_json(resolved_path)
        
        # Get modified data from the method (no output_path parameter)
        modified_ep_data = ep_manager.add_output_variables(
            epjson_data=ep_data,
            variables=variables,
            validation_level=validation_level,
            allow_duplicates=allow_duplicates
        )
        
        # Determine output path
        if output_path is None:
            path_obj = Path(resolved_path)
            output_path = str(path_obj.parent / f"{path_obj.stem}_with_outputs{path_obj.suffix}")
        
        # Save the modified data
        ep_manager.save_json(modified_ep_data, output_path)
        
        result = {
            "success": True,
            "input_file": resolved_path,
            "output_file": output_path,
            "variables_requested": len(variables),
            "validation_level": validation_level
        }
        
        return f"Output variables addition results:\n{json.dumps(result, indent=2)}"

    except FileNotFoundError as e:
        logger.warning(f"epJSON file not found: {epjson_path}")
        return f"File not found: {str(e)}"
    except ValueError as e:
        logger.warning(f"Invalid arguments for add_output_variables: {str(e)}")
        return f"Invalid arguments: {str(e)}"
    except Exception as e:
        logger.error(f"Error adding output variables: {str(e)}")
        return f"Error adding output variables: {str(e)}"


@mcp.tool()
async def add_output_meters(
    epjson_path: str,
    meters: List,  # Can be List[Dict], List[str], or mixed
    validation_level: str = "moderate",
    allow_duplicates: bool = False,
    output_path: Optional[str] = None,
) -> str:
    """
    Add output meters to an EnergyPlus epJSON file with intelligent validation

    Args:
        epjson_path: Path to the input epJSON file (can be absolute, relative, or filename for sample files)
        meters: List of meter specifications. Can be:
               - Simple strings: ["Electricity:Facility", "NaturalGas:Facility"]
               - [name, frequency] pairs: [["Electricity:Facility", "hourly"], ["NaturalGas:Facility", "daily"]]
               - [name, frequency, type] triplets: [["Electricity:Facility", "hourly", "Output:Meter"]]
               - Full specifications: [{"meter_name": "Electricity:Facility", "frequency": "hourly", "meter_type": "Output:Meter"}]
               - Mixed formats in the same list
        validation_level: Validation strictness level:
                         - "strict": Full validation with model checking (recommended for beginners)
                         - "moderate": Basic validation with helpful warnings (default)
                         - "lenient": Minimal validation (for advanced users)
        allow_duplicates: Whether to allow duplicate output meter specifications (default: False)
        output_path: Optional path for output file (if None, creates one with _with_meters suffix)

    Returns:
        JSON string with detailed results including validation report, added meters, and performance metrics

    Examples:
        # Simple usage
        add_output_meters("model.epJSON", ["Electricity:Facility", "NaturalGas:Facility"])

        # With custom frequencies
        add_output_meters("model.epJSON", [["Electricity:Facility", "daily"], ["NaturalGas:Facility", "hourly"]])

        # Full control with meter types
        add_output_meters("model.epJSON", [
            {"meter_name": "Electricity:Facility", "frequency": "hourly", "meter_type": "Output:Meter"},
            {"meter_name": "NaturalGas:Facility", "frequency": "daily", "meter_type": "Output:Meter:Cumulative"}
        ], validation_level="strict")
    """
    try:
        logger.info(
            f"Adding output meters: {epjson_path} ({len(meters)} meters, {validation_level} validation)"
        )
        resolved_path = ep_manager._resolve_epjson_path(epjson_path)
        ep_data = ep_manager.load_json(resolved_path)
        
        # Get modified data from the method (no output_path parameter)
        modified_ep_data = ep_manager.add_output_meters(
            epjson_data=ep_data,
            meters=meters,
            validation_level=validation_level,
            allow_duplicates=allow_duplicates
        )
        
        # Determine output path
        if output_path is None:
            path_obj = Path(resolved_path)
            output_path = str(path_obj.parent / f"{path_obj.stem}_with_meters{path_obj.suffix}")
        
        # Save the modified data
        ep_manager.save_json(modified_ep_data, output_path)
        
        result = {
            "success": True,
            "input_file": resolved_path,
            "output_file": output_path,
            "meters_requested": len(meters),
            "validation_level": validation_level
        }
        
        return f"Output meters addition results:\n{json.dumps(result, indent=2)}"

    except FileNotFoundError as e:
        logger.warning(f"epJSON file not found: {epjson_path}")
        return f"File not found: {str(e)}"
    except ValueError as e:
        logger.warning(f"Invalid arguments for add_output_meters: {str(e)}")
        return f"Invalid arguments: {str(e)}"
    except Exception as e:
        logger.error(f"Error adding output meters: {str(e)}")
        return f"Error adding output meters: {str(e)}"


@mcp.tool()
async def list_available_files(
    include_example_files: bool = False, include_weather_data: bool = False
) -> str:
    """
    List available files in specified directories

    Args:
        include_example_files: Whether to include EnergyPlus example files directory (default: False)
        include_weather_data: Whether to include EnergyPlus weather data directory (default: False)

    Returns:
        JSON string with available files organized by source and type. Always includes sample_files directory.
    """
    try:
        logger.info(
            f"Listing available files (example_files={include_example_files}, weather_data={include_weather_data})"
        )
        files = ep_manager.list_available_files(
            include_example_files, include_weather_data
        )
        return f"Available files:\n{files}"
    except Exception as e:
        logger.error(f"Error listing available files: {str(e)}")
        return f"Error listing available files: {str(e)}"


@mcp.tool()
async def get_server_configuration() -> str:
    """
    Get current server configuration information

    Returns:
        JSON string with configuration details
    """
    try:
        logger.info("Getting server configuration")
        config_info = ep_manager.get_configuration_info()
        return f"Current server configuration:\n{config_info}"
    except Exception as e:
        logger.error(f"Error getting configuration: {str(e)}")
        return f"Error getting configuration: {str(e)}"


@mcp.tool()
async def get_server_status() -> str:
    """
    Get current server status and health information

    Returns:
        JSON string with server status
    """
    try:
        import sys
        import platform
        from datetime import datetime

        status_info = {
            "server": {
                "name": config.server.name,
                "version": config.server.version,
                "status": "running",
                "startup_time": datetime.now().isoformat(),
                "debug_mode": config.debug_mode,
            },
            "system": {
                "python_version": sys.version,
                "platform": platform.platform(),
                "architecture": platform.architecture()[0],
            },
            "energyplus": {
                "version": config.energyplus.version,
                "idd_available": (
                    os.path.exists(config.energyplus.idd_path)
                    if config.energyplus.idd_path
                    else False
                ),
                "executable_available": (
                    os.path.exists(config.energyplus.executable_path)
                    if config.energyplus.executable_path
                    else False
                ),
            },
            "paths": {
                "sample_files_available": os.path.exists(
                    config.paths.sample_files_path
                ),
                "temp_dir_available": os.path.exists(config.paths.temp_dir),
                "output_dir_available": os.path.exists(config.paths.output_dir),
            },
        }

        import json

        return f"Server status:\n{json.dumps(status_info, indent=2)}"

    except Exception as e:
        logger.error(f"Error getting server status: {str(e)}")
        return f"Error getting server status: {str(e)}"


@mcp.tool()
async def discover_hvac_loops(epjson_path: str) -> str:
    """
    Discover all HVAC loops (Plant, Condenser, Air) in the EnergyPlus model

    Args:
        epjson_path: Path to the epJSON file

    Returns:
        JSON string with all HVAC loops found, organized by type
    """
    try:
        logger.info(f"Discovering HVAC loops: {epjson_path}")
        resolved_path = ep_manager._resolve_epjson_path(epjson_path)
        ep_data = ep_manager.load_json(resolved_path)
        loops = ep_manager.discover_hvac_loops(ep_data)
        return f"HVAC loops discovered in {epjson_path}:\n{loops}"
    except FileNotFoundError as e:
        logger.warning(f"epJSON file not found: {epjson_path}")
        return f"File not found: {str(e)}"
    except Exception as e:
        logger.error(f"Error discovering HVAC loops for {epjson_path}: {str(e)}")
        return f"Error discovering HVAC loops for {epjson_path}: {str(e)}"


@mcp.tool()
async def get_loop_topology(epjson_path: str, loop_name: str) -> str:
    """
    Get detailed topology information for a specific HVAC loop

    Args:
        epjson_path: Path to the epJSON file
        loop_name: Name of the specific loop to analyze

    Returns:
        JSON string with detailed loop topology including supply/demand sides, branches, and components
    """
    try:
        logger.info(f"Getting loop topology for '{loop_name}': {epjson_path}")
        resolved_path = ep_manager._resolve_epjson_path(epjson_path)
        ep_data = ep_manager.load_json(resolved_path)
        topology = ep_manager.get_loop_topology(ep_data, loop_name)
        return f"Loop topology for '{loop_name}' in {epjson_path}:\n{topology}"
    except FileNotFoundError as e:
        logger.warning(f"epJSON file not found: {epjson_path}")
        return f"File not found: {str(e)}"
    except ValueError as e:
        logger.warning(f"Loop not found: {loop_name}")
        return f"Loop not found: {str(e)}"
    except Exception as e:
        logger.error(f"Error getting loop topology for {epjson_path}: {str(e)}")
        return f"Error getting loop topology for {epjson_path}: {str(e)}"


@mcp.tool()
async def visualize_loop_diagram(
    epjson_path: str,
    loop_name: Optional[str] = None,
    output_path: Optional[str] = None,
    format: str = "png",
    show_legend: bool = True,
) -> str:
    """
    Generate and save a visual diagram of HVAC loop(s)

    Args:
        epjson_path: Path to the epJSON file
        loop_name: Optional specific loop name (if None, shows all loops)
        output_path: Optional custom output path (if None, creates one automatically)
        format: Image format for the diagram (png, jpg, pdf, svg)
        show_legend: Whether to include a legend in the diagram (default: True)

    Returns:
        JSON string with diagram generation results and file path
    """
    try:
        logger.info(
            f"Creating loop diagram for '{loop_name or 'all loops'}': {epjson_path} (show_legend={show_legend})"
        )
        resolved_path = ep_manager._resolve_epjson_path(epjson_path)
        ep_data = ep_manager.load_json(resolved_path)
        result = ep_manager.visualize_loop_diagram(
            ep_data, loop_name, output_path, format, show_legend
        )
        return f"Loop diagram created:\n{result}"
    except FileNotFoundError as e:
        logger.warning(f"epJSON file not found: {epjson_path}")
        return f"File not found: {str(e)}"
    except Exception as e:
        logger.error(f"Error creating loop diagram for {epjson_path}: {str(e)}")
        return f"Error creating loop diagram for {epjson_path}: {str(e)}"


@mcp.tool()
async def run_energyplus_simulation(
    epjson_path: str,
    weather_file: Optional[str] = None,
    output_directory: Optional[str] = None,
    annual: bool = True,
    design_day: bool = False,
    readvars: bool = True,
    expandobjects: bool = True,
) -> str:
    """
    Run EnergyPlus simulation with specified epJSON and weather file

    Args:
        epjson_path: Path to the epJSON file (can be absolute, relative, or just filename for sample files)
        weather_file: Path to weather file (.epw) or city name (e.g., 'San Francisco'). If None, simulation runs without weather file
        output_directory: Directory for simulation outputs (if None, creates timestamped directory in outputs/)
        annual: Run annual simulation (default: True)
        design_day: Run design day only simulation (default: False)
        readvars: Run ReadVarsESO after simulation to process outputs (default: True)
        expandobjects: Run ExpandObjects prior to simulation for HVAC templates (default: True)

    Returns:
        JSON string with simulation results, duration, and output file paths
    """
    try:
        logger.info(f"Running EnergyPlus simulation: {epjson_path}")
        if weather_file:
            logger.info(f"With weather file: {weather_file}")
        
        resolved_path = ep_manager._resolve_epjson_path(epjson_path)
        ep_data = ep_manager.load_json(resolved_path)
        
        result = ep_manager.run_simulation(
            epjson_data=ep_data,
            weather_file=weather_file,
            output_directory=output_directory,
            annual=annual,
            design_day=design_day,
            readvars=readvars,
            expandobjects=expandobjects,
        )
        return f"EnergyPlus simulation completed:\n{result}"
    except FileNotFoundError as e:
        logger.warning(f"File not found for simulation: {str(e)}")
        return f"File not found: {str(e)}"
    except Exception as e:
        logger.error(f"Error running EnergyPlus simulation: {str(e)}")
        return f"Error running simulation: {str(e)}"


@mcp.tool()
async def create_interactive_plot(
    output_directory: str,
    model_name: Optional[str] = None,
    file_type: str = "auto",
    custom_title: Optional[str] = None,
) -> str:
    """
    Create interactive HTML plot from EnergyPlus output files (meter or variable outputs)

    Args:
        output_directory: Directory containing the CSV output files from simulation
        model_name: Name of the model file (without extension). If None, auto-detects from files
        file_type: Type of file to plot - "meter", "variable", or "auto" (default: auto)
        custom_title: Custom title for the plot (optional)

    Returns:
        JSON string with plot creation results and file path
    """
    try:
        logger.info(f"Creating interactive plot from: {output_directory}")
        result = ep_manager.create_interactive_plot(
            output_directory, model_name, file_type, custom_title
        )
        return f"Interactive plot created:\n{result}"
    except FileNotFoundError as e:
        logger.warning(f"Output files not found: {str(e)}")
        return f"Files not found: {str(e)}"
    except Exception as e:
        logger.error(f"Error creating interactive plot: {str(e)}")
        return f"Error creating interactive plot: {str(e)}"


@mcp.tool()
async def get_server_logs(lines: int = 50) -> str:
    """
    Get recent server log entries

    Args:
        lines: Number of recent log lines to return (default 50)

    Returns:
        Recent log entries as text
    """
    try:
        log_file = (
            Path(config.paths.workspace_root) / "logs" / "energyplus_mcp_server.log"
        )

        if not log_file.exists():
            return "Log file not found. Server may be using console logging only."

        # Read last N lines efficiently
        with open(log_file, "r") as f:
            all_lines = f.readlines()
            recent_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines

        log_content = {
            "log_file": str(log_file),
            "total_lines": len(all_lines),
            "showing_lines": len(recent_lines),
            "recent_logs": "".join(recent_lines),
        }

        return f"Recent server logs:\n{json.dumps(log_content, indent=2)}"

    except Exception as e:
        logger.error(f"Error reading server logs: {str(e)}")
        return f"Error reading server logs: {str(e)}"


@mcp.tool()
async def get_error_logs(lines: int = 20) -> str:
    """
    Get recent error log entries

    Args:
        lines: Number of recent error lines to return (default 20)

    Returns:
        Recent error log entries as text
    """
    try:
        error_log_file = (
            Path(config.paths.workspace_root) / "logs" / "energyplus_mcp_errors.log"
        )

        if not error_log_file.exists():
            return "Error log file not found. No errors logged yet."

        with open(error_log_file, "r") as f:
            all_lines = f.readlines()
            recent_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines

        error_content = {
            "error_log_file": str(error_log_file),
            "total_error_lines": len(all_lines),
            "showing_lines": len(recent_lines),
            "recent_errors": "".join(recent_lines),
        }

        return f"Recent error logs:\n{json.dumps(error_content, indent=2)}"

    except Exception as e:
        logger.error(f"Error reading error logs: {str(e)}")
        return f"Error reading error logs: {str(e)}"


@mcp.tool()
async def clear_logs() -> str:
    """
    Clear/rotate current log files (creates backup)

    Returns:
        Status of log clearing operation
    """
    try:
        log_dir = Path(config.paths.workspace_root) / "logs"

        if not log_dir.exists():
            return "No log directory found."

        cleared_files = []

        # Main log file
        main_log = log_dir / "energyplus_mcp_server.log"
        if main_log.exists():
            backup_name = f"energyplus_mcp_server_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
            main_log.rename(log_dir / backup_name)
            cleared_files.append(str(main_log))

        # Error log file
        error_log = log_dir / "energyplus_mcp_errors.log"
        if error_log.exists():
            backup_name = f"energyplus_mcp_errors_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
            error_log.rename(log_dir / backup_name)
            cleared_files.append(str(error_log))

        result = {
            "success": True,
            "cleared_files": cleared_files,
            "backup_location": str(log_dir),
            "message": "Log files cleared and backed up successfully",
        }

        logger.info("Log files cleared and backed up")
        return json.dumps(result, indent=2)

    except Exception as e:
        logger.error(f"Error clearing logs: {str(e)}")
        return f"Error clearing logs: {str(e)}"


if __name__ == "__main__":
    logger.info(f"Starting {config.server.name} v{config.server.version}")
    logger.info(f"EnergyPlus version: {config.energyplus.version}")
    logger.info(f"Sample files path: {config.paths.sample_files_path}")

    try:
        # Use FastMCP's built-in run method with stdio transport
        mcp.run(transport="stdio")
    except KeyboardInterrupt:
        logger.info("Server shutdown requested")
    except Exception as e:
        logger.error(f"Server error: {str(e)}")
        raise
    finally:
        logger.info("Server stopped")
