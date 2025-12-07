"""
Electric Equipment utility module for EnergyPlus MCP Server.
Handles inspection and modification of ElectricEquipment objects in EnergyPlus models.
"""

import logging
from typing import Dict, List, Any, Optional
import json

logger = logging.getLogger(__name__)


def load_json(file_path: str) -> Dict[str, Any]:
    """Load JSON file and return its content"""
    with open(file_path, "r") as f:
        return json.load(f)


class ElectricEquipmentManager:
    """Manager for EnergyPlus ElectricEquipment objects"""

    # Valid calculation methods for Design Level
    VALID_CALCULATION_METHODS = {
        "EquipmentLevel": "Equipment level (W)",
        "Watts/Area": "Power density (W/m2)",
        "Watts/Person": "Power per person (W/person)",
    }

    # Common electric equipment power densities (W/m2) - from ASHRAE 90.1
    COMMON_EQUIPMENT_DENSITIES = {
        "Office": 12.0,
        "Classroom": 6.4,
        "Conference Room": 6.4,
        "Corridor": 3.2,
        "Lobby": 6.4,
        "Restroom": 3.2,
        "Storage": 3.2,
        "Kitchen": 25.0,
        "Data Center": 215.0,
    }

    def __init__(self):
        """Initialize the ElectricEquipment manager"""
        pass

    def get_electric_equipment_objects(self, ep_path: str) -> Dict[str, Any]:
        """
        Get all ElectricEquipment objects from the epJSON file with detailed information

        Args:
            ep_path: Path to the epJSON file

        Returns:
            Dictionary with electric equipment objects information
        """
        try:
            ep = load_json(ep_path)
            equipment_objects = ep.get("ElectricEquipment", {})

            result = {
                "success": True,
                "file_path": ep_path,
                "total_electric_equipment_objects": len(equipment_objects),
                "electric_equipment_objects": [],
                "summary": {
                    "by_calculation_method": {},
                    "by_zone": {},
                    "total_equipment_power": 0.0,
                },
            }

            # Get all zones as a dictionary for lookup
            zones_dict = ep.get("Zone", {})

            for equipment_name, equipment_data in equipment_objects.items():
                equipment_info = {
                    "name": equipment_name,
                    "zone_or_zonelist_or_space_or_spacelist_name": equipment_data.get(
                        "zone_or_zonelist_or_space_or_spacelist_name", "Unknown"
                    ),
                    "schedule_name": equipment_data.get("schedule_name", "Unknown"),
                    "design_level_calculation_method": equipment_data.get(
                        "design_level_calculation_method", "Unknown"
                    ),
                    "design_level": equipment_data.get("design_level", ""),
                    "watts_per_floor_area": equipment_data.get(
                        "watts_per_floor_area", ""
                    ),
                    "watts_per_person": equipment_data.get("watts_per_person", ""),
                    "fraction_latent": equipment_data.get("fraction_latent", ""),
                    "fraction_radiant": equipment_data.get("fraction_radiant", ""),
                    "fraction_lost": equipment_data.get("fraction_lost", ""),
                    "end_use_subcategory": equipment_data.get(
                        "end_use_subcategory", ""
                    ),
                }

                # Calculate design equipment power if possible
                zone_name = equipment_info[
                    "zone_or_zonelist_or_space_or_spacelist_name"
                ]
                zone_data = (
                    zones_dict.get(zone_name) if zone_name != "Unknown" else None
                )
                design_power = self._calculate_design_power(equipment_info, zone_data)
                equipment_info["design_power"] = design_power

                result["electric_equipment_objects"].append(equipment_info)

                # Update summaries
                calc_method = equipment_info["design_level_calculation_method"]
                if calc_method:
                    result["summary"]["by_calculation_method"][calc_method] = (
                        result["summary"]["by_calculation_method"].get(calc_method, 0)
                        + 1
                    )

                zone_name = equipment_info[
                    "zone_or_zonelist_or_space_or_spacelist_name"
                ]
                if zone_name:
                    if zone_name not in result["summary"]["by_zone"]:
                        result["summary"]["by_zone"][zone_name] = []
                    result["summary"]["by_zone"][zone_name].append(
                        equipment_info["name"]
                    )

                if design_power is not None:
                    result["summary"]["total_equipment_power"] += design_power

            logger.info(
                f"Found {len(equipment_objects)} ElectricEquipment objects in {ep_path}"
            )
            return result

        except Exception as e:
            logger.error(f"Error getting ElectricEquipment objects: {e}")
            return {"success": False, "error": str(e), "file_path": ep_path}

    def _calculate_design_power(
        self, equipment_info: Dict[str, Any], zone_data: Optional[Dict[str, Any]]
    ) -> Optional[float]:
        """Calculate design equipment power based on calculation method and zone data"""
        try:
            calc_method = equipment_info["design_level_calculation_method"]

            if calc_method == "EquipmentLevel":
                value = equipment_info["design_level"]
                if value and value != "":
                    return float(value)

            elif calc_method == "Watts/Area" and zone_data:
                watts_per_area = equipment_info["watts_per_floor_area"]
                if watts_per_area and watts_per_area != "":
                    # Get zone floor area from epJSON
                    floor_area = zone_data.get("floor_area")
                    if (
                        floor_area
                        and floor_area != ""
                        and floor_area != "autocalculate"
                    ):
                        return float(watts_per_area) * float(floor_area)

            elif calc_method == "Watts/Person":
                watts_per_person = equipment_info["watts_per_person"]
                if watts_per_person and watts_per_person != "":
                    # Would need to get occupancy from People objects to calculate total power
                    # For now, just return the watts per person value as a placeholder
                    return float(watts_per_person)

        except (ValueError, TypeError) as e:
            logger.warning(f"Could not calculate design power: {e}")

        return None

    def modify_electric_equipment_objects(
        self, ep_path: str, modifications: List[Dict[str, Any]], output_path: str
    ) -> Dict[str, Any]:
        """
        Modify ElectricEquipment objects in the epJSON file

        Args:
            ep_path: Path to the input epJSON file
            modifications: List of modification specifications
            output_path: Path for the output epJSON file

        Returns:
            Dictionary with modification results
        """
        try:
            ep = load_json(ep_path)
            equipment_objects = ep.get("ElectricEquipment", {})

            result = {
                "success": True,
                "input_file": ep_path,
                "output_file": output_path,
                "modifications_requested": len(modifications),
                "modifications_applied": [],
                "errors": [],
            }

            for mod_spec in modifications:
                try:
                    # Apply modification based on target
                    target = mod_spec.get("target", "all")
                    field_updates = mod_spec.get("field_updates", {})

                    if target == "all":
                        # Apply to all ElectricEquipment objects
                        for equipment_name, equipment_data in equipment_objects.items():
                            self._apply_equipment_modifications(
                                equipment_name, equipment_data, field_updates, result
                            )
                    elif target.startswith("zone:"):
                        # Apply to ElectricEquipment objects in specific zone
                        zone_name = target.replace("zone:", "").strip()
                        for equipment_name, equipment_data in equipment_objects.items():
                            if (
                                equipment_data.get(
                                    "zone_or_zonelist_or_space_or_spacelist_name", ""
                                )
                                == zone_name
                            ):
                                self._apply_equipment_modifications(
                                    equipment_name,
                                    equipment_data,
                                    field_updates,
                                    result,
                                )
                    elif target.startswith("name:"):
                        # Apply to specific ElectricEquipment object by name
                        target_name = target.replace("name:", "").strip()
                        if target_name in equipment_objects:
                            self._apply_equipment_modifications(
                                target_name,
                                equipment_objects[target_name],
                                field_updates,
                                result,
                            )
                        else:
                            result["errors"].append(
                                f"ElectricEquipment object '{target_name}' not found"
                            )
                    else:
                        result["errors"].append(
                            f"Invalid target specification: {target}"
                        )

                except Exception as e:
                    result["errors"].append(f"Error processing modification: {str(e)}")

            # Save the modified epJSON
            with open(output_path, "w") as f:
                json.dump(ep, f, indent=2)

            result["total_modifications_applied"] = len(result["modifications_applied"])

            logger.info(
                f"Applied {len(result['modifications_applied'])} modifications to ElectricEquipment objects"
            )
            return result

        except Exception as e:
            logger.error(f"Error modifying ElectricEquipment objects: {e}")
            return {"success": False, "error": str(e), "input_file": ep_path}

    def _apply_equipment_modifications(
        self,
        equipment_name: str,
        equipment_data: Dict[str, Any],
        field_updates: Dict[str, Any],
        result: Dict[str, Any],
    ) -> None:
        """Apply field updates to an ElectricEquipment object in epJSON format"""
        # Valid ElectricEquipment object fields (epJSON format - lowercase with underscores)
        valid_fields = {
            "schedule_name",
            "design_level_calculation_method",
            "design_level",
            "watts_per_floor_area",
            "watts_per_person",
            "fraction_latent",
            "fraction_radiant",
            "fraction_lost",
            "end_use_subcategory",
        }

        # Fraction fields that must be between 0.0 and 1.0
        fraction_fields = {"fraction_latent", "fraction_radiant", "fraction_lost"}

        # Numeric fields that must be >= 0
        positive_numeric_fields = {
            "design_level",
            "watts_per_floor_area",
            "watts_per_person",
        }

        for field_name, new_value in field_updates.items():
            # Normalize field name to lowercase with underscores
            field_key = field_name.lower().replace(" ", "_")

            if field_key not in valid_fields:
                result["errors"].append(
                    f"Invalid field '{field_name}' for ElectricEquipment object '{equipment_name}'"
                )
                continue

            try:
                # Validate calculation method change
                if field_key == "design_level_calculation_method":
                    if new_value not in self.VALID_CALCULATION_METHODS:
                        result["errors"].append(
                            f"Invalid calculation method '{new_value}' for '{equipment_name}'. "
                            f"Valid options: {list(self.VALID_CALCULATION_METHODS.keys())}"
                        )
                        continue

                # Validate fraction fields (0.0 to 1.0)
                if field_key in fraction_fields:
                    try:
                        float_value = float(new_value)
                        if not (0.0 <= float_value <= 1.0):
                            result["errors"].append(
                                f"Field '{field_key}' for '{equipment_name}' must be between 0.0 and 1.0, got {new_value}"
                            )
                            continue
                    except (ValueError, TypeError):
                        result["errors"].append(
                            f"Field '{field_key}' for '{equipment_name}' must be a number, got {new_value}"
                        )
                        continue

                # Validate positive numeric fields
                if field_key in positive_numeric_fields:
                    try:
                        float_value = float(new_value)
                        if float_value < 0.0:
                            result["errors"].append(
                                f"Field '{field_key}' for '{equipment_name}' must be >= 0.0, got {new_value}"
                            )
                            continue
                    except (ValueError, TypeError):
                        result["errors"].append(
                            f"Field '{field_key}' for '{equipment_name}' must be a number, got {new_value}"
                        )
                        continue

                old_value = equipment_data.get(field_key, "")
                equipment_data[field_key] = new_value

                result["modifications_applied"].append(
                    {
                        "object_name": equipment_name,
                        "field": field_key,
                        "old_value": old_value,
                        "new_value": new_value,
                    }
                )

                logger.debug(
                    f"Updated {equipment_name}.{field_key}: {old_value} -> {new_value}"
                )

            except Exception as e:
                result["errors"].append(
                    f"Error setting {field_name} to {new_value} for '{equipment_name}': {str(e)}"
                )

    def validate_electric_equipment_modifications(
        self, modifications: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Validate modification specifications before applying them

        Args:
            modifications: List of modification specifications

        Returns:
            Validation result dictionary
        """
        validation_result = {"valid": True, "errors": [], "warnings": []}

        # Valid field names based on IDD
        valid_fields = {
            "Schedule_Name",
            "Design_Level_Calculation_Method",
            "Design_Level",
            "Watts_per_Floor_Area",
            "Watts_per_Person",
            "Fraction_Latent",
            "Fraction_Radiant",
            "Fraction_Lost",
            "EndUse_Subcategory",
        }

        for i, mod_spec in enumerate(modifications):
            # Check required fields
            if "target" not in mod_spec:
                validation_result["errors"].append(
                    f"Modification {i}: Missing 'target' field"
                )
                validation_result["valid"] = False

            if "field_updates" not in mod_spec:
                validation_result["errors"].append(
                    f"Modification {i}: Missing 'field_updates' field"
                )
                validation_result["valid"] = False
            elif not isinstance(mod_spec["field_updates"], dict):
                validation_result["errors"].append(
                    f"Modification {i}: 'field_updates' must be a dictionary"
                )
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
                        if (
                            value == "EquipmentLevel"
                            and "Watts_per_Floor_Area" in field_updates
                        ):
                            validation_result["warnings"].append(
                                f"Modification {i}: Setting calculation method to 'EquipmentLevel' "
                                "but also setting 'Watts_per_Floor_Area'"
                            )
                        elif value == "Watts/Area" and "Design_Level" in field_updates:
                            validation_result["warnings"].append(
                                f"Modification {i}: Setting calculation method to 'Watts/Area' "
                                "but also setting 'Design_Level'"
                            )
                        elif value == "Watts/Person" and (
                            "Design_Level" in field_updates
                            or "Watts_per_Floor_Area" in field_updates
                        ):
                            validation_result["warnings"].append(
                                f"Modification {i}: Setting calculation method to 'Watts/Person' "
                                "but also setting other power values"
                            )

            # Validate target format
            target = mod_spec.get("target", "")
            if target and not (
                target == "all"
                or target.startswith("zone:")
                or target.startswith("name:")
            ):
                validation_result["errors"].append(
                    f"Modification {i}: Invalid target format '{target}'. "
                    "Use 'all', 'zone:ZoneName', or 'name:ElectricEquipmentName'"
                )
                validation_result["valid"] = False

        return validation_result
