"""
Lights object utility module for EnergyPlus MCP Server.
Handles inspection and modification of Lights objects in EnergyPlus models.
"""

import logging
from typing import Dict, List, Any, Optional
import json

logger = logging.getLogger(__name__)


def load_json(file_path: str) -> Dict[str, Any]:
    """Load JSON file and return its content"""
    with open(file_path, 'r') as f:
        return json.load(f)


class LightsManager:
    """Manager for EnergyPlus Lights objects"""
    
    # Valid calculation methods for Lighting Level
    VALID_CALCULATION_METHODS = {
        "LightingLevel": "Lighting level (W)",
        "Watts/Area": "Lighting power density (W/m2)", 
        "Watts/Person": "Lighting power per person (W/person)"
    }
    
    # Common lighting power densities (W/m2) - from ASHRAE 90.1
    COMMON_LIGHTING_DENSITIES = {
        "Office": 11.0,
        "Classroom": 12.9,
        "Conference Room": 13.2,
        "Corridor": 5.4,
        "Lobby": 12.9,
        "Restroom": 9.7,
        "Storage": 8.1,
        "Workshop": 14.0
    }
    
    def __init__(self):
        """Initialize the Lights manager"""
        pass
    
    def get_lights_objects(self, ep_path: str) -> Dict[str, Any]:
        """
        Get all Lights objects from the epJSON file with detailed information
        
        Args:
            ep_path: Path to the epJSON file
            
        Returns:
            Dictionary with lights objects information
        """
        try:
            ep = load_json(ep_path)
            lights_objects = ep.get("Lights", {})
            
            result = {
                "success": True,
                "file_path": ep_path,
                "total_lights_objects": len(lights_objects),
                "lights_objects": [],
                "summary": {
                    "by_calculation_method": {},
                    "by_zone": {},
                    "total_lighting_power": 0.0,
                    "total_lighting_density": 0.0
                }
            }
            
            # Get all zones as a dictionary for lookup
            zones_dict = ep.get("Zone", {})
            
            for lights_name, lights_data in lights_objects.items():
                lights_info = {
                    "name": lights_name,
                    "zone_or_zonelist_or_space_or_spacelist_name": lights_data.get("zone_or_zonelist_or_space_or_spacelist_name", "Unknown"),
                    "schedule_name": lights_data.get("schedule_name", "Unknown"),
                    "design_level_calculation_method": lights_data.get("design_level_calculation_method", "Unknown"),
                    "lighting_level": lights_data.get("lighting_level", ""),
                    "watts_per_floor_area": lights_data.get("watts_per_floor_area", ""),
                    "watts_per_person": lights_data.get("watts_per_person", ""),
                    "return_air_fraction": lights_data.get("return_air_fraction", ""),
                    "fraction_radiant": lights_data.get("fraction_radiant", ""),
                    "fraction_visible": lights_data.get("fraction_visible", ""),
                    "fraction_replaceable": lights_data.get("fraction_replaceable", ""),
                    "end_use_subcategory": lights_data.get("end_use_subcategory", ""),
                    "return_air_fraction_calculated_from_plenum_temperature": 
                        lights_data.get("return_air_fraction_calculated_from_plenum_temperature", ""),
                    "return_air_fraction_function_of_plenum_temperature_coefficient_1":
                        lights_data.get("return_air_fraction_function_of_plenum_temperature_coefficient_1", ""),
                    "return_air_fraction_function_of_plenum_temperature_coefficient_2":
                        lights_data.get("return_air_fraction_function_of_plenum_temperature_coefficient_2", ""),
                    "return_air_heat_gain_node_name": lights_data.get("return_air_heat_gain_node_name", ""),
                    "exhaust_air_heat_gain_node_name": lights_data.get("exhaust_air_heat_gain_node_name", "")
                }
                
                # Calculate design lighting power if possible
                zone_name = lights_info["zone_or_zonelist_or_space_or_spacelist_name"]
                zone_data = zones_dict.get(zone_name) if zone_name != "Unknown" else None
                design_power = self._calculate_design_power(lights_info, zone_data)
                lights_info["design_power"] = design_power
                
                result["lights_objects"].append(lights_info)
                
                # Update summaries
                calc_method = lights_info["design_level_calculation_method"]
                if calc_method:
                    result["summary"]["by_calculation_method"][calc_method] = \
                        result["summary"]["by_calculation_method"].get(calc_method, 0) + 1
                
                zone_name = lights_info["zone_or_zonelist_or_space_or_spacelist_name"]
                if zone_name:
                    if zone_name not in result["summary"]["by_zone"]:
                        result["summary"]["by_zone"][zone_name] = []
                    result["summary"]["by_zone"][zone_name].append(lights_info["name"])
                
                if design_power is not None:
                    result["summary"]["total_lighting_power"] += design_power
            
            logger.info(f"Found {len(lights_objects)} Lights objects in {ep_path}")
            return result
            
        except Exception as e:
            logger.error(f"Error getting Lights objects: {e}")
            return {
                "success": False,
                "error": str(e),
                "file_path": ep_path
            }
    
    def _calculate_design_power(self, lights_info: Dict[str, Any], 
                               zone_data: Optional[Dict[str, Any]]) -> Optional[float]:
        """Calculate design lighting power based on calculation method and zone data"""
        try:
            calc_method = lights_info["design_level_calculation_method"]
            
            if calc_method == "LightingLevel":
                value = lights_info["lighting_level"]
                if value and value != '':
                    return float(value)
                    
            elif calc_method == "Watts/Area" and zone_data:
                watts_per_area = lights_info["watts_per_floor_area"]
                if watts_per_area and watts_per_area != '':
                    # Get zone floor area from epJSON
                    floor_area = zone_data.get('floor_area')
                    if floor_area and floor_area != '' and floor_area != 'autocalculate':
                        return float(watts_per_area) * float(floor_area)
                        
            elif calc_method == "Watts/Person":
                watts_per_person = lights_info["watts_per_person"]
                if watts_per_person and watts_per_person != '':
                    # Would need to get occupancy from People objects to calculate total power
                    # For now, just return the watts per person value as a placeholder
                    return float(watts_per_person)
            
        except (ValueError, TypeError) as e:
            logger.warning(f"Could not calculate design power: {e}")
        
        return None
    
    def modify_lights_objects(self, ep_path: str, modifications: List[Dict[str, Any]], 
                             output_path: str) -> Dict[str, Any]:
        """
        Modify Lights objects in the epJSON file
        
        Args:
            ep_path: Path to the input epJSON file
            modifications: List of modification specifications
            output_path: Path for the output epJSON file
            
        Returns:
            Dictionary with modification results
        """
        try:
            ep = load_json(ep_path)
            lights_objects = ep.get("Lights", {})
            
            result = {
                "success": True,
                "input_file": ep_path,
                "output_file": output_path,
                "modifications_requested": len(modifications),
                "modifications_applied": [],
                "errors": []
            }
            
            for mod_spec in modifications:
                try:
                    # Apply modification based on target
                    target = mod_spec.get("target", "all")
                    field_updates = mod_spec.get("field_updates", {})
                    
                    if target == "all":
                        # Apply to all Lights objects
                        for lights_name, lights_data in lights_objects.items():
                            self._apply_lights_modifications(
                                lights_name, lights_data, field_updates, result
                            )
                    elif target.startswith("zone:"):
                        # Apply to Lights objects in specific zone
                        zone_name = target.replace("zone:", "").strip()
                        for lights_name, lights_data in lights_objects.items():
                            if lights_data.get('zone_or_zonelist_or_space_or_spacelist_name', '') == zone_name:
                                self._apply_lights_modifications(
                                    lights_name, lights_data, field_updates, result
                                )
                    elif target.startswith("name:"):
                        # Apply to specific Lights object by name
                        target_name = target.replace("name:", "").strip()
                        if target_name in lights_objects:
                            self._apply_lights_modifications(
                                target_name, lights_objects[target_name], field_updates, result
                            )
                        else:
                            result["errors"].append(f"Lights object '{target_name}' not found")
                    else:
                        result["errors"].append(f"Invalid target specification: {target}")
                        
                except Exception as e:
                    result["errors"].append(f"Error processing modification: {str(e)}")
            
            # Save the modified epJSON
            with open(output_path, 'w') as f:
                json.dump(ep, f, indent=2)
            
            result["total_modifications_applied"] = len(result["modifications_applied"])
            
            logger.info(f"Applied {len(result['modifications_applied'])} modifications to Lights objects")
            return result
            
        except Exception as e:
            logger.error(f"Error modifying Lights objects: {e}")
            return {
                "success": False,
                "error": str(e),
                "input_file": ep_path
            }
    
    def _apply_lights_modifications(self, lights_name: str, lights_data: Dict[str, Any],
                                   field_updates: Dict[str, Any], result: Dict[str, Any]) -> None:
        """Apply field updates to a Lights object in epJSON format"""
        # Valid Lights object fields (epJSON format - lowercase with underscores)
        valid_fields = {
            "schedule_name",
            "design_level_calculation_method", 
            "lighting_level",
            "watts_per_floor_area",
            "watts_per_person",
            "return_air_fraction",
            "fraction_radiant",
            "fraction_visible",
            "fraction_replaceable",
            "end_use_subcategory",
            "return_air_fraction_calculated_from_plenum_temperature",
            "return_air_fraction_function_of_plenum_temperature_coefficient_1",
            "return_air_fraction_function_of_plenum_temperature_coefficient_2",
            "return_air_heat_gain_node_name",
            "exhaust_air_heat_gain_node_name"
        }
        
        # Fraction fields that must be between 0.0 and 1.0
        fraction_fields = {
            "return_air_fraction",
            "fraction_radiant", 
            "fraction_visible",
            "fraction_replaceable"
        }
        
        # Numeric fields that must be >= 0
        positive_numeric_fields = {
            "lighting_level",
            "watts_per_floor_area",
            "watts_per_person",
            "return_air_fraction_function_of_plenum_temperature_coefficient_1",
            "return_air_fraction_function_of_plenum_temperature_coefficient_2"
        }
        
        for field_name, new_value in field_updates.items():
            # Normalize field name to lowercase with underscores
            field_key = field_name.lower().replace(" ", "_")
            
            if field_key not in valid_fields:
                result["errors"].append(f"Invalid field '{field_name}' for Lights object '{lights_name}'")
                continue
            
            try:
                # Validate calculation method change
                if field_key == "design_level_calculation_method":
                    if new_value not in self.VALID_CALCULATION_METHODS:
                        result["errors"].append(
                            f"Invalid calculation method '{new_value}' for '{lights_name}'. "
                            f"Valid options: {list(self.VALID_CALCULATION_METHODS.keys())}"
                        )
                        continue
                
                # Validate fraction fields (0.0 to 1.0)
                if field_key in fraction_fields:
                    try:
                        float_value = float(new_value)
                        if not (0.0 <= float_value <= 1.0):
                            result["errors"].append(
                                f"Field '{field_key}' for '{lights_name}' must be between 0.0 and 1.0, got {new_value}"
                            )
                            continue
                    except (ValueError, TypeError):
                        result["errors"].append(
                            f"Field '{field_key}' for '{lights_name}' must be a number, got {new_value}"
                        )
                        continue
                
                # Validate positive numeric fields
                if field_key in positive_numeric_fields:
                    try:
                        float_value = float(new_value)
                        if float_value < 0.0:
                            result["errors"].append(
                                f"Field '{field_key}' for '{lights_name}' must be >= 0.0, got {new_value}"
                            )
                            continue
                    except (ValueError, TypeError):
                        result["errors"].append(
                            f"Field '{field_key}' for '{lights_name}' must be a number, got {new_value}"
                        )
                        continue
                
                # Validate plenum temperature choice field
                if field_key == "return_air_fraction_calculated_from_plenum_temperature":
                    if str(new_value).lower() not in ['yes', 'no']:
                        result["errors"].append(
                            f"Field '{field_key}' for '{lights_name}' must be 'Yes' or 'No', got {new_value}"
                        )
                        continue
                
                old_value = lights_data.get(field_key, "")
                lights_data[field_key] = new_value
                
                result["modifications_applied"].append({
                    "object_name": lights_name,
                    "field": field_key,
                    "old_value": old_value,
                    "new_value": new_value
                })
                
                logger.debug(f"Updated {lights_name}.{field_key}: {old_value} -> {new_value}")
                
            except Exception as e:
                result["errors"].append(
                    f"Error setting {field_name} to {new_value} for '{lights_name}': {str(e)}"
                )
    
    def validate_lights_modifications(self, modifications: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Validate modification specifications before applying them
        
        Args:
            modifications: List of modification specifications
            
        Returns:
            Validation result dictionary
        """
        validation_result = {
            "valid": True,
            "errors": [],
            "warnings": []
        }
        
        # Valid field names based on IDD
        valid_fields = {
            "Schedule_Name",
            "Design_Level_Calculation_Method", 
            "Lighting_Level",
            "Watts_per_Floor_Area",
            "Watts_per_Person",
            "Return_Air_Fraction",
            "Fraction_Radiant",
            "Fraction_Visible",
            "Fraction_Replaceable",
            "EndUse_Subcategory",
            "Return_Air_Fraction_Calculated_from_Plenum_Temperature",
            "Return_Air_Fraction_Function_of_Plenum_Temperature_Coefficient_1",
            "Return_Air_Fraction_Function_of_Plenum_Temperature_Coefficient_2",
            "Return_Air_Heat_Gain_Node_Name",
            "Exhaust_Air_Heat_Gain_Node_Name"
        }
        
        for i, mod_spec in enumerate(modifications):
            # Check required fields
            if "target" not in mod_spec:
                validation_result["errors"].append(f"Modification {i}: Missing 'target' field")
                validation_result["valid"] = False
            
            if "field_updates" not in mod_spec:
                validation_result["errors"].append(f"Modification {i}: Missing 'field_updates' field")
                validation_result["valid"] = False
            elif not isinstance(mod_spec["field_updates"], dict):
                validation_result["errors"].append(f"Modification {i}: 'field_updates' must be a dictionary")
                validation_result["valid"] = False
            else:
                # Validate individual field updates
                field_updates = mod_spec["field_updates"]
                for field_name, value in field_updates.items():
                    if field_name not in valid_fields:
                        validation_result["errors"].append(
                            f"Modification {i}: Invalid field name '{field_name}'. "
                            f"Valid fields: {sorted(valid_fields)}"
                        )
                        validation_result["valid"] = False
                    
                    # Check for conflicting calculation method and values
                    if field_name == "Design_Level_Calculation_Method":
                        if value == "LightingLevel" and "Watts_per_Floor_Area" in field_updates:
                            validation_result["warnings"].append(
                                f"Modification {i}: Setting calculation method to 'LightingLevel' "
                                "but also setting 'Watts_per_Floor_Area'"
                            )
                        elif value == "Watts/Area" and "Lighting_Level" in field_updates:
                            validation_result["warnings"].append(
                                f"Modification {i}: Setting calculation method to 'Watts/Area' "
                                "but also setting 'Lighting_Level'"
                            )
                        elif value == "Watts/Person" and ("Lighting_Level" in field_updates or "Watts_per_Floor_Area" in field_updates):
                            validation_result["warnings"].append(
                                f"Modification {i}: Setting calculation method to 'Watts/Person' "
                                "but also setting other power values"
                            )
            
            # Validate target format
            target = mod_spec.get("target", "")
            if target and not (target == "all" or target.startswith("zone:") or target.startswith("name:")):
                validation_result["errors"].append(
                    f"Modification {i}: Invalid target format '{target}'. "
                    "Use 'all', 'zone:ZoneName', or 'name:LightsName'"
                )
                validation_result["valid"] = False
        
        return validation_result 
